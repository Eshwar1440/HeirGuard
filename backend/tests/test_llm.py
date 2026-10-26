"""llm.py tests. No API calls: the Anthropic client is replaced with a fake."""

import json
from types import SimpleNamespace

import pytest

from hg import llm
from hg.config import get_settings

FAKE_SSN = "123-45-6789"
FAKE_SSN_PLAIN = "987654321"


class FakeMessages:
    def __init__(self, reply_text: str, stop_reason: str = "end_turn"):
        self.reply_text = reply_text
        self.stop_reason = stop_reason
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        content = [SimpleNamespace(type="text", text=self.reply_text)] if self.reply_text else []
        return SimpleNamespace(content=content, stop_reason=self.stop_reason, model=kwargs["model"])


@pytest.fixture
def fake(monkeypatch):
    def install(reply_text: str, stop_reason: str = "end_turn") -> FakeMessages:
        messages = FakeMessages(reply_text, stop_reason)
        client = SimpleNamespace(beta=SimpleNamespace(messages=messages))
        monkeypatch.setattr(llm, "get_client", lambda: client)
        return messages

    return install


def _log_records() -> list[dict]:
    return llm.read_log()


def test_mask_ssn_patterns():
    text = f"SSN {FAKE_SSN} or {FAKE_SSN_PLAIN}; phone 972-555-0100; zip 75080; acct 12345678901"
    masked = llm.mask_ssn(text)
    assert FAKE_SSN not in masked
    assert FAKE_SSN_PLAIN not in masked
    assert masked.count(llm.SSN_MASK) == 2
    # Not SSN-shaped: left alone
    assert "972-555-0100" in masked
    assert "75080" in masked
    assert "12345678901" in masked


def test_write_text_masks_before_sending_and_in_log(fake):
    messages = fake("Your documents look complete.")
    out = llm.write_text(
        f"System note with {FAKE_SSN}",
        {"heir": "Hypothetical Heir", "ssn": FAKE_SSN, "tin": FAKE_SSN_PLAIN},
        case_id="case-1",
    )

    assert out == "Your documents look complete."
    sent = json.dumps(messages.calls[0], default=str)
    assert FAKE_SSN not in sent
    assert FAKE_SSN_PLAIN not in sent
    assert llm.SSN_MASK in sent

    log_text = "".join(p.read_text() for p in get_settings().ai_log_dir.glob("*.jsonl"))
    assert FAKE_SSN not in log_text
    assert FAKE_SSN_PLAIN not in log_text


def test_extract_json_sends_schema_and_document_block(fake):
    messages = fake(json.dumps({"doc_type": "death_certificate", "note": f"id {FAKE_SSN}"}))
    schema = {
        "type": "object",
        "properties": {"doc_type": {"type": "string"}, "note": {"type": "string"}},
        "required": ["doc_type", "note"],
        "additionalProperties": False,
    }
    pdf_block = {
        "type": "document",
        "source": {"type": "base64", "media_type": "application/pdf", "data": "JVBERi0xLjQK"},
    }
    result = llm.extract_json(
        "Extract fields.",
        [pdf_block, {"type": "text", "text": f"Holder SSN {FAKE_SSN}"}],
        schema,
        case_id="case-2",
    )

    assert result["doc_type"] == "death_certificate"
    assert FAKE_SSN not in result["note"]

    call = messages.calls[0]
    assert call["model"] == "claude-sonnet-5-5"
    assert call["output_config"]["format"] == {"type": "json_schema", "schema": schema}
    assert "tool_choice" not in call
    content = call["messages"][0]["content"]
    assert content[0] == pdf_block
    assert FAKE_SSN not in content[1]["text"]


def test_log_record_shape(fake):
    fake("ok")
    llm.write_text("sys", {"a": 1}, case_id="case-3")
    [record] = _log_records()
    assert record["function"] == "write_text"
    assert record["case_id"] == "case-3"
    assert record["model"] == "claude-sonnet-5-5"
    assert record["prompt"]["system"] == "sys"
    assert record["prompt"]["input_summary"] == '{"a": 1}'
    assert record["output"] == "ok"
    assert isinstance(record["latency_ms"], int)
    assert record["timestamp"]


def test_document_blocks_are_summarized_not_logged_in_full(fake):
    fake(json.dumps({"x": "y"}))
    data = "A" * 50000
    llm.extract_json(
        "sys",
        [{"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": data}}],
        {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"], "additionalProperties": False},
    )
    [record] = _log_records()
    assert "50000 base64 chars" in record["prompt"]["input_summary"]
    assert data not in json.dumps(record)


def test_read_log_filters_by_case(fake):
    fake("ok")
    llm.write_text("sys", "a", case_id="case-a")
    llm.write_text("sys", "b", case_id="case-b")
    assert [r["case_id"] for r in llm.read_log("case-b")] == ["case-b"]
    assert len(llm.read_log()) == 2


def test_refusal_raises_and_is_logged(fake):
    fake("", stop_reason="refusal")
    with pytest.raises(llm.LLMRefusalError):
        llm.write_text("sys", "x", case_id="case-r")
    [record] = _log_records()
    assert record["stop_reason"] == "refusal"
    assert "LLMRefusalError" in record["error"]


def test_truncated_json_raises(fake):
    fake('{"doc_type": "dea', stop_reason="max_tokens")
    with pytest.raises(llm.LLMError):
        llm.extract_json("sys", [{"type": "text", "text": "x"}], {"type": "object"})
