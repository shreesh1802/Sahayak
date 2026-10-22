import pytest

from core.loan import (check_affordability, compare_flat_vs_reducing, emi_reducing,
                       loan_cost)


def test_reducing_emi_matches_textbook():
    # 100,000 at 12% p.a. over 12 months -> EMI 8884.88 (standard amortisation table)
    assert emi_reducing(100_000, 12, 12) == pytest.approx(8884.88, abs=0.01)


def test_reducing_without_fees_effective_rate_is_compounded_nominal():
    c = loan_cost(100_000, 12, 12, 0, "reducing")
    assert c.effective_annual_rate == pytest.approx(12.68, abs=0.01)  # (1.01)^12 - 1


def test_flat_rate_is_far_costlier_than_it_sounds():
    c = loan_cost(100_000, 12, 12, 0, "flat")
    assert c.emi == pytest.approx(9333.33, abs=0.01)
    assert c.total_interest == pytest.approx(12_000, abs=0.01)
    assert c.effective_annual_rate > 21  # "12% flat" is really ~21-22%


def test_fees_raise_effective_rate():
    no_fee = loan_cost(50_000, 18, 24, 0, "reducing")
    with_fee = loan_cost(50_000, 18, 24, 2_500, "reducing")
    assert with_fee.effective_annual_rate > no_fee.effective_annual_rate
    assert with_fee.net_disbursed == 47_500


def test_zero_interest():
    c = loan_cost(12_000, 0, 12, 0, "reducing")
    assert c.emi == 1_000 and c.total_interest == pytest.approx(0)


def test_compare_shows_flat_extra_cost():
    r = compare_flat_vs_reducing(100_000, 12, 12)
    assert r["extra_cost_of_flat"] > 0


@pytest.mark.parametrize("bad", [
    dict(principal=0, annual_rate=10, term_months=12),
    dict(principal=1000, annual_rate=-1, term_months=12),
    dict(principal=1000, annual_rate=10, term_months=0),
    dict(principal=1000, annual_rate=10, term_months=12, fees=1000),
    dict(principal=1000, annual_rate=10, term_months=12, rate_type="weird"),
])
def test_validation_rejects_nonsense(bad):
    with pytest.raises(ValueError):
        loan_cost(**bad)


def test_affordability_verdicts():
    assert check_affordability(30_000, 15_000, 3_000).verdict == "comfortable"
    assert check_affordability(30_000, 15_000, 9_000).verdict == "comfortable"  # 30% EMI, 20% cushion
    assert check_affordability(30_000, 15_000, 13_000).verdict == "tight"  # 43% EMI, 7% cushion
    assert check_affordability(30_000, 25_000, 8_000).verdict == "unaffordable"
