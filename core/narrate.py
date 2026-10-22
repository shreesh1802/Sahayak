"""Plain-language, voice-friendly explanations built only from calculator output.

Short sentences, no jargon, numbers rounded the way people say them aloud.
"""
from __future__ import annotations

import os

CUR = os.environ.get("SAHAYAK_CURRENCY", "₹")


def money(x: float) -> str:
    return f"{CUR}{x:,.0f}"


def narrate_loan(cost: dict, comparison: dict | None = None) -> str:
    kind = "flat" if cost["rate_type"] == "flat" else "reducing-balance"
    parts = [
        f"You borrow {money(cost['principal'])} for {cost['term_months']} months at {cost['stated_annual_rate']:g} percent {kind}.",
        f"You pay {money(cost['emi'])} every month, {money(cost['total_repayment'])} in total.",
        f"That is {money(cost['total_interest'])} in interest"
        + (f" plus {money(cost['upfront_fees'])} in fees." if cost["upfront_fees"] else "."),
    ]
    if cost["upfront_fees"]:
        parts.append(f"Because fees are taken upfront, you actually receive only {money(cost['net_disbursed'])}.")
    parts.append(
        f"The true yearly cost is {cost['effective_annual_rate']:.1f} percent, "
        f"not the {cost['stated_annual_rate']:g} percent that was quoted."
        if abs(cost["effective_annual_rate"] - cost["stated_annual_rate"]) > 0.5
        else f"The true yearly cost is {cost['effective_annual_rate']:.1f} percent."
    )
    if comparison and comparison["extra_cost_of_flat"] > 0:
        flat_vs = comparison["extra_cost_of_flat"]
        if cost["rate_type"] == "flat":
            parts.append(
                f"If the same rate were charged on the reducing balance, you would pay {money(flat_vs)} less."
            )
        else:
            parts.append(f"Be careful: if this rate is actually flat, you would pay {money(flat_vs)} more.")
    return " ".join(parts)


def narrate_affordability(a: dict) -> str:
    head = {
        "comfortable": "This looks comfortable for you.",
        "tight": "This would be tight for you.",
        "unaffordable": "I would not take this loan as it stands.",
    }[a["verdict"]]
    why = " ".join(a["reasons"])
    tail = (
        f"After all instalments you would have {money(a['surplus_after'])} left each month."
        if a["surplus_after"] >= 0
        else f"You would be short by {money(-a['surplus_after'])} every month."
    )
    return f"{head} {why} {tail} This is a guide to help you think, not financial advice."
