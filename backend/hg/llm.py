"""The only place that calls the Anthropic API.

AI does two jobs in HeritageGuard: reading documents (M2, ``extract_json``) and
writing plain English (M5, ``write_text``). Every call:

* masks SSN-like patterns in all text before it is sent (and in what comes back),
* appends one JSONL record to ``ai_log/YYYY-MM-DD.jsonl``.

Notes on the API surface for ``claude-sonnet-5-5``:

* Forced tool use (``tool_choice`` of type ``tool``/``any``) is rejected by this
  model, so ``extract_json`` uses structured outputs (``output_config.format``
  with a JSON schema), which guarantees the reply is valid JSON for the schema.
  Object schemas must set ``additionalProperties: false``.
* Sampling parameters (``temperature`` etc.) are not accepted; depth is set with
  ``output_config.effort``.
* Requests opt into server-side refusal fallback (``fallbacks: "default"``). A
  refusal that survives the fallback raises ``LLMRefusalError``.
* Masking covers text blocks only. Text inside PDFs or images cannot be masked;
  the project only ever sends synthetic documents.
"""

from __future__ import annotations

import json
import re
import threading
import time
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Optional

import anthropic

from hg.config import get_settings

MAX_TOKENS = 16000
EXTRACT_EFFORT = "medium"
WRITE_EFFORT = "medium"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
INPUT_SUMMARY_CHARS = 2000

SSN_MASK = "[SSN-MASKED]"
_SSN_PATTERNS = (
    re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)"),
    re.compile(r"(?<!\d)\d{9}(?!\d)"),
)

_log_lock = threading.Lock()


class LLMError(RuntimeError):
    """The model returned something unusable (truncated, empty, not JSON)."""


class LLMRefusalError(LLMError):
    """The model (and its fallback) declined the request."""


# --- Masking -----------------------------------------------------------------


def mask_ssn(text: str) -> str:
    for pattern in _SSN_PATTERNS:
        text = pattern.sub(SSN_MASK, text)
    return text


def _mask_value(value: Any) -> Any:
    if isinstance(value, str):
        return mask_ssn(value)
    if isinstance(value, dict):
        return {k: _mask_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_mask_value(v) for v in value]
    return value


def _mask_blocks(blocks: list[dict]) -> list[dict]:
    masked = []
    for block in blocks:
        if block.get("type") == "text":
            block = {**block, "text": mask_ssn(block["text"])}
        masked.append(block)
    return masked


# --- Client and logging ------------------------------------------------------


@lru_cache
def get_client() -> anthropic.Anthropic:
    key = get_settings().anthropic_api_key or None
    return anthropic.Anthropic(api_key=key)


def _summarize_blocks(blocks: list[dict]) -> str:
    parts = []
    for block in blocks:
        kind = block.get("type")
        if kind == "text":
            parts.append(block["text"])
        elif kind in ("document", "image"):
            source = block.get("source", {})
            size = len(source.get("data", "")) if source.get("type") == "base64" else 0
            parts.append(f"[{kind} {source.get('media_type', '?')}, {size} base64 chars]")
        else:
            parts.append(f"[{kind} block]")
    return _truncate("\n".join(parts))


def _truncate(text: str) -> str:
    if len(text) <= INPUT_SUMMARY_CHARS:
        return text
    return text[:INPUT_SUMMARY_CHARS] + f"... [truncated, {len(text)} chars total]"


def _write_log(record: dict) -> None:
    log_dir = get_settings().ai_log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"{datetime.now(timezone.utc):%Y-%m-%d}.jsonl"
    line = json.dumps(record, ensure_ascii=False, default=str)
    with _log_lock, path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def read_log(case_id: Optional[str] = None) -> list[dict]:
    """All logged LLM calls, oldest first, optionally filtered to one case."""
    log_dir = get_settings().ai_log_dir
    records = []
    for path in sorted(log_dir.glob("*.jsonl")):
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    record = json.loads(line)
                    if case_id is None or record.get("case_id") == case_id:
                        records.append(record)
    return records


# --- Calls -------------------------------------------------------------------


def _call(
    function: str,
    system: str,
    blocks: list[dict],
    output_config: dict,
    case_id: Optional[str],
) -> str:
    settings = get_settings()
    system = mask_ssn(system)
    blocks = _mask_blocks(blocks)
    record: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "function": function,
        "case_id": case_id,
        "model": settings.anthropic_model,
        "prompt": {"system": _truncate(system), "input_summary": _summarize_blocks(blocks)},
        "output": None,
        "stop_reason": None,
    }
    start = time.perf_counter()
    try:
        response = get_client().beta.messages.create(
            model=settings.anthropic_model,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": blocks}],
            output_config=output_config,
            betas=[FALLBACK_BETA],
            fallbacks="default",
        )
        record["model"] = getattr(response, "model", settings.anthropic_model)
        record["stop_reason"] = response.stop_reason
        if response.stop_reason == "refusal":
            raise LLMRefusalError(f"{function}: model declined the request")
        if response.stop_reason == "max_tokens":
            raise LLMError(f"{function}: output hit max_tokens and is incomplete")
        text = "".join(b.text for b in response.content if b.type == "text")
        if not text.strip():
            raise LLMError(f"{function}: empty response")
        text = mask_ssn(text)
        record["output"] = text
        return text
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        record["latency_ms"] = round((time.perf_counter() - start) * 1000)
        _write_log(record)


def extract_json(
    system: str,
    content_blocks: list[dict],
    json_schema: dict,
    *,
    case_id: Optional[str] = None,
) -> dict:
    """Ask the model to read ``content_blocks`` and reply with JSON matching ``json_schema``.

    ``content_blocks`` are Messages API user content blocks, e.g. a PDF as
    ``{"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": ...}}``
    followed by a text block with the instruction.
    """
    output_config = {
        "effort": EXTRACT_EFFORT,
        "format": {"type": "json_schema", "schema": json_schema},
    }
    text = _call("extract_json", system, content_blocks, output_config, case_id)
    try:
        return _mask_value(json.loads(text))
    except json.JSONDecodeError as exc:
        raise LLMError(f"extract_json: reply is not valid JSON: {exc}") from exc


def write_text(system: str, user_json: Any, *, case_id: Optional[str] = None) -> str:
    """Write plain text from structured input only. ``user_json`` is a str or JSON-able value."""
    if not isinstance(user_json, str):
        user_json = json.dumps(user_json, sort_keys=True, default=str)
    blocks = [{"type": "text", "text": user_json}]
    return _call("write_text", system, blocks, {"effort": WRITE_EFFORT}, case_id)
