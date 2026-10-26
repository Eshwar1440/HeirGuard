"""Regenerate the IRS tables in this folder from the official IRS web pages.

    python -m hg.simulator.tables.build_tables

Values are parsed from the IRS pages' HTML, never typed by hand (AGENTS.md
rule 5). The parser cross-checks what it reads: life expectancies must cover
ages 0-120 with no gaps or conflicts, and every bracket's base tax must equal
the previous base plus that bracket's rate times its width.
"""

from __future__ import annotations

import html
import re
import urllib.request
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).parent

PUB_590B_URL = "https://www.irs.gov/publications/p590b"
RP_2025_32_URL = "https://www.irs.gov/irb/2025-45_IRB"
TAX_YEAR = 2026

SINGLE_LIFE_SOURCE = (
    "# Source: IRS Publication 590-B (2025), Distributions from Individual Retirement Arrangements (IRAs), "
    "Appendix B, Table I (Single Life Expectancy) (For Use by Beneficiaries), for use in preparing 2025 "
    f"returns. {PUB_590B_URL} (page last reviewed or updated 30-Apr-2026). Parsed from the page HTML by "
    "build_tables.py. The IRS labels the last row 120+."
)
BRACKETS_SOURCE = (
    "# Source: IRS Rev. Proc. 2025-32, Section 4.01 (Tax Rate Tables, Tables 1-4) and Section 4.14(1) "
    f"(Standard Deduction), for taxable years beginning in {TAX_YEAR}. Internal Revenue Bulletin 2025-45 "
    f"(November 3, 2025), {RP_2025_32_URL}. Reflects law as in effect on October 9, 2025. Parsed from "
    "the page HTML by build_tables.py."
)

_STATUS_BY_TABLE = {"1": "married_joint", "2": "head_of_household", "3": "single", "4": "married_separate"}
_STD_LABELS = {
    "married_joint": "Married Individuals Filing Joint Returns and Surviving Spouses",
    "head_of_household": "Heads of Households",
    "single": "Unmarried Individuals (other than Surviving Spouses and Heads of Households)",
    "married_separate": "Married Individuals Filing Separate Returns",
}


def _page_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (HeritageGuard table builder)"})
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read().decode("utf-8")
    text = re.sub(r"<[^>]+>", " ", raw)
    return html.unescape(re.sub(r"\s+", " ", text))


def _money(value: str) -> Decimal:
    return Decimal(value.replace(",", ""))


def parse_single_life(text: str) -> list[tuple[int, str]]:
    start = text.find("Table I (Single Life Expectancy)", text.find("Appendix B. Life Expectancy Tables"))
    end = text.find("Table II (Joint and Last Survivor Life Expectancy)", start)
    if start < 0 or end < 0:
        raise ValueError("Table I not found in Publication 590-B")
    rows: dict[int, str] = {}
    for age, value in re.findall(r"(?<![\d.])(\d{1,3})\+? (\d{1,2}\.\d)(?![\d.])", text[start:end]):
        if int(age) in rows and rows[int(age)] != value:
            raise ValueError(f"conflicting values for age {age}")
        rows[int(age)] = value
    if sorted(rows) != list(range(121)):
        raise ValueError("Table I must cover ages 0 through 120")
    values = [Decimal(rows[a]) for a in range(121)]
    if any(a < b for a, b in zip(values, values[1:])):
        raise ValueError("life expectancy must not increase with age")
    return [(a, rows[a]) for a in range(121)]


def parse_brackets(text: str) -> list[tuple[str, str, str, Decimal, Decimal, str, Decimal, str]]:
    section = text.find(f"SECTION 4. {TAX_YEAR} ADJUSTED ITEMS")
    if section < 0:
        raise ValueError(f"Section 4 ({TAX_YEAR}) not found in Rev. Proc. 2025-32")
    rows = []
    for number, status in _STATUS_BY_TABLE.items():
        start = text.find(f"TABLE {number} - Section 1(j)(2)", section)
        segment = text[start:text.find("TABLE", start + 10)]
        first = re.search(r"Not over \$([\d,]+) 10% of the taxable income", segment)
        brackets = [(Decimal("0.10"), Decimal(0), _money(first.group(1)), Decimal(0))]
        for lo, hi, base, rate, over in re.findall(
            r"Over \$([\d,]+)(?: but not over \$([\d,]+))? \$([\d,]+(?:\.\d+)?) plus (\d+)% of the excess over \$([\d,]+)",
            segment,
        ):
            if lo != over:
                raise ValueError(f"{status}: bracket floor and excess base differ")
            brackets.append((Decimal(rate) / 100, _money(lo), _money(hi) if hi else None, _money(base)))
        if len(brackets) != 7:
            raise ValueError(f"{status}: expected 7 brackets, found {len(brackets)}")
        for prev, cur in zip(brackets, brackets[1:]):
            if prev[2] != cur[1] or prev[3] + prev[0] * (cur[1] - prev[1]) != cur[3]:
                raise ValueError(f"{status}: bracket {cur} is inconsistent with {prev}")
        for rate, lo, hi, base in brackets:
            rows.append((str(TAX_YEAR), status, "bracket", rate, lo, "" if hi is None else str(hi), base, ""))

    std_start = text.find(".14 Standard Deduction . (1) In general", section)
    std_segment = text[std_start:text.find("(2) Dependent", std_start)]
    for status, label in _STD_LABELS.items():
        match = re.search(re.escape(label) + r" \(\S+ 1\(j\)\(2\)\([A-D]\)\) \$([\d,]+)", std_segment)
        if not match:
            raise ValueError(f"standard deduction for {status} not found")
        rows.append((str(TAX_YEAR), status, "standard_deduction", "", "", "", "", str(_money(match.group(1)))))
    return rows


def write_tables(out_dir: Path = HERE) -> None:
    life = parse_single_life(_page_text(PUB_590B_URL))
    with (out_dir / "single_life.csv").open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(SINGLE_LIFE_SOURCE + "\n")
        fh.write("age,life_expectancy\n")
        fh.writelines(f"{age},{value}\n" for age, value in life)

    rows = parse_brackets(_page_text(RP_2025_32_URL))
    with (out_dir / "federal_brackets.csv").open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(BRACKETS_SOURCE + "\n")
        fh.write("tax_year,filing_status,item,rate,over,not_over,base_tax,amount\n")
        fh.writelines(",".join(str(v) for v in row) + "\n" for row in rows)


if __name__ == "__main__":
    write_tables()
    print(f"Wrote single_life.csv and federal_brackets.csv to {HERE}")
