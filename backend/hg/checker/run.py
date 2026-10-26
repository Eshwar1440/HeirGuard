"""Run every packet rule, record the results in the case graph, return them."""

from __future__ import annotations

from collections import Counter
from typing import Optional

from hg import store
from hg.checker.rules import RULES
from hg.graph.build import fact_id
from hg.schemas import CaseState, CheckResult


def run_checks(case: CaseState) -> list[CheckResult]:
    """Evaluate all rules. The case graph must already be built for this case."""
    results = [result for rule in RULES.values() for result in rule(case)]
    write_checks(case.case_id, results)
    return results


def write_checks(case_id: str, results: list[CheckResult]) -> None:
    """Replace the case's Check nodes and their EVALUATES edges."""
    store.run("MATCH (c:Check {case_id: $cid}) DETACH DELETE c", cid=case_id)
    seen: Counter = Counter()
    checks, edges = [], []
    for r in results:
        key = (r.rule_id, r.beneficiary_id or "case")
        check_id = f"check:{key[0]}:{key[1]}:{seen[key]}"
        seen[key] += 1
        checks.append(
            {
                "id": check_id,
                "props": {
                    "rule_id": r.rule_id,
                    "status": r.status,
                    "message": r.message,
                    "beneficiary_id": r.beneficiary_id,
                },
            }
        )
        targets = {fact_id(e.document_id, e.field_name) if e.field_name else e.document_id for e in r.evidence}
        if r.beneficiary_id:
            targets.add(r.beneficiary_id)
        edges += [{"check": check_id, "target": t, "status": r.status} for t in sorted(targets)]

    store.run(
        "UNWIND $rows AS row CREATE (c:Check {case_id: $cid, id: row.id}) SET c += row.props",
        rows=checks, cid=case_id,
    )
    store.run(
        "UNWIND $rows AS row "
        "MATCH (c:Check {case_id: $cid, id: row.check}) "
        "MATCH (t {case_id: $cid, id: row.target}) WHERE t:Fact OR t:Document OR t:Person "
        "MERGE (c)-[e:EVALUATES]->(t) SET e.status = row.status",
        rows=edges, cid=case_id,
    )


def blocking(results: list[CheckResult], beneficiary_id: Optional[str]) -> list[CheckResult]:
    """Results that stop this beneficiary: their own non-passing ones plus case-wide ones."""
    return [r for r in results if r.status != "pass" and r.beneficiary_id in (beneficiary_id, None)]
