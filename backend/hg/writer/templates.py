"""Fixed wording used when the model's text is blocked twice or the model is unavailable.

Templates use only the structured inputs, so they always pass hg.safety.check.
"""

from __future__ import annotations

from decimal import Decimal

from hg.schemas import CheckResult

SCENARIO_LABELS: dict[str, str] = {
    "lump_sum_now": "Lump sum now",
    "minimums_then_balloon": "Yearly minimums, with the rest in the final year",
    "even_spread": "Even spread",
    "fill_bracket": "Fill your tax bracket",
}

ISSUE_FIXES: dict[str, str] = {
    "required_docs_present": "Upload the missing documents, then press Re-check.",
    "shares_total_100": "Check the share on each beneficiary's application and correct any that were misread.",
    "name_match": "If these are the same person, confirm it. If a form has a misspelled name, correct it or "
    "upload a corrected form.",
    "dod_consistent": "Check the date on each form against the death certificate, then correct the one that "
    "differs or upload a corrected form.",
    "certified_copy": "You can order a certified copy from the vital records office in the county that issued "
    "the certificate, then upload it.",
    "field_review": "Check these values against your documents and correct any that are wrong.",
}
DEFAULT_FIX = "Check this item and upload a corrected document if needed."

DISCLAIMER = (
    "These tax figures are estimates based on your own inputs and the current federal brackets. "
    "A tax professional can help you decide."
)


def money(value: str | Decimal) -> str:
    return f"${Decimal(value):,.2f}"


def issue_text(check: CheckResult) -> str:
    return f"{check.message} {ISSUE_FIXES.get(check.rule_id, DEFAULT_FIX)}"


def options_text(payload: dict) -> str:
    """Neutral comparison from the summarize_options payload (see writer.write)."""
    scenarios = payload["scenarios"]
    parts = []
    if scenarios:
        parts.append(f"Here is how the {len(scenarios)} options compare, using your inputs.")
        for s in scenarios:
            parts.append(
                f"{s['label']}: estimated total tax {money(s['total_tax'])}, "
                f"and {money(s['after_tax_total'])} kept after tax."
            )
    parts.append(payload["rule"]["summary"])
    parts.append(DISCLAIMER)
    return " ".join(parts)
