"""M1 synthetic packet tests. No LLM, no network."""

import re
import sys
from decimal import Decimal

import pytest
from rapidfuzz import fuzz

from hg.config import NAME_MATCH_THRESHOLD
from hg.data_gen import PACKETS, PacketTruth, generate_all, load_truth
from hg.data_gen.__main__ import main
from hg.data_gen.forms import FORM_FIELDS, FORM_PAGES
from hg.data_gen.packets import DOD_FIELD, HEIR_NAME_FIELD, build_packet, misspell
from hg.data_gen.pdf import VOID_TEXT, WATERMARK
from hg.data_gen.truth import RuleId
from hg.schemas import Account, Beneficiary, Decedent, Document

ALL_RULES = set(RuleId.__args__)
PAGE_RE = re.compile(rb"/Type /Page(?!s)")
SSN_RE = re.compile(r"(?<!\d)(\d{3}-\d{2}-\d{4}|\d{9})(?!\d)")
PACKETS_BY_ID = {spec.packet_id: spec for spec in PACKETS}


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    out = tmp_path_factory.mktemp("packets")
    generate_all(out)
    return out


@pytest.fixture(scope="module")
def truths(generated) -> dict[str, PacketTruth]:
    return {spec.packet_id: load_truth(generated / spec.packet_id) for spec in PACKETS}


def _observed_errors(truth: PacketTruth) -> set[str]:
    """Re-derive each rule's outcome from the truth documents alone."""
    docs = truth.documents
    found = set()

    for account in truth.accounts:
        primary = [b for b in truth.beneficiaries if b.account_id == account.id and b.designation == "primary"]
        if primary and sum((b.share_percent for b in primary), Decimal(0)) != 100:
            found.add("shares_total_100")

    beneficiary_names = {b.name for b in truth.beneficiaries}
    for d in docs:
        field = HEIR_NAME_FIELD.get(d.doc_type)
        if field:
            value = next(f.value for f in d.fields if f.name == field)
            if value not in beneficiary_names:
                found.add("name_match")

    dods = {f.value for d in docs for f in d.fields if f.name == DOD_FIELD[d.doc_type]}
    if len(dods) > 1:
        found.add("dod_consistent")

    have = [d.doc_type for d in docs]
    apps = {f.value for d in docs if d.doc_type == "inherited_ira_application"
            for f in d.fields if f.name == "beneficiary_name"}
    if (
        "death_certificate" not in have
        or any(b.name not in apps for b in truth.beneficiaries)
        or (any(a.type == "trust_owned" for a in truth.accounts) and "trust_certification" not in have)
    ):
        found.add("required_docs_present")

    certificate = next((d for d in docs if d.doc_type == "death_certificate"), None)
    if certificate and next(f.value for f in certificate.fields if f.name == "certified_copy") == "no":
        found.add("certified_copy")
    return found


def test_all_packets_generate(generated):
    expected = {"packet_01_flawed", "packet_01_fixed"} | {f"packet_{n:02d}" for n in range(2, 11)}
    assert {p.name for p in generated.iterdir() if p.is_dir()} == expected
    assert (generated / "index.json").exists()


def test_truth_validates_against_schemas(truths):
    for truth in truths.values():
        Decedent.model_validate(truth.decedent.model_dump())
        for model, items in [(Account, truth.accounts), (Beneficiary, truth.beneficiaries), (Document, truth.documents)]:
            for item in items:
                model.model_validate(item.model_dump())
        assert truth.case_state().case_id == truth.packet_id


def test_planted_errors_present_exactly_where_expected(truths):
    for n in range(2, 10):
        assert truths[f"packet_{n:02d}"].planted_errors, f"packet_{n:02d} has no planted error"
    assert truths["packet_10"].planted_errors == []
    assert truths["packet_01_fixed"].planted_errors == []
    assert truths["packet_01_flawed"].planted_errors == ["shares_total_100"]

    covered = {r for n in range(2, 10) for r in truths[f"packet_{n:02d}"].planted_errors}
    assert covered == ALL_RULES


@pytest.mark.parametrize("packet_id", [spec.packet_id for spec in PACKETS])
def test_documents_show_exactly_the_planted_errors(truths, packet_id):
    truth = truths[packet_id]
    assert _observed_errors(truth) == set(truth.planted_errors)
    assert len(truth.planted_error_details) == len(PACKETS_BY_ID[packet_id].plants)



def test_demo_versions_differ_only_in_the_second_share(truths):
    flawed = truths["packet_01_flawed"].model_dump(mode="json", exclude={"description", "planted_errors", "planted_error_details"})
    fixed = truths["packet_01_fixed"].model_dump(mode="json", exclude={"description", "planted_errors", "planted_error_details"})

    flawed_text = str(flawed).replace("packet_01_flawed", "P")
    fixed_text = str(fixed).replace("packet_01_fixed", "P")
    assert flawed_text != fixed_text
    assert flawed_text.replace("'49.5'", "'50'") == fixed_text

    demo = truths["packet_01_flawed"]
    assert [b.relationship for b in demo.beneficiaries] == ["child", "child"]
    assert demo.accounts[0].type == "traditional_ira"
    assert demo.decedent.rmds_started is True


def test_every_document_has_its_full_field_vocabulary(truths, generated):
    for truth in truths.values():
        for doc in truth.documents:
            names = [f.name for f in doc.fields]
            assert names == [s.name for s in FORM_FIELDS[doc.doc_type]]
            assert all(f.value for f in doc.fields)
            assert all(1 <= f.page <= FORM_PAGES[doc.doc_type] for f in doc.fields)
            assert (generated / doc.file_ref).is_file()


def test_every_pdf_page_carries_the_watermark(truths, generated):
    for truth in truths.values():
        for doc in truth.documents:
            pdf = (generated / doc.file_ref).read_bytes()
            pages = len(PAGE_RE.findall(pdf))
            assert pages == FORM_PAGES[doc.doc_type]
            assert pdf.count(WATERMARK.encode()) == pages


def test_copies_show_only_realistic_signs(truths, generated):
    """No rubber stamp: a photocopy shows the VOID pattern, an uncertified copy its printed notice."""
    kinds = {}
    for truth in truths.values():
        cert = next(d for d in truth.documents if d.doc_type == "death_certificate")
        pdf = (generated / cert.file_ref).read_bytes()
        has_void = f"({VOID_TEXT})".encode() in pdf
        has_notice = b"UNCERTIFIED COPY" in pdf
        has_certification = b"CERTIFIED COPY OF VITAL RECORD" in pdf
        assert b"COPY - NOT CERTIFIED" not in pdf
        if "certified_copy" not in truth.planted_errors:
            assert has_certification and not has_void and not has_notice
            continue
        kind = "photocopy" if has_void else "uncertified" if has_notice else None
        kinds[truth.packet_id] = kind
        assert has_certification is (kind == "photocopy")
    assert kinds == {"packet_06": "photocopy", "packet_08": "uncertified"}


def test_misspelled_names_are_fuzzy_matches_not_exact(truths):
    for truth in truths.values():
        if "name_match" not in truth.planted_errors:
            continue
        names = {b.name for b in truth.beneficiaries}
        for doc in truth.documents:
            field = HEIR_NAME_FIELD.get(doc.doc_type)
            value = field and next(f.value for f in doc.fields if f.name == field)
            if value and value not in names:
                best = max(fuzz.token_sort_ratio(value, n) for n in names)
                assert NAME_MATCH_THRESHOLD <= best < 100


def test_misspell_keeps_names_close():
    for name in ["Katherine Miller", "Amy Fox", "Jordan Lee", "Christopher Fitzgerald"]:
        wrong = misspell(name)
        assert wrong != name
        assert fuzz.token_sort_ratio(wrong, name) >= NAME_MATCH_THRESHOLD


def test_expected_beneficiary_classes_follow_the_age_rule(truths):
    for truth in truths.values():
        for b in truth.beneficiaries:
            gap = (b.date_of_birth - truth.decedent.date_of_birth).days / 365.25
            if b.relationship == "spouse":
                assert b.beneficiary_class == "spouse"
            elif b.beneficiary_class == "eligible_designated":
                assert gap <= 10
            else:
                assert b.beneficiary_class == "designated" and gap > 10


def test_no_ssn_like_numbers_anywhere(truths, generated):
    for truth in truths.values():
        assert not SSN_RE.search(truth.model_dump_json())
        for doc in truth.documents:
            assert not SSN_RE.search((generated / doc.file_ref).read_bytes().decode("latin-1"))


def test_generation_is_deterministic(tmp_path):
    spec = PACKETS_BY_ID["packet_07"]
    a = build_packet(spec, tmp_path / "a")
    b = build_packet(spec, tmp_path / "b")
    assert a == b
    for name in (tmp_path / "a").iterdir():
        assert name.read_bytes() == (tmp_path / "b" / name.name).read_bytes()


def test_cli_writes_packets(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["hg.data_gen", "--out", str(tmp_path)])
    main()
    assert (tmp_path / "packet_10" / "truth.json").exists()
    assert "packet_01_flawed: 3 documents, planted errors: shares_total_100" in capsys.readouterr().out
