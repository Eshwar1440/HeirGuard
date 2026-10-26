from datetime import date, timedelta
from decimal import Decimal

from hypothesis import given, settings
from hypothesis import strategies as st

from hg.config import get_settings
from hg.data_gen import load_truth
from hg.schemas import Beneficiary, Decedent, HeirInputs
from hg.simulator.rmd import required_minimum, rmd_schedule, to_cents
from hg.simulator.scenarios import SCENARIO_NAMES, simulate
from hg.simulator.tables import standard_deduction

D = Decimal


def _decedent(born, died, rmds_started=None):
    return Decedent(id="d", name="Hypothetical Owner", date_of_birth=born, date_of_death=died,
                    rmds_started=rmds_started)


def _heir(born, relationship="child"):
    return Beneficiary(id="b", name="Hypothetical Heir", date_of_birth=born, relationship=relationship,
                       share_percent=D(100), designation="primary")


def _demo():
    truth = load_truth(get_settings().data_dir / "packets" / "packet_01_fixed")
    share = truth.beneficiaries[0].share_percent / 100
    return truth, to_cents(truth.accounts[0].balance * share)


def test_demo_case_runs_all_four_scenarios():
    truth, balance = _demo()
    inputs = HeirInputs(annual_income=D("85000"), filing_status="single")
    result = simulate(balance, truth.decedent, truth.beneficiaries[0], "traditional_ira", inputs)

    assert [s.name for s in result.scenarios] == list(SCENARIO_NAMES)
    assert result.rules.annual_rmds_required is True
    assert len(result.factors) == 10 and result.tax_year == 2026
    for s in result.scenarios:
        assert len(s.years) == 10
        assert s.years[-1].year == result.rules.deadline_year
        assert s.after_tax_total == sum(y.withdrawal for y in s.years) - s.total_tax
    lump = result.scenarios[0]
    assert lump.years[0].end_balance == 0 and all(y.withdrawal == 0 for y in lump.years[1:])


def test_minimums_scenario_matches_rmd_schedule():
    truth, balance = _demo()
    inputs = HeirInputs(annual_income=D("60000"), filing_status="single", growth_rate=D("0.04"))
    result = simulate(balance, truth.decedent, truth.beneficiaries[0], "traditional_ira", inputs)
    minimums = next(s for s in result.scenarios if s.name == "minimums_then_balloon")
    schedule = rmd_schedule(balance, truth.decedent, truth.beneficiaries[0], D("0.04"))
    assert [y.withdrawal for y in minimums.years] == [y.withdrawal for y in schedule.years]


def test_fill_bracket_stays_inside_the_bracket_unless_rmd_forces_more():
    owner = _decedent(date(1950, 3, 1), date(2025, 2, 1), rmds_started=True)
    inputs = HeirInputs(annual_income=D("60000"), filing_status="single", bracket_to_fill="22%")
    result = simulate(D("400000"), owner, _heir(date(1978, 1, 1)), "traditional_ira", inputs)
    fill = next(s for s in result.scenarios if s.name == "fill_bracket")
    room = D("105700") - (D("60000") - standard_deduction("single"))  # 22% ceiling minus taxable income
    for y in fill.years[:-1]:
        assert y.withdrawal == max(min(room, y.withdrawal + y.end_balance), y.rmd_required)


def test_owner_who_died_before_2020_needs_a_specialist():
    owner = _decedent(date(1945, 3, 1), date(2019, 12, 31), rmds_started=True)
    inputs = HeirInputs(annual_income=D("50000"), filing_status="single")
    result = simulate(D("100000"), owner, _heir(date(1975, 1, 1)), "traditional_ira", inputs)
    assert result.scenarios == [] and result.rules.needs_specialist
    assert "before 2020" in result.rules.summary


def test_heir_born_after_the_death_is_rejected():
    import pytest

    owner = _decedent(date(1950, 3, 1), date(2024, 2, 1), rmds_started=True)
    inputs = HeirInputs(annual_income=D("0"), filing_status="single")
    with pytest.raises(ValueError, match="after the owner's date of death"):
        simulate(D("100000"), owner, _heir(date(2024, 6, 1)), "traditional_ira", inputs)


def test_entity_gets_no_scenarios():
    owner = _decedent(date(1950, 3, 1), date(2025, 2, 1), rmds_started=True)
    inputs = HeirInputs(annual_income=D("0"), filing_status="single")
    result = simulate(D("100000"), owner, _heir(date(1980, 1, 1), "estate"), "traditional_ira", inputs)
    assert result.scenarios == [] and result.rules.needs_specialist


@st.composite
def cases(draw):
    born = draw(st.dates(date(1930, 1, 1), date(1965, 12, 31)))
    died = draw(st.dates(max(born + timedelta(days=365 * 40), date(2018, 1, 1)), date(2025, 12, 31)))
    heir_born = draw(st.dates(date(1935, 1, 1), died))
    inputs = HeirInputs(
        annual_income=D(draw(st.integers(0, 600_000))),
        filing_status=draw(st.sampled_from(["single", "married_joint", "married_separate", "head_of_household"])),
        state_tax_rate=D(draw(st.integers(0, 10))) / 100,
        growth_rate=D(draw(st.integers(-5, 15))) / 100,
        bracket_to_fill=draw(st.sampled_from([None, "10", "12", "22", "24", "32", "35", "37"])),
    )
    return (
        D(draw(st.integers(100_000, 500_000_000))) / 100,
        _decedent(born, died, draw(st.sampled_from([None, True, False]))),
        _heir(heir_born, draw(st.sampled_from(["child", "sibling", "spouse", "grandchild"]))),
        draw(st.sampled_from(["traditional_ira", "roth_ira"])),
        inputs,
    )


@settings(max_examples=300, deadline=None)
@given(cases())
def test_every_scenario_reconciles_and_empties_by_the_deadline(case):
    balance, decedent, heir, account_type, inputs = case
    result = simulate(balance, decedent, heir, account_type, inputs)
    deadline = decedent.date_of_death.year + 10
    for s in result.scenarios:
        prior, growth = to_cents(balance), D("0.00")
        for y, f in zip(s.years, result.factors):
            year_growth = to_cents(prior * inputs.growth_rate)
            growth += year_growth
            assert y.end_balance == prior + year_growth - y.withdrawal
            assert y.withdrawal >= y.rmd_required >= 0 and y.end_balance >= 0
            if result.rules.annual_rmds_required:
                assert y.rmd_required == min(required_minimum(prior, f.divisor), prior + year_growth)
            else:
                assert y.rmd_required == 0
            assert y.incremental_federal_tax >= 0 and y.state_tax >= 0
            prior = y.end_balance
        # Sum of withdrawals equals the starting balance plus growth, to the cent.
        assert sum((y.withdrawal for y in s.years), D(0)) == to_cents(balance) + growth
        # The account is empty in or before the deadline year.
        assert s.years[-1].year == deadline and s.years[-1].end_balance == 0
