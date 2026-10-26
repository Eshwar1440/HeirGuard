"""M8 flow tests, in demo order. The LLM is mocked; Neo4j runs the real graph and checks.

The reader is replaced by a fake that returns each file's truth document (matched by
the file's bytes); the writer runs for real with its model call mocked, so the safety
check still sees every text.
"""

import hashlib
import os
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from hg import store
from hg.config import get_settings
from hg.data_gen import load_truth
from hg.flow import checkpoint, files, service
from hg.flow import graph as flow_graph
from hg.flow.service import FlowError
from hg.graph import delete_case_graph
from hg.reader.read import document_id
from hg.schemas import HeirInputs
from hg.writer import write as writer

PACKETS = get_settings().data_dir / "packets"
INPUTS = HeirInputs(annual_income=Decimal("85000"), filing_status="single")
NEUTRAL = "Here is what the check found, in plain words. A tax professional can help you decide."


@pytest.fixture(scope="module")
def neo4j():
    store.get_driver.cache_clear()
    try:
        store.get_driver().verify_connectivity()
    except Exception as exc:
        pytest.skip(f"Neo4j not reachable: {exc}")
    yield
    store.close_driver()


@pytest.fixture
def flow(neo4j, monkeypatch, tmp_path):
    """Fresh in-memory flow, no Supabase, uploads in tmp, LLM mocked."""
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("SUPABASE_URL", "")
    get_settings.cache_clear()
    checkpoint.get_checkpointer.cache_clear()
    service.get_flow.cache_clear()
    monkeypatch.setattr(files, "_uploads_root", lambda: tmp_path / "uploads")

    truth_by_hash = {}
    for pid in ("packet_01_flawed", "packet_01_fixed"):
        for doc in load_truth(PACKETS / pid).documents:
            data = (PACKETS / doc.file_ref).read_bytes()
            truth_by_hash[hashlib.sha256(data).hexdigest()] = doc

    reads = []

    def fake_read(case_id, data, filename, *, file_ref=None):
        reads.append(filename)
        truth = truth_by_hash[hashlib.sha256(data).hexdigest()]
        return truth.model_copy(update={"id": document_id(case_id, filename, data), "case_id": case_id,
                                        "file_ref": file_ref})

    monkeypatch.setattr(flow_graph, "read_document", fake_read)
    monkeypatch.setattr(writer, "write_text", lambda system, user, *, case_id=None: NEUTRAL)
    cases = []
    real_create = service.create_case

    def create(*args, **kwargs):
        view = real_create(*args, **kwargs)
        cases.append(view.case.case_id)
        return view

    monkeypatch.setattr(service, "create_case", create)
    yield reads
    for case_id in cases:
        delete_case_graph(case_id)
    service.get_flow.cache_clear()
    checkpoint.get_checkpointer.cache_clear()


def _actions(case_id):
    return [e.action for e in service.audit_entries(case_id)]


# --- 1. Best case ----------------------------------------------------------------------


def test_best_case_runs_straight_through(flow):
    view = service.create_case("packet_01_fixed")
    case_id = view.case.case_id
    assert view.waiting_for == "approval" and view.case.status == "awaiting_approval"
    assert all(c.status == "pass" for c in view.case.checks)
    assert len(view.case.documents) == 3 and sorted(flow) == sorted(
        ["death_certificate.pdf", "inherited_ira_application_b1.pdf", "inherited_ira_application_b2.pdf"])

    view = service.approve(case_id)
    assert view.case.approved and view.waiting_for == "heir_inputs"

    view = service.simulate(case_id, INPUTS)
    assert view.waiting_for == "choice"
    assert [s.name for s in view.case.scenarios] == ["lump_sum_now", "minimums_then_balloon", "even_spread", "fill_bracket"]
    assert [g.kind for g in view.case.guide] == ["options_summary"]
    assert view.simulation["beneficiary_id"] == view.heir_id and view.simulation["tax_year"] == 2026

    view = service.choose(case_id, "keep", opt_in_rmd_deposit=True)
    assert view.case.status == "prefilled" and view.waiting_for == "choice"  # the choice stays open
    sourced = [f for f in view.case.prefill if f.source_document_id]
    assert len(sourced) == 7 and view.handoff.excluded == []
    assert {f.source_document_id for f in sourced} <= {d.id for d in view.case.documents}
    assert next(f for f in view.case.prefill if f.name == "rmd_deposit_opt_in").value == "yes"
    assert "explain_issues" not in {e.node for e in service.audit_entries(case_id)}
    assert _actions(case_id)[-2:] == ["chose", "prefilled"]


# --- 2. Flawed, fixed by upload; checkpoint survives a new graph instance ----------------


def test_flawed_case_is_caught_fixed_and_finished(flow):
    view = service.create_case("packet_01_flawed")
    case_id = view.case.case_id
    assert view.waiting_for == "heir_fix"
    failed = {c.rule_id for c in view.case.checks if c.status != "pass"}
    assert failed == {"shares_total_100"}
    assert {g.kind for g in view.case.guide} == {"issue_reason"} and all(g.text == NEUTRAL for g in view.case.guide)

    with pytest.raises(FlowError) as exc:
        service.approve(case_id)
    assert exc.value.status_code == 409

    fixed = (PACKETS / "packet_01_fixed" / "inherited_ira_application_b2.pdf").read_bytes()
    view = service.add_documents(case_id, [("inherited_ira_application_b2.pdf", fixed, "application/pdf")])
    assert view.waiting_for == "approval" and all(c.status == "pass" for c in view.case.checks)
    assert len(view.case.documents) == 3  # the corrected application replaced the old one
    assert {"replaced", "share_updated"} <= set(_actions(case_id))

    service.get_flow.cache_clear()  # a new graph instance resumes from the checkpoint
    view = service.approve(case_id)
    view = service.simulate(case_id, INPUTS)
    view = service.choose(case_id, "keep")
    assert view.case.status == "prefilled"
    assert next(f for f in view.case.prefill if f.name == "share_percent").value == "50"


# --- Other paths -----------------------------------------------------------------------


def test_extracted_values_cannot_be_edited(flow):
    """A wrong value is fixed only by uploading a corrected document; there is no edit route."""
    client = TestClient(__import__("api.main", fromlist=["app"]).app)
    case = client.post("/cases", json={"sample_id": "packet_01_flawed"}).json()
    doc = case["case"]["documents"][0]
    r = client.patch(f"/cases/{case['case']['case_id']}/fields/share_percent",
                     json={"document_id": doc["id"], "value": "50"})
    assert r.status_code in (404, 405)
    assert not hasattr(service, "correct_field")
    assert "/cases/{case_id}/fields/{field}" not in client.get("/openapi.json").json()["paths"]


def test_submit_for_review_is_refused_while_a_check_fails(flow):
    view = service.create_case("packet_01_flawed")
    with pytest.raises(FlowError, match="shares_total_100"):
        service.submit_for_review(view.case.case_id)


def test_returned_by_estate_ops_goes_back_to_the_heir(flow):
    case_id = service.create_case("packet_01_fixed").case.case_id
    view = service.approve(case_id, approved=False, note="Please confirm the date of death.")
    assert view.waiting_for == "heir_fix" and not view.case.approved


@pytest.mark.parametrize(("choice", "status"), [("talk", "handed_off"), ("transfer", "transfer_requested")])
def test_talk_and_transfer_are_equal_choices(flow, choice, status):
    case_id = service.create_case("packet_01_fixed").case.case_id
    service.approve(case_id)
    service.simulate(case_id, INPUTS)
    view = service.choose(case_id, choice)
    assert view.case.status == status and view.case.prefill == []


def test_heir_can_switch_from_keep_to_transfer(flow):
    case_id = service.create_case("packet_01_fixed").case.case_id
    service.approve(case_id)
    service.simulate(case_id, INPUTS)
    view = service.choose(case_id, "keep")
    assert view.case.prefill and view.handoff is not None
    heir = view.heir_id

    view = service.choose(case_id, "transfer")
    assert view.case.status == "transfer_requested" and view.case.choice == "transfer"
    assert view.case.prefill == [] and view.handoff is None and view.waiting_for == "choice"
    assert "prefill_withdrawn" in _actions(case_id)
    rows = store.run("MATCH (p:PrefillField {case_id: $cid, beneficiary_id: $bid}) RETURN count(p) AS n",
                     cid=case_id, bid=heir)
    assert rows[0]["n"] == 0

    assert service.choose(case_id, "keep").case.status == "prefilled"


def test_new_inputs_at_the_choice_simulate_again(flow):
    case_id = service.create_case("packet_01_fixed").case.case_id
    service.approve(case_id)
    first = service.simulate(case_id, INPUTS)
    second = service.simulate(case_id, INPUTS.model_copy(update={"annual_income": Decimal("200000")}))
    assert second.waiting_for == "choice"
    assert second.case.scenarios[0].total_tax != first.case.scenarios[0].total_tax
    assert [g.kind for g in second.case.guide] == ["options_summary"]


@pytest.mark.skipif(not os.environ.get("TEST_DATABASE_URL"), reason="set TEST_DATABASE_URL to a disposable Postgres")
def test_postgres_checkpoint_survives_a_restart(flow, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    get_settings.cache_clear()
    checkpoint.get_checkpointer.cache_clear()
    service.get_flow.cache_clear()
    case_id = service.create_case("packet_01_fixed").case.case_id
    service.approve(case_id)
    with checkpoint.get_checkpointer().conn.connection() as conn:
        rows = conn.execute("select tablename, rowsecurity from pg_tables where tablename = any(%s)",
                            (list(checkpoint.CHECKPOINT_TABLES),)).fetchall()
    assert {r["tablename"]: r["rowsecurity"] for r in rows} == dict.fromkeys(checkpoint.CHECKPOINT_TABLES, True)

    checkpoint.get_checkpointer.cache_clear()  # as if the process restarted: new pool, new graph
    service.get_flow.cache_clear()
    assert service.get_case(case_id).waiting_for == "heir_inputs"
    service.simulate(case_id, INPUTS)
    assert service.choose(case_id, "keep").case.status == "prefilled"


# --- API -------------------------------------------------------------------------------


def test_api_demo_path(flow):
    client = TestClient(__import__("api.main", fromlist=["app"]).app)
    assert client.get("/health").json()["checkpointer"] == "memory"
    assert "packet_01_flawed" in {s["sample_id"] for s in client.get("/samples").json()}
    assert client.get("/cases/case-missing").status_code == 404

    case = client.post("/cases", json={"sample_id": "packet_01_flawed"}).json()
    case_id = case["case"]["case_id"]
    assert case["waiting_for"] == "heir_fix"
    fixed = (PACKETS / "packet_01_fixed" / "inherited_ira_application_b2.pdf").read_bytes()
    r = client.post(f"/cases/{case_id}/documents",
                    files=[("files", ("inherited_ira_application_b2.pdf", fixed, "application/pdf"))])
    assert r.status_code == 200 and r.json()["waiting_for"] == "approval"
    assert client.post(f"/cases/{case_id}/approve").json()["waiting_for"] == "heir_inputs"
    r = client.post(f"/cases/{case_id}/simulate", json={"annual_income": "85000", "filing_status": "single"})
    assert r.json()["waiting_for"] == "choice"
    r = client.post(f"/cases/{case_id}/choice", json={"choice": "keep", "opt_in_rmd_deposit": False})
    assert r.json()["case"]["status"] == "prefilled"

    graph = client.get(f"/cases/{case_id}/graph").json()
    assert any(n["data"]["type"] == "PrefillField" for n in graph["nodes"])
    assert any(e["data"]["label"] == "SOURCED_FROM" for e in graph["edges"])
    assert client.get(f"/cases/{case_id}/audit").json()[0]["action"] == "opened"
    assert client.get(f"/cases/{case_id}/ai-log").json() == []  # the LLM was mocked
    doc_id = r.json()["case"]["documents"][0]["id"]
    pdf = client.get(f"/cases/{case_id}/documents/{doc_id}/file")
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    assert client.post(f"/cases/{case_id}/approve").status_code == 409
