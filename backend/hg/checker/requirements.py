"""Which documents each account type needs, and where each requirement comes from.

Sources are Schwab public pages and forms. Schwab's site refuses automated
fetches, so the excerpts below were checked against search-engine excerpts of
those pages on 2026-10-25. A person should confirm them in a browser before the
demo. Rows with no Schwab source are marked ``hypothetical=True`` and say so in
the UI, per AGENTS.md rule 2.
"""

from __future__ import annotations

from dataclasses import dataclass

LOSING_A_LOVED_ONE = (
    "Schwab, \"Death Notification: What to do when a loved one dies\" (Inheritance Center), "
    "https://www.schwab.com/life-events/losing-a-loved-one"
)
INHERITED_IRA_APPLICATION = (
    "Schwab, Inherited IRA Application for Individual Beneficiaries (form LPM27474), "
    "https://content.schwab.com/MARS-files/LPM27474.pdf"
)
INHERITED_AND_CUSTODIAL_IRA = (
    "Schwab, \"What are Inherited and Custodial IRAs?\", "
    "https://www.schwab.com/ira/inherited-and-custodial-ira"
)


@dataclass(frozen=True)
class Requirement:
    account_type: str
    doc_type: str
    per_beneficiary: bool
    source: str
    excerpt: str
    hypothetical: bool = False
    note: str = ""


_DEATH_CERT_EXCERPT = "A death certificate will be needed for the estate administration process"

REQUIREMENTS: tuple[Requirement, ...] = (
    # Inherited IRAs (traditional and Roth)
    *(
        row
        for account_type in ("traditional_ira", "roth_ira")
        for row in (
            Requirement(account_type, "death_certificate", False, LOSING_A_LOVED_ONE, _DEATH_CERT_EXCERPT),
            Requirement(
                account_type,
                "inherited_ira_application",
                True,
                INHERITED_IRA_APPLICATION,
                "Each Beneficiary must complete a separate application.",
                note=f"See also {INHERITED_AND_CUSTODIAL_IRA}",
            ),
        )
    ),
    # Trust-owned accounts
    Requirement("trust_owned", "death_certificate", False, LOSING_A_LOVED_ONE, _DEATH_CERT_EXCERPT),
    Requirement(
        "trust_owned",
        "trust_certification",
        False,
        source="hypothetical: no Schwab public page found stating this requirement",
        excerpt="",
        hypothetical=True,
        note="A successor trustee usually proves authority with a certification of trust; confirm with Schwab.",
    ),
    # Accounts that pass through the estate or by transfer-on-death
    Requirement("individual", "death_certificate", False, LOSING_A_LOVED_ONE, _DEATH_CERT_EXCERPT),
    Requirement(
        "individual", "letters_testamentary", False, LOSING_A_LOVED_ONE,
        "Copy of the death certificate and letters testamentary",
        note="Scoping to individual (estate) accounts is a hypothetical simplification.",
    ),
    Requirement(
        "individual", "affidavit_of_domicile", False, LOSING_A_LOVED_ONE,
        "Notarized Affidavit of Domicile",
        note="Scoping to individual (estate) accounts is a hypothetical simplification.",
    ),
    Requirement("tod_brokerage", "death_certificate", False, LOSING_A_LOVED_ONE, _DEATH_CERT_EXCERPT),
    Requirement(
        "tod_brokerage", "affidavit_of_domicile", False, LOSING_A_LOVED_ONE,
        "Notarized Affidavit of Domicile",
        note="Scoping to TOD accounts is a hypothetical simplification.",
    ),
    Requirement("joint", "death_certificate", False, LOSING_A_LOVED_ONE, _DEATH_CERT_EXCERPT),
)


def requirements_for(account_type: str) -> list[Requirement]:
    return [r for r in REQUIREMENTS if r.account_type == account_type]
