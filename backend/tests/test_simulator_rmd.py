from datetime import date
from decimal import Decimal

from hg.schemas import Beneficiary, Decedent
from hg.simulator.rmd import divisors, required_minimum, rmd_schedule


def _decedent(born, died, rmds_started=None):
    return Decedent(id="d", name="Hypothetical Owner", date_of_birth=born, date_of_death=died,
                    rmds_started=rmds_started)


def _heir(born, relationship="child"):
    return Beneficiary(id="b", name="Hypothetical Heir", date_of_birth=born, relationship=relationship,
                       share_percent=Decimal(100), designation="primary")


def test_golden_rmd_from_publication_590b_example():
    """IRS Pub. 590-B (2025), "Owner Died on or After Required Beginning Date", Example:

    "Your father died in 2021 at the age of 80 and you were the designated beneficiary.
    You started taking required minimum distributions from the inherited IRA in 2022 when
    you were age 55 ... the life expectancy for a 55-year-old is 31.6; therefore, you
    calculate your required minimum distribution for 2026 by dividing the account balance
    by 27.6 (31.6 - 4)."

    Worked by hand:
      Table I, age 55                      = 31.6  (beneficiary factor for 2022, year 1)
      2026 is year 5, so 31.6 - 4          = 27.6  (the IRS's divisor)
      Father: Table I, age 80 (2021)       = 11.2; for 2026, 11.2 - 5 = 6.2
      Longer divisor for 2026              = 27.6
      2026 RMD on a hypothetical $100,000 2025 year-end balance:
        100,000 / 27.6 = 3,623.1884...     -> $3,623.19
      2022 RMD on a hypothetical $100,000 2021 year-end balance:
        100,000 / 31.6 = 3,164.5569...     -> $3,164.56
    """
    father = _decedent(date(1941, 3, 1), date(2021, 8, 1))  # age 80 in 2021, after his RBD
    you = _heir(date(1967, 5, 1))  # age 55 in 2022

    by_year = {d.year: d for d in divisors(father, you)}
    assert by_year[2022].beneficiary_factor == Decimal("31.6")
    assert by_year[2026].beneficiary_factor == Decimal("27.6")
    assert by_year[2026].decedent_factor == Decimal("6.2")
    assert by_year[2026].divisor == Decimal("27.6")

    assert required_minimum(Decimal("100000"), by_year[2026].divisor) == Decimal("3623.19")
    schedule = rmd_schedule(Decimal("100000"), father, you, Decimal("0"))
    assert schedule.years[0].year == 2022 and schedule.years[0].rmd == Decimal("3164.56")


def test_owner_divisor_used_when_longer():
    owner = _decedent(date(1950, 2, 1), date(2025, 6, 1), rmds_started=True)  # 75 in 2025: 14.8
    older_sibling = _heir(date(1946, 1, 1), "sibling")  # 80 in 2026: 11.2
    first = divisors(owner, older_sibling)[0]
    assert first.beneficiary_factor == Decimal("11.2")
    assert first.decedent_factor == Decimal("13.8")
    assert first.divisor == Decimal("13.8")


def test_no_annual_rmds_when_owner_died_before_rbd():
    owner = _decedent(date(1961, 3, 3), date(2024, 6, 1))
    schedule = rmd_schedule(Decimal("250000"), owner, _heir(date(1990, 1, 1)), Decimal("0.05"))
    assert schedule.annual_rmds_required is False
    assert all(y.rmd == 0 and y.withdrawal == 0 for y in schedule.years[:9])
    assert schedule.years[9].year == 2034 and schedule.years[9].end_balance == 0


def test_inherited_roth_has_no_annual_rmds():
    owner = _decedent(date(1940, 1, 1), date(2025, 3, 1), rmds_started=True)
    schedule = rmd_schedule(Decimal("90000"), owner, _heir(date(1975, 1, 1)), Decimal("0.05"), "roth_ira")
    assert not schedule.annual_rmds_required and not schedule.year_of_death_rmd_may_be_due
    assert all(y.rmd == 0 for y in schedule.years)


def test_year_of_death_flag_and_deadline_on_december_31():
    owner = _decedent(date(1945, 1, 1), date(2025, 12, 31), rmds_started=True)
    schedule = rmd_schedule(Decimal("100000"), owner, _heir(date(1975, 1, 1)), Decimal("0"))
    assert schedule.year_of_death_rmd_may_be_due is True
    assert schedule.deadline_year == 2035
    assert schedule.years[-1].year == 2035 and schedule.years[-1].end_balance == 0


def test_divisor_at_or_below_one_takes_everything():
    assert required_minimum(Decimal("5000.00"), Decimal("0.8")) == Decimal("5000.00")
    assert required_minimum(Decimal("5000.00"), Decimal("1.0")) == Decimal("5000.00")
