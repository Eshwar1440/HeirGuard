from datetime import date
from decimal import Decimal

import pytest

from hg.schemas import Beneficiary, Decedent
from hg.simulator.rules import (
    annual_rmds_required,
    applicable_age,
    classify,
    deadline_year,
    died_on_or_after_rbd,
    required_beginning_date,
    rule_summary,
)


def _decedent(born: date, died: date, rmds_started=None) -> Decedent:
    return Decedent(id="d", name="Hypothetical Owner", date_of_birth=born, date_of_death=died,
                    rmds_started=rmds_started)


def _heir(born: date, relationship: str = "child", **extra) -> Beneficiary:
    return Beneficiary(id="b", name="Hypothetical Heir", date_of_birth=born, relationship=relationship,
                       share_percent=Decimal(100), designation="primary", **extra)


@pytest.mark.parametrize(
    "born, age",
    [
        (date(1949, 6, 30), "70.5"),
        (date(1949, 7, 1), "72"),
        (date(1950, 12, 31), "72"),
        (date(1951, 1, 1), "73"),
        (date(1959, 12, 31), "73"),
        (date(1960, 1, 1), "75"),
    ],
)
def test_applicable_age_boundaries(born, age):
    assert applicable_age(born) == Decimal(age)


@pytest.mark.parametrize(
    "born, rbd",
    [
        (date(1950, 5, 10), date(2023, 4, 1)),   # 72 in 2022
        (date(1949, 3, 15), date(2020, 4, 1)),   # 70.5 on 2019-09-15
        (date(1949, 1, 31), date(2020, 4, 1)),   # 70.5 on 2019-07-31
        (date(1948, 11, 20), date(2020, 4, 1)),  # 70.5 on 2019-05-20
        (date(1948, 6, 30), date(2019, 4, 1)),   # 70.5 on 2018-12-30
        (date(1955, 2, 1), date(2029, 4, 1)),    # 73 in 2028
        (date(1962, 8, 8), date(2038, 4, 1)),    # 75 in 2037
    ],
)
def test_required_beginning_date(born, rbd):
    assert required_beginning_date(born) == rbd


def test_rmds_started_overrides_the_date_comparison():
    young = _decedent(date(1960, 1, 1), date(2025, 1, 1))
    assert died_on_or_after_rbd(young) is False
    assert died_on_or_after_rbd(young.model_copy(update={"rmds_started": True})) is True


def test_decedent_died_before_rbd_means_no_annual_rmds_only_the_deadline():
    decedent = _decedent(date(1961, 3, 3), date(2024, 6, 1))
    summary = rule_summary(_heir(date(1990, 1, 1)), decedent, "traditional_ira")
    assert summary.beneficiary_class == "designated"
    assert summary.annual_rmds_required is False
    assert summary.deadline_year == 2034
    assert "No minimum is required" in summary.summary


def test_inherited_roth_never_has_annual_rmds():
    decedent = _decedent(date(1940, 1, 1), date(2025, 3, 1), rmds_started=True)
    assert annual_rmds_required("roth_ira", decedent) is False
    assert annual_rmds_required("traditional_ira", decedent) is True
    assert rule_summary(_heir(date(1975, 1, 1)), decedent, "roth_ira").year_of_death_rmd_may_be_due is False


def test_death_on_december_31_still_gives_year_plus_ten():
    assert deadline_year(_decedent(date(1950, 1, 1), date(2025, 12, 31))) == 2035


def test_classify():
    decedent = _decedent(date(1950, 6, 15), date(2025, 3, 1))
    assert classify(_heir(date(1955, 1, 1), "spouse"), decedent) == "spouse"
    assert classify(_heir(date(1960, 6, 15), "sibling"), decedent) == "eligible_designated"  # exactly 10 years
    assert classify(_heir(date(1960, 6, 16), "sibling"), decedent) == "designated"  # 10 years and 1 day
    assert classify(_heir(date(2010, 1, 1), "child"), decedent) == "eligible_designated"  # minor child
    assert classify(_heir(date(2004, 2, 28), "child"), decedent) == "designated"  # 21 before the death
    assert classify(_heir(date(2005, 3, 2), "grandchild"), decedent) == "designated"  # not the owner's child
    assert classify(_heir(date(1980, 1, 1), disabled=True), decedent) == "eligible_designated"
    assert classify(_heir(date(1980, 1, 1), chronically_ill=True), decedent) == "eligible_designated"
    assert classify(_heir(date(1980, 1, 1), "estate"), decedent) == "entity"


def test_entity_needs_a_specialist():
    decedent = _decedent(date(1950, 6, 15), date(2025, 3, 1))
    summary = rule_summary(_heir(date(1980, 1, 1), "trust"), decedent, "traditional_ira")
    assert summary.needs_specialist and summary.deadline_year is None and not summary.annual_rmds_required


def test_demo_packet_rules():
    from hg.config import get_settings
    from hg.data_gen import load_truth

    truth = load_truth(get_settings().data_dir / "packets" / "packet_01_fixed")
    summary = rule_summary(truth.beneficiaries[0], truth.decedent, truth.accounts[0].type)
    assert summary.beneficiary_class == "designated"
    assert summary.annual_rmds_required is True
    assert summary.deadline_year == truth.decedent.date_of_death.year + 10
