"""Export one case's graph as Cytoscape.js elements."""

from __future__ import annotations

from typing import Any

from hg import store

_HIDDEN = {"case_id", "build"}
_PRIMARY = ("Decedent", "Person", "Account", "Designation", "Trust", "Document", "Fact", "Check", "PrefillField")


def _caption(kind: str, props: dict) -> str:
    if kind in ("Decedent", "Person"):
        return props.get("name", "")
    if kind == "Account":
        return props.get("title", "")
    if kind == "Designation":
        return f"{props.get('designation', '')} {props.get('share_percent', '')}%"
    if kind == "Trust":
        return props.get("name", "")
    if kind == "Document":
        return props.get("doc_type", "")
    if kind == "Fact":
        return f"{props.get('field_name', '')}: {props.get('value', '')}"
    if kind == "Check":
        return f"{props.get('rule_id', '')} ({props.get('status', '')})"
    if kind == "PrefillField":
        return f"{props.get('name', '')}: {props.get('value', '')}"
    return props.get("id", "")


def export_case_graph(case_id: str) -> dict[str, list[dict[str, Any]]]:
    """``{"nodes": [...], "edges": [...]}`` in Cytoscape element form.

    Each node's data has ``id``, ``type`` (primary label), ``label`` (caption)
    and its properties. Each edge's data has ``id``, ``source``, ``target``,
    ``label`` (relationship type) and ``status``: the evaluating check's status
    on EVALUATES edges (``fail`` edges render red), otherwise None.
    """
    node_rows = store.run(
        "MATCH (n {case_id: $cid}) RETURN n.id AS id, labels(n) AS labels, properties(n) AS props",
        cid=case_id,
    )
    edge_rows = store.run(
        "MATCH (a {case_id: $cid})-[r]->(b {case_id: $cid}) "
        "RETURN a.id AS source, b.id AS target, type(r) AS type, properties(r) AS props",
        cid=case_id,
    )

    nodes = []
    for row in sorted(node_rows, key=lambda r: r["id"]):
        kind = next((label for label in _PRIMARY if label in row["labels"]), row["labels"][0])
        props = {k: v for k, v in row["props"].items() if k not in _HIDDEN}
        nodes.append({"data": {**props, "id": row["id"], "type": kind, "label": _caption(kind, props)}})

    edges = []
    for row in sorted(edge_rows, key=lambda r: (r["type"], r["source"], r["target"])):
        props = {k: v for k, v in row["props"].items() if k not in _HIDDEN}
        status = props.pop("status", None)
        edges.append(
            {
                "data": {
                    **props,
                    "id": f"{row['type']}:{row['source']}->{row['target']}",
                    "source": row["source"],
                    "target": row["target"],
                    "label": row["type"],
                    "status": status,
                }
            }
        )
    return {"nodes": nodes, "edges": edges}
