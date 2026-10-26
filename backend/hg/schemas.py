"""Shared contracts. Every module imports from here.

Changes to this file go in their own small PR.

Money is always ``Decimal``. Pydantic v2 serializes ``Decimal`` to a JSON
string, so values round-trip exactly (no float drift). All balances and
amounts in this project are hypothetical.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from hg.config import DEFAULT_GROWTH_RATE

# --- Enumerations ------------------------------------------------------------

AccountType = Literal[
    "traditional_ira",
    "roth_ira",
    "tod_brokerage",
    "joint",
    "individual",
    "trust_owned",
]

DesignationType = Literal["primary", "contingent"]

BeneficiaryClass = Literal["spouse", "eligible_designated", "designated", "entity"]

DocType = Literal[
    "death_certificate",
    "inherited_ira_application",
    "letters_testamentary",
    "affidavit_of_domicile",
    "trust_certification",
    "will",
    "unknown",
]

CheckStatus = Literal["pass", "fail", "needs_review"]

FilingStatus = Literal["single", "married_joint", "married_separate", "head_of_household"]

GuideKind = Literal["issue_reason", "options_summary"]

Choice = Literal["keep", "talk", "transfer"]

CaseStatus = Literal[
    "intake",
    "reading_documents",
    "checking",
    "awaiting_heir_fix",
    "awaiting_approval",
    "simulating",
    "awaiting_choice",
    "prefilled",
    "handed_off",
    "transfer_requested",
    "error",
]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- People and accounts -----------------------------------------------------


class Decedent(_Model):
    id: str
    name: str
    date_of_birth: date
    date_of_death: date
    rmds_started: Optional[bool] = Field(
        default=None,
        description="Whether the decedent had started RMDs. None means unknown; "
        "M4 then compares date_of_death to the required beginning date.",
    )


class Account(_Model):
    id: str
    type: AccountType
    title: str
    balance: Decimal = Field(
        description="hypothetical balance in USD",
        json_schema_extra={"hypothetical": True},
    )


class Beneficiary(_Model):
    id: str
    name: str
    date_of_birth: date
    relationship: str = Field(description="Relationship to the decedent, e.g. child, spouse, sibling")
    share_percent: Decimal
    designation: DesignationType
    account_id: Optional[str] = Field(
        default=None, description="Account this designation applies to"
    )
    beneficiary_class: Optional[BeneficiaryClass] = None
    disabled: Optional[bool] = Field(
        default=None, description="Explicit input only. Never inferred."
    )
    chronically_ill: Optional[bool] = Field(
        default=None, description="Explicit input only. Never inferred."
    )


# --- Documents and checks ----------------------------------------------------


class ExtractedField(_Model):
    name: str
    value: Optional[str] = Field(
        default=None, description="None when the field is unreadable or absent"
    )
    confidence: float = Field(ge=0.0, le=1.0)
    page: int = Field(ge=1)


class Document(_Model):
    id: str
    case_id: str
    file_ref: str
    doc_type: DocType
    fields: list[ExtractedField] = Field(default_factory=list)
    needs_review: bool = False


class Evidence(_Model):
    document_id: str
    field_name: str


class CheckResult(_Model):
    rule_id: str
    status: CheckStatus
    message: str
    beneficiary_id: Optional[str] = None
    evidence: list[Evidence] = Field(default_factory=list)


# --- Heir inputs and simulation ----------------------------------------------


class HeirInputs(_Model):
    annual_income: Decimal = Field(ge=0)
    filing_status: FilingStatus
    state_tax_rate: Decimal = Field(
        default=Decimal("0"), ge=0, le=1, description="Flat rate as a fraction, e.g. 0.05"
    )
    growth_rate: Decimal = Field(
        default=DEFAULT_GROWTH_RATE,
        description="hypothetical annual growth rate as a fraction",
        json_schema_extra={"hypothetical": True},
    )
    bracket_to_fill: Optional[str] = Field(
        default=None, description="Federal bracket rate to fill, e.g. '0.22'"
    )


class ScenarioYear(_Model):
    year: int
    withdrawal: Decimal
    rmd_required: Decimal = Field(description="Required minimum for the year; 0 if none")
    incremental_federal_tax: Decimal
    state_tax: Decimal
    end_balance: Decimal


class Scenario(_Model):
    name: str
    years: list[ScenarioYear] = Field(default_factory=list)
    total_tax: Decimal
    after_tax_total: Decimal


# --- Writer, prefill, audit --------------------------------------------------


class BlockedAttempt(_Model):
    text: str
    reason: str


class GuideText(_Model):
    kind: GuideKind
    text: str
    numbers_used: list[str] = Field(default_factory=list)
    blocked_attempts: list[BlockedAttempt] = Field(default_factory=list)
    rule_id: Optional[str] = Field(default=None, description="Set for issue_reason")
    beneficiary_id: Optional[str] = None


class PrefillField(_Model):
    name: str
    value: Optional[str] = None
    source_document_id: Optional[str] = Field(
        default=None, description="None only for fields entered by the heir at signing"
    )
    source_field: Optional[str] = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditEntry(_Model):
    timestamp: datetime = Field(default_factory=_utcnow)
    case_id: str
    node: str
    action: str
    summary: str


# --- Case --------------------------------------------------------------------


class CaseState(_Model):
    case_id: str
    decedent: Optional[Decedent] = None
    accounts: list[Account] = Field(default_factory=list)
    beneficiaries: list[Beneficiary] = Field(default_factory=list)
    documents: list[Document] = Field(default_factory=list)
    checks: list[CheckResult] = Field(default_factory=list)
    approved: bool = False
    heir_inputs: Optional[HeirInputs] = None
    scenarios: list[Scenario] = Field(default_factory=list)
    guide: list[GuideText] = Field(default_factory=list)
    choice: Optional[Choice] = None
    prefill: list[PrefillField] = Field(default_factory=list)
    status: CaseStatus = "intake"
