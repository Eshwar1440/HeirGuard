"""M3 checker and case-graph tests. Cases are built from M1 truth files (no LLM).

These run against Neo4j: `docker compose up neo4j` locally, the service
container in CI. They skip when no Neo4j is reachable.
"""

from decimal import Decimal

import pytest

from hg import store
from hg.checker import RULES, blocking, run_checks
from hg.checker.requirements import REQUIREMENTS
from hg.config import get_settings
from hg.data_gen import PACKETS, load_truth
from hg.graph import build_case_graph, delete_case_graph, export_case_graph, write_prefill
from hg.graph.resolve import link_applications, name_score
from hg.schemas import ExtractedField, PrefillField

PACKET_DIR = get_settings().data_dir / "packets"


def _truth(packet_id: str):
    return load_truth(PACKET_DIR / packet_id)


def _by_rule(results, rule_id):
    return {r.beneficiary_id: r for r in results if r.rule_id == rule_id}


# --- No database needed ------------------------------------------------------


def test_requirements_cite_a_source_or_say_hypothetical():
    for row in REQUIREMENTS:
        assert row.source
        if row.hypothetical:
            assert row.source.startswith("hypothetical")
        else:
            assert "schwab.com" in row.source and row.excerpt


def test_applications_link_to_their_beneficiaries():
    case = _truth("packet_07").case_state()
    links = link_applications(case)
    assert sorted(links.values()) == sorted(b.id for b in case.beneficiaries)


def test_name_score_tolerates_case_and_punctuation():
    assert name_score("MELISSA  fitzgerald.", "Melissa Fitzgerald") == 100
    assert name_score("Melisa Fitzgerald", "Melissa Fitzgerald") >= get_settings().name_match_threshold


# --- Neo4j -------------------------------------------------------------------


@pytest.fixture(scope="module")
def neo4j():
    store.get_driver.cache_clear()
    try:
        store.get_driver().verify_connectivity()
    except Exception as exc:
        pytest.skip(f"Neo4j not reachable: {exc}")
    yield
    for spec in PACKETS:
        delete_case_graph(spec.packet_id)
    delete_case_graph("test-variant")
    store.close_driver()


@pytest.fixture(scope="module")
def checked(neo4j):
    """Every packet built and checked once: {packet_id: results}."""
    out = {}
    for spec in PACKETS:
        case = _truth(spec.packet_id).case_state()
        build_case_graph(case)
        out[spec.packet_id] = run_checks(case)
    return out


def _flagged(results):
    return sorted({r.rule_id for r in results if r.status != "pass"})


@pytest.mark.neo4j
@pytest.mark.parametrize("packet_id", [spec.packet_id for spec in PACKETS])
def test_each_packet_flags_exactly_its_planted_errors(checked, packet_id):
    assert _flagged(checked[packet_id]) == sorted(_truth(packet_id).planted_errors)
    assert {r.rule_id for r in checked[packet_id]} == set(RULES)


@pytest.mark.neo4j
def test_clean_packets_fully_pass(checked):
    for packet_id in ("packet_10", "packet_01_fixed"):
        assert all(r.status == "pass" for r in checked[packet_id]), packet_id


@pytest.mark.neo4j
def test_demo_flawed_fails_only_shares(checked):
    results = checked["packet_01_flawed"]
    assert _flagged(results) == ["shares_total_100"]
    shares = _by_rule(results, "shares_total_100")
    assert {r.status for r in shares.values()} == {"fail"}
    assert "99.5%" in next(iter(shares.values())).message


@pytest.mark.neo4j
def test_shares_total_100(checked):
    shares = _by_rule(checked["packet_09"], "shares_total_100")
    assert len(shares) == 3 and all(r.status == "fail" for r in shares.values())
    assert "99.99%" in shares["packet_09-b1"].message


@pytest.mark.neo4j
def test_name_match_misspelling_needs_review_for_that_heir_only(checked):
    names = _by_rule(checked["packet_03"], "name_match")
    assert names["packet_03-b1"].status == "needs_review"
    assert names["packet_03-b2"].status == "pass"
    assert names["packet_03-b1"].evidence[0].field_name == "executor_name"


@pytest.mark.neo4j
def test_dod_consistent_scoped_to_the_application_with_the_wrong_date(checked):
    dods = _by_rule(checked["packet_09"], "dod_consistent")
    assert dods["packet_09-b3"].status == "fail"
    assert dods["packet_09-b1"].status == dods["packet_09-b2"].status == "pass"
    # A wrong date on a shared document (letters) affects every heir.
    shared = _by_rule(checked["packet_07"], "dod_consistent")
    assert {r.status for r in shared.values()} == {"fail"}


@pytest.mark.neo4j
def test_required_docs_present_missing_application_blocks_only_that_heir(checked):
    results = checked["packet_05"]
    docs = _by_rule(results, "required_docs_present")
    assert docs["packet_05-b2"].status == "fail"
    assert docs["packet_05-b1"].status == "pass"
    assert blocking(results, "packet_05-b1") == []
    assert blocking(results, "packet_05-b2")


@pytest.mark.neo4j
def test_required_docs_present_missing_trust_certification_is_case_wide(checked):
    docs = _by_rule(checked["packet_08"], "required_docs_present")
    assert docs[None].status == "fail"
    assert "hypothetical" in docs[None].message
    assert docs["packet_08-b1"].status == "pass"


@pytest.mark.neo4j
def test_certified_copy(checked):
    assert {r.status for r in _by_rule(checked["packet_06"], "certified_copy").values()} == {"fail"}
    assert {r.status for r in _by_rule(checked["packet_10"], "certified_copy").values()} == {"pass"}


@pytest.mark.neo4j
def test_check_nodes_written(checked):
    rows = store.run("MATCH (c:Check {case_id: 'packet_08'}) RETURN count(c) AS n")
    assert rows[0]["n"] == len(checked["packet_08"])


@pytest.mark.neo4j
def test_rebuild_is_idempotent_and_drops_stale_facts(neo4j):
    case = _truth("packet_01_flawed").case_state().model_copy(update={"case_id": "test-variant"})
    case = case.model_copy(update={"documents": [d.model_copy(update={"case_id": "test-variant"}) for d in case.documents]})

    def counts():
        return store.run(
            "MATCH (n {case_id: 'test-variant'}) WITH count(n) AS nodes "
            "OPTIONAL MATCH ({case_id: 'test-variant'})-[r]->() RETURN nodes, count(r) AS rels"
        )[0]

    build_case_graph(case)
    first = counts()
    build_case_graph(case)
    assert counts() == first

    # Heir fixes the share and drops one document: no stale facts remain.
    fixed_bens = [b.model_copy(update={"share_percent": Decimal("50")}) for b in case.beneficiaries]
    fewer_docs = [d for d in case.documents if not d.id.endswith("-b2")]
    fixed = case.model_copy(update={"beneficiaries": fixed_bens, "documents": fewer_docs})
    build_case_graph(fixed)
    results = run_checks(fixed)
    assert {r.status for r in _by_rule(results, "shares_total_100").values()} == {"pass"}
    stale = store.run(
        "MATCH (f:Fact {case_id: 'test-variant'}) WHERE f.document_id ENDS WITH '-b2' RETURN count(f) AS n"
    )
    assert stale[0]["n"] == 0
    assert _by_rule(results, "required_docs_present")[fixed_bens[1].id].status == "fail"


@pytest.mark.neo4j
def test_field_review_flags_low_confidence_for_the_right_heir(neo4j):
    case = _truth("packet_10").case_state()
    app_b2 = next(d for d in case.documents if d.id.endswith("-b2"))
    low = [
        f.model_copy(update={"confidence": 0.4}) if f.name == "beneficiary_date_of_birth" else f
        for f in app_b2.fields
    ]
    docs = [d.model_copy(update={"fields": low}) if d.id == app_b2.id else d for d in case.documents]
    case = case.model_copy(update={"case_id": "test-variant", "documents": docs})
    build_case_graph(case)
    review = _by_rule(run_checks(case), "field_review")
    assert review["packet_10-b2"].status == "needs_review"
    assert "beneficiary_date_of_birth" in review["packet_10-b2"].message
    assert review["packet_10-b1"].status == "pass"


@pytest.mark.neo4j
def test_application_for_unknown_person_fails(neo4j):
    case = _truth("packet_10").case_state()
    app_b2 = next(d for d in case.documents if d.id.endswith("-b2"))
    renamed = [
        ExtractedField(name=f.name, value="Zelda Quartermaine", confidence=f.confidence, page=f.page)
        if f.name in ("beneficiary_name", "signature_name") else f
        for f in app_b2.fields
    ]
    docs = [d.model_copy(update={"fields": renamed}) if d.id == app_b2.id else d for d in case.documents]
    case = case.model_copy(update={"case_id": "test-variant", "documents": docs})
    build_case_graph(case)
    results = run_checks(case)
    assert _by_rule(results, "name_match")[None].status == "fail"
    assert _by_rule(results, "required_docs_present")["packet_10-b2"].status == "fail"


@pytest.mark.neo4j
def test_export_marks_failed_check_edges(checked):
    graph = export_case_graph("packet_02")
    types = {n["data"]["type"] for n in graph["nodes"]}
    assert {"Decedent", "Person", "Account", "Designation", "Document", "Fact", "Check"} <= types
    ids = {n["data"]["id"] for n in graph["nodes"]}
    for e in graph["edges"]:
        assert e["data"]["source"] in ids and e["data"]["target"] in ids
    evaluates = [e for e in graph["edges"] if e["data"]["label"] == "EVALUATES"]
    failed = [e for e in evaluates if e["data"]["status"] == "fail"]
    assert failed and all(e["data"]["source"].startswith("check:shares_total_100") for e in failed)
    assert all(e["data"]["status"] is None for e in graph["edges"] if e["data"]["label"] != "EVALUATES")


@pytest.mark.neo4j
def test_export_shows_possibly_same_as_with_score(checked):
    graph = export_case_graph("packet_03")
    same = [e for e in graph["edges"] if e["data"]["label"] == "POSSIBLY_SAME_AS"]
    assert len(same) == 1
    assert get_settings().name_match_threshold <= same[0]["data"]["score"] < 100


@pytest.mark.neo4j
def test_write_prefill_links_to_source_facts(checked):
    truth = _truth("packet_10")
    app = next(d for d in truth.documents if d.id.endswith("-b1"))
    write_prefill(
        "packet_10",
        "packet_10-b1",
        [
            PrefillField(name="beneficiary_name", value="x", source_document_id=app.id, source_field="beneficiary_name"),
            PrefillField(name="ssn", value="entered by heir at signing"),
        ],
    )
    rows = store.run(
        "MATCH (p:PrefillField {case_id: 'packet_10'}) OPTIONAL MATCH (p)-[:SOURCED_FROM]->(f:Fact) "
        "RETURN p.name AS name, f.id AS fact ORDER BY name"
    )
    assert rows == [
        {"name": "beneficiary_name", "fact": f"{app.id}/beneficiary_name"},
        {"name": "ssn", "fact": None},
    ]
