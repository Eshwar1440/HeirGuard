"""The committed IRS tables are complete, internally consistent and cite their source."""

from decimal import Decimal

from hg.simulator import tables

STATUSES = ("single", "married_joint", "married_separate", "head_of_household")


def test_source_lines_cite_official_irs_pages():
    life = tables.source_line(tables.SINGLE_LIFE_CSV)
    assert life.startswith("# Source: IRS Publication 590-B (2025)") and "irs.gov/publications/p590b" in life
    federal = tables.source_line(tables.FEDERAL_BRACKETS_CSV)
    assert federal.startswith("# Source: IRS Rev. Proc. 2025-32") and "irs.gov/irb/2025-45_IRB" in federal


def test_single_life_table_is_complete_and_non_increasing():
    table = tables.single_life_table()
    assert sorted(table) == list(range(121))
    values = [table[a] for a in range(121)]
    assert all(a >= b for a, b in zip(values, values[1:]))
    assert tables.life_expectancy(130) == table[120]


def test_brackets_are_contiguous_and_base_taxes_chain():
    assert tables.tax_year() == 2026
    for status in STATUSES:
        rows = tables.brackets(status)
        assert len(rows) == 7
        assert [b.rate for b in rows] == [Decimal(r) for r in ("0.10", "0.12", "0.22", "0.24", "0.32", "0.35", "0.37")]
        assert rows[0].over == 0 and rows[0].base_tax == 0 and rows[-1].not_over is None
        for prev, cur in zip(rows, rows[1:]):
            assert prev.not_over == cur.over
            assert prev.base_tax + prev.rate * (cur.over - prev.over) == cur.base_tax


def test_standard_deduction_present_for_every_status():
    deductions = {s: tables.standard_deduction(s) for s in STATUSES}
    assert all(d > 0 for d in deductions.values())
    assert deductions["married_joint"] == 2 * deductions["single"]
    assert deductions["married_separate"] == deductions["single"]
