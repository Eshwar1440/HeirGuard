"""M5: write the words on the Heir Compass page from structured inputs only.

The model sees JSON built here from check results, scenarios, the rule summary
and the heir's own inputs; it never sees documents. Every text goes through
hg.safety.check with the numbers in that JSON as the allowed set. On a block the
model gets one retry with the reasons appended; if that is blocked too (or the
model is unavailable) the text comes from writer/templates.py, which is checked
the same way.
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal
from typing import Any, Callable, Iterable, Optional

import anthropic

from hg.llm import LLMError, write_text
from hg.safety import check, find_numbers
from hg.schemas import AuditEntry, BlockedAttempt, CheckResult, GuideKind, GuideText, HeirInputs, Scenario
from hg.simulator.rmd import YEARS
from hg.simulator.rules import RuleSummary
from hg.simulator.tables import tax_year as current_tax_year
from hg.writer import templates

log = logging.getLogger(__name__)

Recorder = Callable[[AuditEntry], None]

_COMMON_RULES = """- Warm and plain. Short sentences. Speak to the reader as "you".
- Use only numbers and dates that appear in the input, copied exactly. You may add a dollar sign and commas, \
and you may write a date in words. Never round, add, subtract or compute a new number. Write numbers as digits.
- Explain, never recommend. Do not use the words "should", "recommend", "suggest", "best" or "right choice", \
and never tell the reader which option to take.
- No headings, bold or other markdown.
- If the input has previous_attempt_blocked, write a new version that fixes every listed reason."""

ISSUE_SYSTEM = f"""You explain one problem found in a packet of estate documents to the person who inherited the \
account. The input is JSON from a rule check: rule_id, status (fail or needs_review) and the checker's message.

Write one or two short sentences: what is wrong and how to fix it. For example: "Your upload looks like a \
photocopy. Schwab needs a certified copy, which you can order from the county that issued it."
{_COMMON_RULES}"""

OPTIONS_SYSTEM = f"""You summarize withdrawal options for a person who inherited an IRA. The input is JSON: the \
scenarios a calculator produced, the IRS rule that applies, and the heir's own inputs.

Write a short, neutral comparison as 4 to 6 points, one per line, each line starting with "- ".
Each point is one short sentence.
- Name each scenario by its label with its estimated total tax and the amount kept after tax.
- State the one rule that applies: the deadline (rule.deadline_date) and whether a minimum must be taken \
each year (rule.annual_minimums_required).
- Say that the tax figures are estimates based on your own inputs and the current federal brackets, and that \
a tax professional can help with the decision.
- Do not rank the options as better or worse for the reader.
{_COMMON_RULES}"""


# --- Inputs ------------------------------------------------------------------------


def _pct(fraction: Decimal) -> str:
    return format((fraction * 100).normalize(), "f")


def issue_payload(check_result: CheckResult) -> dict:
    return {"rule_id": check_result.rule_id, "status": check_result.status, "message": check_result.message}


def options_payload(
    scenarios: Iterable[Scenario],
    rules_summary: RuleSummary,
    heir_inputs: HeirInputs,
    tax_year: Optional[int] = None,
) -> dict:
    scenarios = list(scenarios)
    deadline = rules_summary.deadline_year
    return {
        "scenario_count": len(scenarios),
        "scenarios": [
            {
                "name": s.name,
                "label": templates.SCENARIO_LABELS.get(s.name, s.name),
                "total_tax": str(s.total_tax),
                "after_tax_total": str(s.after_tax_total),
                "first_year_withdrawal": str(s.years[0].withdrawal) if s.years else None,
                "final_year_withdrawal": str(s.years[-1].withdrawal) if s.years else None,
            }
            for s in scenarios
        ],
        "rule": {
            "summary": rules_summary.summary,
            "deadline_year": deadline,
            "deadline_date": f"{deadline}-12-31" if deadline else None,
            "window_years": YEARS if deadline else None,
            "annual_minimums_required": rules_summary.annual_rmds_required,
            "needs_specialist": rules_summary.needs_specialist,
        },
        "heir_inputs": {
            "annual_income": str(heir_inputs.annual_income),
            "filing_status": heir_inputs.filing_status,
            "state_tax_rate_percent": _pct(heir_inputs.state_tax_rate),
            "growth_rate_percent_hypothetical": _pct(heir_inputs.growth_rate),
            "bracket_to_fill_percent": _pct(Decimal(heir_inputs.bracket_to_fill))
            if heir_inputs.bracket_to_fill else None,
        },
        "federal_brackets_year": tax_year or current_tax_year(),
    }


def allowed_numbers(payload: Any) -> set[str]:
    """Every value in the payload, plus the year of every date in it."""
    out: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                walk(item)
        elif value is not None and not isinstance(value, bool):
            text = str(value)
            out.add(text)
            out.update(token[:4] for _, token in find_numbers(text)
                       if isinstance(token, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", token))

    walk(payload)
    return out


# --- Writing -----------------------------------------------------------------------


def _guide(kind: GuideKind, text: str, attempts: list[BlockedAttempt], **extra: Any) -> GuideText:
    return GuideText(kind=kind, text=text, numbers_used=[raw for raw, _ in find_numbers(text)],
                     blocked_attempts=attempts, **extra)


def _write(
    kind: GuideKind,
    system: str,
    payload: dict,
    template: str,
    *,
    case_id: Optional[str],
    record: Optional[Recorder],
    **extra: Any,
) -> GuideText:
    allowed = allowed_numbers(payload)
    attempts: list[BlockedAttempt] = []
    request = payload
    for _ in range(2):
        try:
            text = write_text(system, request, case_id=case_id).strip()
        except (LLMError, anthropic.APIError) as exc:  # logged in ai_log by hg.llm
            log.warning("writer falling back to template: %s", exc)
            break
        result = check(text, allowed, case_id=case_id, record=record)
        if result.ok:
            return _guide(kind, text, attempts, **extra)
        attempts.append(BlockedAttempt(text=text, reason="; ".join(result.reasons)))
        request = {**payload, "previous_attempt_blocked": {"text": text, "reasons": result.reasons}}

    result = check(template, allowed, case_id=case_id, record=record)
    if not result.ok:
        raise RuntimeError(f"writer template failed the safety check: {result.reasons}")
    return _guide(kind, template, attempts, **extra)


def explain_issue(
    check_result: CheckResult,
    *,
    case_id: Optional[str] = None,
    record: Optional[Recorder] = None,
) -> GuideText:
    """One or two sentences on what is wrong and how to fix it."""
    return _write(
        "issue_reason", ISSUE_SYSTEM, issue_payload(check_result), templates.issue_text(check_result),
        case_id=case_id, record=record, rule_id=check_result.rule_id, beneficiary_id=check_result.beneficiary_id,
    )


def summarize_options(
    scenarios: Iterable[Scenario],
    rules_summary: RuleSummary,
    heir_inputs: HeirInputs,
    *,
    tax_year: Optional[int] = None,
    beneficiary_id: Optional[str] = None,
    case_id: Optional[str] = None,
    record: Optional[Recorder] = None,
) -> GuideText:
    """A neutral comparison of the scenarios and the rule that applies. Never a recommendation."""
    payload = options_payload(scenarios, rules_summary, heir_inputs, tax_year)
    return _write(
        "options_summary", OPTIONS_SYSTEM, payload, templates.options_text(payload),
        case_id=case_id, record=record, beneficiary_id=beneficiary_id,
    )
