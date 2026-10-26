"""Loaders for the IRS tables in this folder (see build_tables.py for their source)."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Optional

HERE = Path(__file__).parent
SINGLE_LIFE_CSV = HERE / "single_life.csv"
FEDERAL_BRACKETS_CSV = HERE / "federal_brackets.csv"


@dataclass(frozen=True)
class Bracket:
    rate: Decimal
    over: Decimal
    not_over: Optional[Decimal]
    base_tax: Decimal


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(line for line in fh if not line.startswith("#")))


def source_line(path: Path) -> str:
    with path.open(encoding="utf-8") as fh:
        return fh.readline().strip()


@lru_cache
def single_life_table() -> dict[int, Decimal]:
    return {int(r["age"]): Decimal(r["life_expectancy"]) for r in _rows(SINGLE_LIFE_CSV)}


def life_expectancy(age: int) -> Decimal:
    """IRS Table I factor. The IRS's last row is 120+, so older ages use it."""
    if age < 0:
        raise ValueError(f"age must be non-negative, got {age}")
    return single_life_table()[min(age, 120)]


@lru_cache
def _federal() -> tuple[int, dict[str, tuple[Bracket, ...]], dict[str, Decimal]]:
    brackets: dict[str, list[Bracket]] = {}
    standard: dict[str, Decimal] = {}
    years = set()
    for r in _rows(FEDERAL_BRACKETS_CSV):
        years.add(int(r["tax_year"]))
        if r["item"] == "bracket":
            brackets.setdefault(r["filing_status"], []).append(
                Bracket(
                    rate=Decimal(r["rate"]),
                    over=Decimal(r["over"]),
                    not_over=Decimal(r["not_over"]) if r["not_over"] else None,
                    base_tax=Decimal(r["base_tax"]),
                )
            )
        else:
            standard[r["filing_status"]] = Decimal(r["amount"])
    (year,) = years
    return year, {k: tuple(sorted(v, key=lambda b: b.over)) for k, v in brackets.items()}, standard


def tax_year() -> int:
    return _federal()[0]


def brackets(filing_status: str) -> tuple[Bracket, ...]:
    return _federal()[1][filing_status]


def standard_deduction(filing_status: str) -> Decimal:
    return _federal()[2][filing_status]
