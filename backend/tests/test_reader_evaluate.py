"""The evaluation report counts hits, caught misses and silent misses honestly (LLM mocked)."""

from hg.config import get_settings
from hg.reader import evaluate
from hg.schemas import Document

PACKETS = get_settings().data_dir / "packets"


def _fake_reader(overrides: dict[tuple[str, str], tuple], fail: set[str] = frozenset()):
    """Return truth values, except (doc_type, field) -> (value, confidence) overrides."""
    from hg.data_gen import load_truth

    truth_docs = {}
    for pid in ("packet_06", "packet_07"):
        for d in load_truth(PACKETS / pid).documents:
            truth_docs[(f"eval-{pid}", d.file_ref.split("/")[-1])] = d

    def read(case_id, data, filename):
        if filename in fail:
            raise RuntimeError("simulated API failure")
        truth = truth_docs[(case_id, filename)]
        fields = []
        for f in truth.fields:
            value, confidence = overrides.get((truth.doc_type, f.name), (f.value, 0.95))
            fields.append(f.model_copy(update={"value": value, "confidence": confidence}))
        return Document(id="x", case_id=case_id, file_ref=filename, doc_type=truth.doc_type, fields=fields)

    return read


def test_report_separates_caught_and_silent_misses(monkeypatch, tmp_path):
    monkeypatch.setattr(
        evaluate,
        "read_document",
        _fake_reader(
            {
                ("death_certificate", "certificate_number"): ("WRONG-123", 0.97),  # silent
                ("letters_testamentary", "case_number"): (None, 0.1),  # caught
            },
            fail={"affidavit_of_domicile.pdf"},
        ),
    )
    results, truths = evaluate.run(PACKETS, ["packet_06", "packet_07"], workers=2)
    report = evaluate.render(results, truths)

    assert "| **Wrong values with high confidence (silent errors)** | **2** |" in report  # one per packet
    assert "| Documents that failed to read | 1 |" in report
    assert "WRONG-123" in report and "**no (silent)**" in report
    assert "simulated API failure" in report
    # Planted errors that live in fields are checked "as printed".
    assert "| packet_06 | certified_copy | certified_copy | no | no | yes |" in report
    assert "| packet_07 | dod_consistent | date_of_death |" in report


def test_perfect_reader_scores_100_percent(monkeypatch):
    monkeypatch.setattr(evaluate, "read_document", _fake_reader({}))
    results, truths = evaluate.run(PACKETS, ["packet_06"], workers=1)
    report = evaluate.render(results, truths)
    fields = sum(len(r.fields) for r in results)
    assert f"| Fields correct | {fields}/{fields} (100.0%) |" in report
    assert "No misses." in report
    assert "## Limits of this test" in report and "best case" in report
