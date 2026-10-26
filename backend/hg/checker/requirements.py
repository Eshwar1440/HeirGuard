"""Which documents each account type needs, and where each requirement comes from.

Every row cites an official Schwab page or form, verified against the live
pages on 2026-10-25. Each row has a level:

* ``required``: a Schwab form, agreement or page says the document is needed.
  Missing it fails the check.
* ``conditional``: Schwab lists the document, but does not say when it applies.
  Missing it never blocks; the check mentions it may be requested.
* ``not_established``: no verified Schwab source states the requirement.
  Missing it needs human review, not a failure (AGENTS.md rule 2).

``certified=True`` on a death_certificate row means the source asks for a
certified copy specifically. Only the TOD agreement does; for inherited IRAs
Schwab does not say whether a photocopy is accepted.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Level = Literal["required", "conditional", "not_established"]

ESTATE_PLANNING_FAQS = (
    "Schwab, Estate Planning FAQs, \"Settling an estate\" > \"How do I notify Schwab of a death?\", "
    "https://www.schwab.com/estate-planning/faqs"
)
INHERITED_IRA_APPLICATION = (
    "Schwab, Inherited IRA Application for Individual Beneficiaries, form APP13599-33 (11/24), "
    "https://content.schwab.com/MARS-files/LPM27474.pdf"
)
INHERITED_IRA_CHECKLIST = (
    "Schwab, \"What are Inherited and Custodial IRAs?\", \"What do I need to open an Inherited IRA?\", "
    "https://www.schwab.com/ira/inherited-and-custodial-ira"
)
DESIGNATED_BENEFICIARY_PLAN = (
    "Schwab, Designated Beneficiary Plan Agreement, Section G \"Payment on Death\", "
    "form APP10780-23 (03/25), https://content.schwab.com/dcc/APP10780.pdf"
)
TRUSTEE_CHANGE_FORM = (
    "Schwab, Trustee Change Form, APP32257-19 (11/22), "
    "https://www.schwab.com/resource/trustee-change-for-s1-and-ic"
)


@dataclass(frozen=True)
class Requirement:
    account_type: str
    doc_type: str
    per_beneficiary: bool
    level: Level
    source: str
    excerpt: str
    certified: bool = False
    note: str = ""


_DEATH_CERT = Requirement(
    account_type="",
    doc_type="death_certificate",
    per_beneficiary=False,
    level="required",
    source=ESTATE_PLANNING_FAQS,
    excerpt="A death certificate will be needed for the estate administration process",
)
_CHECKLIST_NOTE = "Listed as information to have on hand; Schwab does not say when it is required."


def _death_cert(account_type: str, **changes) -> Requirement:
    return Requirement(**{**_DEATH_CERT.__dict__, "account_type": account_type, **changes})


REQUIREMENTS: tuple[Requirement, ...] = (
    # Inherited IRAs. The same application covers traditional and Roth.
    *(
        row
        for account_type, coverage in (
            ("traditional_ira", "Traditional IRA (includes Rollover, SEP, SIMPLE, and Inherited Traditional IRA)"),
            ("roth_ira", "Roth IRA (includes Inherited Roth IRA)"),
        )
        for row in (
            _death_cert(
                account_type,
                note="The application adds: \"A death certificate and/or other forms/documents may be "
                "required before assets can transfer to the beneficiaries.\"",
            ),
            Requirement(
                account_type, "inherited_ira_application", True, "required",
                INHERITED_IRA_APPLICATION, "Each Beneficiary must complete a separate application.",
                note=f"Account types on the form include \"{coverage}\".",
            ),
            Requirement(
                account_type, "letters_testamentary", False, "conditional",
                INHERITED_IRA_CHECKLIST, "Copy of the death certificate and letters testamentary",
                note=_CHECKLIST_NOTE,
            ),
            Requirement(
                account_type, "affidavit_of_domicile", False, "conditional",
                INHERITED_IRA_CHECKLIST, "Notarized Affidavit of Domicile",
                note=_CHECKLIST_NOTE,
            ),
        )
    ),
    # Trust-owned accounts
    _death_cert("trust_owned"),
    Requirement(
        "trust_owned", "trust_certification", False, "not_established",
        TRUSTEE_CHANGE_FORM,
        "This Trustee Change Form can be used to add and/or remove Trustees on a Schwab One Trust account",
        note="Schwab handles successor trustees through this form; no Schwab source names a certification "
        "of trust, and the form's document list could not be re-verified (PDF unavailable).",
    ),
    # Transfer-on-death accounts
    _death_cert(
        "tod_brokerage",
        source=DESIGNATED_BENEFICIARY_PLAN,
        excerpt="a certified copy of the death certificate",
        certified=True,
        note="The agreement also requires a completed Designated Beneficiary Plan Distribution Form and a "
        "tax waiver if required by state law; this prototype does not model those documents.",
    ),
    # Accounts that pass through the estate
    _death_cert("individual"),
    Requirement(
        "individual", "letters_testamentary", False, "conditional",
        INHERITED_IRA_CHECKLIST, "Copy of the death certificate and letters testamentary",
        note="Listed on Schwab's inherited IRA checklist; the trigger for estate accounts is not established.",
    ),
    Requirement(
        "individual", "affidavit_of_domicile", False, "conditional",
        INHERITED_IRA_CHECKLIST, "Notarized Affidavit of Domicile",
        note="Listed on Schwab's inherited IRA checklist; the trigger for estate accounts is not established.",
    ),
    # Joint accounts
    _death_cert("joint", note="Schwab does not publish a full post-death checklist for joint accounts."),
)


def requirements_for(account_type: str) -> list[Requirement]:
    return [r for r in REQUIREMENTS if r.account_type == account_type]


def certified_copy_required(account_types: set[str]) -> list[Requirement]:
    """Rows whose source asks for a certified death certificate, for these account types."""
    return [
        r for r in REQUIREMENTS
        if r.account_type in account_types and r.doc_type == "death_certificate" and r.certified
    ]
