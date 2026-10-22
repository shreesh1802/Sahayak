from agents.pipeline import State, compose, loan_analyst, review, untraceable_numbers

BUDGET = {"monthly_income": 25_000.0, "monthly_expenses": 14_000.0}


def offer(rate_type="flat", profile=BUDGET, fees=2_000.0, rate=24.0):
    return State(principal=50_000, annual_rate=rate, term_months=12, fees=fees, rate_type=rate_type, profile=profile)


def agents_run(result):
    return [t["agent"] + ":" + t["action"] for t in result["agent_trace"]]


def test_full_pipeline_runs_specialists_in_order_and_verifier_approves():
    r = review(offer())
    steps = agents_run(r)
    assert steps.index("loan_analyst:computed true cost") < steps.index("affordability:checked budget") \
        < steps.index("coach:chose follow-ups") < steps.index("verifier:approved")
    assert r["cost"]["emi"] == 5166.67 or abs(r["cost"]["emi"] - 5166.67) < 0.01
    assert r["affordability"]["verdict"] == "comfortable"


def test_supervisor_adapts_when_budget_is_unknown():
    r = review(offer(profile=None))
    steps = agents_run(r)
    assert "affordability:checked budget" not in steps
    assert "supervisor:skipped affordability" in steps
    assert r["affordability"] is None
    assert "do not have your income" in r["speech"]


def test_verifier_rejects_a_composer_that_invents_a_number():
    def lying_composer(s):
        return "Your monthly payment is 4,000 rupees and the true yearly cost is 31.5 percent."

    r = review(offer(), composer=lying_composer)
    assert any(t["agent"] == "verifier" and t["action"] == "REJECTED draft" and not t["ok"] for t in r["agent_trace"])
    assert "4,000" not in r["speech"] and "31.5" not in r["speech"]  # the lie was never spoken
    assert "5,167" in r["speech"]  # the safe fallback is built from the calculator


def test_verifier_accepts_calculator_numbers_at_spoken_precision():
    s = offer()
    loan_analyst(s)
    assert untraceable_numbers("You pay 5,167 a month and the true cost is 63.4 percent.", s) == []
    assert untraceable_numbers("You pay 5,200 a month.", s) == ["5,200"]
    assert untraceable_numbers("The true cost is 63.9 percent.", s) == ["63.9"]


def test_default_composer_never_trips_the_verifier():
    for rt in ("flat", "reducing"):
        for fees in (0.0, 2_000.0):
            for profile in (None, BUDGET, {"monthly_income": 9_000.0, "monthly_expenses": 8_000.0}):
                r = review(offer(rt, profile, fees))
                assert not any(not t["ok"] for t in r["agent_trace"]), (rt, fees, profile)


def test_coach_picks_lesson_from_the_findings():
    flat = review(offer("flat"))
    assert flat["lesson"]["id"] == "flat-vs-reducing"
    assert any("reducing-balance" in q for q in flat["questions"])

    clean = review(offer("reducing", fees=0.0, rate=12.0))
    assert clean["lesson"] is None
    assert not any("reducing-balance" in q for q in clean["questions"])

    stretched = review(offer("reducing", {"monthly_income": 9_000.0, "monthly_expenses": 6_000.0}, fees=0.0, rate=12.0))
    assert stretched["affordability"]["verdict"] != "comfortable"
    assert stretched["lesson"]["id"] == "emi-limit"


def test_compose_includes_questions_to_ask_the_lender():
    s = offer()
    r = review(s)
    assert "ask the lender" in r["speech"] and "(1)" in r["speech"]
    assert compose(s) == r["speech"]
