"""Inherited IRA rules (SECURE Act and SECURE 2.0), as code.

Sources: IRS Publication 590-B (2025) for the beneficiary categories, the
required beginning date and the 10-year rule; 26 CFR 1.401(a)(9)-4(e)(3) for
the age of majority (21). Disabled and chronically ill status come only from
explicit inputs on the beneficiary; they are never inferred.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from hg.schemas import BeneficiaryClass, Beneficiary, Decedent

#: 26 CFR 1.401(a)(9)-4(e)(3): an individual reaches the age of majority on their 21st birthday.
AGE_OF_MAJORITY = 21

#: Pub. 590-B: the 10-year rule applies when "the IRA owner dies in a tax year beginning
#: after December 31, 2019". Earlier deaths follow older rules and need a specialist.
FIRST_SECURE_DEATH_YEAR = 2020

ENTITY_RELATIONSHIPS = frozenset({"estate", "trust", "charity", "entity", "organization"})


def _add_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # February 29 in a non-leap year
        return date(d.year + years, 3, 1)


def _add_months(d: date, months: int) -> date:
    month = d.month - 1 + months
    year, month = d.year + month // 12, month % 12 + 1
    for day in (d.day, 30, 29, 28):
        try:
            return date(year, month, day)
        except ValueError:
            continue
    raise ValueError(d)


def age_on_birthday_in(birth: date, year: int) -> int:
    """Age attained on the birthday that falls in ``year``."""
    return year - birth.year


def applicable_age(birth: date) -> Decimal:
    """Age at which RMDs begin: 70.5 (born before July 1, 1949), 72 (through 1950),
    73 (1951 through 1959), 75 (1960 or later)."""
    if birth < date(1949, 7, 1):
        return Decimal("70.5")
    if birth.year <= 1950:
        return Decimal(72)
    if birth.year <= 1959:
        return Decimal(73)
    return Decimal(75)


def required_beginning_date(birth: date) -> date:
    """April 1 of the year after the year the owner reaches the applicable age."""
    age = applicable_age(birth)
    if age == Decimal("70.5"):
        reached = _add_months(_add_years(birth, 70), 6)
    else:
        reached = _add_years(birth, int(age))
    return date(reached.year + 1, 4, 1)


def died_on_or_after_rbd(decedent: Decedent) -> bool:
    """Uses ``rmds_started`` when the packet states it; otherwise compares dates."""
    if decedent.rmds_started is not None:
        return decedent.rmds_started
    return decedent.date_of_death >= required_beginning_date(decedent.date_of_birth)


def classify(beneficiary: Beneficiary, decedent: Decedent) -> BeneficiaryClass:
    relationship = beneficiary.relationship.strip().lower()
    if relationship in ENTITY_RELATIONSHIPS:
        return "entity"
    if relationship == "spouse":
        return "spouse"
    minor_child = (
        relationship == "child"
        and decedent.date_of_death < _add_years(beneficiary.date_of_birth, AGE_OF_MAJORITY)
    )
    not_more_than_10_years_younger = beneficiary.date_of_birth <= _add_years(decedent.date_of_birth, 10)
    if minor_child or beneficiary.disabled or beneficiary.chronically_ill or not_more_than_10_years_younger:
        return "eligible_designated"
    return "designated"


def deadline_year(decedent: Decedent) -> int:
    """Designated beneficiaries must empty the account by December 31 of this year."""
    return decedent.date_of_death.year + 10


def annual_rmds_required(account_type: str, decedent: Decedent) -> bool:
    """For a designated beneficiary: yes for a traditional IRA when the owner died on or
    after the RBD; never for an inherited Roth IRA."""
    return account_type == "traditional_ira" and died_on_or_after_rbd(decedent)


@dataclass(frozen=True)
class RuleSummary:
    beneficiary_class: BeneficiaryClass
    needs_specialist: bool
    deadline_year: Optional[int]
    annual_rmds_required: bool
    died_on_or_after_rbd: bool
    required_beginning_date: date
    year_of_death_rmd_may_be_due: bool
    summary: str


_SUMMARIES = {
    "spouse": (
        "As a surviving spouse you have more options than other heirs, such as treating the IRA as "
        "your own. The scenarios here show the 10-year path for comparison."
    ),
    "eligible_designated": (
        "As an eligible designated beneficiary you may be able to take distributions over your life "
        "expectancy instead of within 10 years. The scenarios here show the 10-year path for comparison."
    ),
    "entity": (
        "This beneficiary is an estate, trust or organization. Its rules need a specialist, so no "
        "scenarios are shown."
    ),
}


def rule_summary(beneficiary: Beneficiary, decedent: Decedent, account_type: str) -> RuleSummary:
    if beneficiary.date_of_birth > decedent.date_of_death:
        raise ValueError("the beneficiary's date of birth is after the owner's date of death")
    klass = beneficiary.beneficiary_class or classify(beneficiary, decedent)
    after_rbd = died_on_or_after_rbd(decedent)
    annual = annual_rmds_required(account_type, decedent)
    pre_secure = decedent.date_of_death.year < FIRST_SECURE_DEATH_YEAR
    specialist = klass == "entity" or pre_secure
    deadline = None if specialist else deadline_year(decedent)
    if pre_secure:
        summary = (
            "The owner died before 2020, so older inherited IRA rules apply. These need a specialist, "
            "so no scenarios are shown."
        )
    elif klass == "designated":
        summary = f"The account must be empty by December 31, {deadline}."
        summary += (
            " You must also take a minimum amount each year before then."
            if annual else " No minimum is required in the years before that."
        )
    else:
        summary = _SUMMARIES[klass]
    return RuleSummary(
        beneficiary_class=klass,
        needs_specialist=specialist,
        deadline_year=deadline,
        annual_rmds_required=annual and not specialist,
        died_on_or_after_rbd=after_rbd,
        required_beginning_date=required_beginning_date(decedent.date_of_birth),
        year_of_death_rmd_may_be_due=after_rbd and account_type == "traditional_ira",
        summary=summary,
    )
