"""Estimated tax on inherited IRA withdrawals.

incremental_federal_tax = tax(income + withdrawal - standard deduction)
                        - tax(income - standard deduction), never below zero.
State tax is a flat rate times the withdrawal. Every year reuses the same federal
brackets (see ASSUMPTIONS).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from hg.simulator.rmd import to_cents
from hg.simulator.tables import brackets, standard_deduction, tax_year

ZERO = Decimal("0.00")


def federal_tax(taxable_income: Decimal, filing_status: str) -> Decimal:
    if taxable_income <= 0:
        return ZERO
    for b in brackets(filing_status):
        if b.not_over is None or taxable_income <= b.not_over:
            return to_cents(b.base_tax + b.rate * (taxable_income - b.over))
    raise AssertionError("the top bracket has no ceiling")


def incremental_federal_tax(income: Decimal, withdrawal: Decimal, filing_status: str) -> Decimal:
    deduction = standard_deduction(filing_status)
    extra = federal_tax(income + withdrawal - deduction, filing_status) - federal_tax(income - deduction, filing_status)
    return max(extra, ZERO)


def state_tax(withdrawal: Decimal, rate: Decimal) -> Decimal:
    return to_cents(withdrawal * rate)


def parse_rate(value: str) -> Decimal:
    """'0.22', '22' and '22%' all mean 22%."""
    rate = Decimal(value.strip().rstrip("%"))
    return rate / 100 if rate > 1 else rate


def bracket_ceiling(rate: Decimal, filing_status: str) -> Optional[Decimal]:
    """Top of the bracket taxed at ``rate`` (taxable income); None for the top bracket."""
    for b in brackets(filing_status):
        if b.rate == rate:
            return b.not_over
    raise ValueError(f"{rate} is not a federal bracket rate for {filing_status}")


def current_rate(income: Decimal, filing_status: str) -> Decimal:
    """Rate of the bracket the heir's income alone falls in."""
    taxable = income - standard_deduction(filing_status)
    for b in brackets(filing_status):
        if b.not_over is None or taxable <= b.not_over:
            return b.rate
    raise AssertionError("the top bracket has no ceiling")


def assumptions() -> list[str]:
    year = tax_year()
    return [
        f"Federal tax uses the {year} IRS brackets and standard deduction for every year. "
        "Future brackets will differ.",
        "Tax shown is the extra tax from adding the withdrawal to your income. It ignores other "
        "deductions, credits and the extra standard deduction for age 65 or blindness.",
        "Your income stays the same every year.",
        "State tax is the flat rate you entered times the withdrawal.",
        "The growth rate is hypothetical. Growth is added during the year and withdrawals are taken "
        "at year end.",
        "These are estimates for comparison, not tax advice.",
    ]
