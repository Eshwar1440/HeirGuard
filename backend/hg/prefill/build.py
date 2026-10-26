"""M7: prefill a mock Inherited IRA application from verified document fields.

Each prefilled value comes from exactly one document field and is written to
Neo4j as (PrefillField)-[:SOURCED_FROM]->(Fact). A field is used only when it
was read (value present, confidence at or above CONFIDENCE_THRESHOLD) and no
non-passing check for this beneficiary, or for the whole case, cites that field
or its whole document. SSNs and account numbers are never filled; the heir
enters them at signing.

The output is a proposed handoff to Schwab's digital onboarding workflow, not a
real submission.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from hg.checker.run import blocking
from hg.config import get_settings
from hg.graph import write_prefill
from hg.graph.resolve import link_applications
from hg.schemas import CaseState, CheckResult, Document, ExtractedField, PrefillField

PROPOSAL_LABEL = (
    "Proposed handoff to Schwab's digital onboarding workflow. Not a real submission; "
    "nothing is sent or opened."
)
HEIR_ENTERED = "Entered by heir at signing"

APP = "inherited_ira_application"
CERT = "death_certificate"

#: Prefill field -> (document type, field) sources, in order of preference.
SOURCES: dict[str, tuple[tuple[str, str], ...]] = {
    "beneficiary_name": ((APP, "beneficiary_name"),),
    "beneficiary_date_of_birth": ((APP, "beneficiary_date_of_birth"),),
    "relationship": ((APP, "relationship"),),
    "decedent_name": ((CERT, "decedent_name"), (APP, "decedent_name")),
    "decedent_date_of_death": ((CERT, "date_of_death"), (APP, "decedent_date_of_death")),
    "account_type": ((APP, "account_type"),),
    "share_percent": ((APP, "share_percent"),),
}

#: Never filled from documents.
HEIR_FIELDS: tuple[str, ...] = ("beneficiary_ssn", "linked_brokerage_account_number")

RMD_DEPOSIT_FIELD = "rmd_deposit_opt_in"

#: Rules whose evidence lists the documents that are present, not fields in doubt.
PRESENCE_RULES = frozenset({"required_docs_present"})


class ExcludedField(BaseModel):
    name: str
    reason: str


class PrefillHandoff(BaseModel):
    label: str = PROPOSAL_LABEL
    case_id: str
    beneficiary_id: str
    fields: list[PrefillField] = Field(default_factory=list)
    heir_entered: dict[str, str] = Field(default_factory=dict, description="field -> note shown instead of a value")
    excluded: list[ExcludedField] = Field(default_factory=list)


def _documents_for(case: CaseState, beneficiary_id: str) -> dict[str, list[Document]]:
    """Death certificates for the case, applications for this beneficiary only."""
    links = link_applications(case)
    docs: dict[str, list[Document]] = {CERT: [], APP: []}
    for doc in sorted(case.documents, key=lambda d: d.id):
        if doc.doc_type == CERT:
            docs[CERT].append(doc)
        elif doc.doc_type == APP and links.get(doc.id) == beneficiary_id:
            docs[APP].append(doc)
    return docs


def _cited(checks: list[CheckResult], doc: Document, field: str) -> Optional[CheckResult]:
    for check in checks:
        if check.rule_id in PRESENCE_RULES:
            continue
        for ev in check.evidence:
            if ev.document_id == doc.id and ev.field_name in (field, ""):
                return check
    return None


def _source(
    doc_types: dict[str, list[Document]],
    sources: tuple[tuple[str, str], ...],
    open_checks: list[CheckResult],
    threshold: float,
) -> tuple[Optional[tuple[Document, ExtractedField]], str]:
    """The first usable source, or None with the reason the last candidate was rejected."""
    reason = "no document provides it"
    for doc_type, name in sources:
        for doc in doc_types[doc_type]:
            field = next((f for f in doc.fields if f.name == name), None)
            if field is None or field.value is None:
                reason = f"{name} on the {doc_type} was not read"
            elif field.confidence < threshold:
                reason = f"{name} on the {doc_type} was read with low confidence"
            elif check := _cited(open_checks, doc, name):
                reason = f"{name} on the {doc_type} is cited by the {check.rule_id} check ({check.status})"
            else:
                return (doc, field), ""
    return None, reason


def build_handoff(
    case_state: CaseState,
    beneficiary_id: str,
    opt_in_rmd_deposit: bool,
    *,
    write_graph: bool = True,
) -> PrefillHandoff:
    """Build the proposed application for one beneficiary and record its sources in Neo4j."""
    if not any(b.id == beneficiary_id for b in case_state.beneficiaries):
        raise ValueError(f"unknown beneficiary {beneficiary_id!r}")
    if not case_state.checks:
        raise ValueError("run the packet checks before prefilling")

    threshold = get_settings().confidence_threshold
    open_checks = blocking(case_state.checks, beneficiary_id)
    docs = _documents_for(case_state, beneficiary_id)
    handoff = PrefillHandoff(case_id=case_state.case_id, beneficiary_id=beneficiary_id)

    for name, sources in SOURCES.items():
        found, reason = _source(docs, sources, open_checks, threshold)
        if found is None:
            handoff.excluded.append(ExcludedField(name=name, reason=reason))
            continue
        doc, field = found
        handoff.fields.append(
            PrefillField(name=name, value=field.value, source_document_id=doc.id, source_field=field.name)
        )
    for name in HEIR_FIELDS:
        handoff.fields.append(PrefillField(name=name))
        handoff.heir_entered[name] = HEIR_ENTERED
    handoff.fields.append(PrefillField(name=RMD_DEPOSIT_FIELD, value="yes" if opt_in_rmd_deposit else "no"))
    handoff.heir_entered[RMD_DEPOSIT_FIELD] = "Chosen by the heir (opt-in; off unless selected)"

    if write_graph:
        write_prefill(case_state.case_id, beneficiary_id, handoff.fields)
    return handoff


def build_prefill(case_state: CaseState, beneficiary_id: str, opt_in_rmd_deposit: bool) -> list[PrefillField]:
    """The prefilled fields for one beneficiary (see build_handoff for exclusions and labels)."""
    return build_handoff(case_state, beneficiary_id, opt_in_rmd_deposit).fields
