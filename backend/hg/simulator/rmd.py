"""Required minimum distributions for a designated beneficiary over years 1-10 after death.

Year N's RMD is the prior year-end balance divided by that year's divisor:

* beneficiary divisor: Table I factor at the beneficiary's age on their birthday in
  year 1, minus 1 for each later year;
* if the owner died on or after the required beginning date, also the owner's
  remaining divisor: Table I factor at the owner's age on their birthday in the year
  of death, minus 1 for each year after; the larger (longer) divisor is used.

Simulation convention (an assumption, shown in the UI): growth accrues on the prior
year-end balance during the year and the withdrawal is taken at year end. Year 10
withdraws whatever remains. Money is Decimal, rounded to cents each year.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from hg.schemas import Beneficiary, Decedent
from hg.simulator.rules import age_on_birthday_in, annual_rmds_required, deadline_year, died_on_or_after_rbd
from hg.simulator.tables import life_expectancy

CENTS = Decimal("0.01")
YEARS = 10


def to_cents(value: Decimal) -> Decimal:
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class DivisorYear:
    year: int
    n: int
    beneficiary_factor: Decimal
    decedent_factor: Optional[Decimal]
    divisor: Decimal


def divisors(decedent: Decedent, beneficiary: Beneficiary) -> list[DivisorYear]:
    first_year = decedent.date_of_death.year + 1
    beneficiary_start = life_expectancy(age_on_birthday_in(beneficiary.date_of_birth, first_year))
    decedent_start = (
        life_expectancy(age_on_birthday_in(decedent.date_of_birth, decedent.date_of_death.year))
        if died_on_or_after_rbd(decedent) else None
    )
    out = []
    for n in range(1, YEARS + 1):
        b_factor = beneficiary_start - (n - 1)
        d_factor = decedent_start - n if decedent_start is not None else None
        out.append(
            DivisorYear(
                year=first_year + n - 1,
                n=n,
                beneficiary_factor=b_factor,
                decedent_factor=d_factor,
                divisor=max(b_factor, d_factor) if d_factor is not None else b_factor,
            )
        )
    return out


def required_minimum(prior_year_end: Decimal, divisor: Decimal) -> Decimal:
    """prior / divisor in cents; the whole balance once the divisor reaches 1 or less."""
    if divisor <= 1:
        return to_cents(prior_year_end)
    return min(to_cents(prior_year_end / divisor), to_cents(prior_year_end))


@dataclass(frozen=True)
class RmdYear:
    year: int
    n: int
    divisor: Decimal
    rmd: Decimal
    growth: Decimal
    withdrawal: Decimal
    end_balance: Decimal


@dataclass(frozen=True)
class RmdSchedule:
    years: list[RmdYear]
    annual_rmds_required: bool
    year_of_death_rmd_may_be_due: bool
    deadline_year: int


def rmd_schedule(
    balance_start: Decimal,
    decedent: Decedent,
    beneficiary: Beneficiary,
    growth_rate: Decimal,
    account_type: str = "traditional_ira",
) -> RmdSchedule:
    """Take only the minimums in years 1-9 and the rest in year 10.

    ``balance_start`` is the inherited balance at the end of the year of death.
    """
    annual = annual_rmds_required(account_type, decedent)
    prior = to_cents(balance_start)
    years = []
    for d in divisors(decedent, beneficiary):
        growth = to_cents(prior * growth_rate)
        available = prior + growth
        rmd = min(required_minimum(prior, d.divisor), available) if annual else Decimal("0.00")
        withdrawal = available if d.n == YEARS else rmd
        end = available - withdrawal
        years.append(RmdYear(d.year, d.n, d.divisor, rmd, growth, withdrawal, end))
        prior = end
    return RmdSchedule(
        years=years,
        annual_rmds_required=annual,
        year_of_death_rmd_may_be_due=died_on_or_after_rbd(decedent) and account_type == "traditional_ira",
        deadline_year=deadline_year(decedent),
    )
