"""Fixed wording used when the model's text is blocked twice or the model is unavailable.

Templates use only the structured inputs, so they always pass hg.safety.check.
"""

from __future__ import annotations

from decimal import Decimal

from hg.schemas import CheckResult

SCENARIO_LABELS: dict[str, str] = {
    "lump_sum_now": "Lump sum now",
    "minimums_then_balloon": "Minimums, rest at the end",
    "even_spread": "Even spread",
    "fill_bracket": "Fill your tax bracket",
}

ISSUE_FIXES: dict[str, str] = {
    "required_docs_present": "Upload the missing documents, then press Re-check.",
    "shares_total_100": "Upload a corrected application so the shares add up to the full account.",
    "name_match": "If a form has a misspelled name, upload a corrected form. If it is the same person, "
    "estate operations can confirm it.",
    "dod_consistent": "Upload a corrected form so its date matches the death certificate.",
    "certified_copy": "You can order a certified copy from the vital records office in the county that issued "
    "the certificate, then upload it.",
    "field_review": "If a value was read wrong, upload a clearer or corrected copy of that document.",
}
DEFAULT_FIX = "Check this item and upload a corrected document if needed."

DISCLAIMER = (
    "These are estimates from your own inputs and the current federal brackets. "
    "A tax professional can help you decide."
)


def money(value: str | Decimal) -> str:
    return f"${Decimal(value):,.2f}"


def issue_text(check: CheckResult) -> str:
    return f"{check.message} {ISSUE_FIXES.get(check.rule_id, DEFAULT_FIX)}"


def options_text(payload: dict) -> str:
    """Neutral comparison from the summarize_options payload (see writer.write), one point per line."""
    points = [
        f"{s['label']}: {money(s['total_tax'])} in tax, you keep {money(s['after_tax_total'])}."
        for s in payload["scenarios"]
    ]
    points.append(payload["rule"]["summary"])
    points.append(DISCLAIMER)
    return "\n".join(f"- {p}" for p in points)
