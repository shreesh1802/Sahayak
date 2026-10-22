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
MIN_MONTHLY = 1_000  # a monthly income or expense below this is almost certainly a cut-off number like "25"


_UNITS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
    "seventeen eighteen nineteen".split())}
_TENS = {w: 10 * (i + 2) for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split())}
_SCALES = {"hundred": 100, "thousand": 1_000, "lakh": 100_000, "lakhs": 100_000, "lac": 100_000, "crore": 10_000_000}


def words_to_digits(text: str) -> str:
    """'eight thousand' -> '8000', 'twenty five thousand' -> '25000', 'one lakh fifty thousand' -> '150000'.

    Browsers sometimes transcribe spoken numbers as words. A lone 'one' is left alone ('one of my loans').
    """
    tokens = re.sub(r"(?<=[a-z])-(?=[a-z])", " ", text).split()  # 'twenty-five' -> 'twenty five'; keeps '50,000'
    core = lambda tok: tok.strip(".,;:!?")  # noqa: E731
    out: list[str] = []
    i = 0
    while i < len(tokens):
        w = core(tokens[i])
        if w not in _UNITS and w not in _TENS and w not in _SCALES:
            out.append(tokens[i]); i += 1; continue
        if w in _SCALES and out and re.fullmatch(r"[\d.,]+", out[-1]):  # '2 lakh', '25 thousand': the amount parser handles it
            out.append(tokens[i]); i += 1; continue
        j, total, current, seen_scale = i, 0, 0, False
        while j < len(tokens):
            w = core(tokens[j])
            if w in _UNITS:
                current += _UNITS[w]
            elif w in _TENS:
                current += _TENS[w]
            elif w in _SCALES:
                if _SCALES[w] == 100:
                    current = (current or 1) * 100
                else:
                    total += (current or 1) * _SCALES[w]; current = 0; seen_scale = True
            elif w == "and" and j + 1 < len(tokens) and core(tokens[j + 1]) in {**_UNITS, **_TENS}:
                pass
            else:
                break
            j += 1
        value = total + current
        if j - i == 1 and core(tokens[i]) == "one" and not seen_scale and (not out or out[-1] not in ("loan", "number")):
            out.append(tokens[i])
        else:
            out.append(str(value))
        i = j
    return " ".join(out)


def suggest_full(n: float) -> float:
    """A cut-off number is usually missing zeros: 8 -> 8,000 ('eight thousand' heard as 'eight'), 800 -> 8,000."""
    return n * 1000 if n < 100 else n * 10


def low_note(low: dict) -> str:
    field_, n = next(iter(low.items()))
    what = "income" if field_ == "monthly_income" else "monthly expenses"
    return (f"I heard {n:,.0f} for your {what}, which sounds low. Did you mean {suggest_full(n):,.0f}? "
            f"Say yes, or say the full amount.")


def _to_amount(num: str, mult: str | None) -> float:
    v = float(num.replace(",", ""))
    return v * _MULT.get((mult or "").lower(), 1)


def _find_amount(pattern: str, text: str) -> float | None:
    m = re.search(pattern, text, re.I)
    return _to_amount(m.group(1), m.group(2)) if m else None


def _parse_offer(t: str) -> dict | None:
    """Pull principal, rate, term, fees and (if stated) flat/reducing out of a loan offer."""
    principal = _find_amount(r"(?:borrow|loan(?: of)?|lend|credit(?: of)?)\s*(?:of\s*)?" + _NUM, t) \
        or _find_amount(_NUM + r"\s*(?:loan|rupees)?", t)
    rate = re.search(r"(\d+(?:\.\d+)?)\s*(?:%|percent|per cent)", t)
    term = re.search(r"(\d+)\s*(months?|years?|yrs?)", t)
    if not (principal and rate and term):
        return None
    months = int(term.group(1)) * (12 if term.group(2).startswith("y") else 1)
    args = {"principal": principal, "annual_rate": float(rate.group(1)), "term_months": months,
            "fees": _find_amount(r"(?:fees?|processing)[^\d]{0,15}" + _NUM, t) or 0.0}
    if "flat" in t:
        args["rate_type"] = "flat"
    elif "reducing" in t:
        args["rate_type"] = "reducing"
    return args


@dataclass
class Route:
    tool: str | None
    args: dict = field(default_factory=dict)
    note: str = ""  # shown when no tool matches
    partial: dict = field(default_factory=dict)  # half-given budget the conversation should remember
    suspect: dict = field(default_factory=dict)  # amounts that sound too low; the conversation asks to confirm


def route(utterance: str) -> Route:
    t = words_to_digits(utterance.strip().lower().replace("₹", "").replace("rs.", "").replace("rs ", ""))

    if re.search(r"\b(lesson|teach me|learn)\b", t):
        return Route("next_lesson")

    if re.search(r"\b(my loans?|what do i owe|loan summary)\b", t):
        return Route("my_loans")

    m = re.search(r"\b(?:paid|repaid)\s+" + _NUM + r"(.*)$", t)
    if m:
        args: dict = {"amount": _to_amount(m.group(1), m.group(2))}
        rest = m.group(3)
        by_number = re.search(r"\bloan\s*(?:number\s*)?(\d+)", rest)
        by_name = re.search(r"\b(?:on|towards|toward|for)\s+(?:my\s+|the\s+)?([a-z][a-z \-]{1,30}?)(?:\s+loan)?\s*$", rest)
        if by_number:
            args["loan_number"] = int(by_number.group(1))
        elif by_name:
            args["lender_label"] = by_name.group(1).strip()
        return Route("log_repayment", args)

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
    given = {k: v for k, v in (("monthly_income", inc), ("monthly_expenses", exp)) if v}
    low = {k: v for k, v in given.items() if v < MIN_MONTHLY}
    if low:
        return Route(None, suspect=given, note=low_note(low))
    if inc and exp:
        return Route("save_my_budget", {"monthly_income": inc, "monthly_expenses": exp})
    if given:
        what = "income" if inc else "expenses"
        ask = "What are your regular monthly expenses?" if inc else "What is your monthly income?"
        return Route(None, partial=given, note=f"Got your {what}: {next(iter(given.values())):,.0f} a month. {ask}")

    if re.search(r"\b(should i|review|good idea|worth it|take it)\b", t) and _parse_offer(t):
        return Route("review_loan_offer", _parse_offer(t))

    if re.search(r"\bafford|can i pay|too much\b", t):
        emi = _find_amount(r"(?:afford|pay)[^\d]{0,15}" + _NUM, t) or _find_amount(_NUM, t)
        if emi:
            return Route("check_affordability", {"new_emi": emi})
        return Route(None, note="How much would the monthly payment be?")

    if re.search(r"\b(loan|borrow|lend|credit|emi|interest)\b", t):
        args = _parse_offer(t)
        if args:
            wants_review = re.search(r"\b(should i|review|good idea|worth it|take it|take this|take that)\b", t)
            return Route("review_loan_offer" if wants_review else "explain_loan", args)
        return Route(None, note="Tell me the loan amount, the interest rate and how many months, "
                                "for example: a loan of 50000 at 24 percent for 12 months.")

    return Route(None, note="I can explain a loan, check if a payment is affordable, track your loans, "
                            "or teach you a quick money lesson. What would you like?")
