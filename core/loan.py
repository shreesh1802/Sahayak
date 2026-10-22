"""Deterministic loan maths. No LLM touches these numbers.

Every figure the assistant speaks must come from here (see agents/verifier).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

RATE_TYPES = ("flat", "reducing")


@dataclass(frozen=True)
class LoanCost:
    rate_type: str
    principal: float
    stated_annual_rate: float  # percent, as quoted by the lender
    term_months: int
    upfront_fees: float
    emi: float  # monthly instalment
    total_repayment: float  # sum of all instalments
    total_interest: float  # total_repayment - principal
    total_cost: float  # interest + upfront fees
    net_disbursed: float  # principal - upfront fees (cash actually received)
    effective_annual_rate: float  # percent, true yearly cost incl. fees

    def to_dict(self) -> dict:
        return {k: (round(v, 2) if isinstance(v, float) else v) for k, v in asdict(self).items()}


def _validate(principal: float, annual_rate: float, term_months: int, fees: float, rate_type: str) -> None:
    if rate_type not in RATE_TYPES:
        raise ValueError(f"rate_type must be one of {RATE_TYPES}, got {rate_type!r}")
    if principal <= 0:
        raise ValueError("principal must be positive")
    if annual_rate < 0 or annual_rate > 500:
        raise ValueError("annual_rate must be between 0 and 500 percent")
    if not (1 <= term_months <= 600):
        raise ValueError("term_months must be between 1 and 600")
    if fees < 0 or fees >= principal:
        raise ValueError("fees must be non-negative and smaller than the principal")


def emi_reducing(principal: float, annual_rate: float, term_months: int) -> float:
    r = annual_rate / 12 / 100
    if r == 0:
        return principal / term_months
    return principal * r / (1 - (1 + r) ** -term_months)


def emi_flat(principal: float, annual_rate: float, term_months: int) -> float:
    interest = principal * (annual_rate / 100) * (term_months / 12)
    return (principal + interest) / term_months


def _monthly_irr(net_disbursed: float, emi: float, term_months: int) -> float:
    """Monthly rate i with sum_{k=1..n} emi/(1+i)^k == net_disbursed (bisection)."""
    if emi * term_months <= net_disbursed:
        return 0.0
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        pv = emi * (1 - (1 + mid) ** -term_months) / mid if mid else emi * term_months
        if pv > net_disbursed:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def loan_cost(principal: float, annual_rate: float, term_months: int,
              fees: float = 0.0, rate_type: str = "reducing") -> LoanCost:
    _validate(principal, annual_rate, term_months, fees, rate_type)
    emi = (emi_flat if rate_type == "flat" else emi_reducing)(principal, annual_rate, term_months)
    total_repayment = emi * term_months
    net = principal - fees
    i = _monthly_irr(net, emi, term_months)
    return LoanCost(
        rate_type=rate_type,
        principal=principal,
        stated_annual_rate=annual_rate,
        term_months=term_months,
        upfront_fees=fees,
        emi=emi,
        total_repayment=total_repayment,
        total_interest=total_repayment - principal,
        total_cost=total_repayment - principal + fees,
        net_disbursed=net,
        effective_annual_rate=((1 + i) ** 12 - 1) * 100,
    )


def compare_flat_vs_reducing(principal: float, annual_rate: float, term_months: int,
                             fees: float = 0.0) -> dict:
    """Same quoted rate, two ways of charging it. Shows why 'flat 12%' is not '12%'."""
    flat = loan_cost(principal, annual_rate, term_months, fees, "flat")
    reducing = loan_cost(principal, annual_rate, term_months, fees, "reducing")
    return {
        "flat": flat.to_dict(),
        "reducing": reducing.to_dict(),
        "extra_cost_of_flat": round(flat.total_cost - reducing.total_cost, 2),
    }


@dataclass(frozen=True)
class Affordability:
    verdict: str  # "comfortable" | "tight" | "unaffordable"
    monthly_income: float
    monthly_expenses: float
    existing_emis: float
    new_emi: float
    surplus_before: float
    surplus_after: float
    emi_to_income_ratio: float  # all EMIs / income, percent
    reasons: tuple[str, ...]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["reasons"] = list(self.reasons)
        return {k: (round(v, 2) if isinstance(v, float) else v) for k, v in d.items()}


def check_affordability(monthly_income: float, monthly_expenses: float, new_emi: float,
                        existing_emis: float = 0.0) -> Affordability:
    """Rule-of-thumb check. Education, not credit advice: thresholds are stated openly.

    - EMIs above 40% of income are widely treated as a debt-stress warning.
    - Surplus must stay positive after the new EMI, and ideally keep a 10% income cushion.
    """
    if monthly_income <= 0:
        raise ValueError("monthly_income must be positive")
    if min(monthly_expenses, new_emi, existing_emis) < 0:
        raise ValueError("expenses and EMIs cannot be negative")

    surplus_before = monthly_income - monthly_expenses - existing_emis
    surplus_after = surplus_before - new_emi
    ratio = (existing_emis + new_emi) / monthly_income * 100
    reasons: list[str] = []

    if surplus_after < 0:
        verdict = "unaffordable"
        reasons.append("After this instalment your expenses and EMIs exceed your income.")
    elif ratio > 40 or surplus_after < 0.10 * monthly_income:
        verdict = "tight"
        if ratio > 40:
            reasons.append("Your total EMIs would be above 40% of income, a common stress threshold.")
        if surplus_after < 0.10 * monthly_income:
            reasons.append("You would keep less than 10% of income as a cushion for emergencies.")
    else:
        verdict = "comfortable"
        reasons.append("You keep a healthy surplus after all instalments.")

    return Affordability(verdict, monthly_income, monthly_expenses, existing_emis, new_emi,
                         surplus_before, surplus_after, ratio, tuple(reasons))
