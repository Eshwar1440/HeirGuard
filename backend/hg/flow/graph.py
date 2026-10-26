"""M8: the case flow as a LangGraph StateGraph.

intake -> read_documents (M2) -> build_case_graph (M3) -> check_packet (M3)
check_packet -> explain_issues (M5 + M6) if any check is not "pass", else await_approval
explain_issues -> await_heir_fix (pause) -> read_documents | build_case_graph | await_approval
await_approval (pause, estate ops) -> simulate (M4) | await_heir_fix
simulate (pauses for the heir's inputs if none yet) -> write_summary (M5 + M6) -> await_choice (pause)
await_choice -> prefill (M7) | handoff | transfer_request | simulate (new inputs)
prefill | handoff | transfer_request -> await_choice: the heir can change their mind at any time,
so a transfer out is never held up by an earlier choice.

Every routing function is plain Python over the state. No LLM decides a transition.
The state holds only JSON values, so any checkpointer can store it. Nodes that pause
call interrupt() before any side effect, because a resumed node runs again from the top.
"""

from __future__ import annotations

import json
import operator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal, Optional, TypedDict

from langgraph.graph import START, StateGraph
from langgraph.types import interrupt
from pydantic import BaseModel, Field, model_validator

from hg import audit
from hg.checker import run_checks
from hg.config import get_settings
from hg.flow import files
from hg.graph import build_case_graph as write_case_graph
from hg.graph import write_prefill
from hg.graph.resolve import field_value, link_applications
from hg.prefill import build_handoff
from hg.reader import read_document
from hg.schemas import Account, AuditEntry, Beneficiary, CaseState, Choice, Document, HeirInputs
from hg.simulator.rmd import to_cents
from hg.simulator.rules import rule_summary
from hg.simulator.scenarios import simulate as run_simulation
from hg.writer import explain_issue, summarize_options

# Pause kinds, as found in the interrupt value's "kind".
HEIR_FIX = "heir_fix"
APPROVAL = "approval"
HEIR_INPUTS = "heir_inputs"
CHOICE = "choice"

READ_WORKERS = 4


class FlowState(TypedDict, total=False):
    case: dict  # CaseState as JSON
    heir_id: Optional[str]  # the beneficiary using the app
    pending_uploads: list[str]  # file refs to read next
    audit: Annotated[list[dict], operator.add]  # AuditEntry JSON, appended by every node
    simulation: Optional[dict]
    handoff: Optional[dict]
    last_fix: Optional[dict]
    last_decision: Optional[dict]


# --- Resume payloads -----------------------------------------------------------------


class Correction(BaseModel):
    document_id: str
    field: str
    value: str


class HeirFix(BaseModel):
    uploads: list[str] = Field(default_factory=list, description="file refs of new uploads")
    corrections: list[Correction] = Field(default_factory=list)
    submit_for_review: bool = False


class Approval(BaseModel):
    approved: bool
    by: str = "estate_ops"
    note: str = ""


class ChoiceAnswer(BaseModel):
    choice: Optional[Choice] = None
    opt_in_rmd_deposit: bool = False
    heir_inputs: Optional[HeirInputs] = None

    @model_validator(mode="after")
    def _one_of(self) -> "ChoiceAnswer":
        if (self.choice is None) == (self.heir_inputs is None):
            raise ValueError("send either a choice or new heir_inputs")
        return self


# --- Helpers ---------------------------------------------------------------------------


def _case(state: FlowState) -> CaseState:
    return CaseState.model_validate(state["case"])


def _dump(case: CaseState) -> dict:
    return case.model_dump(mode="json")


def _log(case_id: str, node: str, action: str, summary: str) -> dict:
    return audit.entry(case_id, node, action, summary).model_dump(mode="json")


def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def _open(case: CaseState) -> list:
    return [c for c in case.checks if c.status != "pass"]


def heir_and_account(case: CaseState, heir_id: Optional[str]) -> tuple[Beneficiary, Account]:
    heir = next((b for b in case.beneficiaries if b.id == heir_id), None)
    if heir is None:
        raise ValueError(f"unknown beneficiary {heir_id!r}")
    account = next((a for a in case.accounts if a.id == heir.account_id), None) if heir.account_id else None
    if account is None:
        iras = [a for a in case.accounts if a.type in ("traditional_ira", "roth_ira")]
        account = (iras or case.accounts or [None])[0]
    if account is None:
        raise ValueError("the case has no account to simulate")
    return heir, account


def sync_shares(case: CaseState) -> tuple[CaseState, list[str]]:
    """Each beneficiary's share follows the share on their own application.

    In this prototype the applications are where shares are declared, so a corrected
    application (or a corrected field) must change the designation the checker sees.
    """
    links = link_applications(case)
    notes, beneficiaries = [], []
    for b in case.beneficiaries:
        shares = set()
        for doc in case.documents:
            if links.get(doc.id) == b.id:
                try:
                    shares.add(Decimal(field_value(doc, "share_percent") or ""))
                except InvalidOperation:
                    continue
        if len(shares) == 1 and (share := shares.pop()) != b.share_percent:
            notes.append(f"Share for {b.name} set to {share}% from their application (was {b.share_percent}%).")
            b = b.model_copy(update={"share_percent": share})
        beneficiaries.append(b)
    return case.model_copy(update={"beneficiaries": beneficiaries}), notes


def apply_corrections(case: CaseState, corrections: list[Correction]) -> tuple[CaseState, list[str]]:
    threshold = get_settings().confidence_threshold
    docs = {d.id: d for d in case.documents}
    notes = []
    for c in corrections:
        doc = docs[c.document_id]
        fields = []
        for f in doc.fields:
            if f.name == c.field:
                notes.append(f"Heir corrected {c.field} on the {doc.doc_type} from {f.value!r} to {c.value!r}.")
                f = f.model_copy(update={"value": c.value, "confidence": 1.0})
            fields.append(f)
        needs_review = any(f.value is None or f.confidence < threshold for f in fields)
        docs[doc.id] = doc.model_copy(update={"fields": fields, "needs_review": needs_review})
    return case.model_copy(update={"documents": [docs[d.id] for d in case.documents]}), notes


# --- Nodes ----------------------------------------------------------------------------


def intake(state: FlowState) -> dict:
    case = _case(state).model_copy(update={"status": "intake"})
    n = len(state.get("pending_uploads") or [])
    return {"case": _dump(case), "audit": [_log(case.case_id, "intake", "opened", f"Case opened with {n} document(s) to read.")]}


def read_documents(state: FlowState) -> dict:
    case = _case(state)
    refs = state.get("pending_uploads") or []
    threshold = get_settings().confidence_threshold

    def one(ref: str) -> tuple[str, Optional[Document], Optional[Exception]]:
        try:
            return ref, read_document(case.case_id, files.load(ref), files.filename_of(ref), file_ref=ref), None
        except Exception as exc:  # one unreadable upload must not stop the case; the audit says why
            return ref, None, exc

    with ThreadPoolExecutor(max_workers=READ_WORKERS) as pool:
        results = list(pool.map(one, refs))
    new_docs, entries = [], []
    for ref, doc, exc in results:
        name = files.filename_of(ref)
        if doc is None:
            entries.append(_log(case.case_id, "read_documents", "read_failed",
                                f"Could not read {name}: {type(exc).__name__}: {exc}"))
            continue
        new_docs.append(doc)
        flagged = [f.name for f in doc.fields if f.value is None or f.confidence < threshold]
        detail = f"; needs review: {', '.join(flagged)}" if flagged else ""
        entries.append(_log(case.case_id, "read_documents", "read",
                            f"Read {name} as {doc.doc_type} ({len(doc.fields)} fields{detail})."))
    docs, replaced = supersede(case, new_docs)
    entries += [_log(case.case_id, "read_documents", "replaced", f"{n} was replaced by a newer upload.") for n in replaced]
    case = case.model_copy(update={"documents": docs, "status": "reading_documents"})
    return {"case": _dump(case), "pending_uploads": [], "audit": entries}


def supersede(case: CaseState, new_docs: list[Document]) -> tuple[list[Document], list[str]]:
    """Add new reads. A file with the same name, or an older application for the same
    beneficiary, is replaced by the new one."""
    new_names = {files.filename_of(d.file_ref) for d in new_docs}
    links = link_applications(case.model_copy(update={"documents": case.documents + new_docs}))
    new_app_owners = {links.get(d.id) for d in new_docs if d.doc_type == "inherited_ira_application"} - {None}
    kept, replaced = [], []
    for d in case.documents:
        name = files.filename_of(d.file_ref)
        if name in new_names or (d.doc_type == "inherited_ira_application" and links.get(d.id) in new_app_owners):
            replaced.append(name)
        else:
            kept.append(d)
    return kept + new_docs, replaced


def build_case_graph(state: FlowState) -> dict:
    case, notes = sync_shares(_case(state))
    counts = write_case_graph(case)
    entries = [_log(case.case_id, "build_case_graph", "share_updated", n) for n in notes]
    entries.append(_log(case.case_id, "build_case_graph", "built",
                        "Case graph built: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) + "."))
    return {"case": _dump(case), "audit": entries}


def check_packet(state: FlowState) -> dict:
    case = _case(state)
    results = run_checks(case)
    case = case.model_copy(update={"checks": results, "status": "checking"})
    open_checks = _open(case)
    summary = f"{len(results) - len(open_checks)} checks passed"
    if open_checks:
        summary += f"; {len(open_checks)} need attention: " + ", ".join(sorted({c.rule_id for c in open_checks}))
    return {"case": _dump(case), "audit": [_log(case.case_id, "check_packet", "checked", summary + ".")]}


def explain_issues(state: FlowState) -> dict:
    case = _case(state)
    blocks: list[AuditEntry] = []
    with ThreadPoolExecutor(max_workers=READ_WORKERS) as pool:
        texts = list(pool.map(lambda c: explain_issue(c, case_id=case.case_id, record=blocks.append), _open(case)))
    guide = [g for g in case.guide if g.kind != "issue_reason"] + texts
    case = case.model_copy(update={"guide": guide, "status": "awaiting_heir_fix"})
    entries = [e.model_dump(mode="json") for e in blocks]
    entries.append(_log(case.case_id, "explain_issues", "explained", f"Explained {len(texts)} issue(s) in plain English."))
    return {"case": _dump(case), "audit": entries}


def await_heir_fix(state: FlowState) -> dict:
    case = _case(state)
    fix = HeirFix.model_validate(interrupt({"kind": HEIR_FIX, "open_checks": len(_open(case))}))
    case, notes = apply_corrections(case, fix.corrections)
    entries = [_log(case.case_id, "await_heir_fix", "corrected", n) for n in notes]
    if fix.uploads:
        entries.append(_log(case.case_id, "await_heir_fix", "uploaded", f"Heir uploaded {len(fix.uploads)} file(s)."))
    if fix.submit_for_review:
        entries.append(_log(case.case_id, "await_heir_fix", "submitted",
                            "Heir sent the remaining review items to estate operations."))
    return {"case": _dump(case), "pending_uploads": fix.uploads, "last_fix": fix.model_dump(), "audit": entries}


def await_approval(state: FlowState) -> dict:
    case = _case(state).model_copy(update={"status": "awaiting_approval"})
    decision = Approval.model_validate(interrupt({"kind": APPROVAL}))
    note = f" Note: {decision.note}" if decision.note else ""
    if decision.approved:
        case = case.model_copy(update={"approved": True})
        entry = _log(case.case_id, "await_approval", "approved", f"Approved by {decision.by}.{note}")
    else:
        entry = _log(case.case_id, "await_approval", "returned", f"Returned to the heir by {decision.by}.{note}")
    return {"case": _dump(case), "last_decision": decision.model_dump(), "audit": [entry]}


def simulate(state: FlowState) -> dict:
    case = _case(state)
    if case.heir_inputs is None:
        inputs = HeirInputs.model_validate(interrupt({"kind": HEIR_INPUTS}))
        case = case.model_copy(update={"heir_inputs": inputs})
    heir, account = heir_and_account(case, state.get("heir_id"))
    balance = to_cents(account.balance * heir.share_percent / 100)
    result = run_simulation(balance, case.decedent, heir, account.type, case.heir_inputs)
    simulation = _jsonable({
        "beneficiary_id": heir.id,
        "balance": balance,
        "account_type": account.type,
        "rules": asdict(result.rules),
        "factors": [asdict(f) for f in result.factors],
        "assumptions": result.assumptions,
        "tax_year": result.tax_year,
        "fill_rate": result.fill_rate,
    })
    case = case.model_copy(update={"scenarios": result.scenarios, "status": "simulating"})
    summary = (f"Simulated {len(result.scenarios)} scenarios on a hypothetical balance of ${balance:,.2f} "
               f"({heir.share_percent}% of {account.title}).")
    return {"case": _dump(case), "simulation": simulation, "audit": [_log(case.case_id, "simulate", "simulated", summary)]}


def write_summary(state: FlowState) -> dict:
    case = _case(state)
    heir, account = heir_and_account(case, state.get("heir_id"))
    rules = rule_summary(heir, case.decedent, account.type)
    blocks: list[AuditEntry] = []
    text = summarize_options(case.scenarios, rules, case.heir_inputs, tax_year=(state.get("simulation") or {}).get("tax_year"),
                             beneficiary_id=heir.id, case_id=case.case_id, record=blocks.append)
    guide = [g for g in case.guide if g.kind != "options_summary"] + [text]
    case = case.model_copy(update={"guide": guide, "status": "awaiting_choice"})
    entries = [e.model_dump(mode="json") for e in blocks]
    entries.append(_log(case.case_id, "write_summary", "summarized", "Wrote the neutral options summary."))
    return {"case": _dump(case), "audit": entries}


def await_choice(state: FlowState) -> dict:
    case = _case(state)
    answer = ChoiceAnswer.model_validate(interrupt({"kind": CHOICE, "options": ["keep", "talk", "transfer"]}))
    if answer.heir_inputs is not None:
        case = case.model_copy(update={"heir_inputs": answer.heir_inputs})
        entry = _log(case.case_id, "await_choice", "new_inputs", "Heir changed their inputs; simulating again.")
    else:
        case = case.model_copy(update={"choice": answer.choice})
        opt_in = "yes" if answer.opt_in_rmd_deposit else "no"
        entry = _log(case.case_id, "await_choice", "chose", f"Heir chose {answer.choice} (RMD deposit opt-in: {opt_in}).")
    return {"case": _dump(case), "last_decision": answer.model_dump(mode="json"), "audit": [entry]}


def prefill(state: FlowState) -> dict:
    case = _case(state)
    opt_in = bool((state.get("last_decision") or {}).get("opt_in_rmd_deposit"))
    handoff = build_handoff(case, state.get("heir_id"), opt_in)
    case = case.model_copy(update={"prefill": handoff.fields, "status": "prefilled"})
    sourced = sum(1 for f in handoff.fields if f.source_document_id)
    summary = (f"Prefilled {sourced} fields from documents; {len(handoff.excluded)} left out; "
               f"{len(handoff.heir_entered)} entered or chosen by the heir. Proposed handoff only, not a submission.")
    return {"case": _dump(case), "handoff": handoff.model_dump(mode="json"),
            "audit": [_log(case.case_id, "prefill", "prefilled", summary)]}


def _withdraw_prefill(case: CaseState, heir_id: Optional[str]) -> tuple[CaseState, list[dict]]:
    """A later talk or transfer choice withdraws a proposed application."""
    if not case.prefill:
        return case, []
    if heir_id:
        write_prefill(case.case_id, heir_id, [])
    note = _log(case.case_id, "await_choice", "prefill_withdrawn", "The proposed application was withdrawn.")
    return case.model_copy(update={"prefill": []}), [note]


def handoff(state: FlowState) -> dict:
    case, entries = _withdraw_prefill(_case(state), state.get("heir_id"))
    case = case.model_copy(update={"status": "handed_off"})
    entries.append(_log(case.case_id, "handoff", "handed_off",
                        "Heir chose to talk to a professional. No account action taken."))
    return {"case": _dump(case), "handoff": None, "audit": entries}


def transfer_request(state: FlowState) -> dict:
    case, entries = _withdraw_prefill(_case(state), state.get("heir_id"))
    case = case.model_copy(update={"status": "transfer_requested"})
    entries.append(_log(case.case_id, "transfer_request", "transfer_requested",
                        "Heir chose to transfer out. Request recorded (mock); nothing blocks it."))
    return {"case": _dump(case), "handoff": None, "audit": entries}


# --- Routing (plain Python) -----------------------------------------------------------


def route_after_check(state: FlowState) -> Literal["explain_issues", "await_approval"]:
    return "explain_issues" if _open(_case(state)) else "await_approval"


def route_after_fix(state: FlowState) -> Literal["read_documents", "build_case_graph", "await_approval", "await_heir_fix"]:
    fix = HeirFix.model_validate(state.get("last_fix") or {})
    if fix.uploads:
        return "read_documents"
    if fix.corrections:
        return "build_case_graph"
    if fix.submit_for_review and not any(c.status == "fail" for c in _case(state).checks):
        return "await_approval"
    return "await_heir_fix"


def route_after_approval(state: FlowState) -> Literal["simulate", "await_heir_fix"]:
    return "simulate" if _case(state).approved else "await_heir_fix"


def route_after_choice(state: FlowState) -> Literal["simulate", "prefill", "handoff", "transfer_request"]:
    answer = state.get("last_decision") or {}
    if answer.get("heir_inputs"):
        return "simulate"
    return {"keep": "prefill", "talk": "handoff", "transfer": "transfer_request"}[answer["choice"]]


def build_flow(checkpointer):
    g = StateGraph(FlowState)
    for node in (intake, read_documents, build_case_graph, check_packet, explain_issues, await_heir_fix,
                 await_approval, simulate, write_summary, await_choice, prefill, handoff, transfer_request):
        g.add_node(node.__name__, node)
    g.add_edge(START, "intake")
    g.add_edge("intake", "read_documents")
    g.add_edge("read_documents", "build_case_graph")
    g.add_edge("build_case_graph", "check_packet")
    g.add_conditional_edges("check_packet", route_after_check)
    g.add_edge("explain_issues", "await_heir_fix")
    g.add_conditional_edges("await_heir_fix", route_after_fix)
    g.add_conditional_edges("await_approval", route_after_approval)
    g.add_edge("simulate", "write_summary")
    g.add_edge("write_summary", "await_choice")
    g.add_conditional_edges("await_choice", route_after_choice)
    for chosen in ("prefill", "handoff", "transfer_request"):
        g.add_edge(chosen, "await_choice")
    return g.compile(checkpointer=checkpointer)
