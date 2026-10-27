"""Write ai_log/summary.md: the one-page source for the AI log.

    python -m hg.ai_log_summary

It collects (1) what the model calls in ai_log/*.jsonl were, (2) the extraction accuracy
report from AI-log check #1, (3) the hand-checked RMD from IRS Pub. 590-B, recomputed by the
simulator, and (4) three safety-check blocks. The blocked texts in (4) are written on purpose
to break the rules; each runs through the real hg.safety.check.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal

from hg.config import get_settings
from hg.llm import read_log
from hg.safety import check
from hg.schemas import Beneficiary, Decedent
from hg.simulator.rmd import divisors, required_minimum

# Allowed numbers for the safety examples: the figures a real options summary would carry.
SAFETY_ALLOWED = {"115447.78", "259219.44", "2035-12-31", "2035", "10"}
SAFETY_EXAMPLES = (
    ("A number the calculator never produced",
     "Lump sum now: about $120,000 in tax, you keep $259,219.44."),
    ("Advice instead of an explanation",
     "You should take the lump sum, since the account must be empty by December 31, 2035."),
    ("A recommendation hidden in a bullet point",
     "- Take the lump sum now and keep $259,219.44."),
)


def _section(report: str, heading: str) -> str:
    """The body of one '## heading' section of a markdown report."""
    start = report.index(f"## {heading}")
    end = report.find("\n## ", start + 3)
    return report[start:end if end != -1 else None].strip()


def _calls() -> list[str]:
    records = read_log()
    by_function = Counter(r.get("function") for r in records)
    by_model = Counter(r.get("model") for r in records)
    refusals = sum(r.get("stop_reason") == "refusal" for r in records)
    errors = sum(bool(r.get("error")) for r in records)
    lines = [
        "## 1. Model calls",
        "",
        f"Every call goes through `hg/llm.py` and is logged to `ai_log/*.jsonl` (prompt, input summary, output, model). "
        f"Logged calls: **{len(records)}**.",
        "",
        "| Job | Calls |",
        "|---|---|",
    ]
    lines += [f"| {name} | {n} |" for name, n in sorted(by_function.items())]
    lines += ["", "| Model that answered | Calls |", "|---|---|"]
    lines += [f"| `{name}` | {n} |" for name, n in sorted(by_model.items())]
    lines += ["", f"Refusals: {refusals}. Failed calls: {errors}."]
    return lines


def _extraction() -> list[str]:
    path = get_settings().ai_log_dir / "extraction_accuracy.md"
    if not path.exists():
        return ["## 2. Extraction accuracy (AI-log check #1)", "", "Not run yet: `python -m hg.reader.evaluate`."]
    report = path.read_text(encoding="utf-8")
    summary = _section(report, "Summary").replace("## Summary", "").strip()
    planted = _section(report, "Planted errors: read as printed?").split("\n", 1)[1].strip()
    limits = _section(report, "Limits of this test").split("\n", 1)[1].strip()
    return [
        "## 2. Extraction accuracy (AI-log check #1)",
        "",
        "The reader (`hg/reader`) against the truth files of every synthetic packet. Full report: "
        "`ai_log/extraction_accuracy.md`.",
        "",
        summary,
        "",
        "**Planted errors read as printed (not silently fixed):**",
        "",
        planted,
        "",
        "**Limits:**",
        "",
        limits,
    ]


def _rmd() -> list[str]:
    # IRS Pub. 590-B (2025), "Owner Died on or After Required Beginning Date", Example.
    father = Decedent(id="d", name="Example father", date_of_birth=date(1941, 3, 1),
                      date_of_death=date(2021, 8, 1), rmds_started=True)
    heir = Beneficiary(id="b", name="Example heir", date_of_birth=date(1967, 5, 1), relationship="child",
                       share_percent=Decimal(100), designation="primary")
    by_year = {d.year: d for d in divisors(father, heir)}
    divisor = by_year[2026].divisor
    rmd = required_minimum(Decimal("100000"), divisor)
    return [
        "## 3. Hand-checked RMD (IRS Pub. 590-B example)",
        "",
        "Pub. 590-B (2025), \"Owner Died on or After Required Beginning Date\", Example: the father died in 2021 "
        "at 80; the heir was 55 in 2022, so \"the life expectancy for a 55-year-old is 31.6; therefore, you "
        "calculate your required minimum distribution for 2026 by dividing the account balance by 27.6 (31.6 - 4).\"",
        "",
        "| Step | By hand | Simulator (`hg/simulator/rmd.py`) |",
        "|---|---|---|",
        "| Heir factor, age 55 (Table I) | 31.6 | |",
        "| 2026 is year 5: 31.6 - 4 | 27.6 | |",
        "| Father: 11.2 at 80, minus 5 for 2026 | 6.2 | |",
        f"| Divisor used (the longer) | 27.6 | {divisor} |",
        f"| 2026 RMD on a hypothetical $100,000 | $3,623.19 | ${rmd:,.2f} |",
        "",
        f"Match: **{'yes' if divisor == Decimal('27.6') and rmd == Decimal('3623.19') else 'NO'}**. "
        "The same example is a test (`tests/test_simulator_rmd.py`).",
    ]


def _safety() -> list[str]:
    lines = [
        "## 4. Safety check: three blocks",
        "",
        "Every text the writer (`hg/writer`) produces passes `hg/safety/check.py` before anyone sees it: no number "
        "the calculator did not produce, no advice, no telling the heir which option to take. A blocked text is "
        "regenerated once, then replaced by a fixed template.",
        "",
        "These three texts were written on purpose to break the rules and run through the real check. "
        f"Allowed numbers for the examples: {', '.join(sorted(SAFETY_ALLOWED))}.",
        "",
        "| Case | Text | Result | Reasons |",
        "|---|---|---|---|",
    ]
    for label, text in SAFETY_EXAMPLES:
        result = check(text, SAFETY_ALLOWED)
        verdict = "passed" if result.ok else "**blocked**"
        lines.append(f"| {label} | {text} | {verdict} | {'; '.join(result.reasons) or '-'} |")
    return lines


def render() -> str:
    lines = [
        "# AI log summary",
        "",
        "> Concept prototype. Not affiliated with Charles Schwab. All data is hypothetical.",
        "",
        f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} by `python -m hg.ai_log_summary`. "
        "AI does two jobs only: reading documents (`hg/reader`) and writing plain English (`hg/writer`). "
        "Numbers, rules, routing and approval are code or a person.",
        "",
    ]
    for part in (_calls(), _extraction(), _rmd(), _safety()):
        lines += part + [""]
    return "\n".join(lines)


def main() -> None:
    out = get_settings().ai_log_dir / "summary.md"
    out.write_text(render(), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
