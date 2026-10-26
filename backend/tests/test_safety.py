"""M6 safety check (AI-log check #2). Deterministic; no LLM."""

from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from hg.safety import check, find_numbers, normalize_allowed
from hg.schemas import AuditEntry

ALLOWED = {"100000.00", "3623.19", "25", "0.22", "22", "2035", "2035-12-31", "10"}

NEUTRAL_SUMMARY = (
    "Here is how the four options compare. Taking the lump sum now adds about $100,000.00 to "
    "this year's income. If you take the minimums each year, the first one is $3,623.19, and the "
    "rest of the account must come out by December 31, 2035. The even spread splits withdrawals "
    "over 10 years. These tax figures are estimates based on your inputs and current brackets. "
    "A tax professional can help you decide."
)


# --- Required cases ---------------------------------------------------------------


def test_invented_dollar_amount_fails():
    result = check("Withdrawing everything now would cost $18,450 in federal tax.", ALLOWED)
    assert not result.ok
    assert result.reasons == ['number "$18,450" is not in the input']


def test_you_should_take_the_lump_sum_fails():
    result = check("You should take the lump sum.", ALLOWED)
    assert not result.ok
    assert 'advice phrase "you should"' in result.reasons


def test_clean_neutral_summary_passes():
    result = check(NEUTRAL_SUMMARY, ALLOWED)
    assert result.ok, result.reasons
    assert result.reasons == []


@pytest.mark.parametrize("variant", ["$3,623.19", "3623.19", "$3623.19", "3,623.19", "$ 3,623.190"])
def test_formatting_variants_of_an_allowed_number_pass(variant):
    assert check(f"The first minimum is {variant}.", ALLOWED).ok


@given(cents=st.integers(min_value=0, max_value=10**10))
def test_every_currency_format_of_an_allowed_amount_passes(cents):
    amount = Decimal(cents) / 100
    allowed = {str(amount)}
    for text in (f"${amount:,.2f}", f"{amount:.2f}", f"${amount:,}", f"{amount:,.2f} dollars"):
        assert check(f"The amount is {text}.", allowed).ok, text


# --- Number check details -------------------------------------------------------


def test_normalization():
    tokens = [token for _, token in find_numbers("$1,234.50, 25%, 22 percent, $1.2 million, $3.6k and 0.22")]
    assert tokens == [Decimal("1234.50"), Decimal(25), Decimal(22), Decimal(1_200_000), Decimal(3_600), Decimal("0.22")]
    assert find_numbers("by Dec. 31st, 2035 or 12/31/2035 or 2035-12-31") == [
        ("Dec. 31st, 2035", "2035-12-31"),
        ("12/31/2035", "2035-12-31"),
        ("2035-12-31", "2035-12-31"),
    ]


def test_percent_and_fraction_are_different_numbers():
    assert check("Your bracket is 22%.", {"22"}).ok
    assert not check("Your bracket is 22%.", {"0.22"}).ok


def test_rounded_number_is_blocked():
    result = check("The first minimum is about $3,600.", ALLOWED)
    assert result.reasons == ['number "$3,600" is not in the input']


def test_deadline_year_and_date_are_allowed_but_other_years_are_not():
    assert check("Everything must come out by the end of 2035.", ALLOWED).ok
    assert check("The deadline is December 31, 2035.", ALLOWED).ok
    assert check("The deadline is December 31, 2034.", ALLOWED).reasons == [
        'date "December 31, 2034" is not in the input'
    ]
    assert check("The deadline is 2036.", ALLOWED).reasons == ['number "2036" is not in the input']


def test_invalid_date_never_matches():
    assert not check("Due February 30, 2035.", {"2035-02-30", "2035"}).ok


def test_hyphenated_and_ordinal_numbers_are_checked():
    assert check("This is the 10-year rule.", ALLOWED).ok
    assert check("Under the 5-year rule.", ALLOWED).reasons == ['number "5" is not in the input']


def test_allowed_values_use_the_same_normalization():
    assert normalize_allowed(["$1,000", "25%", "2035-12-31", "not a number"]) == {
        Decimal(1000), Decimal(25), "2035-12-31",
    }


# --- Advice check details -------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "We recommend the even spread.",
        "I suggest waiting until next year.",
        "The best option for most people is the balloon.",
        "That is the right choice for you.",
        "You’d be better off spreading it out.",
        "YOU SHOULD talk to us first.",
        "Do this before December.",
    ],
)
def test_advice_phrases_fail(text):
    assert not check(text, ALLOWED).ok


@pytest.mark.parametrize(
    ("text", "match"),
    [
        ("Take the lump sum.", "take the lump sum"),
        ("Choose the even spread.", "choose the even spread"),
        ("To keep more, go with the fill-the-bracket option.", "go with the fill-the-bracket"),
        ("So just pick the even spread", "pick the even spread"),
        ("Honestly, consider the lump-sum option.", "consider the lump-sum"),
        ("Stick with the minimums.", "stick with the minimums"),
    ],
)
def test_imperative_scenario_recommendation_fails(text, match):
    assert f'recommends a scenario: "{match}"' in check(text, ALLOWED).reasons


@pytest.mark.parametrize(
    "text",
    [
        "If you take the lump sum, the tax comes in one year.",
        "Taking the lump sum now adds the whole balance to this year's income.",
        "The even spread splits withdrawals across the years.",
        "You could take the minimums each year and leave the rest for later.",
        "Use the table below to compare how the even spread and the lump sum differ.",
        "A tax professional can help you decide.",
    ],
)
def test_neutral_mentions_of_scenarios_pass(text):
    assert check(text, ALLOWED).ok, check(text, ALLOWED).reasons


def test_every_reason_is_returned():
    result = check("You should take the lump sum and save $9,999.", ALLOWED)
    assert result.reasons == [
        'number "$9,999" is not in the input',
        'advice phrase "you should"',
    ]
    result = check("We recommend this. Take the lump sum, worth $5.", ALLOWED)
    assert len(result.reasons) == 3


# --- Audit ------------------------------------------------------------------------


def test_block_is_logged_as_an_audit_entry():
    recorded: list[AuditEntry] = []
    result = check("You should take $1.", ALLOWED, case_id="case-1", record=recorded.append)
    assert recorded == [result.audit_entry]
    entry = result.audit_entry
    assert entry.case_id == "case-1" and entry.node == "safety_check" and entry.action == "blocked"
    assert 'advice phrase "you should"' in entry.summary and '"$1"' in entry.summary


def test_pass_records_nothing():
    recorded: list[AuditEntry] = []
    result = check(NEUTRAL_SUMMARY, ALLOWED, case_id="case-1", record=recorded.append)
    assert result.ok and result.audit_entry is None and recorded == []
