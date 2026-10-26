"""M5 writer tests. The LLM is mocked; no API calls."""

import json
from datetime import date
from decimal import Decimal

import pytest

from hg.config import get_settings
from hg.data_gen import load_truth
from hg.llm import LLMRefusalError
from hg.safety import check, normalize_allowed
from hg.schemas import CheckResult, Decedent, HeirInputs
from hg.simulator.rmd import to_cents
from hg.simulator.rules import rule_summary
from hg.simulator.scenarios import simulate
from hg.writer import allowed_numbers, explain_issue, summarize_options
from hg.writer import templates
from hg.writer import write as writer

PHOTOCOPY = CheckResult(
    rule_id="certified_copy",
    status="fail",
    message="The death certificate is a photocopy. Schwab's terms for transfer-on-death accounts ask for a "
    "certified copy of the death certificate.",
    beneficiary_id="b1",
)
DOD = CheckResult(
    rule_id="dod_consistent",
    status="fail",
    message="The date of death reads 2025-04-30 on the death certificate but 2025-05-01 on the inherited IRA "
    "application.",
    beneficiary_id="b1",
)


@pytest.fixture
def replies(monkeypatch):
    """Queue model replies; each call pops one. An exception instance is raised instead."""
    calls = []

    def install(*queued):
        queue = list(queued)

        def fake_write_text(system, user_json, *, case_id=None):
            calls.append({"system": system, "input": user_json, "case_id": case_id})
            reply = queue.pop(0)
            if isinstance(reply, Exception):
                raise reply
            return reply

        monkeypatch.setattr(writer, "write_text", fake_write_text)
        return calls

    return install


def _demo():
    truth = load_truth(get_settings().data_dir / "packets" / "packet_01_fixed")
    heir = truth.beneficiaries[0]
    balance = to_cents(truth.accounts[0].balance * heir.share_percent / 100)
    inputs = HeirInputs(annual_income=Decimal("85000"), filing_status="single", state_tax_rate=Decimal("0.05"))
    result = simulate(balance, truth.decedent, heir, "traditional_ira", inputs)
    return result, inputs


# --- explain_issue -------------------------------------------------------------------


def test_clean_reply_is_returned_with_numbers_used(replies):
    text = "Your death certificate reads 2025-04-30, but the application says May 1, 2025. Correct the form."
    calls = replies(text)
    guide = explain_issue(DOD, case_id="case-1")

    assert guide.kind == "issue_reason" and guide.text == text
    assert guide.rule_id == "dod_consistent" and guide.beneficiary_id == "b1"
    assert guide.numbers_used == ["2025-04-30", "May 1, 2025"]
    assert guide.blocked_attempts == []
    assert calls[0]["input"] == {"rule_id": "dod_consistent", "status": "fail", "message": DOD.message}
    assert calls[0]["case_id"] == "case-1"


def test_blocked_then_regenerated(replies):
    bad = "You should order a certified copy. It costs $25."
    good = "Your upload looks like a photocopy. Schwab needs a certified copy, which you can order from the county."
    calls = replies(bad, good)
    recorded = []
    guide = explain_issue(PHOTOCOPY, case_id="case-1", record=recorded.append)

    assert guide.text == good
    assert len(guide.blocked_attempts) == 1
    assert guide.blocked_attempts[0].text == bad
    assert 'number "$25" is not in the input' in guide.blocked_attempts[0].reason
    assert 'advice phrase "you should"' in guide.blocked_attempts[0].reason
    retry = calls[1]["input"]["previous_attempt_blocked"]
    assert retry["text"] == bad and 'advice phrase "you should"' in retry["reasons"]
    assert [e.action for e in recorded] == ["blocked"]


def test_blocked_twice_falls_back_to_template(replies):
    replies("You should pay $40 for a copy.", "We recommend the county office.")
    guide = explain_issue(PHOTOCOPY)

    assert guide.text == templates.issue_text(PHOTOCOPY)
    assert len(guide.blocked_attempts) == 2
    assert check(guide.text, allowed_numbers(writer.issue_payload(PHOTOCOPY))).ok


def test_model_unavailable_falls_back_to_template(replies):
    calls = replies(LLMRefusalError("declined"))
    guide = explain_issue(DOD)
    assert len(calls) == 1
    assert guide.text == templates.issue_text(DOD) and guide.blocked_attempts == []
    assert guide.numbers_used == ["2025-04-30", "2025-05-01"]


@pytest.mark.parametrize("rule_id", [*templates.ISSUE_FIXES, "some_new_rule"])
@pytest.mark.parametrize("status", ["fail", "needs_review"])
def test_every_issue_template_passes_the_safety_check(rule_id, status):
    result = CheckResult(rule_id=rule_id, status=status,
                         message="Primary beneficiary shares on Hypothetical IRA total 90%. They must total 100%.")
    text = templates.issue_text(result)
    assert check(text, allowed_numbers(writer.issue_payload(result))).ok


# --- summarize_options ---------------------------------------------------------------


def test_options_payload_is_structured_inputs_only():
    result, inputs = _demo()
    payload = writer.options_payload(result.scenarios, result.rules, inputs, result.tax_year)

    assert set(payload) == {"scenario_count", "scenarios", "rule", "heir_inputs", "federal_brackets_year"}
    assert payload["rule"]["deadline_date"] == f"{result.rules.deadline_year}-12-31"
    assert payload["heir_inputs"]["state_tax_rate_percent"] == "5"
    assert payload["heir_inputs"]["growth_rate_percent_hypothetical"] == "5"
    text = json.dumps(payload)
    assert "%PDF" not in text and "file_ref" not in text


def test_options_template_passes_and_names_every_scenario(replies):
    result, inputs = _demo()
    replies(LLMRefusalError("declined"))
    guide = summarize_options(result.scenarios, result.rules, inputs, tax_year=result.tax_year, beneficiary_id="b1")

    assert guide.kind == "options_summary" and guide.beneficiary_id == "b1"
    for s in result.scenarios:
        assert templates.SCENARIO_LABELS[s.name] in guide.text
        assert templates.money(s.total_tax) in guide.text
    assert "estimates" in guide.text and "tax professional" in guide.text
    assert f"December 31, {result.rules.deadline_year}" in guide.text


def test_options_summary_blocks_a_recommendation_then_falls_back(replies):
    result, inputs = _demo()
    lump = result.scenarios[0]
    replies(
        f"Take the lump sum: tax is {templates.money(lump.total_tax)}.",
        "The even spread is the best option for you.",
    )
    guide = summarize_options(result.scenarios, result.rules, inputs)

    reasons = [a.reason for a in guide.blocked_attempts]
    assert 'recommends a scenario: "take the lump sum"' in reasons[0]
    assert 'advice phrase "the best option"' in reasons[1]
    assert guide.text == templates.options_text(writer.options_payload(result.scenarios, result.rules, inputs))


def test_options_summary_accepts_numbers_from_the_input(replies):
    result, inputs = _demo()
    even = result.scenarios[2]
    text = (
        f"With the even spread, the estimated total tax is {templates.money(even.total_tax)} at your "
        f"$85,000 income and 5% state rate, using the {result.tax_year} brackets. Everything must be out by "
        f"December 31, {result.rules.deadline_year}, within the 10-year window. These are estimates; a tax "
        "professional can help you decide."
    )
    replies(text)
    guide = summarize_options(result.scenarios, result.rules, inputs, tax_year=result.tax_year)
    assert guide.text == text and guide.blocked_attempts == []


def test_specialist_case_template_passes():
    decedent = Decedent(id="d", name="Hypothetical Owner", date_of_birth=date(1940, 1, 1),
                        date_of_death=date(2019, 6, 1))
    _, inputs = _demo()
    truth = load_truth(get_settings().data_dir / "packets" / "packet_01_fixed")
    rules = rule_summary(truth.beneficiaries[0], decedent, "traditional_ira")
    payload = writer.options_payload([], rules, inputs, 2026)
    assert check(templates.options_text(payload), allowed_numbers(payload)).ok


def test_allowed_numbers_include_years_of_dates():
    allowed = allowed_numbers({"message": "died 2025-04-30", "flag": True, "none": None})
    assert allowed == {"died 2025-04-30", "2025"}
    assert normalize_allowed(allowed) == {"2025-04-30", Decimal(2025)}


def test_options_template_is_one_point_per_line():
    result, inputs = _demo()
    text = templates.options_text(writer.options_payload(result.scenarios, result.rules, inputs))
    lines = text.splitlines()
    assert len(lines) == len(result.scenarios) + 2 and all(line.startswith("- ") for line in lines)
    assert "Plain" not in writer.OPTIONS_SYSTEM and 'starting with "- "' in writer.OPTIONS_SYSTEM
