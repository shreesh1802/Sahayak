from agents.router import route
from web.app import remember_budget


def turn(state, text):
    return remember_budget(state, route(text), text)


def test_affordability_question_remembers_it_asked_for_the_payment():
    # the screenshot: "is the payment affordable" -> "How much...?" -> "14"
    state = {}
    r = turn(state, "if the payment is affordable")
    assert r.tool is None and "How much" in r.note
    r = turn(state, "4500")
    assert (r.tool, r.args) == ("check_affordability", {"new_emi": 4_500}) and "ask" not in state


def test_affordable_after_an_offer_reuses_that_offers_payment():
    state = {"last_emi": 5166.67}  # set by the app after explaining or reviewing an offer
    r = turn(state, "is the payment affordable")
    assert (r.tool, r.args) == ("check_affordability", {"new_emi": 5166.67})
    assert "5,167" in r.note and "offer we just looked at" in r.note
    assert "ask" not in state


def test_an_explicit_payment_still_beats_the_remembered_one():
    state = {"last_emi": 5166.67}
    assert turn(state, "can I afford 9000 a month").args == {"new_emi": 9_000}


def test_cut_off_payment_is_queried_then_confirmed():
    state = {}
    turn(state, "is the payment affordable")
    r = turn(state, "14")
    assert r.tool is None and "Did you mean 14,000?" in r.note
    r = turn(state, "yes")
    assert (r.tool, r.args) == ("check_affordability", {"new_emi": 14_000}) and not state


def test_cut_off_payment_then_no_then_full_amount():
    state = {}
    turn(state, "is the payment affordable")
    turn(state, "14")
    assert "full monthly payment" in turn(state, "no").note
    assert turn(state, "4500").args == {"new_emi": 4_500}


def test_payment_answered_with_number_words():
    state = {}
    turn(state, "is the payment affordable")
    assert turn(state, "around four thousand five hundred").args == {"new_emi": 4_500}


def test_pending_payment_question_is_dropped_when_user_moves_on():
    state = {}
    turn(state, "is the payment affordable")
    assert turn(state, "teach me something").tool == "next_lesson"
    assert "ask" not in state
    assert turn(state, "14000").tool is None  # a stray number is no longer an answer to anything


def test_budget_given_in_two_turns_is_completed():
    state = {}
    r1 = turn(state, "my income is 25000")
    assert r1.tool is None and "expenses" in r1.note
    r2 = turn(state, "14000")  # a bare number answers the question just asked
    assert (r2.tool, r2.args) == ("save_my_budget", {"monthly_income": 25_000, "monthly_expenses": 14_000})
    assert "budget" not in state  # nothing left pending


def test_expenses_first_then_income():
    state = {}
    turn(state, "my expenses are 14k")
    r = turn(state, "income 25k")
    assert r.args == {"monthly_expenses": 14_000, "monthly_income": 25_000}


def test_cut_off_number_is_queried_then_confirmed_with_yes():
    # the real failure: the user says 8000 and the browser hears "8"
    state = {}
    turn(state, "my income is 25000")
    r = turn(state, "Uh around 8")
    assert r.tool is None and "Did you mean 8,000?" in r.note
    assert state["budget"] == {"monthly_income": 25_000}  # the real income is still remembered
    r = turn(state, "yes")
    assert (r.tool, r.args) == ("save_my_budget", {"monthly_income": 25_000, "monthly_expenses": 8_000})
    assert not state


def test_three_digit_miss_suggests_ten_times():
    state = {}
    turn(state, "my income is 25000")
    r = turn(state, "around 800")
    assert "Did you mean 8,000?" in r.note
    assert turn(state, "yeah").args["monthly_expenses"] == 8_000


def test_saying_the_full_amount_instead_of_yes_works():
    state = {}
    turn(state, "my income is 25000")
    turn(state, "8")
    r = turn(state, "8000")  # corrects it directly
    assert r.args == {"monthly_income": 25_000, "monthly_expenses": 8_000}


def test_no_asks_for_the_full_amount_and_does_not_guess():
    state = {}
    turn(state, "my income is 25000")
    turn(state, "8")
    r = turn(state, "no")
    assert r.tool is None and "full amount" in r.note
    assert "suspect" not in state and state["budget"] == {"monthly_income": 25_000}


def test_both_given_but_one_low_asks_about_the_low_one_and_keeps_the_other():
    state = {}
    r = turn(state, "my income is 25000 and my expenses are 8")
    assert "Did you mean 8,000?" in r.note
    assert turn(state, "yes").args == {"monthly_income": 25_000, "monthly_expenses": 8_000}


def test_pending_question_is_dropped_when_user_moves_on():
    state = {}
    turn(state, "my income is 25000")
    r = turn(state, "teach me something")
    assert r.tool == "next_lesson" and "budget" not in state


def test_a_stray_number_without_a_pending_question_is_not_a_budget():
    state = {}
    r = turn(state, "14000")
    assert r.tool is None and "budget" not in state
