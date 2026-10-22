"""Sahayak MCP server: the Alexa+ add-on. Streamable HTTP, MCP spec 2025-11-25.

Alexa+ is the MCP *client*: it discovers these tools, calls them, and turns the
results into speech and screen output. Everything numeric comes from core.loan.

Identity: the demo uses a default user. In production the user id comes from the
OAuth access token that Alexa+ account linking sends on every request.
"""
from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import Context, FastMCP
from pydantic import BaseModel, Field

from agents.pipeline import State, review
from core import lessons as lesson_bank
from core import store
from core.loan import (RATE_TYPES, check_affordability as _affordability,
                       compare_flat_vs_reducing, loan_cost)
from core.narrate import money, narrate_affordability, narrate_loan

DEFAULT_USER = "demo"

# MCP Apps: tools point at a ui:// resource that the host renders as the on-screen card (Echo Show etc.).
# `_meta.ui.resourceUri` is the current key; the flat `ui/resourceUri` is the deprecated one older hosts read.
# A host without MCP Apps support ignores both and uses the text in `speech` / `content` (text-only fallback).
UI_URI = "ui://sahayak/card"
UI_MIME = "text/html;profile=mcp-app"
UI_META = {"ui": {"resourceUri": UI_URI}, "ui/resourceUri": UI_URI}
CARD_HTML = (Path(__file__).parent / "ui" / "card.html").read_text(encoding="utf-8")

mcp = FastMCP(
    "sahayak",
    instructions=(
        "Sahayak is a financial-literacy coach for first-time borrowers. It explains the true cost of "
        "loans, checks whether a repayment is realistic, tracks the user's loans and repayments, and "
        "teaches short lessons. It gives education, not regulated financial advice, and never "
        "recommends specific lenders or investments."
    ),
    host=os.environ.get("HOST", "127.0.0.1"),
    port=int(os.environ.get("PORT", "8000")),
    stateless_http=False,  # elicitation needs a session
)


class RateTypeChoice(BaseModel):
    rate_type: str = Field(description="How the interest is charged: 'flat' or 'reducing'")


class BudgetChoice(BaseModel):
    monthly_income: float = Field(description="Total household income per month")
    monthly_expenses: float = Field(description="Regular spending per month, excluding loan payments")


async def _ask_rate_type(ctx: Context, rate_type: str) -> tuple[str, bool]:
    """Return (rate_type, assumed). Asks the user if unknown; falls back to the pessimistic 'flat' and says so."""
    if rate_type in RATE_TYPES:
        return rate_type, False
    res = await ctx.elicit(
        "Is the interest rate flat, or charged on the reducing balance? If you are not sure, "
        "ask your lender; flat is much more expensive.",
        schema=RateTypeChoice,
    )
    if res.action != "accept" or res.data.rate_type not in RATE_TYPES:
        return "flat", True
    return res.data.rate_type, False


@mcp.tool(meta=UI_META)
async def explain_loan(ctx: Context, principal: float, annual_rate: float, term_months: int,
                       fees: float = 0.0, rate_type: str = "", user_id: str = DEFAULT_USER) -> dict:
    """Explain what a loan really costs, in plain words: monthly payment, total repayment,
    fees, and the true yearly rate. Use when someone is offered or considering a loan.
    rate_type is 'flat' or 'reducing'; if unknown, the user is asked."""
    rate_type, assumed = await _ask_rate_type(ctx, rate_type)
    cost = loan_cost(principal, annual_rate, term_months, fees, rate_type).to_dict()
    comparison = compare_flat_vs_reducing(principal, annual_rate, term_months, fees)
    speech = narrate_loan(cost, comparison)
    if assumed:
        speech += " I assumed a flat rate because I could not confirm it, so check with your lender."
    return {"speech": speech, "cost": cost, "comparison": comparison, "assumed_rate_type": assumed}


@mcp.tool(meta=UI_META)
async def review_loan_offer(ctx: Context, principal: float, annual_rate: float, term_months: int,
                            fees: float = 0.0, rate_type: str = "", user_id: str = DEFAULT_USER) -> dict:
    """Review a whole loan offer in one go: the true cost, whether the payment fits the user's budget,
    questions to ask the lender, and the most relevant lesson. Use when someone asks whether they should
    take a loan or wants an offer reviewed. Several specialist agents run behind this one tool, and a
    verifier checks every spoken number against the calculator. Asks for the rate type and budget if unknown."""
    rate_type, assumed = await _ask_rate_type(ctx, rate_type)
    profile = store.get_profile(user_id)
    if profile is None:
        res = await ctx.elicit("To check whether this fits your budget I need your monthly income and "
                               "regular expenses. You can decline and I will skip that part.", schema=BudgetChoice)
        if res.action == "accept":
            store.save_profile(user_id, res.data.monthly_income, res.data.monthly_expenses)
            profile = store.get_profile(user_id)
    existing = sum(l["emi"] for l in store.list_loans(user_id) if l["paid"] < l["emi"] * l["term_months"])
    state = State(principal, annual_rate, term_months, fees, rate_type,
                  {"monthly_income": profile["monthly_income"], "monthly_expenses": profile["monthly_expenses"]}
                  if profile else None, existing)
    result = review(state)
    if assumed:
        result["speech"] += " I assumed a flat rate because I could not confirm it, so check with your lender."
    result["assumed_rate_type"] = assumed
    return result


@mcp.tool(meta=UI_META)
def save_my_budget(monthly_income: float, monthly_expenses: float, user_id: str = DEFAULT_USER) -> dict:
    """Remember the user's monthly income and regular expenses, so affordability checks can reuse them."""
    if monthly_income <= 0 or monthly_expenses < 0:
        raise ValueError("income must be positive and expenses cannot be negative")
    store.save_profile(user_id, monthly_income, monthly_expenses)
    return {"speech": "Got it. I have saved your income and expenses.", "saved": True}


@mcp.tool(meta=UI_META)
async def check_affordability(ctx: Context, new_emi: float, user_id: str = DEFAULT_USER) -> dict:
    """Check whether a monthly loan payment is realistic against the user's saved income, expenses and
    existing loans. Asks for income and expenses if not yet saved."""
    profile = store.get_profile(user_id)
    if profile is None:
        res = await ctx.elicit("To check this I need your monthly income and regular expenses.", schema=BudgetChoice)
        if res.action != "accept":
            return {"speech": "No problem. Tell me your income and expenses whenever you are ready.", "needs": "budget"}
        store.save_profile(user_id, res.data.monthly_income, res.data.monthly_expenses)
        profile = store.get_profile(user_id)
    existing = sum(l["emi"] for l in store.list_loans(user_id) if l["paid"] < l["emi"] * l["term_months"])
    result = _affordability(profile["monthly_income"], profile["monthly_expenses"], new_emi, existing).to_dict()
    return {"speech": narrate_affordability(result), "affordability": result}


@mcp.tool(meta=UI_META)
def add_loan(lender_label: str, principal: float, annual_rate: float, term_months: int,
             rate_type: str, fees: float = 0.0, user_id: str = DEFAULT_USER) -> dict:
    """Record a loan the user has taken so Sahayak can track repayments. lender_label is a nickname
    like 'self-help group' or 'shop credit'; no account numbers are stored."""
    cost = loan_cost(principal, annual_rate, term_months, fees, rate_type)
    store.add_loan(user_id, lender_label, principal, annual_rate, term_months, fees, rate_type, cost.emi)
    number = len(store.list_loans(user_id))  # per-user number: the user's first loan is always loan 1
    return {"speech": f"I have added your {lender_label} loan as loan {number}. "
                      f"Your payment is {money(cost.emi)} a month.",
            "loan_number": number, "emi": round(cost.emi, 2)}


def _resolve_loan(user_id: str, loan_number: int, lender_label: str) -> dict:
    """Find which of the user's loans is meant. Voice users say a name or a number, never a database id."""
    loans = store.list_loans(user_id)
    if not loans:
        raise ValueError("You have no saved loans yet. Add one first.")
    if lender_label:
        hits = [l for l in loans if lender_label.lower() in l["lender_label"].lower()]
        if len(hits) == 1:
            return hits[0]
        raise ValueError(f"I could not find exactly one loan matching '{lender_label}'.")
    if loan_number:
        if 1 <= loan_number <= len(loans):
            return loans[loan_number - 1]
        raise ValueError(f"You have {len(loans)} loan{'s' if len(loans) != 1 else ''}, so there is no loan {loan_number}.")
    if len(loans) == 1:
        return loans[0]
    raise ValueError("Which loan did you pay? Say its name or number.")


@mcp.tool(meta=UI_META)
def log_repayment(amount: float, loan_number: int = 0, lender_label: str = "",
                  user_id: str = DEFAULT_USER) -> dict:
    """Record a repayment the user made. Say which loan by number or by name; if the user has only one loan,
    neither is needed."""
    if amount <= 0:
        raise ValueError("amount must be positive")
    loan = _resolve_loan(user_id, loan_number, lender_label)
    store.log_repayment(user_id, loan["id"], amount)
    return {"speech": f"Recorded a payment of {money(amount)} on your {loan['lender_label']} loan. "
                      f"Well done for staying on track.", "logged": True}


@mcp.tool(meta=UI_META)
def my_loans(user_id: str = DEFAULT_USER) -> dict:
    """Summarise the user's loans: what is owed, what is paid, and the monthly payment total."""
    loans = store.list_loans(user_id)
    for n, l in enumerate(loans, start=1):
        l["number"] = n
        l["total_due"] = round(l["emi"] * l["term_months"], 2)
        l["remaining"] = round(max(l["total_due"] - l["paid"], 0), 2)
    monthly = sum(l["emi"] for l in loans if l["remaining"] > 0)
    speech = ("You have no loans saved yet." if not loans else
              f"You have {len(loans)} loan{'s' if len(loans) != 1 else ''}. "
              f"Your monthly payments total {money(monthly)}.")
    return {"speech": speech, "loans": loans, "monthly_total": round(monthly, 2)}


@mcp.tool(meta=UI_META)
def next_lesson(user_id: str = DEFAULT_USER, mark_previous_done: bool = True) -> dict:
    """Give the next short money lesson, one the user has not heard yet, with a quiz question."""
    done = store.completed_lessons(user_id)
    lesson = lesson_bank.next_lesson(done)
    if lesson is None:
        return {"speech": "You have finished every lesson. Great work!", "finished": True}
    if mark_previous_done:
        store.complete_lesson(user_id, lesson["id"])
    return {"speech": f"{lesson['title']}. {lesson['body']} Quick question: {lesson['quiz']}", "lesson": lesson}


@mcp.resource(UI_URI, name="Sahayak card", mime_type=UI_MIME,
              description="The on-screen card for Sahayak results (an MCP App view). Rendered by the host in a "
                          "sandboxed iframe; it receives the tool result over postMessage.")
def card_ui() -> str:
    return CARD_HTML


@mcp.resource("sahayak://loans/{user_id}")
def loans_resource(user_id: str) -> str:
    """The user's saved loans as text, for the assistant to read as context."""
    loans = store.list_loans(user_id)
    return "\n".join(f"{l['lender_label']}: {l['principal']} at {l['annual_rate']}% {l['rate_type']}, "
                     f"{l['term_months']} months, paid {l['paid']}" for l in loans) or "No loans saved."


def main() -> None:
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
