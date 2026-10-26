"""M2: read one uploaded document into an hg.schemas.Document.

One call to hg.llm.extract_json per document. The model returns JSON matching
``extraction_schema()``; this module then normalizes values, drops field names
outside the document type's vocabulary, fills any missing field with null at
confidence 0, and sets needs_review when anything is below CONFIDENCE_THRESHOLD
(hypothetical, tunable). The file name is never sent to the model, so it cannot
hint at the answer.
"""

from __future__ import annotations

import base64
import hashlib
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import PurePath
from typing import Any, Optional

from hg.config import get_settings
from hg.llm import extract_json
from hg.reader.vocab import ALL_FIELD_NAMES, VOCAB, FieldDef, describe, fields_for
from hg.schemas import DocType, Document, ExtractedField

DOC_TYPES: tuple[str, ...] = DocType.__args__

SYSTEM_PROMPT = """You read estate documents (PDFs or images) and report exactly what is printed on them.

Rules:
- Extract only what is visible on the document. Never guess, infer, or fill in a value from other knowledge.
- If a field is unreadable, cut off or not present, return value null with a low confidence (0.3 or less).
- confidence is your probability, from 0 to 1, that the value is exactly what is printed.
- page is the 1-based page number where the value appears.
- Choose one doc_type. Return each field listed for that type once, and no other fields.
- certified_copy reports only what the upload shows. Nobody can confirm a certified copy from an image, and a raised seal does not show in a scan. It is "no" if you see any sign that this is not a certified copy: a pattern repeated across the background such as VOID or COPY (security paper shows this when it is photocopied), a printed note that the copy is uncertified, informational or not valid for legal purposes, or no registrar's certification statement and signature. It is "yes" when the registrar's certification is visible and none of those signs is. If you cannot tell, return null with a low confidence.
- The diagonal "SPECIMEN - HYPOTHETICAL DATA" watermark is not a copy sign, and the word "void" inside a printed sentence is not a background pattern.
- Normalize values: dates as YYYY-MM-DD; percentages as a plain number without the % sign; relationship, designation and affiant capacity in lowercase; account_type as one of traditional_ira, roth_ira, tod_brokerage, joint, individual, trust_owned; names and other text exactly as printed.
- If the document is a will, use doc_type "will" and return no fields. If it is none of the listed types, use "unknown" and return no fields."""

INSTRUCTION = """Identify the document type and extract its fields.

Field vocabulary by document type:
{vocab}"""

_MEDIA_TYPES = (
    (b"%PDF", "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)

_ACCOUNT_TYPES = {
    "traditional_ira": "traditional_ira", "traditional ira": "traditional_ira",
    "roth_ira": "roth_ira", "roth ira": "roth_ira",
    "tod_brokerage": "tod_brokerage", "tod brokerage": "tod_brokerage", "transfer on death": "tod_brokerage",
    "joint": "joint", "individual": "individual",
    "trust_owned": "trust_owned", "trust-owned": "trust_owned", "trust owned": "trust_owned",
}
_YES_NO = {"yes": "yes", "y": "yes", "true": "yes", "no": "no", "n": "no", "false": "no"}
_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%B %d, %Y", "%b %d, %Y", "%d %B %Y")

#: Confidence ceiling for a value the reader returned but this module could not normalize.
UNPARSED_CONFIDENCE = 0.5


class UnsupportedFileError(ValueError):
    """The upload is not a PDF or a supported image."""


def media_type(data: bytes) -> str:
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    for magic, kind in _MEDIA_TYPES:
        if data.startswith(magic):
            return kind
    raise UnsupportedFileError("upload must be a PDF, PNG, JPEG, GIF or WebP file")


def file_block(data: bytes) -> dict:
    kind = media_type(data)
    source = {"type": "base64", "media_type": kind, "data": base64.standard_b64encode(data).decode("ascii")}
    return {"type": "document" if kind == "application/pdf" else "image", "source": source}


def extraction_schema() -> dict:
    """JSON schema for structured outputs (no numeric bounds: the API does not support them)."""
    field_item = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "enum": list(ALL_FIELD_NAMES)},
            "value": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "confidence": {"type": "number"},
            "page": {"type": "integer"},
        },
        "required": ["name", "value", "confidence", "page"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {
            "doc_type": {"type": "string", "enum": list(DOC_TYPES)},
            "fields": {"type": "array", "items": field_item},
        },
        "required": ["doc_type", "fields"],
        "additionalProperties": False,
    }


# --- Normalization -------------------------------------------------------------


def normalize(value: str, kind: str) -> str:
    """Normalize a raw value for its field kind. Raises ValueError when it cannot."""
    text = " ".join(value.split())
    if not text:
        raise ValueError("empty value")
    if kind == "date":
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(text, fmt).date().isoformat()
            except ValueError:
                continue
        raise ValueError(f"unrecognized date {text!r}")
    if kind == "percent":
        try:
            return format(Decimal(text.rstrip("%").strip()).normalize(), "f")
        except InvalidOperation as exc:
            raise ValueError(f"unrecognized percent {text!r}") from exc
    if kind == "choice":
        return text.lower().replace(" ", "_")
    if kind == "account_type":
        key = text.lower()
        if key not in _ACCOUNT_TYPES:
            raise ValueError(f"unrecognized account type {text!r}")
        return _ACCOUNT_TYPES[key]
    if kind == "yes_no":
        if text.lower() not in _YES_NO:
            raise ValueError(f"unrecognized yes/no {text!r}")
        return _YES_NO[text.lower()]
    return text


def _clamp(confidence: Any) -> float:
    try:
        return min(max(float(confidence), 0.0), 1.0)
    except (TypeError, ValueError):
        return 0.0


def _field(spec: FieldDef, raw: Optional[dict]) -> ExtractedField:
    if raw is None:
        return ExtractedField(name=spec.name, value=None, confidence=0.0, page=1)
    confidence = _clamp(raw.get("confidence"))
    page = raw.get("page") if isinstance(raw.get("page"), int) and raw.get("page") >= 1 else 1
    value = raw.get("value")
    if value is None:
        return ExtractedField(name=spec.name, value=None, confidence=min(confidence, 0.3), page=page)
    try:
        value = normalize(str(value), spec.kind)
    except ValueError:
        value, confidence = " ".join(str(value).split()), min(confidence, UNPARSED_CONFIDENCE)
    return ExtractedField(name=spec.name, value=value, confidence=confidence, page=page)


def build_document(case_id: str, document_id: str, file_ref: str, data: dict) -> Document:
    """Turn the model's JSON into a Document, enforcing the vocabulary and review rules."""
    doc_type = data.get("doc_type") if data.get("doc_type") in DOC_TYPES else "unknown"
    returned: dict[str, dict] = {}
    for item in data.get("fields") or []:
        if isinstance(item, dict) and item.get("name") not in returned:
            returned[item.get("name")] = item
    fields = [_field(spec, returned.get(spec.name)) for spec in fields_for(doc_type)]
    threshold = get_settings().confidence_threshold
    needs_review = (
        not VOCAB.get(doc_type)
        or any(f.value is None or f.confidence < threshold for f in fields)
    )
    return Document(
        id=document_id,
        case_id=case_id,
        file_ref=file_ref,
        doc_type=doc_type,
        fields=fields,
        needs_review=needs_review,
    )


def document_id(case_id: str, filename: str, data: bytes) -> str:
    stem = re.sub(r"[^a-z0-9]+", "_", PurePath(filename).stem.lower()).strip("_") or "document"
    return f"{case_id}-{stem}-{hashlib.sha256(data).hexdigest()[:8]}"


def read_document(case_id: str, file_bytes: bytes, filename: str, *, file_ref: Optional[str] = None) -> Document:
    """Read one uploaded PDF or image. ``file_ref`` defaults to the Supabase Storage path."""
    blocks = [file_block(file_bytes), {"type": "text", "text": INSTRUCTION.format(vocab=describe())}]
    data = extract_json(SYSTEM_PROMPT, blocks, extraction_schema(), case_id=case_id)
    return build_document(
        case_id,
        document_id(case_id, filename, file_bytes),
        file_ref or f"packets/{case_id}/{filename}",
        data,
    )


__all__ = ["read_document", "build_document", "extraction_schema", "normalize", "UnsupportedFileError"]
