"""Packet rules. Each rule returns ``list[CheckResult]`` under a stable ``rule_id``.

Scope: each result names the beneficiary it concerns, so one heir's problem
never blocks another. ``beneficiary_id=None`` means the whole case (an account
with no beneficiaries, or a case with no beneficiaries yet). A beneficiary is
clear when their own results and every case-wide result pass.

Shares, names and dates of death are read from the case graph with Cypher, so
``hg.graph.build_case_graph`` must run first. Messages are plain facts; the
writer (M5) turns them into friendly text.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Callable, Optional

from hg import store
from hg.checker.requirements import Requirement, requirements_for
from hg.config import get_settings
from hg.graph.resolve import field_value, link_applications
from hg.schemas import Account, Beneficiary, CaseState, CheckResult, Evidence

APP = "inherited_ira_application"


def _targets(case: CaseState) -> list[Optional[str]]:
    return [b.id for b in case.beneficiaries] or [None]


def _ev(document_id: str, field_name: str = "") -> Evidence:
    return Evidence(document_id=document_id, field_name=field_name)


def _pct(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _label(doc_type: str) -> str:
    return doc_type.replace("_", " ").replace("ira ", "IRA ")


def _account_for(case: CaseState, b: Beneficiary) -> Optional[Account]:
    if b.account_id:
        return next((a for a in case.accounts if a.id == b.account_id), None)
    iras = [a for a in case.accounts if a.type in ("traditional_ira", "roth_ira")]
    return (iras or case.accounts or [None])[0]


def _applications_by_beneficiary(case: CaseState) -> dict[Optional[str], list[str]]:
    out: dict[Optional[str], list[str]] = defaultdict(list)
    for doc_id, bid in link_applications(case).items():
        out[bid].append(doc_id)
    return out


# --- required_docs_present ---------------------------------------------------


def _missing_message(missing: list[Requirement], title: str, who: Optional[str] = None) -> str:
    parts = [
        _label(r.doc_type) + (" (requirement is hypothetical)" if r.hypothetical else "")
        for r in missing
    ]
    scope = f"{who} on {title}" if who else title
    return f"Missing for {scope}: " + ", ".join(parts) + "."


def required_docs_present(case: CaseState) -> list[CheckResult]:
    rule = "required_docs_present"
    apps = _applications_by_beneficiary(case)
    by_type: dict[str, list[str]] = defaultdict(list)
    for doc in case.documents:
        by_type[doc.doc_type].append(doc.id)

    def evaluate(reqs: list[Requirement], beneficiary_id: Optional[str]) -> tuple[list[Requirement], list[Evidence]]:
        missing, evidence = [], []
        for r in reqs:
            found = apps.get(beneficiary_id, []) if r.per_beneficiary else by_type[r.doc_type]
            if found:
                evidence += [_ev(d) for d in found]
            else:
                missing.append(r)
        return missing, evidence

    results, covered = [], set()
    for b in case.beneficiaries:
        account = _account_for(case, b)
        if account:
            covered.add(account.id)
        missing, evidence = evaluate(requirements_for(account.type) if account else [], b.id)
        title = account.title if account else "the account"
        results.append(
            CheckResult(
                rule_id=rule,
                status="fail" if missing else "pass",
                message=_missing_message(missing, title, b.name) if missing
                else f"All required documents for {b.name} on {title} are present.",
                beneficiary_id=b.id,
                evidence=evidence,
            )
        )
    for account in case.accounts:
        if account.id in covered:
            continue
        reqs = [r for r in requirements_for(account.type) if not r.per_beneficiary]
        missing, evidence = evaluate(reqs, None)
        results.append(
            CheckResult(
                rule_id=rule,
                status="fail" if missing else "pass",
                message=_missing_message(missing, account.title) if missing
                else f"All required documents for {account.title} are present.",
                evidence=evidence,
            )
        )
    if not results:
        has_cert = bool(by_type["death_certificate"])
        results.append(
            CheckResult(
                rule_id=rule,
                status="pass" if has_cert else "fail",
                message="A death certificate is present." if has_cert else "Missing: death certificate.",
                evidence=[_ev(d) for d in by_type["death_certificate"]],
            )
        )
    return results


# --- shares_total_100 --------------------------------------------------------


def shares_total_100(case: CaseState) -> list[CheckResult]:
    rows = store.run(
        "MATCH (a:Account {case_id: $cid})-[:HAS_DESIGNATION]->(g:Designation {designation: 'primary'}) "
        "RETURN a.id AS account_id, a.title AS title, "
        "collect({beneficiary_id: g.beneficiary_id, share: g.share_percent}) AS designations "
        "ORDER BY account_id",
        cid=case.case_id,
    )
    apps = _applications_by_beneficiary(case)
    results = []
    for row in rows:
        designations = row["designations"]
        total = sum((Decimal(d["share"]) for d in designations), Decimal(0))
        ok = total == 100
        message = f"Primary beneficiary shares on {row['title']} total {_pct(total)}%."
        if not ok:
            message += " They must total exactly 100%."
        evidence = [_ev(doc, "share_percent") for d in designations for doc in apps.get(d["beneficiary_id"], [])]
        for d in sorted(designations, key=lambda d: d["beneficiary_id"]):
            results.append(
                CheckResult(
                    rule_id="shares_total_100",
                    status="pass" if ok else "fail",
                    message=message,
                    beneficiary_id=d["beneficiary_id"],
                    evidence=evidence,
                )
            )
    return results


# --- name_match --------------------------------------------------------------


def name_match(case: CaseState) -> list[CheckResult]:
    rule = "name_match"
    apps = _applications_by_beneficiary(case)
    results = []
    for b in case.beneficiaries:
        fuzzy = store.run(
            "MATCH (b:Person {case_id: $cid, id: $bid})<-[s:POSSIBLY_SAME_AS]-(p:Person)<-[m:MENTIONS]-(d:Document) "
            "RETURN d.id AS doc, d.doc_type AS doc_type, m.field AS field, p.name AS name, s.score AS score "
            "ORDER BY doc, field",
            cid=case.case_id, bid=b.id,
        )
        exact = store.run(
            "MATCH (b:Person {case_id: $cid, id: $bid})<-[m:MENTIONS]-(d:Document) "
            "RETURN d.id AS doc, m.field AS field ORDER BY doc, field",
            cid=case.case_id, bid=b.id,
        )
        if fuzzy:
            parts = [
                f"\"{r['name']}\" on the {_label(r['doc_type'])} ({r['score']:.0f}% similar)" for r in fuzzy
            ]
            results.append(
                CheckResult(
                    rule_id=rule,
                    status="needs_review",
                    message=f"{b.name} appears as " + "; ".join(parts) + ". Confirm it is the same person.",
                    beneficiary_id=b.id,
                    evidence=[_ev(r["doc"], r["field"]) for r in fuzzy],
                )
            )
        elif not apps.get(b.id):
            results.append(
                CheckResult(
                    rule_id=rule,
                    status="pass",
                    message=f"No application for {b.name} yet, so there is no name to compare.",
                    beneficiary_id=b.id,
                )
            )
        else:
            docs = sorted({r["doc"] for r in exact})
            results.append(
                CheckResult(
                    rule_id=rule,
                    status="pass",
                    message=f"{b.name} is named exactly the same on {len(docs)} document(s).",
                    beneficiary_id=b.id,
                    evidence=[_ev(r["doc"], r["field"]) for r in exact],
                )
            )
    for doc_id in apps.get(None, []):
        doc = next(d for d in case.documents if d.id == doc_id)
        applicant = field_value(doc, "beneficiary_name") or "an unreadable name"
        results.append(
            CheckResult(
                rule_id=rule,
                status="fail",
                message=f"An application names {applicant}, who does not match any listed beneficiary.",
                evidence=[_ev(doc_id, "beneficiary_name")],
            )
        )
    return results


# --- dod_consistent ----------------------------------------------------------


def dod_consistent(case: CaseState) -> list[CheckResult]:
    rows = store.run(
        "MATCH (d:Document {case_id: $cid})-[:PROVES]->(f:Fact {kind: 'date_of_death'}) "
        "WHERE f.value IS NOT NULL "
        "RETURN d.id AS doc, d.doc_type AS doc_type, f.field_name AS field, f.value AS value "
        "ORDER BY doc",
        cid=case.case_id,
    )
    links = link_applications(case)
    on_certificate = [r for r in rows if r["doc_type"] == "death_certificate"]
    if on_certificate:
        reference, ref_rows = on_certificate[0]["value"], on_certificate[:1]
    elif case.decedent:
        reference, ref_rows = case.decedent.date_of_death.isoformat(), []
    elif rows:
        reference, ref_rows = rows[0]["value"], rows[:1]
    else:
        return [
            CheckResult(rule_id="dod_consistent", status="pass", message="No date of death found yet.",
                        beneficiary_id=t)
            for t in _targets(case)
        ]

    disagree = [r for r in rows if r["value"] != reference]
    case_wide = [r for r in disagree if links.get(r["doc"]) is None]
    results = []
    for target in _targets(case):
        bad = case_wide + [r for r in disagree if target is not None and links.get(r["doc"]) == target]
        if bad:
            parts = [f"{r['value']} on the {_label(r['doc_type'])}" for r in bad]
            message = f"The date of death reads {reference} on the death certificate but " + ", ".join(parts) + "."
        else:
            message = f"Every document gives the same date of death, {reference}."
        results.append(
            CheckResult(
                rule_id="dod_consistent",
                status="fail" if bad else "pass",
                message=message,
                beneficiary_id=target,
                evidence=[_ev(r["doc"], r["field"]) for r in ref_rows + bad],
            )
        )
    return results


# --- certified_copy ----------------------------------------------------------


def certified_copy(case: CaseState) -> list[CheckResult]:
    certs = [d for d in case.documents if d.doc_type == "death_certificate"]
    values = [field_value(d, "certified_copy") for d in certs]
    if not certs:
        status, message = "needs_review", "No death certificate has been uploaded yet."
    elif "yes" in values:
        status, message = "pass", "The death certificate is a certified copy."
    elif None in values:
        status, message = "needs_review", "Could not tell whether the death certificate is a certified copy."
    else:
        status, message = "fail", "The death certificate is a photocopy, not a certified copy."
    evidence = [_ev(d.id, "certified_copy") for d in certs]
    return [
        CheckResult(rule_id="certified_copy", status=status, message=message, beneficiary_id=t, evidence=evidence)
        for t in _targets(case)
    ]


# --- field_review ------------------------------------------------------------


def field_review(case: CaseState) -> list[CheckResult]:
    threshold = get_settings().confidence_threshold
    links = link_applications(case)
    results = []
    for target in _targets(case):
        docs = [
            d for d in case.documents
            if target is None or d.doc_type != APP or links.get(d.id) == target
        ]
        flagged = [
            (d, f) for d in docs for f in d.fields if f.value is None or f.confidence < threshold
        ]
        unflagged_docs = [d for d in docs if d.needs_review and not any(fd is d for fd, _ in flagged)]
        if flagged or unflagged_docs:
            names = [f"{f.name} on the {_label(d.doc_type)}" for d, f in flagged]
            names += [f"the {_label(d.doc_type)}" for d in unflagged_docs]
            message = "These need a second look: " + ", ".join(names) + "."
            status = "needs_review"
        else:
            message, status = "Every field was read with high confidence.", "pass"
        results.append(
            CheckResult(
                rule_id="field_review",
                status=status,
                message=message,
                beneficiary_id=target,
                evidence=[_ev(d.id, f.name) for d, f in flagged] + [_ev(d.id) for d in unflagged_docs],
            )
        )
    return results


RULES: dict[str, Callable[[CaseState], list[CheckResult]]] = {
    "required_docs_present": required_docs_present,
    "shares_total_100": shares_total_100,
    "name_match": name_match,
    "dod_consistent": dod_consistent,
    "certified_copy": certified_copy,
    "field_review": field_review,
}
