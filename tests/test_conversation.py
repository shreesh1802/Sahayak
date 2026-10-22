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


def test_cut_off_number_is_not_accepted_as_the_answer():
    state = {}
    turn(state, "my income is 25000")
    r = turn(state, "14")  # recognition stopped mid-number
    assert r.tool is None and "full number" in r.note
    assert state["budget"] == {"monthly_income": 25_000}  # still waiting for a real answer


def test_pending_question_is_dropped_when_user_moves_on():
    state = {}
    turn(state, "my income is 25000")
    r = turn(state, "teach me something")
    assert r.tool == "next_lesson" and "budget" not in state


def test_a_stray_number_without_a_pending_question_is_not_a_budget():
    state = {}
    r = turn(state, "14000")
    assert r.tool is None and "budget" not in state
