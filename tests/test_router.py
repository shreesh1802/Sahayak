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


def test_income_alone_is_remembered_not_rejected():
    r = route("my income is 25000")
    assert r.tool is None and r.partial == {"monthly_income": 25_000} and "expenses" in r.note


def test_expenses_alone_is_remembered():
    r = route("my expenses are 14k")
    assert r.tool is None and r.partial == {"monthly_expenses": 14_000} and "What is your monthly income?" in r.note


def test_cut_off_number_is_queried_not_saved():
    # what the browser produced when speech recognition stopped mid-number
    r = route("My income is 25")
    assert r.tool is None and not r.partial
    assert r.suspect == {"monthly_income": 25.0} and "Did you mean 25,000?" in r.note


def test_number_words_are_understood():
    assert route("my income is twenty five thousand and my expenses are fourteen thousand").args == \
        {"monthly_income": 25_000, "monthly_expenses": 14_000}
    assert route("I paid two thousand on loan one").args == {"amount": 2_000, "loan_number": 1}
    assert route("borrow one lakh at 18 percent for two years reducing").args["principal"] == 100_000
    assert route("borrow one lakh at 18 percent for two years reducing").args["term_months"] == 24


def test_words_to_digits_leaves_ordinary_words_alone():
    from agents.router import words_to_digits
    assert words_to_digits("one of my loans") == "one of my loans"
    assert words_to_digits("one lakh fifty thousand") == "150000"
    assert words_to_digits("a hundred and five") == "a 105"
    assert words_to_digits("no thanks") == "no thanks"


def test_repayment_by_number():
    r = route("I paid 2,000 on loan 1")
    assert (r.tool, r.args) == ("log_repayment", {"amount": 2_000, "loan_number": 1})


def test_repayment_by_name():
    r = route("I paid 1500 on my shop credit loan")
    assert (r.tool, r.args) == ("log_repayment", {"amount": 1_500, "lender_label": "shop credit"})


def test_repayment_without_naming_a_loan():
    r = route("I paid 500 today")
    assert (r.tool, r.args) == ("log_repayment", {"amount": 500})


def test_add_loan_with_label():
    r = route("add a loan called shop credit of 12000 at 18 percent for 12 months reducing")
    assert r.tool == "add_loan"
    assert r.args == {"lender_label": "shop credit", "principal": 12_000, "annual_rate": 18,
                      "term_months": 12, "rate_type": "reducing", "fees": 0.0}


def test_add_loan_without_rate_type_asks_instead_of_guessing():
    r = route("add a loan of 12000 at 18 percent for 12 months")
    assert r.tool is None and "flat or" in r.note


def test_offer_is_explained_not_saved():
    assert route("I was offered a loan of 50000 at 24 percent flat for 12 months").tool == "explain_loan"


def test_should_i_take_it_goes_to_the_multi_agent_review():
    r = route("should I take a loan of 50000 at 24 percent flat for 12 months with a fee of 2000")
    assert r.tool == "review_loan_offer"
    assert r.args == {"principal": 50_000, "annual_rate": 24, "term_months": 12, "fees": 2_000, "rate_type": "flat"}


def test_review_without_numbers_is_not_guessed():
    assert route("should I take a loan").tool is None


def test_simple_intents():
    assert route("teach me something").tool == "next_lesson"
    assert route("show my loans").tool == "my_loans"


def test_unknown_gets_helpful_note():
    r = route("what's the weather")
    assert r.tool is None and r.note
