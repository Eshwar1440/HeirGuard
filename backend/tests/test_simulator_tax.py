"""Tax figures checked by hand against Rev. Proc. 2025-32 (2026 brackets)."""

from decimal import Decimal

import pytest

from hg.simulator.tax import (
    assumptions,
    bracket_ceiling,
    current_rate,
    federal_tax,
    incremental_federal_tax,
    parse_rate,
    state_tax,
)

D = Decimal


@pytest.mark.parametrize(
    "income, withdrawal, status, expected",
    [
        # Single, std 16,100. Before: 68,900 -> 5,800 + 22% x 18,500 = 9,870.
        # After: 78,900 -> 5,800 + 22% x 28,500 = 12,070. Extra = 2,200.
        ("85000", "10000", "single", "2200.00"),
        # Joint, std 32,200. Before: 57,800 -> 2,480 + 12% x 33,000 = 6,440.
        # After: 107,800 -> 11,600 + 22% x 7,000 = 13,140. Extra = 6,700 (crosses 12% -> 22%).
        ("90000", "50000", "married_joint", "6700.00"),
        # Single, income below the deduction. After: 13,900 -> 1,240 + 12% x 1,500 = 1,420.
        ("10000", "20000", "single", "1420.00"),
        # Still under the standard deduction: no tax.
        ("10000", "5000", "single", "0.00"),
    ],
)
def test_incremental_federal_tax(income, withdrawal, status, expected):
    assert incremental_federal_tax(D(income), D(withdrawal), status) == D(expected)


def test_bracket_edges_and_top_bracket():
    assert federal_tax(D("12400"), "single") == D("1240.00")
    assert federal_tax(D("12401"), "single") == D("1240.12")
    # 192,979.25 + 37% x (700,000 - 640,600) = 192,979.25 + 21,978 = 214,957.25
    assert federal_tax(D("700000"), "single") == D("214957.25")
    assert federal_tax(D("-5"), "single") == D("0.00")


def test_state_tax_is_flat():
    assert state_tax(D("10000"), D("0.05")) == D("500.00")
    assert state_tax(D("10000"), D("0")) == D("0.00")


def test_rates_and_ceilings():
    assert parse_rate("0.22") == parse_rate("22") == parse_rate("22%") == D("0.22")
    assert bracket_ceiling(D("0.22"), "single") == D("105700")
    assert bracket_ceiling(D("0.37"), "single") is None
    with pytest.raises(ValueError):
        bracket_ceiling(D("0.25"), "single")
    assert current_rate(D("85000"), "single") == D("0.22")


def test_assumptions_name_the_tax_year_and_hypothetical_growth():
    text = " ".join(assumptions())
    assert "2026" in text and "hypothetical" in text
