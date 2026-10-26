"""M7 prefill tests. Cases come from M1 truth files (no LLM).

The first group needs no database (checks are given, the graph write is off).
The Neo4j group runs the real checks and verifies the SOURCED_FROM edges.
"""

import pytest

from hg import store
from hg.checker import run_checks
from hg.config import get_settings
from hg.data_gen import load_truth
from hg.graph import build_case_graph, delete_case_graph
from hg.prefill import HEIR_ENTERED, PROPOSAL_LABEL, build_handoff, build_prefill
from hg.prefill.build import HEIR_FIELDS, RMD_DEPOSIT_FIELD, SOURCES
from hg.schemas import CheckResult, Evidence

PACKET_DIR = get_settings().data_dir / "packets"
ALL_PASS = [CheckResult(rule_id="field_review", status="pass", message="ok")]


def _case(packet_id: str, checks=ALL_PASS):
    case = load_truth(PACKET_DIR / packet_id).case_state()
    return case.model_copy(update={"case_id": f"prefill-{packet_id}", "checks": checks})


def _by_name(fields):
    return {f.name: f for f in fields}


def _doc_value(case, document_id, field):
    doc = next(d for d in case.documents if d.id == document_id)
    return next(f.value for f in doc.fields if f.name == field)


# --- No database needed ----------------------------------------------------------------


def test_every_value_comes_from_its_own_document_field():
    case = _case("packet_10")
    for b in case.beneficiaries:
        handoff = build_handoff(case, b.id, False, write_graph=False)
        fields = _by_name(handoff.fields)
        assert handoff.label == PROPOSAL_LABEL and handoff.excluded == []
        for name in SOURCES:
            f = fields[name]
            assert f.source_document_id and f.source_field
            assert f.value == _doc_value(case, f.source_document_id, f.source_field)
        assert fields["beneficiary_name"].value == b.name
        assert fields["decedent_date_of_death"].source_document_id.endswith("death_certificate")
        app = fields["share_percent"].source_document_id
        assert "inherited_ira_application" in app and _doc_value(case, app, "beneficiary_name") == b.name


def test_ssn_and_account_numbers_are_never_filled():
    case = _case("packet_10")
    handoff = build_handoff(case, case.beneficiaries[0].id, False, write_graph=False)
    fields = _by_name(handoff.fields)
    for name in HEIR_FIELDS:
        assert fields[name].value is None and fields[name].source_document_id is None
        assert handoff.heir_entered[name] == HEIR_ENTERED
    assert not any("ssn" in f.name or "account_number" in f.name for f in handoff.fields if f.value)


def test_rmd_deposit_is_opt_in():
    case = _case("packet_10")
    bid = case.beneficiaries[0].id
    assert _by_name(build_handoff(case, bid, False, write_graph=False).fields)[RMD_DEPOSIT_FIELD].value == "no"
    assert _by_name(build_handoff(case, bid, True, write_graph=False).fields)[RMD_DEPOSIT_FIELD].value == "yes"


def test_low_confidence_field_is_excluded():
    case = _case("packet_10")
    bid = case.beneficiaries[0].id
    app_id = next(f.source_document_id for f in build_handoff(case, bid, False, write_graph=False).fields
                  if f.name == "relationship")
    docs = []
    for d in case.documents:
        if d.id == app_id:
            d = d.model_copy(update={"fields": [
                f.model_copy(update={"confidence": 0.4}) if f.name == "relationship" else f for f in d.fields
            ]})
        docs.append(d)
    handoff = build_handoff(case.model_copy(update={"documents": docs}), bid, False, write_graph=False)
    assert "relationship" not in _by_name(handoff.fields)
    assert [(e.name, "low confidence" in e.reason) for e in handoff.excluded] == [("relationship", True)]


def test_field_cited_by_an_open_check_falls_back_or_is_excluded():
    case = _case("packet_10")
    bid = case.beneficiaries[0].id
    cert = next(d for d in case.documents if d.doc_type == "death_certificate")
    checks = [CheckResult(rule_id="dod_consistent", status="fail", message="x", beneficiary_id=bid,
                          evidence=[Evidence(document_id=cert.id, field_name="date_of_death")])]
    handoff = build_handoff(case.model_copy(update={"checks": checks}), bid, False, write_graph=False)
    # The certificate's date is in doubt, so the application's own date is used instead.
    dod = _by_name(handoff.fields)["decedent_date_of_death"]
    assert dod.source_field == "decedent_date_of_death" and "inherited_ira_application" in dod.source_document_id

    whole_doc = [CheckResult(rule_id="field_review", status="needs_review", message="x",
                             evidence=[Evidence(document_id=cert.id, field_name="")])]
    handoff = build_handoff(case.model_copy(update={"checks": whole_doc}), bid, False, write_graph=False)
    assert all(f.source_document_id != cert.id for f in handoff.fields)


def test_presence_check_evidence_does_not_exclude_fields():
    case = _case("packet_10")
    bid = case.beneficiaries[0].id
    present = [CheckResult(rule_id="required_docs_present", status="needs_review", message="x",
                           evidence=[Evidence(document_id=d.id, field_name="") for d in case.documents])]
    assert build_handoff(case.model_copy(update={"checks": present}), bid, False, write_graph=False).excluded == []


def test_requires_checks_and_a_known_beneficiary():
    case = _case("packet_10", checks=[])
    with pytest.raises(ValueError, match="checks"):
        build_handoff(case, case.beneficiaries[0].id, False, write_graph=False)
    with pytest.raises(ValueError, match="unknown beneficiary"):
        build_handoff(_case("packet_10"), "nobody", False, write_graph=False)


# --- Neo4j ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def neo4j():
    store.get_driver.cache_clear()
    try:
        store.get_driver().verify_connectivity()
    except Exception as exc:
        pytest.skip(f"Neo4j not reachable: {exc}")
    yield
    for pid in ("packet_04", "packet_09", "packet_10"):
        delete_case_graph(f"prefill-{pid}")
    store.close_driver()


def _checked(packet_id: str):
    case = _case(packet_id, checks=[])
    build_case_graph(case)
    return case.model_copy(update={"checks": run_checks(case)})


def _edges(case_id: str, beneficiary_id: str):
    return store.run(
        "MATCH (p:PrefillField {case_id: $cid, beneficiary_id: $bid})-[:SOURCED_FROM]->(f:Fact) "
        "RETURN p.name AS name, p.value AS value, f.id AS fact, f.value AS fact_value ORDER BY name",
        cid=case_id, bid=beneficiary_id,
    )


@pytest.mark.neo4j
def test_every_prefilled_value_traces_to_a_document_fact(neo4j):
    case = _checked("packet_10")
    for b in case.beneficiaries:
        fields = build_prefill(case, b.id, True)
        sourced = [f for f in fields if f.source_document_id]
        edges = _edges(case.case_id, b.id)
        assert len(edges) == len(sourced) == len(SOURCES)
        for f, e in zip(sorted(sourced, key=lambda f: f.name), edges):
            assert e["fact"] == f"{f.source_document_id}/{f.source_field}"
            assert e["value"] == e["fact_value"] == f.value
        heir = store.run(
            "MATCH (p:PrefillField {case_id: $cid, beneficiary_id: $bid}) WHERE NOT (p)-[:SOURCED_FROM]->() "
            "RETURN p.name AS name ORDER BY name", cid=case.case_id, bid=b.id,
        )
        assert [r["name"] for r in heir] == sorted([*HEIR_FIELDS, RMD_DEPOSIT_FIELD])


@pytest.mark.neo4j
def test_failed_check_fields_are_excluded(neo4j):
    case = _checked("packet_09")  # shares total 99.99%; b3's application has the wrong date of death
    for b in case.beneficiaries:
        handoff = build_handoff(case, b.id, False)
        fields = _by_name(handoff.fields)
        excluded = {e.name: e.reason for e in handoff.excluded}
        assert "share_percent" not in fields and "shares_total_100" in excluded["share_percent"]
        assert {e["name"] for e in _edges(case.case_id, b.id)} == {
            f.name for f in handoff.fields if f.source_document_id
        }
        if b.id.endswith("b3"):
            # Both dates are cited by the failed check, so neither is used.
            assert "decedent_date_of_death" not in fields and "dod_consistent" in excluded["decedent_date_of_death"]
        else:
            assert fields["decedent_date_of_death"].value == case.decedent.date_of_death.isoformat()


@pytest.mark.neo4j
def test_prefill_rebuild_replaces_nodes(neo4j):
    case = _checked("packet_04")
    bid = case.beneficiaries[0].id
    build_prefill(case, bid, False)
    build_prefill(case, bid, True)
    rows = store.run("MATCH (p:PrefillField {case_id: $cid, beneficiary_id: $bid}) RETURN count(p) AS n",
                     cid=case.case_id, bid=bid)
    fields = build_handoff(case, bid, True, write_graph=False).fields
    assert rows[0]["n"] == len(fields)
