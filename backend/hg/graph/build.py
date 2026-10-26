"""Write a case into Neo4j.

Graph schema (every node carries ``case_id`` and an ``id`` unique within the case):

Nodes
  (:Person:Decedent)  the decedent                  id = decedent.id
  (:Person)           a beneficiary                 id = beneficiary.id
  (:Person)           a name seen only on documents id = "person:<normalized name>"
  (:Account)          id = account.id; balance stored as a string (hypothetical)
  (:Designation)      one per beneficiary per account; share_percent as a string
  (:Trust)            from a trust-owned account or a trust certification
  (:Document)         id = document.id
  (:Fact)             one per extracted field; id = "<document id>/<field name>"
  (:Check)            written by hg.checker.run
  (:PrefillField)     written by write_prefill (M7)

Relationships
  (Decedent)-[:OWNED]->(Account)          (Trust)-[:OWNED]->(Account) for trust-owned
  (Account)-[:HAS_DESIGNATION]->(Designation)-[:FOR]->(Person)
  (Trust)-[:HAS_TRUSTEE]->(Person)
  (Document)-[:MENTIONS {field}]->(Person)
  (Document)-[:PROVES]->(Fact)-[:ABOUT]->(Person | Account | Trust)
  (Person)-[:POSSIBLY_SAME_AS {score}]->(Person)   doc-only name -> known person
  (Check)-[:EVALUATES {status}]->(Fact | Document | Person)
  (PrefillField)-[:SOURCED_FROM]->(Fact)

Writes use MERGE, so re-running a build is idempotent. Each build stamps what
it writes; anything left from an older build of the same case is removed, so a
corrected document never leaves stale facts behind.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Iterable, Optional
from uuid import uuid4

from hg import store
from hg.config import get_settings
from hg.graph.resolve import (
    ACCOUNT_FIELDS,
    BENEFICIARY_FIELDS,
    PERSON_FIELDS,
    TRUST_FIELDS,
    best_match,
    fact_kind,
    field_value,
    link_applications,
    normalize_name,
)
from hg.schemas import CaseState, PrefillField

LABELS = ("Person", "Account", "Designation", "Trust", "Document", "Fact", "Check", "PrefillField")


def fact_id(document_id: str, field_name: str) -> str:
    return f"{document_id}/{field_name}"


@dataclass
class _Graph:
    nodes: dict[str, tuple[str, dict]] = field(default_factory=dict)  # id -> (label, props)
    extra_labels: dict[str, str] = field(default_factory=dict)
    rels: list[tuple[str, str, str, dict]] = field(default_factory=list)  # (type, src, dst, props)

    def node(self, label: str, node_id: str, **props: Any) -> str:
        self.nodes[node_id] = (label, {k: v for k, v in props.items() if v is not None})
        return node_id

    def rel(self, rel_type: str, src: str, dst: str, **props: Any) -> None:
        self.rels.append((rel_type, src, dst, props))


@lru_cache
def ensure_schema() -> None:
    for label in LABELS:
        store.run(f"CREATE INDEX hg_{label.lower()}_key IF NOT EXISTS FOR (n:{label}) ON (n.case_id, n.id)")


def _plan(case: CaseState) -> _Graph:
    g = _Graph()
    threshold = get_settings().name_match_threshold
    known: dict[str, str] = {}  # person id -> name, for decedent and beneficiaries
    by_norm: dict[str, str] = {}  # normalized name -> person id

    def person(pid: str, name: str, role: str, **props: Any) -> str:
        known[pid] = name
        by_norm.setdefault(normalize_name(name), pid)
        return g.node("Person", pid, name=name, role=role, **props)

    dec = case.decedent
    if dec:
        person(dec.id, dec.name, "decedent", date_of_birth=dec.date_of_birth.isoformat(),
               date_of_death=dec.date_of_death.isoformat())
        g.extra_labels[dec.id] = "Decedent"
    for b in case.beneficiaries:
        person(b.id, b.name, "beneficiary", date_of_birth=b.date_of_birth.isoformat(),
               relationship=b.relationship, beneficiary_id=b.id)

    ira_ids = [a.id for a in case.accounts if a.type in ("traditional_ira", "roth_ira")]
    trust_id: Optional[str] = None
    for a in case.accounts:
        g.node("Account", a.id, type=a.type, title=a.title, balance=str(a.balance), hypothetical=True)
        if a.type == "trust_owned":
            trust_id = trust_id or g.node("Trust", f"trust:{a.id}", name=a.title)
            g.rel("OWNED", trust_id, a.id)
        elif dec:
            g.rel("OWNED", dec.id, a.id)

    for b in case.beneficiaries:
        account_id = b.account_id or (ira_ids[0] if ira_ids else None)
        if account_id:
            did = g.node("Designation", f"{account_id}/{b.id}", designation=b.designation,
                         share_percent=str(b.share_percent), beneficiary_id=b.id, account_id=account_id)
            g.rel("HAS_DESIGNATION", account_id, did)
            g.rel("FOR", did, b.id)

    links = link_applications(case)

    def named_person(name: str) -> str:
        pid = by_norm.get(normalize_name(name))
        if pid:
            return pid
        pid = g.node("Person", f"person:{normalize_name(name)}", name=name, role="mentioned")
        by_norm[normalize_name(name)] = pid
        match_id, score = best_match(name, known)
        if match_id and score >= threshold:
            g.rel("POSSIBLY_SAME_AS", pid, match_id, score=round(score, 1))
        return pid

    for doc in case.documents:
        g.node("Document", doc.id, doc_type=doc.doc_type, file_ref=doc.file_ref, needs_review=doc.needs_review)
        beneficiary_id = links.get(doc.id)
        if doc.doc_type == "trust_certification" and trust_id is None:
            trust_name = field_value(doc, "trust_name") or "Trust"
            trust_id = g.node("Trust", f"trust:{normalize_name(trust_name)}", name=trust_name)

        for f in doc.fields:
            fid = g.node("Fact", fact_id(doc.id, f.name), kind=fact_kind(f.name), field_name=f.name,
                         value=f.value, confidence=f.confidence, page=f.page, document_id=doc.id)
            g.rel("PROVES", doc.id, fid)
            about = None
            if f.name in PERSON_FIELDS and f.value:
                about = named_person(f.value)
                g.rel("MENTIONS", doc.id, about, field=f.name)
                if f.name == "successor_trustee_name" and trust_id:
                    g.rel("HAS_TRUSTEE", trust_id, about)
            elif fact_kind(f.name) == "date_of_death" or (doc.doc_type == "death_certificate" and f.name == "date_of_birth"):
                about = dec.id if dec else None
            elif f.name in BENEFICIARY_FIELDS:
                about = beneficiary_id
            elif f.name in ACCOUNT_FIELDS:
                about = next((b.account_id for b in case.beneficiaries if b.id == beneficiary_id), None) or (
                    ira_ids[0] if ira_ids else None)
            elif f.name in TRUST_FIELDS:
                about = trust_id
            if about:
                g.rel("ABOUT", fid, about)
    return g


def build_case_graph(case: CaseState) -> dict[str, int]:
    """Write (or refresh) one case's graph. Returns node and relationship counts."""
    ensure_schema()
    g = _plan(case)
    cid, build = case.case_id, uuid4().hex

    by_label: dict[str, list[dict]] = defaultdict(list)
    for nid, (label, props) in g.nodes.items():
        by_label[label].append({"id": nid, "props": props})
    for label, rows in by_label.items():
        store.run(
            f"UNWIND $rows AS row MERGE (n:{label} {{case_id: $cid, id: row.id}}) "
            "SET n = row.props, n.case_id = $cid, n.id = row.id, n.build = $build",
            rows=rows, cid=cid, build=build,
        )
    for nid, label in g.extra_labels.items():
        store.run(f"MATCH (n:Person {{case_id: $cid, id: $id}}) SET n:{label}", cid=cid, id=nid)

    by_type: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for rel_type, src, dst, props in g.rels:
        by_type[(rel_type, g.nodes[src][0], g.nodes[dst][0])].append({"src": src, "dst": dst, "props": props})
    for (rel_type, src_label, dst_label), rows in by_type.items():
        store.run(
            f"UNWIND $rows AS row "
            f"MATCH (a:{src_label} {{case_id: $cid, id: row.src}}) "
            f"MATCH (b:{dst_label} {{case_id: $cid, id: row.dst}}) "
            f"MERGE (a)-[r:{rel_type}]->(b) SET r = row.props, r.build = $build",
            rows=rows, cid=cid, build=build,
        )

    store.run(
        "MATCH (a {case_id: $cid})-[r]->() WHERE r.build IS NOT NULL AND r.build <> $build "
        "AND type(r) <> 'EVALUATES' AND type(r) <> 'SOURCED_FROM' DELETE r",
        cid=cid, build=build,
    )
    store.run(
        "MATCH (n {case_id: $cid}) WHERE n.build <> $build AND NOT n:Check AND NOT n:PrefillField "
        "DETACH DELETE n",
        cid=cid, build=build,
    )
    return {"nodes": len(g.nodes), "relationships": len(g.rels)}


def delete_case_graph(case_id: str) -> None:
    store.run("MATCH (n {case_id: $cid}) DETACH DELETE n", cid=case_id)


def write_prefill(case_id: str, beneficiary_id: str, fields: Iterable[PrefillField]) -> None:
    """Replace a beneficiary's PrefillField nodes, each SOURCED_FROM its document fact (M7)."""
    store.run(
        "MATCH (p:PrefillField {case_id: $cid, beneficiary_id: $bid}) DETACH DELETE p",
        cid=case_id, bid=beneficiary_id,
    )
    rows = [
        {
            "id": f"prefill:{beneficiary_id}:{f.name}",
            "props": {"name": f.name, "value": f.value, "beneficiary_id": beneficiary_id},
            "fact": fact_id(f.source_document_id, f.source_field) if f.source_document_id and f.source_field else None,
        }
        for f in fields
    ]
    store.run(
        "UNWIND $rows AS row "
        "MERGE (p:PrefillField {case_id: $cid, id: row.id}) SET p += row.props "
        "WITH p, row WHERE row.fact IS NOT NULL "
        "MATCH (f:Fact {case_id: $cid, id: row.fact}) MERGE (p)-[:SOURCED_FROM]->(f)",
        rows=rows, cid=case_id,
    )
