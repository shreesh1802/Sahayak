from agents.router import route


def test_loan_with_flat_rate():
    r = route("I was offered a loan of 50,000 at 24% flat for 12 months with a fee of 2000")
    assert r.tool == "explain_loan"
    assert r.args == {"principal": 50_000, "annual_rate": 24, "term_months": 12, "fees": 2_000, "rate_type": "flat"}


def test_years_and_lakh():
    r = route("borrow 2 lakh at 18 percent for 3 years")
    assert r.args["principal"] == 200_000 and r.args["term_months"] == 36
    assert "rate_type" not in r.args  # unknown -> server will ask


def test_affordability():
    r = route("can I afford 4500 a month?")
    assert (r.tool, r.args) == ("check_affordability", {"new_emi": 4_500})


def test_budget():
    r = route("my income is 25k and my expenses are 14k")
    assert r.tool == "save_my_budget" and r.args == {"monthly_income": 25_000, "monthly_expenses": 14_000}


def test_repayment():
    r = route("I paid 2,000 on loan 1")
    assert (r.tool, r.args) == ("log_repayment", {"amount": 2_000, "loan_id": 1})


def test_simple_intents():
    assert route("teach me something").tool == "next_lesson"
    assert route("show my loans").tool == "my_loans"


def test_unknown_gets_helpful_note():
    r = route("what's the weather")
    assert r.tool is None and r.note
