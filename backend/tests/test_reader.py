"""M2 reader tests. The LLM is mocked; no API calls."""

import json

import pytest

from hg.config import get_settings
from hg.data_gen import load_truth
from hg.reader import read as reader
from hg.reader.vocab import ALL_FIELD_NAMES, fields_for

PACKETS = get_settings().data_dir / "packets"


def _truth_reply(doc) -> dict:
    """What a perfect reader would return for a truth document."""
    return {
        "doc_type": doc.doc_type,
        "fields": [{"name": f.name, "value": f.value, "confidence": 0.97, "page": f.page} for f in doc.fields],
    }


@pytest.fixture
def mock_llm(monkeypatch):
    calls = []

    def install(reply: dict):
        def fake_extract_json(system, content_blocks, json_schema, *, case_id=None):
            calls.append({"system": system, "blocks": content_blocks, "schema": json_schema, "case_id": case_id})
            return reply

        monkeypatch.setattr(reader, "extract_json", fake_extract_json)
        return calls

    return install


def _pdf(packet: str, name: str) -> bytes:
    return (PACKETS / packet / name).read_bytes()


def _walk_objects(schema):
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            yield schema
        for value in schema.values():
            yield from _walk_objects(value)
    elif isinstance(schema, list):
        for value in schema:
            yield from _walk_objects(value)


def test_schema_is_valid_for_structured_outputs():
    schema = reader.extraction_schema()
    for obj in _walk_objects(schema):
        assert obj["additionalProperties"] is False
        assert set(obj["required"]) == set(obj["properties"])
    text = json.dumps(schema)
    for unsupported in ("minimum", "maximum", "minLength", "maxLength"):
        assert unsupported not in text
    assert schema["properties"]["fields"]["items"]["properties"]["name"]["enum"] == list(ALL_FIELD_NAMES)


def test_reads_a_packet_document(mock_llm):
    truth = load_truth(PACKETS / "packet_10")
    cert = next(d for d in truth.documents if d.doc_type == "death_certificate")
    calls = mock_llm(_truth_reply(cert))

    doc = reader.read_document("case-x", _pdf("packet_10", "death_certificate.pdf"), "death_certificate.pdf")

    assert doc.doc_type == "death_certificate" and doc.case_id == "case-x"
    assert [(f.name, f.value) for f in doc.fields] == [(f.name, f.value) for f in cert.fields]
    assert doc.needs_review is False
    assert doc.file_ref == "packets/case-x/death_certificate.pdf"

    call = calls[0]
    assert call["case_id"] == "case-x"
    assert call["blocks"][0]["type"] == "document"
    assert call["blocks"][0]["source"]["media_type"] == "application/pdf"
    assert "death_certificate.pdf" not in json.dumps(call["blocks"][1])  # no filename hint
    assert "Never guess" in call["system"]
    assert "COPY - NOT CERTIFIED" not in call["system"]  # real photocopies carry no such stamp
    assert "VOID" in call["system"] and "uncertified" in call["system"]


def test_low_confidence_field_sets_needs_review(mock_llm):
    reply = _truth_reply(next(d for d in load_truth(PACKETS / "packet_10").documents if d.doc_type == "death_certificate"))
    reply["fields"][2]["confidence"] = 0.4
    mock_llm(reply)
    doc = reader.read_document("c", _pdf("packet_10", "death_certificate.pdf"), "x.pdf")
    assert doc.needs_review is True
    assert doc.fields[2].confidence == 0.4


def test_unknown_doc_type_returns_no_fields_and_needs_review(mock_llm):
    mock_llm({"doc_type": "unknown", "fields": [{"name": "decedent_name", "value": "X", "confidence": 0.9, "page": 1}]})
    doc = reader.read_document("c", _pdf("packet_10", "death_certificate.pdf"), "x.pdf")
    assert doc.doc_type == "unknown" and doc.fields == [] and doc.needs_review is True


def test_invalid_doc_type_falls_back_to_unknown(mock_llm):
    mock_llm({"doc_type": "passport", "fields": []})
    assert reader.read_document("c", _pdf("packet_10", "death_certificate.pdf"), "x.pdf").doc_type == "unknown"


def test_missing_fields_are_null_and_foreign_fields_dropped(mock_llm):
    mock_llm(
        {
            "doc_type": "letters_testamentary",
            "fields": [
                {"name": "executor_name", "value": "Hypothetical Executor", "confidence": 0.95, "page": 1},
                {"name": "share_percent", "value": "50", "confidence": 0.99, "page": 1},  # not on letters
            ],
        }
    )
    doc = reader.read_document("c", _pdf("packet_10", "letters_testamentary.pdf"), "x.pdf")
    assert [f.name for f in doc.fields] == [s.name for s in fields_for("letters_testamentary")]
    by_name = {f.name: f for f in doc.fields}
    assert by_name["executor_name"].value == "Hypothetical Executor"
    assert by_name["date_of_death"].value is None and by_name["date_of_death"].confidence == 0.0
    assert doc.needs_review is True


def test_values_are_normalized_and_confidence_clamped(mock_llm):
    mock_llm(
        {
            "doc_type": "inherited_ira_application",
            "fields": [
                {"name": "decedent_date_of_death", "value": "04/30/2025", "confidence": 1.7, "page": 1},
                {"name": "account_type", "value": "Traditional IRA", "confidence": 0.95, "page": 1},
                {"name": "relationship", "value": "Child", "confidence": 0.95, "page": 1},
                {"name": "share_percent", "value": "49.50%", "confidence": 0.95, "page": 1},
                {"name": "signature_date", "value": "sometime in spring", "confidence": 0.95, "page": 0},
                {"name": "beneficiary_name", "value": "  Hypothetical   Heir ", "confidence": -0.2, "page": 1},
            ],
        }
    )
    doc = reader.read_document("c", _pdf("packet_10", "inherited_ira_application_b1.pdf"), "x.pdf")
    by_name = {f.name: f for f in doc.fields}
    assert by_name["decedent_date_of_death"].value == "2025-04-30" and by_name["decedent_date_of_death"].confidence == 1.0
    assert by_name["account_type"].value == "traditional_ira"
    assert by_name["relationship"].value == "child"
    assert by_name["share_percent"].value == "49.5"
    # Unparseable values are kept as read but capped below the review threshold.
    assert by_name["signature_date"].value == "sometime in spring"
    assert by_name["signature_date"].confidence <= reader.UNPARSED_CONFIDENCE
    assert by_name["signature_date"].page == 1
    assert by_name["beneficiary_name"].value == "Hypothetical Heir" and by_name["beneficiary_name"].confidence == 0.0


def test_images_and_unsupported_files():
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
    assert reader.file_block(png)["type"] == "image"
    assert reader.file_block(png)["source"]["media_type"] == "image/png"
    with pytest.raises(reader.UnsupportedFileError):
        reader.file_block(b"hello, not a document")


def test_document_id_is_stable_per_file():
    data = _pdf("packet_10", "death_certificate.pdf")
    assert reader.document_id("c", "Death Certificate.PDF", data) == reader.document_id("c", "Death Certificate.PDF", data)
    assert reader.document_id("c", "Death Certificate.PDF", data).startswith("c-death_certificate-")
    assert reader.document_id("c", "a.pdf", data) != reader.document_id("c", "a.pdf", data + b" ")
