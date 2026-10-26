"""Specimen form layouts and the field vocabulary each form carries.

The field names here are the vocabulary M2 (``hg.reader.vocab``) must use, and
truth.json records every one of them for every generated document.

Truth values are normalized, which is also what the reader should return:

* ``date``: ISO ``YYYY-MM-DD`` (printed as MM/DD/YYYY)
* ``percent``: plain number, no ``%`` (printed as ``49.5%``)
* ``choice``: lowercase (printed title-cased, e.g. ``Child``)
* ``account_type``: ``hg.schemas.AccountType`` value (printed as ``Traditional IRA``)
* ``yes_no``: ``yes`` or ``no``. Not printed as a field: ``certified_copy`` is
  ``yes`` when the registrar's certification and seal are present and ``no``
  when a copy marker is present or the seal text is missing.

Layouts are plausible but generic. They do not copy any real state's,
court's or custodian's form.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, Literal

from hg.data_gen.pdf import FormCanvas

FieldKind = Literal["text", "date", "percent", "choice", "account_type", "yes_no"]


@dataclass(frozen=True)
class FieldSpec:
    name: str
    label: str
    kind: FieldKind = "text"
    page: int = 1
    wide: bool = False

    @property
    def printed(self) -> bool:
        return self.kind != "yes_no"


FORM_FIELDS: dict[str, tuple[FieldSpec, ...]] = {
    "death_certificate": (
        FieldSpec("decedent_name", "Name of decedent", wide=True),
        FieldSpec("date_of_birth", "Date of birth", "date"),
        FieldSpec("date_of_death", "Date of death", "date"),
        FieldSpec("place_of_death", "Place of death (city)"),
        FieldSpec("issuing_county", "County of registration"),
        FieldSpec("issuing_state", "State"),
        FieldSpec("certificate_number", "Certificate number"),
        FieldSpec("date_issued", "Date issued", "date"),
        FieldSpec("certified_copy", "Certified copy", "yes_no"),
    ),
    "inherited_ira_application": (
        FieldSpec("decedent_name", "Name of deceased account owner", wide=True),
        FieldSpec("decedent_date_of_death", "Date of death", "date"),
        FieldSpec("account_type", "Type of account inherited", "account_type"),
        FieldSpec("account_title", "Account title", wide=True),
        FieldSpec("beneficiary_name", "Beneficiary full name", wide=True),
        FieldSpec("beneficiary_date_of_birth", "Beneficiary date of birth", "date"),
        FieldSpec("relationship", "Relationship to deceased", "choice"),
        FieldSpec("designation", "Beneficiary designation", "choice"),
        FieldSpec("share_percent", "Share of account (%)", "percent"),
        FieldSpec("signature_name", "Printed name of signer", page=2, wide=True),
        FieldSpec("signature_date", "Date signed", "date", page=2),
    ),
    "letters_testamentary": (
        FieldSpec("decedent_name", "Estate of (decedent)", wide=True),
        FieldSpec("date_of_death", "Date of death", "date"),
        FieldSpec("case_number", "Cause number"),
        FieldSpec("court_name", "Court", wide=True),
        FieldSpec("court_county", "County"),
        FieldSpec("date_issued", "Date issued", "date"),
        FieldSpec("executor_name", "Executor appointed", wide=True),
    ),
    "affidavit_of_domicile": (
        FieldSpec("decedent_name", "Name of decedent", wide=True),
        FieldSpec("date_of_death", "Date of death", "date"),
        FieldSpec("affiant_capacity", "Capacity of affiant", "choice"),
        FieldSpec("domicile_address", "Domicile at time of death", wide=True),
        FieldSpec("affiant_name", "Name of affiant", wide=True),
        FieldSpec("notary_date", "Sworn and subscribed on", "date"),
    ),
    "trust_certification": (
        FieldSpec("trust_name", "Name of trust", wide=True),
        FieldSpec("trust_date", "Date trust established", "date"),
        FieldSpec("grantor_date_of_death", "Grantor date of death", "date"),
        FieldSpec("grantor_name", "Grantor", wide=True),
        FieldSpec("successor_trustee_name", "Successor trustee", wide=True),
        FieldSpec("certification_date", "Date of certification", "date"),
    ),
}

FORM_PAGES = {
    "death_certificate": 1,
    "inherited_ira_application": 2,
    "letters_testamentary": 1,
    "affidavit_of_domicile": 1,
    "trust_certification": 1,
}

ACCOUNT_TYPE_LABELS = {
    "traditional_ira": "Traditional IRA",
    "roth_ira": "Roth IRA",
    "tod_brokerage": "TOD Brokerage",
    "joint": "Joint",
    "individual": "Individual",
    "trust_owned": "Trust-Owned",
}

COPY_MARKER = "COPY - NOT CERTIFIED"


def display(spec: FieldSpec, value: str) -> str:
    if spec.kind == "date":
        return date.fromisoformat(value).strftime("%m/%d/%Y")
    if spec.kind == "percent":
        return f"{value}%"
    if spec.kind == "choice":
        return value.replace("_", " ").title()
    if spec.kind == "account_type":
        return ACCOUNT_TYPE_LABELS[value]
    return value


def field_spec(doc_type: str, name: str) -> FieldSpec:
    return next(s for s in FORM_FIELDS[doc_type] if s.name == name)


def _items(
    doc_type: str, values: dict[str, str], page: int, names: tuple[str, ...] | None = None
) -> list[tuple[str, str, bool]]:
    return [
        (spec.label, display(spec, values[spec.name]), spec.wide)
        for spec in FORM_FIELDS[doc_type]
        if spec.printed and spec.page == page and (names is None or spec.name in names)
    ]


def _show(doc_type: str, name: str, values: dict[str, str]) -> str:
    return display(field_spec(doc_type, name), values[name])


def _fmt(value: str) -> str:
    return date.fromisoformat(value).strftime("%B %d, %Y").replace(" 0", " ")


# --- Renderers ---------------------------------------------------------------
# Each takes the normalized field values plus layout-only extras.


def render_death_certificate(path: Path, v: dict[str, str], extra: dict) -> None:
    doc = "death_certificate"
    f = FormCanvas(path, "Form VR-DC (specimen)", FORM_PAGES[doc], "Certificate of Death")
    f.header("Certificate of Death", f"Office of Vital Records, State of {v['issuing_state']} (hypothetical)")
    f.paragraph(
        "This certificate records the facts of death as reported to the local registrar. "
        "Alterations or erasures void this certificate."
    )
    f.section("Decedent")
    f.fields(_items(doc, v, 1))
    f.section("Certification")
    if v["certified_copy"] == "yes":
        f.seal(
            [
                "CERTIFIED COPY OF VITAL RECORD",
                "I certify that this is a true and correct copy of the official record",
                f"registered in {v['issuing_county']}, {v['issuing_state']}.",
                f"Local Registrar: {extra['registrar']}",
                "Valid only with the raised seal of the registrar.",
            ]
        )
    else:
        f.paragraph("This reproduction was made from a document provided by the requester.")
        f.stamp(COPY_MARKER)
    f.end_page()
    f.save()


def render_inherited_ira_application(path: Path, v: dict[str, str], extra: dict) -> None:
    doc = "inherited_ira_application"
    f = FormCanvas(path, "Form HG-IRA-1 (specimen)", FORM_PAGES[doc], "Inherited IRA Application")
    f.header("Inherited IRA Application", "Hypothetical Custodian, Inc.")
    f.paragraph(
        "Use this application to open an inherited IRA for one beneficiary of a deceased "
        "IRA owner. Each beneficiary completes a separate application."
    )
    owner = ("decedent_name", "decedent_date_of_death", "account_type", "account_title")
    beneficiary = ("beneficiary_name", "beneficiary_date_of_birth", "relationship", "designation", "share_percent")
    f.section("1. Deceased account owner")
    f.fields(_items(doc, v, 1, owner))
    f.section("2. Beneficiary information")
    f.fields(_items(doc, v, 1, beneficiary))
    f.paragraph(
        "Social Security number: entered by the beneficiary at signing. "
        "Not collected on this specimen form.",
        size=8.5,
    )
    f.end_page()

    f.section("3. Signature and certification")
    f.paragraph(
        "I certify that I am the beneficiary named above, that the information on this "
        "application is true and complete, and that I have received the account agreement. "
        "I understand that distributions from an inherited IRA may be taxable."
    )
    f.fields(_items(doc, v, 2))
    f.signature(
        "Signature of beneficiary",
        v["signature_name"],
        field_spec(doc, "signature_date").label,
        _show(doc, "signature_date", v),
    )
    f.end_page()
    f.save()


def render_letters_testamentary(path: Path, v: dict[str, str], extra: dict) -> None:
    doc = "letters_testamentary"
    f = FormCanvas(path, "Probate form LT-1 (specimen)", FORM_PAGES[doc], "Letters Testamentary")
    f.header("Letters Testamentary", f"{v['court_name']} (hypothetical)")
    f.fields(_items(doc, v, 1))
    f.paragraph(
        f"The last will and testament of {v['decedent_name']}, deceased, having been admitted "
        f"to probate, the Court grants these Letters Testamentary to {v['executor_name']}, who "
        "has qualified and is authorized to act as executor of the estate."
    )
    f.signature("Clerk of the court", extra["clerk"], "Date", _show(doc, "date_issued", v))
    f.end_page()
    f.save()


def render_affidavit_of_domicile(path: Path, v: dict[str, str], extra: dict) -> None:
    doc = "affidavit_of_domicile"
    f = FormCanvas(path, "Form AD-1 (specimen)", FORM_PAGES[doc], "Affidavit of Domicile")
    f.header("Affidavit of Domicile", "Sworn statement for transfer of assets")
    f.fields(_items(doc, v, 1))
    f.paragraph(
        f"I, {v['affiant_name']}, being duly sworn, state that I am the "
        f"{v['affiant_capacity']} of the estate of {v['decedent_name']}, who died on "
        f"{_fmt(v['date_of_death'])}, and that at the time of death the decedent was "
        f"domiciled at {v['domicile_address']}."
    )
    f.signature("Signature of affiant", v["affiant_name"], "Date", _show(doc, "notary_date", v))
    f.signature("Notary public (hypothetical)", extra["notary"], "Commission expires", extra["commission_expires"])
    f.end_page()
    f.save()


def render_trust_certification(path: Path, v: dict[str, str], extra: dict) -> None:
    doc = "trust_certification"
    f = FormCanvas(path, "Form TC-1 (specimen)", FORM_PAGES[doc], "Certification of Trust")
    f.header("Certification of Trust", "Trustee certification for financial institutions")
    f.fields(_items(doc, v, 1))
    f.paragraph(
        f"The undersigned certifies that {v['trust_name']} exists, has not been revoked, "
        f"modified or amended in any way that would make these statements incorrect, and that "
        f"upon the death of the grantor, {v['grantor_name']}, the undersigned became the "
        "successor trustee with authority to act for the trust."
    )
    f.signature(
        "Signature of successor trustee",
        v["successor_trustee_name"],
        "Date",
        _show(doc, "certification_date", v),
    )
    f.end_page()
    f.save()


RENDERERS: dict[str, Callable[[Path, dict[str, str], dict], None]] = {
    "death_certificate": render_death_certificate,
    "inherited_ira_application": render_inherited_ira_application,
    "letters_testamentary": render_letters_testamentary,
    "affidavit_of_domicile": render_affidavit_of_domicile,
    "trust_certification": render_trust_certification,
}
