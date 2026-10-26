"""Case operations the API calls. Each one checks where the flow is paused, then
starts or resumes it with a typed payload. thread_id = case_id.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Optional
from uuid import uuid4

from langgraph.types import Command
from pydantic import BaseModel

from hg import audit, llm
from hg.config import get_settings
from hg.data_gen import load_truth
from hg.flow import files
from hg.flow.checkpoint import get_checkpointer
from hg.flow.graph import (
    APPROVAL,
    CHOICE,
    HEIR_FIX,
    HEIR_INPUTS,
    Approval,
    ChoiceAnswer,
    HeirFix,
    build_flow,
)
from hg.graph import export_case_graph
from hg.prefill import PrefillHandoff
from hg.schemas import AuditEntry, CaseState, CaseStatus, Choice, HeirInputs

_STATUS_WHILE_WAITING: dict[str, CaseStatus] = {
    HEIR_FIX: "awaiting_heir_fix",
    APPROVAL: "awaiting_approval",
    HEIR_INPUTS: "simulating",
    CHOICE: "awaiting_choice",
}


class FlowError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


class CaseView(BaseModel):
    case: CaseState
    heir_id: Optional[str] = None
    waiting_for: Optional[str] = None  # heir_fix | approval | heir_inputs | choice
    simulation: Optional[dict] = None
    handoff: Optional[PrefillHandoff] = None
    review_note: Optional[str] = None  # why estate operations returned the packet, shown to the heir


class Sample(BaseModel):
    sample_id: str
    description: str
    planted_errors: list[str]


@lru_cache
def get_flow():
    return build_flow(get_checkpointer())


def _config(case_id: str) -> dict:
    return {"configurable": {"thread_id": case_id}}


def _snapshot(case_id: str):
    snap = get_flow().get_state(_config(case_id))
    if not snap.values:
        raise FlowError(404, f"no case {case_id!r}")
    return snap


def _waiting_for(snap) -> Optional[str]:
    return snap.interrupts[0].value.get("kind") if snap.interrupts else None


def _view(case_id: str) -> CaseView:
    snap = _snapshot(case_id)
    values = snap.values
    waiting = _waiting_for(snap)
    case = CaseState.model_validate(values["case"])
    if waiting and not (waiting == CHOICE and case.choice):  # after a choice, its status stands
        case = case.model_copy(update={"status": _STATUS_WHILE_WAITING[waiting]})
    decision = values.get("last_decision") or {}
    note = decision.get("note") if waiting == HEIR_FIX and decision.get("approved") is False else None
    return CaseView(case=case, heir_id=values.get("heir_id"), waiting_for=waiting,
                    simulation=values.get("simulation"), handoff=values.get("handoff"), review_note=note)


def _run(case_id: str, payload: Any) -> CaseView:
    before = len((get_flow().get_state(_config(case_id)).values or {}).get("audit", []))
    get_flow().invoke(payload, _config(case_id))
    view = _view(case_id)
    entries = [AuditEntry.model_validate(e) for e in _snapshot(case_id).values.get("audit", [])[before:]]
    audit.mirror(view.case, entries)
    return view


def _resume(case_id: str, expected: str, value: Any) -> CaseView:
    waiting = _waiting_for(_snapshot(case_id))
    if waiting != expected:
        raise FlowError(409, f"case is waiting for {waiting or 'nothing'}, not {expected}")
    return _run(case_id, Command(resume=value))


# --- Operations -------------------------------------------------------------------------


def list_samples() -> list[Sample]:
    index = json.loads((get_settings().data_dir / "packets" / "index.json").read_text(encoding="utf-8"))
    return [Sample(sample_id=p["packet_id"], description=p["description"], planted_errors=p["planted_errors"])
            for p in index]


def create_case(
    sample_id: Optional[str] = None, beneficiary_id: Optional[str] = None, with_documents: bool = True,
) -> CaseView:
    """Open a case. A sample brings the decedent, accounts and designations on file. With
    with_documents its packet is read at once; without, the case waits for the heir to upload
    (or for POST /cases/{id}/sample-documents in a demo)."""
    case_id = f"case-{uuid4().hex[:12]}"
    uploads: list[str] = []
    if sample_id:
        if sample_id not in {s.sample_id for s in list_samples()}:
            raise FlowError(404, f"no sample {sample_id!r}")
        truth = load_truth(get_settings().data_dir / "packets" / sample_id)
        case = truth.case_state().model_copy(update={"case_id": case_id, "documents": []})
        if with_documents:
            uploads = sample_uploads(sample_id)
    else:
        case = CaseState(case_id=case_id)
    ids = [b.id for b in case.beneficiaries]
    if beneficiary_id and beneficiary_id not in ids:
        raise FlowError(422, f"no beneficiary {beneficiary_id!r} in this case")
    state = {"case": case.model_dump(mode="json"), "heir_id": beneficiary_id or (ids[0] if ids else None),
             "pending_uploads": uploads, "audit": [], "sample_id": sample_id}
    return _run(case_id, state)


def sample_uploads(sample_id: str) -> list[str]:
    truth = load_truth(get_settings().data_dir / "packets" / sample_id)
    return [files.sample_ref(sample_id, files.filename_of(d.file_ref)) for d in truth.documents]


def load_sample_documents(case_id: str) -> CaseView:
    """Demo helper (under the hood): read the case's sample packet as if the heir uploaded it."""
    sample_id = _snapshot(case_id).values.get("sample_id")
    if not sample_id:
        raise FlowError(409, "this case has no sample packet")
    _require(case_id, HEIR_FIX)
    return _resume(case_id, HEIR_FIX, HeirFix(uploads=sample_uploads(sample_id)).model_dump())


def add_documents(case_id: str, uploads: list[tuple[str, bytes, str]]) -> CaseView:
    """uploads: (filename, data, content_type). Resumes the heir-fix pause."""
    if not uploads:
        raise FlowError(422, "no files uploaded")
    _require(case_id, HEIR_FIX)
    refs = [files.save_upload(case_id, name, data, ctype) for name, data, ctype in uploads]
    return _resume(case_id, HEIR_FIX, HeirFix(uploads=refs).model_dump())


def submit_for_review(case_id: str) -> CaseView:
    view = _require(case_id, HEIR_FIX)
    if not view.case.documents:
        raise FlowError(409, "upload the documents first")
    failed = sorted({c.rule_id for c in view.case.checks if c.status == "fail"})
    if failed:
        raise FlowError(409, "these checks must be fixed first: " + ", ".join(failed))
    return _resume(case_id, HEIR_FIX, HeirFix(submit_for_review=True).model_dump())


def approve(case_id: str, approved: bool = True, by: str = "estate_ops", note: str = "") -> CaseView:
    """Approve the packet, or return it to the heir with a reason (required, shown to the heir)."""
    if not approved and not note.strip():
        raise FlowError(422, "give the heir a reason when returning the packet")
    return _resume(case_id, APPROVAL, Approval(approved=approved, by=by, note=note).model_dump())


def simulate(case_id: str, inputs: HeirInputs) -> CaseView:
    waiting = _waiting_for(_snapshot(case_id))
    payload = inputs.model_dump(mode="json")
    if waiting == HEIR_INPUTS:
        return _resume(case_id, HEIR_INPUTS, payload)
    if waiting == CHOICE:
        return _resume(case_id, CHOICE, ChoiceAnswer(heir_inputs=inputs).model_dump(mode="json"))
    raise FlowError(409, f"case is waiting for {waiting or 'nothing'}, not heir inputs")


def choose(case_id: str, choice: Choice, opt_in_rmd_deposit: bool = False) -> CaseView:
    answer = ChoiceAnswer(choice=choice, opt_in_rmd_deposit=opt_in_rmd_deposit)
    return _resume(case_id, CHOICE, answer.model_dump(mode="json"))


def get_case(case_id: str) -> CaseView:
    return _view(case_id)


def case_graph(case_id: str) -> dict:
    _snapshot(case_id)
    return export_case_graph(case_id)


def audit_entries(case_id: str) -> list[AuditEntry]:
    return [AuditEntry.model_validate(e) for e in _snapshot(case_id).values.get("audit", [])]


def ai_log(case_id: str) -> list[dict]:
    _snapshot(case_id)
    return llm.read_log(case_id)


def document_file(case_id: str, document_id: str) -> tuple[str, bytes]:
    doc = next((d for d in _view(case_id).case.documents if d.id == document_id), None)
    if doc is None:
        raise FlowError(404, f"no document {document_id!r}")
    return files.filename_of(doc.file_ref), files.load(doc.file_ref)


def _require(case_id: str, expected: str) -> CaseView:
    view = _view(case_id)
    if view.waiting_for != expected:
        raise FlowError(409, f"case is waiting for {view.waiting_for or 'nothing'}, not {expected}")
    return view
