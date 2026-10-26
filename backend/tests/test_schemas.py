from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from hg.config import DEFAULT_GROWTH_RATE
from hg.schemas import (
    Account,
    AuditEntry,
    Beneficiary,
    BlockedAttempt,
    CaseState,
    CheckResult,
    Decedent,
    Document,
    Evidence,
    ExtractedField,
    GuideText,
    HeirInputs,
    PrefillField,
    Scenario,
    ScenarioYear,
)


def _sample_case() -> CaseState:
    return CaseState(
        case_id="case-test",
        decedent=Decedent(
            id="d1",
            name="Hypothetical Parent",
            date_of_birth=date(1950, 3, 14),
            date_of_death=date(2025, 6, 2),
            rmds_started=True,
        ),
        accounts=[
            Account(id="a1", type="traditional_ira", title="Traditional IRA", balance=Decimal("412345.67"))
        ],
        beneficiaries=[
            Beneficiary(
                id="b1",
                name="Hypothetical Child",
                date_of_birth=date(1980, 1, 1),
                relationship="child",
                share_percent=Decimal("50"),
                designation="primary",
                account_id="a1",
                beneficiary_class="designated",
            ),
            Beneficiary(
                id="b2",
                name="Hypothetical Sibling",
                date_of_birth=date(1983, 7, 9),
                relationship="child",
                share_percent=Decimal("49.5"),
                designation="primary",
                account_id="a1",
            ),
        ],
        documents=[
            Document(
                id="doc1",
                case_id="case-test",
                file_ref="packets/case-test/death_certificate.pdf",
                doc_type="death_certificate",
                fields=[ExtractedField(name="date_of_death", value="2025-06-02", confidence=0.97, page=1)],
            )
        ],
        checks=[
            CheckResult(
                rule_id="shares_total_100",
                status="fail",
                message="Primary shares total 99.5%",
                evidence=[Evidence(document_id="doc1", field_name="share_percent")],
            )
        ],
        heir_inputs=HeirInputs(annual_income=Decimal("85000.00"), filing_status="single"),
        scenarios=[
            Scenario(
                name="lump_sum_now",
                years=[
                    ScenarioYear(
                        year=2026,
                        withdrawal=Decimal("206172.84"),
                        rmd_required=Decimal("0"),
                        incremental_federal_tax=Decimal("61234.10"),
                        state_tax=Decimal("0.00"),
                        end_balance=Decimal("0.00"),
                    )
                ],
                total_tax=Decimal("61234.10"),
                after_tax_total=Decimal("144938.74"),
            )
        ],
        guide=[
            GuideText(
                kind="issue_reason",
                text="The shares add up to 99.5%, not 100%.",
                numbers_used=["99.5", "100"],
                blocked_attempts=[BlockedAttempt(text="You should fix it", reason="advice phrase")],
                rule_id="shares_total_100",
            )
        ],
        choice="keep",
        prefill=[PrefillField(name="ssn", value="entered by heir at signing")],
        status="awaiting_choice",
    )


def test_case_state_round_trips_with_decimals_intact():
    case = _sample_case()
    restored = CaseState.model_validate_json(case.model_dump_json())

    assert restored == case
    assert restored.accounts[0].balance == Decimal("412345.67")
    assert isinstance(restored.accounts[0].balance, Decimal)
    assert restored.beneficiaries[1].share_percent == Decimal("49.5")
    assert restored.scenarios[0].years[0].withdrawal == Decimal("206172.84")


def test_decimals_serialize_as_exact_strings():
    payload = _sample_case().model_dump(mode="json")
    assert payload["accounts"][0]["balance"] == "412345.67"
    assert payload["heir_inputs"]["growth_rate"] == str(DEFAULT_GROWTH_RATE)


def test_every_model_round_trips():
    case = _sample_case()
    for model in [
        case.decedent,
        *case.accounts,
        *case.beneficiaries,
        *case.documents,
        *case.checks,
        case.heir_inputs,
        *case.scenarios,
        *case.guide,
        *case.prefill,
        AuditEntry(case_id="case-test", node="intake", action="start", summary="Case created"),
    ]:
        assert type(model).model_validate_json(model.model_dump_json()) == model


def test_heir_inputs_default_growth_is_the_hypothetical_config_value():
    inputs = HeirInputs(annual_income=Decimal("50000"), filing_status="married_joint")
    assert inputs.growth_rate == DEFAULT_GROWTH_RATE
    assert inputs.state_tax_rate == Decimal("0")


def test_new_case_defaults():
    case = CaseState(case_id="c")
    assert case.status == "intake"
    assert case.approved is False
    assert case.choice is None
    assert case.documents == []


@pytest.mark.parametrize(
    "build",
    [
        lambda: ExtractedField(name="x", value="y", confidence=1.2, page=1),
        lambda: ExtractedField(name="x", value="y", confidence=0.5, page=0),
        lambda: Account(id="a", type="savings", title="t", balance=Decimal("1")),
        lambda: CheckResult(rule_id="r", status="maybe", message="m"),
        lambda: CaseState(case_id="c", choice="sell"),
        lambda: CaseState(case_id="c", unexpected_field=True),
    ],
)
def test_invalid_values_are_rejected(build):
    with pytest.raises(ValidationError):
        build()
