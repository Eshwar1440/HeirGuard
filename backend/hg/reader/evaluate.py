"""AI-log check #1: extraction accuracy of the reader against the M1 truth files.

    python -m hg.reader.evaluate [--packets packet_01_flawed packet_10] [--workers 4]

Reads every document in every packet with the real model (through hg.llm, so each
call is logged), compares each field with truth.json, and writes
ai_log/extraction_accuracy.md. The report shows misses as plainly as hits.
"""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from hg.config import get_settings
from hg.data_gen.packets import PACKETS, load_truth
from hg.data_gen.truth import PacketTruth
from hg.reader.read import read_document
from hg.reader.vocab import fields_for
from hg.schemas import Document


@dataclass
class FieldResult:
    packet_id: str
    document_id: str
    doc_type: str
    field: str
    expected: Optional[str]
    got: Optional[str]
    confidence: float
    correct: bool
    flagged: bool


@dataclass
class DocResult:
    packet_id: str
    document_id: str
    doc_type: str
    got_type: Optional[str]
    needs_review: Optional[bool]
    error: Optional[str] = None
    fields: list[FieldResult] = field(default_factory=list)


def _same(expected: Optional[str], got: Optional[str], kind: str) -> bool:
    if expected is None or got is None:
        return expected is got
    a, b = " ".join(expected.split()), " ".join(got.split())
    return a.casefold() == b.casefold() if kind == "text" else a == b


def score(truth_doc: Document, predicted: Document, packet_id: str, threshold: float) -> DocResult:
    by_name = {f.name: f for f in predicted.fields} if predicted.doc_type == truth_doc.doc_type else {}
    kinds = {f.name: f.kind for f in fields_for(truth_doc.doc_type)}
    result = DocResult(packet_id, truth_doc.id, truth_doc.doc_type, predicted.doc_type, predicted.needs_review)
    for f in truth_doc.fields:
        got = by_name.get(f.name)
        value, confidence = (got.value, got.confidence) if got else (None, 0.0)
        result.fields.append(
            FieldResult(
                packet_id, truth_doc.id, truth_doc.doc_type, f.name, f.value, value, confidence,
                correct=_same(f.value, value, kinds.get(f.name, "text")),
                flagged=value is None or confidence < threshold,
            )
        )
    return result


def _jobs(packets_dir: Path, packet_ids: Optional[list[str]]) -> list[tuple[PacketTruth, Document, bytes]]:
    ids = packet_ids or [spec.packet_id for spec in PACKETS]
    jobs = []
    for pid in ids:
        truth = load_truth(packets_dir / pid)
        for doc in truth.documents:
            jobs.append((truth, doc, (packets_dir / doc.file_ref).read_bytes()))
    return jobs


def run(packets_dir: Path, packet_ids: Optional[list[str]] = None, workers: int = 4) -> tuple[list[DocResult], list[PacketTruth]]:
    threshold = get_settings().confidence_threshold
    jobs = _jobs(packets_dir, packet_ids)

    def one(job: tuple[PacketTruth, Document, bytes]) -> DocResult:
        truth, doc, data = job
        try:
            predicted = read_document(f"eval-{truth.packet_id}", data, Path(doc.file_ref).name)
        except Exception as exc:  # report every failure; never hide one
            return DocResult(truth.packet_id, doc.id, doc.doc_type, None, None, error=f"{type(exc).__name__}: {exc}")
        return score(doc, predicted, truth.packet_id, threshold)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(one, jobs))
    truths = list({job[0].packet_id: job[0] for job in jobs}.values())
    return results, truths


# --- Report --------------------------------------------------------------------


def _pct(n: int, d: int) -> str:
    return f"{n}/{d} ({100 * n / d:.1f}%)" if d else "n/a"


def _cell(value: Optional[str]) -> str:
    return "*(null)*" if value is None else value.replace("|", "\\|")


_PLANT_FIELD = re.compile(r"^(\w+)\.(\w+) reads")


def _planted_checks(truths: list[PacketTruth], results: list[DocResult]) -> list[tuple[str, str, str, FieldResult]]:
    """For each planted error that lives in a document field, did the reader read it as printed?"""
    fields = {(r.document_id, f.field): f for r in results for f in r.fields}
    out = []
    for truth in truths:
        for p in truth.planted_error_details:
            if not p.document_id:
                continue
            if p.rule_id == "certified_copy":
                name = "certified_copy"
            else:
                match = _PLANT_FIELD.match(p.note)
                if not match:
                    continue
                name = match.group(2)
            if (p.document_id, name) in fields:
                out.append((truth.packet_id, p.rule_id, name, fields[(p.document_id, name)]))
    return out


def render(results: list[DocResult], truths: list[PacketTruth]) -> str:
    settings = get_settings()
    threshold = settings.confidence_threshold
    done = [r for r in results if r.error is None]
    failed = [r for r in results if r.error is not None]
    all_fields = [f for r in done for f in r.fields]
    wrong = [f for f in all_fields if not f.correct]
    silent = [f for f in wrong if not f.flagged]
    caught = [f for f in wrong if f.flagged]
    false_alarms = [f for f in all_fields if f.correct and f.flagged]

    lines = [
        "# Extraction accuracy (AI-log check #1)",
        "",
        "> All documents are synthetic specimens with hypothetical data. Ground truth is each packet's "
        "`truth.json` from the M1 generator.",
        "",
        f"- Run: {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
        f"- Model: `{settings.anthropic_model}` via `hg.llm.extract_json` (every call is in `ai_log/*.jsonl`)",
        f"- Packets: {len(truths)}; documents: {len(results)}; fields scored: {len(all_fields)}",
        f"- Review threshold: confidence below {threshold} (CONFIDENCE_THRESHOLD, hypothetical) or a null value",
        "- The file name is not sent to the model. Text values are compared ignoring case and extra spaces; "
        "all other values must match exactly after normalization.",
        "",
        "## Summary",
        "",
        "| Measure | Result |",
        "|---|---|",
        f"| Document type correct | {_pct(sum(r.got_type == r.doc_type for r in done), len(done))} |",
        f"| Fields correct | {_pct(len(all_fields) - len(wrong), len(all_fields))} |",
        f"| Wrong values flagged for review (caught) | {_pct(len(caught), len(wrong))} |",
        f"| **Wrong values with high confidence (silent errors)** | **{len(silent)}** |",
        f"| Correct values flagged anyway (false alarms) | {len(false_alarms)} |",
        f"| Documents that failed to read | {len(failed)} |",
        "",
        "## By document type",
        "",
        "| Document type | Documents | Type correct | Fields correct | Flagged for review |",
        "|---|---|---|---|---|",
    ]
    by_type: dict[str, list[DocResult]] = defaultdict(list)
    for r in done:
        by_type[r.doc_type].append(r)
    for doc_type in sorted(by_type):
        rs = by_type[doc_type]
        fs = [f for r in rs for f in r.fields]
        lines.append(
            f"| {doc_type} | {len(rs)} | {_pct(sum(r.got_type == doc_type for r in rs), len(rs))} | "
            f"{_pct(sum(f.correct for f in fs), len(fs))} | {sum(bool(r.needs_review) for r in rs)} |"
        )

    lines += ["", "## By field", "", "| Field | Correct | Mean confidence |", "|---|---|---|"]
    by_field: dict[str, list[FieldResult]] = defaultdict(list)
    for f in all_fields:
        by_field[f"{f.doc_type}.{f.field}"].append(f)
    for key in sorted(by_field):
        fs = by_field[key]
        lines.append(f"| {key} | {_pct(sum(f.correct for f in fs), len(fs))} | {sum(f.confidence for f in fs) / len(fs):.2f} |")

    lines += [
        "",
        "## Planted errors: read as printed?",
        "",
        "The reader must report a planted error exactly as printed (not silently fix it), so the checker can catch it.",
        "",
        "| Packet | Rule | Field | Printed | Read | As printed |",
        "|---|---|---|---|---|---|",
    ]
    for pid, rule, name, f in _planted_checks(truths, done):
        lines.append(f"| {pid} | {rule} | {name} | {_cell(f.expected)} | {_cell(f.got)} | {'yes' if f.correct else '**no**'} |")

    lines += ["", "## Every miss", ""]
    if wrong:
        lines += [
            "| Packet | Document | Field | Expected | Read | Confidence | Flagged |",
            "|---|---|---|---|---|---|---|",
        ]
        for f in sorted(wrong, key=lambda f: (f.packet_id, f.document_id, f.field)):
            lines.append(
                f"| {f.packet_id} | {f.document_id} | {f.field} | {_cell(f.expected)} | {_cell(f.got)} | "
                f"{f.confidence:.2f} | {'yes' if f.flagged else '**no (silent)**'} |"
            )
    else:
        lines.append("No misses.")

    wrong_type = [r for r in done if r.got_type != r.doc_type]
    if wrong_type:
        lines += ["", "## Wrong document type", "", "| Packet | Document | Expected | Read |", "|---|---|---|---|"]
        lines += [f"| {r.packet_id} | {r.document_id} | {r.doc_type} | {r.got_type} |" for r in wrong_type]
    if failed:
        lines += ["", "## Failed reads", "", "| Packet | Document | Error |", "|---|---|---|"]
        lines += [f"| {r.packet_id} | {r.document_id} | {_cell(r.error)} |" for r in failed]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Score the document reader against the M1 truth files.")
    parser.add_argument("--packets", nargs="*", help="packet ids (default: all)")
    parser.add_argument("--packets-dir", type=Path, default=get_settings().data_dir / "packets")
    parser.add_argument("--out", type=Path, default=get_settings().ai_log_dir / "extraction_accuracy.md")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    results, truths = run(args.packets_dir, args.packets, args.workers)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(results, truths), encoding="utf-8")
    fields = [f for r in results for f in r.fields]
    print(f"{sum(f.correct for f in fields)}/{len(fields)} fields correct; "
          f"{sum(r.error is not None for r in results)} failed reads. Report: {args.out}")


if __name__ == "__main__":
    main()
