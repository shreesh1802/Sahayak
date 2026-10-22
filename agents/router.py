"""Rule-based intent router: maps what the user said to an MCP tool call.

This stands in for Alexa+'s own language understanding in the simulator, and is the
no-LLM fallback. An LLM-backed router (Bedrock) can replace route() behind the same shape.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_MULT = {"k": 1_000, "thousand": 1_000, "lakh": 100_000, "lakhs": 100_000, "lac": 100_000,
         "crore": 10_000_000, "m": 1_000_000, "million": 1_000_000}
_NUM = r"(\d[\d,]*(?:\.\d+)?)\s*(k|thousand|lakhs?|lac|crore|m|million)?"


def _to_amount(num: str, mult: str | None) -> float:
    v = float(num.replace(",", ""))
    return v * _MULT.get((mult or "").lower(), 1)


def _find_amount(pattern: str, text: str) -> float | None:
    m = re.search(pattern, text, re.I)
    return _to_amount(m.group(1), m.group(2)) if m else None


@dataclass
class Route:
    tool: str | None
    args: dict = field(default_factory=dict)
    note: str = ""  # shown when no tool matches


def route(utterance: str) -> Route:
    t = utterance.strip().lower().replace("₹", "").replace("rs.", "").replace("rs ", "")

    if re.search(r"\b(lesson|teach me|learn)\b", t):
        return Route("next_lesson")

    if re.search(r"\b(my loans?|what do i owe|loan summary)\b", t):
        return Route("my_loans")

    m = re.search(r"(?:paid|pay|repaid)\s+" + _NUM + r".*?loan\s*(\d+)", t)
    if m:
        return Route("log_repayment", {"amount": _to_amount(m.group(1), m.group(2)), "loan_id": int(m.group(3))})

    if re.search(r"\b(add|save|record|took|taken|got)\b.*\bloan\b", t) and not re.search(r"\b(offered|should i|considering)\b", t):
        principal = _find_amount(r"\bof\s+" + _NUM, t) or _find_amount(r"loan\s*" + _NUM, t)
        rate = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent|per cent)", t)
        term = re.search(r"(\d+)\s*(months?|years?|yrs?)", t)
        kind ="flat" if "flat" in t else "reducing" if "reducing" in t else None
        if principal and rate and term and kind:
            label = re.search(r"(?:called|named|from|label(?:l)?ed)\s+(?:the\s+|a\s+|an\s+)?([a-z][a-z \-]{1,30}?)(?=\s+(?:of|for|at|with|,)|\s*\d|$)", t)
            return Route("add_loan", {
                "lender_label": label.group(1).strip() if label else "my loan",
                "principal": principal, "annual_rate": float(rate.group(1)),
                "term_months": int(term.group(1)) * (12 if term.group(2).startswith("y") else 1),
                "rate_type": kind, "fees": _find_amount(r"(?:fees?|processing)[^\d]{0,15}" + _NUM, t) or 0.0})
        return Route(None, note="To save a loan, tell me the amount, the rate, the months, and whether it is flat or "
                                "reducing, for example: add a loan called shop credit of 12000 at 18 percent for "
                                "12 months reducing.")

    inc = _find_amount(r"(?:income|earn|salary)[^\d]{0,20}" + _NUM, t)
    exp = _find_amount(r"(?:expenses?|spend)[^\d]{0,20}" + _NUM, t)
    if inc and exp:
        return Route("save_my_budget", {"monthly_income": inc, "monthly_expenses": exp})

    if re.search(r"\bafford|can i pay|too much\b", t):
        emi = _find_amount(r"(?:afford|pay)[^\d]{0,15}" + _NUM, t) or _find_amount(_NUM, t)
        if emi:
            return Route("check_affordability", {"new_emi": emi})
        return Route(None, note="How much would the monthly payment be?")

    if re.search(r"\b(loan|borrow|lend|credit|emi|interest)\b", t):
        principal = _find_amount(r"(?:borrow|loan(?: of)?|lend|credit(?: of)?)\s*(?:of\s*)?" + _NUM, t) \
            or _find_amount(_NUM + r"\s*(?:loan|rupees)?", t)
        rate = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent|per cent)", t)
        term = re.search(r"(\d+)\s*(months?|years?|yrs?)", t)
        fees = _find_amount(r"(?:fees?|processing)[^\d]{0,15}" + _NUM, t) or 0.0
        if principal and rate and term:
            months = int(term.group(1)) * (12 if term.group(2).startswith(("y",)) else 1)
            args = {"principal": principal, "annual_rate": float(rate.group(1)),
                    "term_months": months, "fees": fees}
            if "flat" in t:
                args["rate_type"] = "flat"
            elif "reducing" in t:
                args["rate_type"] = "reducing"
            return Route("explain_loan", args)
        return Route(None, note="Tell me the loan amount, the interest rate and how many months, "
                                "for example: a loan of 50000 at 24 percent for 12 months.")

    return Route(None, note="I can explain a loan, check if a payment is affordable, track your loans, "
                            "or teach you a quick money lesson. What would you like?")
