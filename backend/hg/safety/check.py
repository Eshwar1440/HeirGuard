"""M6: deterministic safety check on every text the writer produces.

check(text, allowed_numbers) blocks a text when

- it contains a number or date that is not in ``allowed_numbers`` (after both
  sides go through the same normalization: "$1,234.50" -> 1234.5, "25%" -> 25,
  "$1.2 million" -> 1200000, "December 31, 2035" -> 2035-12-31), or
- it uses recommendation language (safety/phrases.py), or
- it tells the heir to pick a specific scenario ("take the lump sum").

Every reason is returned, so the under-the-hood panel can show exactly why a
text was blocked. Numbers written as words ("ten") are not detected.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Callable, Iterable, Optional, Union

from pydantic import BaseModel, Field

from hg.safety.phrases import ADVICE_PHRASES, CLAUSE_LEADERS, IMPERATIVE_VERBS, SCENARIO_PHRASES
from hg.schemas import AuditEntry

log = logging.getLogger(__name__)

Token = Union[Decimal, str]  # a number, or an ISO date string

_MONTHS = (
    "january|february|march|april|may|june|july|august|september|october|november|december|"
    "jan|feb|mar|apr|jun|jul|aug|sept|sep|oct|nov|dec"
)
_DATE = re.compile(
    rf"\b(?P<named>(?:{_MONTHS})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}})\b"
    r"|\b(?P<iso>\d{4}-\d{2}-\d{2})\b"
    r"|\b(?P<us>\d{1,2}/\d{1,2}/\d{4})\b",
    re.IGNORECASE,
)
_NUMBER = re.compile(
    r"(?<![\w.,])(?P<cur>\$\s?)?"
    r"(?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)"
    r"(?P<scale>\s?(?:million|thousand|billion)\b|[kKmM]\b)?"
    r"(?P<pct>\s?(?:%|percent\b|per cent\b))?",
    re.IGNORECASE,
)
_SCALES = {"thousand": Decimal(1_000), "k": Decimal(1_000), "million": Decimal(1_000_000), "m": Decimal(1_000_000),
           "billion": Decimal(1_000_000_000)}


class SafetyResult(BaseModel):
    ok: bool
    reasons: list[str] = Field(default_factory=list)
    audit_entry: Optional[AuditEntry] = Field(default=None, description="Set when a block is logged for a case")


# --- Numbers -------------------------------------------------------------------


def _parse_date(raw: str) -> Optional[str]:
    text = re.sub(r"(?<=\d)(st|nd|rd|th)\b", "", raw, flags=re.IGNORECASE).replace(",", " ").replace(".", " ")
    text = re.sub(r"\bsept\b", "sep", " ".join(text.split()), flags=re.IGNORECASE)
    for fmt in ("%B %d %Y", "%b %d %Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def find_numbers(text: str) -> list[tuple[str, Token]]:
    """Every number and date in ``text`` as (raw text, normalized token), in order.

    A date that does not parse (e.g. "February 30, 2035") keeps its raw text as the token,
    so it can never match an allowed value.
    """
    found: list[tuple[int, str, Token]] = []
    spans: list[tuple[int, int]] = []
    for m in _DATE.finditer(text):
        raw = m.group(0)
        found.append((m.start(), raw, _parse_date(raw) or f"invalid date {raw}"))
        spans.append(m.span())
    masked = list(text)
    for start, end in spans:
        masked[start:end] = " " * (end - start)
    for m in _NUMBER.finditer("".join(masked)):
        try:
            value = Decimal(m.group("num").replace(",", ""))
        except InvalidOperation:  # pragma: no cover - the regex only admits digits
            continue
        if m.group("scale"):
            value *= _SCALES[m.group("scale").strip().lower()]
        found.append((m.start(), m.group(0).strip(), value))
    return [(raw, token) for _, raw, token in sorted(found, key=lambda item: item[0])]


def normalize_allowed(allowed_numbers: Iterable[str]) -> set[Token]:
    """Run allowed values through the same normalization as the text."""
    tokens: set[Token] = set()
    for item in allowed_numbers:
        tokens.update(token for _, token in find_numbers(str(item)))
    return tokens


def number_reasons(text: str, allowed_numbers: Iterable[str]) -> list[str]:
    allowed = normalize_allowed(allowed_numbers)
    reasons = []
    for raw, token in find_numbers(text):
        if token not in allowed:
            kind = "date" if isinstance(token, str) else "number"
            reasons.append(f'{kind} "{raw}" is not in the input')
    return reasons


# --- Advice --------------------------------------------------------------------


def _clean(text: str) -> str:
    text = text.translate({0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: '"', 0x2014: ";", 0x2013: "-"})
    return " ".join(text.lower().split())


def _words(phrase: str, sep: str = r"\s+") -> str:
    return sep.join(re.escape(word) for word in phrase.split())


def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![\w']){_words(phrase)}(?![\w'])")


_ADVICE = [(phrase, _phrase_pattern(phrase)) for phrase in ADVICE_PHRASES]
_SCENARIO_ALTS = "|".join(_words(p, r"[\s-]+") for phrases in SCENARIO_PHRASES.values() for p in phrases)
_LEADERS = re.compile(rf"^(?:(?:{'|'.join(CLAUSE_LEADERS)})\b[\s,]*)+")
_IMPERATIVE = re.compile(
    rf"^(?:{'|'.join(_words(v) for v in IMPERATIVE_VERBS)})\b(?:\s+[\w'-]+){{0,3}}?\s+(?:{_SCENARIO_ALTS})(?![\w'])"
)


def advice_reasons(text: str) -> list[str]:
    cleaned = _clean(text)
    reasons = [f'advice phrase "{phrase}"' for phrase, pattern in _ADVICE if pattern.search(cleaned)]
    for clause in re.split(r"[.!?;:,\n]", cleaned):
        clause = _LEADERS.sub("", clause.strip(" \"'()-*•"))  # also bullet markers
        match = _IMPERATIVE.match(clause)
        if match:
            reasons.append(f'recommends a scenario: "{match.group(0)}"')
    return reasons


# --- Check ---------------------------------------------------------------------


def check(
    text: str,
    allowed_numbers: Iterable[str],
    *,
    case_id: Optional[str] = None,
    record: Optional[Callable[[AuditEntry], None]] = None,
) -> SafetyResult:
    """Return ok=False with every reason when ``text`` fails a check.

    When a block happens for a case, the result carries an AuditEntry and, if given,
    ``record`` is called with it (M8 passes the Supabase audit writer).
    """
    reasons = list(dict.fromkeys(number_reasons(text, allowed_numbers) + advice_reasons(text)))
    if not reasons:
        return SafetyResult(ok=True)
    log.info("safety check blocked text: %s", "; ".join(reasons))
    entry = None
    if case_id is not None:
        entry = AuditEntry(case_id=case_id, node="safety_check", action="blocked", summary="; ".join(reasons))
        if record is not None:
            record(entry)
    return SafetyResult(ok=False, reasons=reasons, audit_entry=entry)
