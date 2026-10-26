"""Field meanings and name resolution shared by the graph builder and the checker.

Field names follow the vocabulary in ``hg.data_gen.forms`` (also used by the
reader). Names are compared with RapidFuzz ``token_sort_ratio`` after
lowercasing and stripping punctuation.
"""

from __future__ import annotations

from typing import Optional

from rapidfuzz import fuzz, utils

from hg.config import get_settings
from hg.schemas import CaseState, Document

#: Fields holding the decedent's date of death, on any document type.
DOD_FIELDS = frozenset({"date_of_death", "decedent_date_of_death", "grantor_date_of_death"})

#: Fields holding a person's name, mapped to the role that person plays.
PERSON_FIELDS = {
    "decedent_name": "decedent",
    "grantor_name": "decedent",
    "beneficiary_name": "beneficiary",
    "signature_name": "beneficiary",
    "executor_name": "executor",
    "affiant_name": "affiant",
    "successor_trustee_name": "trustee",
}

#: Application fields that describe the beneficiary or the inherited account.
BENEFICIARY_FIELDS = frozenset(
    {"beneficiary_date_of_birth", "relationship", "designation", "share_percent", "signature_date"}
)
ACCOUNT_FIELDS = frozenset({"account_type", "account_title"})
TRUST_FIELDS = frozenset({"trust_name", "trust_date"})


def fact_kind(field_name: str) -> str:
    if field_name in DOD_FIELDS:
        return "date_of_death"
    if field_name in PERSON_FIELDS:
        return "person_name"
    return field_name


def normalize_name(name: str) -> str:
    return utils.default_process(name)


def name_score(a: str, b: str) -> float:
    return fuzz.token_sort_ratio(a, b, processor=utils.default_process)


def best_match(name: str, candidates: dict[str, str]) -> tuple[Optional[str], float]:
    """The candidate id whose name scores highest against ``name``, and that score."""
    best_id, best = None, 0.0
    for cid, cname in candidates.items():
        score = name_score(name, cname)
        if score > best:
            best_id, best = cid, score
    return best_id, best


def field_value(doc: Document, name: str) -> Optional[str]:
    return next((f.value for f in doc.fields if f.name == name), None)


def link_applications(case: CaseState) -> dict[str, Optional[str]]:
    """Map each inherited IRA application to the beneficiary it names.

    An application links to the best-scoring beneficiary at or above
    NAME_MATCH_THRESHOLD (hypothetical); otherwise it maps to None.
    """
    threshold = get_settings().name_match_threshold
    names = {b.id: b.name for b in case.beneficiaries}
    links: dict[str, Optional[str]] = {}
    for doc in case.documents:
        if doc.doc_type != "inherited_ira_application":
            continue
        applicant = field_value(doc, "beneficiary_name")
        bid, score = best_match(applicant, names) if applicant else (None, 0.0)
        links[doc.id] = bid if score >= threshold else None
    return links
