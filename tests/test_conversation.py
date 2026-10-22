from agents.router import route
from web.app import remember_budget


def turn(state, text):
    return remember_budget(state, route(text), text)


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
