"""Packet specifications and the generator for hypothetical estate packets.

Every name, date, place and balance comes from Faker with a fixed seed. No real
person, account or record is used. Balances are hypothetical.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Optional

from faker import Faker
from rapidfuzz import fuzz

from hg.config import NAME_MATCH_THRESHOLD
from hg.data_gen.forms import FORM_FIELDS, RENDERERS
from hg.data_gen.truth import PacketTruth, PlantedError, RuleId
from hg.schemas import Account, Beneficiary, Decedent, Document, ExtractedField

SEED = 20261026

ACCOUNT_TITLES = {"traditional_ira": "Traditional IRA", "roth_ira": "Roth IRA"}

# Field that carries the decedent's date of death, and the person-name field
# that names heir 0, on each document type.
DOD_FIELD = {
    "death_certificate": "date_of_death",
    "inherited_ira_application": "decedent_date_of_death",
    "letters_testamentary": "date_of_death",
    "affidavit_of_domicile": "date_of_death",
    "trust_certification": "grantor_date_of_death",
}
HEIR_NAME_FIELD = {
    "letters_testamentary": "executor_name",
    "affidavit_of_domicile": "affiant_name",
    "trust_certification": "successor_trustee_name",
}


@dataclass(frozen=True)
class Heir:
    relationship: str
    share: str
    born: tuple[date, date]
    beneficiary_class: str


@dataclass(frozen=True)
class Plant:
    """One planted error. ``doc_type`` is the document that carries it (or is missing)."""

    rule_id: RuleId
    doc_type: Optional[str] = None
    heir: int = 0
    copy_kind: str = "photocopy"  # certified_copy only: "photocopy" or "uncertified"


@dataclass(frozen=True)
class PacketSpec:
    packet_id: str
    seed: int
    description: str
    decedent_born: tuple[date, date]
    died: tuple[date, date]
    rmds_started: Optional[bool]
    ira_type: str
    heirs: tuple[Heir, ...]
    trust_account: bool = False
    extra_docs: tuple[str, ...] = ()
    plants: tuple[Plant, ...] = ()


def _years(first: int, last: int) -> tuple[date, date]:
    return date(first, 1, 1), date(last, 12, 31)


# Applicable age 72 (born July 1, 1949 through 1950); RBD already passed by 2025.
_BORN_1949H2_1950 = (date(1949, 7, 1), date(1950, 12, 31))
_DIED_2025H1 = (date(2025, 1, 6), date(2025, 6, 30))
_ADULT_CHILD = _years(1972, 1984)


def _demo(packet_id: str, second_share: str, description: str, plants: tuple[Plant, ...]) -> PacketSpec:
    return PacketSpec(
        packet_id=packet_id,
        seed=1,
        description=description,
        decedent_born=_BORN_1949H2_1950,
        died=_DIED_2025H1,
        rmds_started=True,
        ira_type="traditional_ira",
        heirs=(
            Heir("child", "50", _ADULT_CHILD, "designated"),
            Heir("child", second_share, _ADULT_CHILD, "designated"),
        ),
        plants=plants,
    )


PACKETS: tuple[PacketSpec, ...] = (
    _demo(
        "packet_01_flawed",
        "49.5",
        "Demo case. An adult child and their sibling inherit a traditional IRA from a parent "
        "who had started RMDs. The applications list shares of 50% and 49.5%.",
        (Plant("shares_total_100"),),
    ),
    _demo(
        "packet_01_fixed",
        "50",
        "Demo case, corrected. Same family and documents; the second application now lists 50%.",
        (),
    ),
    PacketSpec(
        "packet_02", 2,
        "Two adult children inherit a traditional IRA. Their applications list 60% and 30%.",
        _years(1944, 1947), _DIED_2025H1, True, "traditional_ira",
        (Heir("child", "60", _ADULT_CHILD, "designated"), Heir("child", "30", _ADULT_CHILD, "designated")),
        plants=(Plant("shares_total_100"),),
    ),
    PacketSpec(
        "packet_03", 3,
        "Two adult children inherit a traditional IRA. The letters testamentary misspell the "
        "executor's (first heir's) name.",
        _years(1940, 1945), (date(2024, 2, 1), date(2024, 10, 31)), True, "traditional_ira",
        (Heir("child", "50", _ADULT_CHILD, "designated"), Heir("child", "50", _ADULT_CHILD, "designated")),
        extra_docs=("letters_testamentary",),
        plants=(Plant("name_match", "letters_testamentary"),),
    ),
    PacketSpec(
        "packet_04", 4,
        "One adult child inherits a Roth IRA. The application shows a date of death one day "
        "off from the death certificate.",
        _years(1952, 1955), _DIED_2025H1, None, "roth_ira",
        (Heir("child", "100", _ADULT_CHILD, "designated"),),
        plants=(Plant("dod_consistent", "inherited_ira_application", heir=0),),
    ),
    PacketSpec(
        "packet_05", 5,
        "Two adult children inherit a traditional IRA from a parent who died before RMDs began. "
        "The second child's application is missing.",
        _years(1960, 1962), (date(2024, 3, 1), date(2024, 11, 30)), False, "traditional_ira",
        (Heir("child", "50", _years(1985, 1995), "designated"), Heir("child", "50", _years(1985, 1995), "designated")),
        plants=(Plant("required_docs_present", "inherited_ira_application", heir=1),),
    ),
    PacketSpec(
        "packet_06", 6,
        "A sibling less than 10 years younger inherits a traditional IRA. The death certificate "
        "is a photocopy of a certified copy: the printed certification shows, but so does the "
        "security paper's VOID pattern.",
        _years(1946, 1946), _DIED_2025H1, True, "traditional_ira",
        (Heir("sibling", "100", _years(1950, 1951), "eligible_designated"),),
        plants=(Plant("certified_copy", "death_certificate"),),
    ),
    PacketSpec(
        "packet_07", 7,
        "An adult child and a grandchild inherit a traditional IRA. The affidavit of domicile "
        "misspells the child's name and the letters testamentary show a different date of death.",
        _years(1938, 1942), _DIED_2025H1, True, "traditional_ira",
        (Heir("child", "70", _years(1962, 1970), "designated"), Heir("grandchild", "30", _years(1990, 1998), "designated")),
        extra_docs=("letters_testamentary", "affidavit_of_domicile"),
        plants=(
            Plant("name_match", "affidavit_of_domicile"),
            Plant("dod_consistent", "letters_testamentary"),
        ),
    ),
    PacketSpec(
        "packet_08", 8,
        "A spouse inherits a traditional IRA and the decedent also held a trust-owned account. "
        "The trust certification is missing and the death certificate is an uncertified copy "
        "from the issuing office.",
        _years(1945, 1947), _DIED_2025H1, True, "traditional_ira",
        (Heir("spouse", "100", _years(1947, 1950), "spouse"),),
        trust_account=True,
        plants=(
            Plant("required_docs_present", "trust_certification"),
            Plant("certified_copy", "death_certificate", copy_kind="uncertified"),
        ),
    ),
    PacketSpec(
        "packet_09", 9,
        "Three adult children inherit a traditional IRA at 33.33% each (99.99% total). The third "
        "application shows a date of death one day off. RMD status is not stated.",
        (date(1947, 1, 1), date(1948, 12, 31)), _DIED_2025H1, None, "traditional_ira",
        tuple(Heir("child", "33.33", _ADULT_CHILD, "designated") for _ in range(3)),
        plants=(
            Plant("shares_total_100"),
            Plant("dod_consistent", "inherited_ira_application", heir=2),
        ),
    ),
    PacketSpec(
        "packet_10", 10,
        "Clean packet. Two adult children inherit a traditional IRA; the decedent also held a "
        "trust-owned account. Letters, affidavit and trust certification are all consistent.",
        _BORN_1949H2_1950, _DIED_2025H1, True, "traditional_ira",
        (Heir("child", "50", _ADULT_CHILD, "designated"), Heir("child", "50", _ADULT_CHILD, "designated")),
        trust_account=True,
        extra_docs=("letters_testamentary", "affidavit_of_domicile"),
    ),
)


# --- Helpers -----------------------------------------------------------------


def misspell(name: str) -> str:
    """Drop one interior letter of the first name, keeping the names fuzzy-similar.

    The result scores at or above NAME_MATCH_THRESHOLD (hypothetical) with
    RapidFuzz token_sort_ratio but is not an exact match, so the checker sees
    POSSIBLY_SAME_AS rather than a different person.
    """
    first, rest = name.split(" ", 1)
    for i in range(len(first) - 2, 0, -1):
        candidate = f"{first[:i]}{first[i + 1:]} {rest}"
        if fuzz.token_sort_ratio(candidate, name) >= NAME_MATCH_THRESHOLD:
            return candidate
    raise ValueError(f"cannot misspell {name!r} within the match threshold")


def _iso(d: date) -> str:
    return d.isoformat()


def _share_str(share: Decimal) -> str:
    return format(share.normalize(), "f")


@dataclass
class _Doc:
    doc_type: str
    doc_id: str
    filename: str
    values: dict[str, str]
    extra: dict


class _People:
    """Faker-backed name source that never repeats a first name within a packet."""

    def __init__(self, fake: Faker):
        self.fake = fake
        self.used: set[str] = set()

    def name(self, last: str) -> str:
        while True:
            first = self.fake.first_name()
            if first not in self.used and len(first) >= 4:
                self.used.add(first)
                return f"{first} {last}"

    def official(self) -> str:
        return f"{self.fake.first_name()} {self.fake.last_name()}"


# --- Build -------------------------------------------------------------------


def build_packet(spec: PacketSpec, out_dir: Path) -> PacketTruth:
    fake = Faker("en_US")
    fake.seed_instance(SEED + spec.seed)
    people = _People(fake)
    pid = spec.packet_id

    def days(lo: int, hi: int) -> timedelta:
        return timedelta(days=fake.random_int(lo, hi))

    def money() -> Decimal:
        return (Decimal(fake.random_int(15_000_000, 95_000_000)) / 100).quantize(Decimal("0.01"))

    family = fake.last_name()
    state = fake.state()
    city = fake.city()
    county = f"{fake.last_name()} County"

    dob = fake.date_between_dates(*spec.decedent_born)
    dod = fake.date_between_dates(*spec.died)
    decedent = Decedent(
        id=f"{pid}-d1",
        name=people.name(family),
        date_of_birth=dob,
        date_of_death=dod,
        rmds_started=spec.rmds_started,
    )

    ira = Account(
        id=f"{pid}-a1",
        type=spec.ira_type,
        title=f"{ACCOUNT_TITLES[spec.ira_type]} of {decedent.name}, deceased",
        balance=money(),
    )
    accounts = [ira]
    trust_name = f"The {family} Family Trust"
    trust_date = fake.date_between_dates(date(2004, 1, 1), date(2018, 12, 31))
    if spec.trust_account:
        accounts.append(
            Account(
                id=f"{pid}-a2",
                type="trust_owned",
                title=f"{trust_name}, dated {trust_date:%m/%d/%Y}",
                balance=money(),
            )
        )

    beneficiaries = [
        Beneficiary(
            id=f"{pid}-b{k}",
            name=people.name(family),
            date_of_birth=fake.date_between_dates(*heir.born),
            relationship=heir.relationship,
            share_percent=Decimal(heir.share),
            designation="primary",
            account_id=ira.id,
            beneficiary_class=heir.beneficiary_class,
        )
        for k, heir in enumerate(spec.heirs, 1)
    ]
    lead = beneficiaries[0]

    docs: list[_Doc] = [
        _Doc(
            "death_certificate",
            f"{pid}-death_certificate",
            "death_certificate.pdf",
            {
                "decedent_name": decedent.name,
                "date_of_birth": _iso(dob),
                "date_of_death": _iso(dod),
                "place_of_death": city,
                "issuing_county": county,
                "issuing_state": state,
                "certificate_number": fake.numerify(f"{dod.year}-###-######"),
                "date_issued": _iso(dod + days(5, 30)),
                "certified_copy": "yes",
            },
            {"registrar": people.official()},
        )
    ]
    for k, b in enumerate(beneficiaries, 1):
        docs.append(
            _Doc(
                "inherited_ira_application",
                f"{pid}-inherited_ira_application-b{k}",
                f"inherited_ira_application_b{k}.pdf",
                {
                    "decedent_name": decedent.name,
                    "decedent_date_of_death": _iso(dod),
                    "account_type": ira.type,
                    "account_title": ira.title,
                    "beneficiary_name": b.name,
                    "beneficiary_date_of_birth": _iso(b.date_of_birth),
                    "relationship": b.relationship,
                    "designation": b.designation,
                    "share_percent": _share_str(b.share_percent),
                    "signature_name": b.name,
                    "signature_date": _iso(dod + days(45, 120)),
                },
                {},
            )
        )
    if "letters_testamentary" in spec.extra_docs:
        docs.append(
            _Doc(
                "letters_testamentary",
                f"{pid}-letters_testamentary",
                "letters_testamentary.pdf",
                {
                    "decedent_name": decedent.name,
                    "date_of_death": _iso(dod),
                    "case_number": fake.numerify(f"PR-{dod.year}-#####"),
                    "court_name": f"Probate Court of {county}",
                    "court_county": county,
                    "date_issued": _iso(dod + days(20, 75)),
                    "executor_name": lead.name,
                },
                {"clerk": people.official()},
            )
        )
    if "affidavit_of_domicile" in spec.extra_docs:
        has_letters = "letters_testamentary" in spec.extra_docs
        docs.append(
            _Doc(
                "affidavit_of_domicile",
                f"{pid}-affidavit_of_domicile",
                "affidavit_of_domicile.pdf",
                {
                    "decedent_name": decedent.name,
                    "date_of_death": _iso(dod),
                    "affiant_capacity": "executor" if has_letters else "beneficiary",
                    "domicile_address": f"{fake.street_address()}, {city}, {state}",
                    "affiant_name": lead.name,
                    "notary_date": _iso(dod + days(80, 110)),
                },
                {
                    "notary": people.official(),
                    "commission_expires": (dod + timedelta(days=3 * 365)).strftime("%m/%d/%Y"),
                },
            )
        )
    if spec.trust_account:
        docs.append(
            _Doc(
                "trust_certification",
                f"{pid}-trust_certification",
                "trust_certification.pdf",
                {
                    "trust_name": trust_name,
                    "trust_date": _iso(trust_date),
                    "grantor_date_of_death": _iso(dod),
                    "grantor_name": decedent.name,
                    "successor_trustee_name": lead.name,
                    "certification_date": _iso(dod + days(20, 60)),
                },
                {},
            )
        )

    details = [_plant(p, spec, docs, beneficiaries, dod) for p in spec.plants]
    docs = [d for d in docs if not d.extra.get("omitted")]

    out_dir.mkdir(parents=True, exist_ok=True)
    documents = []
    for d in docs:
        RENDERERS[d.doc_type](out_dir / d.filename, d.values, d.extra)
        documents.append(
            Document(
                id=d.doc_id,
                case_id=pid,
                file_ref=f"{pid}/{d.filename}",
                doc_type=d.doc_type,
                fields=[
                    ExtractedField(name=s.name, value=d.values[s.name], confidence=1.0, page=s.page)
                    for s in FORM_FIELDS[d.doc_type]
                ],
            )
        )

    planted: list[RuleId] = []
    for p in spec.plants:
        if p.rule_id not in planted:
            planted.append(p.rule_id)

    return PacketTruth(
        packet_id=pid,
        description=spec.description,
        decedent=decedent,
        accounts=accounts,
        beneficiaries=beneficiaries,
        documents=documents,
        planted_errors=planted,
        planted_error_details=details,
    )


def _plant(
    plant: Plant,
    spec: PacketSpec,
    docs: list[_Doc],
    beneficiaries: list[Beneficiary],
    dod: date,
) -> PlantedError:
    heir = beneficiaries[plant.heir]

    def target() -> _Doc:
        if plant.doc_type == "inherited_ira_application":
            return next(d for d in docs if d.doc_id.endswith(f"-b{plant.heir + 1}") and d.doc_type == plant.doc_type)
        return next(d for d in docs if d.doc_type == plant.doc_type)

    if plant.rule_id == "shares_total_100":
        total = sum((b.share_percent for b in beneficiaries), Decimal(0))
        assert total != 100, f"{spec.packet_id}: shares_total_100 planted but shares total 100"
        return PlantedError(rule_id=plant.rule_id, note=f"Primary shares total {_share_str(total)}%, not 100%.")

    doc = target()
    if plant.rule_id == "name_match":
        field = HEIR_NAME_FIELD[doc.doc_type]
        assert plant.heir == 0, "only the lead heir is named on other documents"
        doc.values[field] = misspell(heir.name)
        return PlantedError(
            rule_id=plant.rule_id,
            note=f"{doc.doc_type}.{field} reads {doc.values[field]!r}; the application reads {heir.name!r}.",
            document_id=doc.doc_id,
            beneficiary_id=heir.id,
        )
    if plant.rule_id == "dod_consistent":
        field = DOD_FIELD[doc.doc_type]
        doc.values[field] = _iso(dod + timedelta(days=1))
        return PlantedError(
            rule_id=plant.rule_id,
            note=f"{doc.doc_type}.{field} reads {doc.values[field]}; the death certificate reads {_iso(dod)}.",
            document_id=doc.doc_id,
            beneficiary_id=heir.id if doc.doc_type == "inherited_ira_application" else None,
        )
    if plant.rule_id == "required_docs_present":
        doc.extra["omitted"] = True
        is_app = doc.doc_type == "inherited_ira_application"
        return PlantedError(
            rule_id=plant.rule_id,
            note=f"Required {doc.doc_type} is missing for {heir.name}." if is_app
            else f"{doc.doc_type} is missing for the trust-owned account. No Schwab source establishes "
            "that it is required, so the checker asks for review.",
            beneficiary_id=heir.id if is_app else None,
        )
    if plant.rule_id == "certified_copy":
        doc.values["certified_copy"] = "no"
        doc.extra["copy_kind"] = plant.copy_kind
        note = {
            "photocopy": "Death certificate is a photocopy of a certified copy: the printed certification "
            "is there, but the security paper's VOID pattern shows through.",
            "uncertified": "Death certificate is the issuing office's uncertified copy, marked as "
            "informational and not valid for legal purposes, with no registrar certification.",
        }[plant.copy_kind]
        return PlantedError(
            rule_id=plant.rule_id,
            note=note,
            document_id=doc.doc_id,
        )
    raise ValueError(f"unknown rule {plant.rule_id}")


def generate_all(out: Path) -> list[PacketTruth]:
    """Write every packet (PDFs + truth.json) under ``out`` and an index.json."""
    out.mkdir(parents=True, exist_ok=True)
    truths = []
    for spec in PACKETS:
        packet_dir = out / spec.packet_id
        if packet_dir.exists():
            shutil.rmtree(packet_dir)
        truth = build_packet(spec, packet_dir)
        (packet_dir / "truth.json").write_text(truth.model_dump_json(indent=2) + "\n", encoding="utf-8")
        truths.append(truth)
    index = [
        {"packet_id": t.packet_id, "description": t.description, "planted_errors": t.planted_errors}
        for t in truths
    ]
    (out / "index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    return truths


def load_truth(packet_dir: Path) -> PacketTruth:
    return PacketTruth.model_validate_json((packet_dir / "truth.json").read_text(encoding="utf-8"))
