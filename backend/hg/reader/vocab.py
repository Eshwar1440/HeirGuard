"""Fixed field vocabulary per document type, and how each value is normalized.

The reader may only return these field names. They match the specimen forms in
``hg.data_gen.forms`` (a test enforces this). Normalized values:

* date: ISO YYYY-MM-DD
* percent: a plain number without "%" (e.g. 49.5)
* choice: lowercase words (e.g. child, primary, executor)
* account_type: traditional_ira, roth_ira, tod_brokerage, joint, individual or trust_owned
* yes_no: yes or no
* text: as printed
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Kind = Literal["text", "date", "percent", "choice", "account_type", "yes_no"]


@dataclass(frozen=True)
class FieldDef:
    name: str
    kind: Kind
    description: str


def _f(name: str, kind: Kind, description: str) -> FieldDef:
    return FieldDef(name, kind, description)


VOCAB: dict[str, tuple[FieldDef, ...]] = {
    "death_certificate": (
        _f("decedent_name", "text", "Full name of the person who died"),
        _f("date_of_birth", "date", "Decedent's date of birth"),
        _f("date_of_death", "date", "Date of death"),
        _f("place_of_death", "text", "City of death"),
        _f("issuing_county", "text", "County where the death was registered"),
        _f("issuing_state", "text", "State that issued the certificate"),
        _f("certificate_number", "text", "Certificate number"),
        _f("date_issued", "date", "Date the certificate was issued"),
        _f("certified_copy", "yes_no",
           "what the upload shows, not a verification: no if a VOID or COPY background pattern, an "
           "uncertified or informational notice, or no registrar certification is visible; yes if the "
           "registrar's certification is visible with none of those signs"),
    ),
    "inherited_ira_application": (
        _f("decedent_name", "text", "Name of the deceased account owner"),
        _f("decedent_date_of_death", "date", "Deceased owner's date of death"),
        _f("account_type", "account_type", "Type of account inherited"),
        _f("account_title", "text", "Account title as printed"),
        _f("beneficiary_name", "text", "Beneficiary's full name"),
        _f("beneficiary_date_of_birth", "date", "Beneficiary's date of birth"),
        _f("relationship", "choice", "Beneficiary's relationship to the deceased"),
        _f("designation", "choice", "primary or contingent"),
        _f("share_percent", "percent", "Beneficiary's share of the account"),
        _f("signature_name", "text", "Printed name of the signer"),
        _f("signature_date", "date", "Date signed"),
    ),
    "letters_testamentary": (
        _f("decedent_name", "text", "Name of the decedent (estate of)"),
        _f("date_of_death", "date", "Date of death"),
        _f("case_number", "text", "Court cause or case number"),
        _f("court_name", "text", "Name of the court"),
        _f("court_county", "text", "County of the court"),
        _f("date_issued", "date", "Date the letters were issued"),
        _f("executor_name", "text", "Name of the executor appointed"),
    ),
    "affidavit_of_domicile": (
        _f("decedent_name", "text", "Name of the decedent"),
        _f("date_of_death", "date", "Date of death"),
        _f("affiant_capacity", "choice", "Capacity of the affiant, e.g. executor"),
        _f("domicile_address", "text", "Decedent's domicile address at death"),
        _f("affiant_name", "text", "Name of the person swearing the affidavit"),
        _f("notary_date", "date", "Date sworn before the notary"),
    ),
    "trust_certification": (
        _f("trust_name", "text", "Name of the trust"),
        _f("trust_date", "date", "Date the trust was established"),
        _f("grantor_date_of_death", "date", "Grantor's date of death"),
        _f("grantor_name", "text", "Name of the grantor"),
        _f("successor_trustee_name", "text", "Name of the successor trustee"),
        _f("certification_date", "date", "Date of the certification"),
    ),
    # No vocabulary yet for wills; the reader classifies them but extracts nothing.
    "will": (),
    "unknown": (),
}

ALL_FIELD_NAMES: tuple[str, ...] = tuple(sorted({f.name for fields in VOCAB.values() for f in fields}))


def fields_for(doc_type: str) -> tuple[FieldDef, ...]:
    return VOCAB.get(doc_type, ())


def describe() -> str:
    """The vocabulary as prompt text."""
    lines = []
    for doc_type, fields in VOCAB.items():
        if not fields:
            continue
        lines.append(f"{doc_type}:")
        lines += [f"  - {f.name} ({f.kind}): {f.description}" for f in fields]
    return "\n".join(lines)
