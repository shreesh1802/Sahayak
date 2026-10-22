"""Multi-agent review of a loan offer: supervisor -> specialists -> verifier.

Alexa+ only ever calls one MCP tool; the orchestration happens behind it.

    Supervisor     plans which specialists to run, from what it knows so far, and adapts as results arrive
    LoanAnalyst    the true cost of the offer (deterministic calculator)
    Affordability  whether the payment fits the user's budget (skipped if the budget is unknown)
    Coach          questions to ask the lender and the most relevant lesson, chosen from the findings
    Verifier       rejects any spoken number that cannot be traced to the calculator

The planner and composer here are rule-based. They sit behind plain function interfaces so a model-backed
planner or composer (for example on Bedrock) can replace them; the Verifier is what makes that safe, because it
re-checks every figure no matter who wrote the sentence.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from core import lessons as lesson_bank
from core.loan import check_affordability, compare_flat_vs_reducing, loan_cost
from core.narrate import narrate_affordability, narrate_loan


@dataclass
class Step:
    agent: str
    action: str
    detail: str = ""
    ok: bool = True

    def to_dict(self) -> dict:
        return {"agent": self.agent, "action": self.action, "detail": self.detail, "ok": self.ok}


@dataclass
class State:
    principal: float
    annual_rate: float
    term_months: int
    fees: float
    rate_type: str
    profile: dict | None = None  # {"monthly_income", "monthly_expenses"} or None when unknown
    existing_emis: float = 0.0
    cost: dict | None = None
    comparison: dict | None = None
    affordability: dict | None = None
    questions: list[str] = field(default_factory=list)
    lesson: dict | None = None
    trace: list[Step] = field(default_factory=list)

    def log(self, agent: str, action: str, detail: str = "", ok: bool = True) -> None:
        self.trace.append(Step(agent, action, detail, ok))


# ---------------------------------------------------------------- specialists

def loan_analyst(s: State) -> None:
    s.cost = loan_cost(s.principal, s.annual_rate, s.term_months, s.fees, s.rate_type).to_dict()
    s.comparison = compare_flat_vs_reducing(s.principal, s.annual_rate, s.term_months, s.fees)
    gap = s.cost["effective_annual_rate"] - s.cost["stated_annual_rate"]
    s.log("loan_analyst", "computed true cost",
          f"EMI {s.cost['emi']:.0f}, true yearly rate {s.cost['effective_annual_rate']:.1f}% vs quoted "
          f"{s.cost['stated_annual_rate']:g}% (gap {gap:+.1f} points)")


def affordability_agent(s: State) -> None:
    assert s.profile is not None and s.cost is not None
    s.affordability = check_affordability(
        s.profile["monthly_income"], s.profile["monthly_expenses"], s.cost["emi"], s.existing_emis).to_dict()
    s.log("affordability", "checked budget", f"verdict {s.affordability['verdict']}, "
          f"{s.affordability['emi_to_income_ratio']:.0f}% of income goes to loan payments")


def coach(s: State) -> None:
    """Pick questions and a lesson from the findings, not from a fixed script."""
    assert s.cost is not None
    gap = s.cost["effective_annual_rate"] - s.cost["stated_annual_rate"]
    qs = ["Can you write down the total amount I will repay, including every fee?"]
    lesson_id = None
    if s.rate_type == "flat" and gap > 5:
        qs.append("Is the rate flat or on the reducing balance, and what would the reducing-balance rate be?")
        lesson_id = "flat-vs-reducing"
    if s.cost["upfront_fees"] > 0:
        qs.append("Are the fees deducted before I receive the money, and can they be reduced?")
        lesson_id = lesson_id or "true-cost"
    if s.affordability and s.affordability["verdict"] != "comfortable":
        qs.append("Is there a smaller amount or a longer term that gives me a lower monthly payment?")
        lesson_id = "emi-limit"
    qs.append("What happens if I miss a payment, and what is the late fee?")
    s.questions = qs
    s.lesson = next((l for l in lesson_bank.LESSONS if l["id"] == lesson_id), None)
    s.log("coach", "chose follow-ups", f"{len(qs)} questions" + (f", lesson '{lesson_id}'" if lesson_id else ""))


SPECIALISTS: dict[str, Callable[[State], None]] = {
    "loan_analyst": loan_analyst, "affordability": affordability_agent, "coach": coach,
}


# ---------------------------------------------------------------- planner and composer

def plan(s: State) -> list[str]:
    """What to run, given what is known now. Re-planned after each step."""
    steps = []
    if s.cost is None:
        steps.append("loan_analyst")
    if s.affordability is None and s.profile is not None:
        steps.append("affordability")
    if not s.questions:
        steps.append("coach")
    return steps


def compose(s: State) -> str:
    """Default composer: template sentences built only from specialist output."""
    parts = [narrate_loan(s.cost, s.comparison)]
    if s.affordability:
        parts.append(narrate_affordability(s.affordability))
    else:
        parts.append("I could not check this against your budget because I do not have your income and expenses yet.")
    parts.append("Before you decide, ask the lender: " + " ".join(f"({i}) {q}" for i, q in enumerate(s.questions, 1)))
    return " ".join(parts)


# ---------------------------------------------------------------- verifier

_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_CONSTANTS = {40.0, 10.0}  # the two stated affordability rules of thumb (see core/loan.py)


def _numbers_in(obj) -> set[float]:
    out: set[float] = set()
    if isinstance(obj, bool):
        return out
    if isinstance(obj, (int, float)):
        out.add(float(obj))
        out.add(abs(float(obj)))
    elif isinstance(obj, dict):
        for v in obj.values():
            out |= _numbers_in(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            out |= _numbers_in(v)
    return out


def untraceable_numbers(text: str, s: State) -> list[str]:
    """Every number in `text` must match a calculator output or a user input (to the precision spoken)."""
    allowed = _numbers_in([s.cost, s.comparison, s.affordability, s.profile]) | _CONSTANTS
    allowed |= {s.principal, s.annual_rate, float(s.term_months), s.fees, s.existing_emis}
    bad = []
    for m in _NUMBER.finditer(text):
        raw = m.group(0)
        if re.match(r"^\(\d+\)", text[max(m.start() - 1, 0):m.end() + 1]):  # enumeration markers like (1)
            continue
        n = float(raw.replace(",", ""))
        tol = 0.051 if "." in raw else 0.51  # spoken precision: 63.4 is within 0.05, 5,167 within 0.5
        if not any(abs(n - a) <= tol for a in allowed):
            bad.append(raw)
    return bad


# ---------------------------------------------------------------- supervisor

def review(s: State, composer: Callable[[State], str] = compose) -> dict:
    """Run the pipeline and return speech plus the full agent trace."""
    s.log("supervisor", "received offer", f"{s.principal:,.0f} at {s.annual_rate:g}% {s.rate_type} for {s.term_months} months"
          + ("" if s.profile else "; budget unknown"))
    guard = 0
    while (todo := plan(s)) and guard < 6:
        guard += 1
        s.log("supervisor", "plan", " -> ".join(todo))
        agent = todo[0]  # run one step, then re-plan with the new facts
        SPECIALISTS[agent](s)
    if s.profile is None:
        s.log("supervisor", "skipped affordability", "no budget available", ok=True)

    speech = composer(s)
    bad = untraceable_numbers(speech, s)
    if bad:
        s.log("verifier", "REJECTED draft", f"numbers not from the calculator: {', '.join(bad)}", ok=False)
        speech = compose(s)  # safe fallback built only from calculator output
        bad = untraceable_numbers(speech, s)
        s.log("verifier", "re-checked fallback", "all numbers traced" if not bad else f"still bad: {bad}", ok=not bad)
        if bad:  # should be impossible; refuse rather than speak an untraced number
            speech = "Sorry, I could not produce a trustworthy answer for that offer."
    else:
        s.log("verifier", "approved", "every spoken number traced to the calculator")
    return {"speech": speech, "cost": s.cost, "comparison": s.comparison, "affordability": s.affordability,
            "questions": s.questions, "lesson": s.lesson, "agent_trace": [t.to_dict() for t in s.trace]}
