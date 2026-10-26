"""Four withdrawal scenarios on the same balance and growth assumption.

* lump_sum_now: everything in year 1.
* minimums_then_balloon: only the RMD in years 1-9, the rest in year 10.
* even_spread: the available balance divided by the years remaining, never below the RMD.
* fill_bracket: withdraw up to the top of the chosen federal bracket, never below the
  RMD; whatever is left comes out in year 10. Without a chosen bracket, the heir's
  current bracket is filled.

Every scenario empties the account by the 10th year after death. The engine targets
the designated-beneficiary 10-year path; entities get no scenarios.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable

from hg.schemas import Beneficiary, Decedent, HeirInputs, Scenario, ScenarioYear
from hg.simulator.rmd import YEARS, DivisorYear, divisors, required_minimum, to_cents
from hg.simulator.rules import RuleSummary, rule_summary
from hg.simulator.tables import standard_deduction, tax_year
from hg.simulator.tax import (
    assumptions,
    bracket_ceiling,
    current_rate,
    incremental_federal_tax,
    parse_rate,
    state_tax,
)

SCENARIO_NAMES = ("lump_sum_now", "minimums_then_balloon", "even_spread", "fill_bracket")
ZERO = Decimal("0.00")

# A policy proposes a withdrawal from (available balance, years remaining incl. this one).
Policy = Callable[[Decimal, int], Decimal]


@dataclass(frozen=True)
class SimulationResult:
    scenarios: list[Scenario]
    factors: list[DivisorYear]
    rules: RuleSummary
    assumptions: list[str]
    tax_year: int
    fill_rate: Decimal


def _fill_bracket_policy(inputs: HeirInputs, rate: Decimal) -> Policy:
    ceiling = bracket_ceiling(rate, inputs.filing_status)

    def policy(available: Decimal, _years_left: int) -> Decimal:
        if ceiling is None:
            return available
        room = ceiling - (inputs.annual_income - standard_deduction(inputs.filing_status))
        return max(to_cents(room), ZERO)

    return policy


def _run(
    name: str,
    policy: Policy,
    balance: Decimal,
    factors: list[DivisorYear],
    annual_rmds: bool,
    inputs: HeirInputs,
) -> Scenario:
    prior = to_cents(balance)
    years = []
    for d in factors:
        available = prior + to_cents(prior * inputs.growth_rate)
        rmd = min(required_minimum(prior, d.divisor), available) if annual_rmds else ZERO
        if d.n == YEARS:
            withdrawal = available
        else:
            withdrawal = min(max(to_cents(policy(available, YEARS - d.n + 1)), rmd), available)
        years.append(
            ScenarioYear(
                year=d.year,
                withdrawal=withdrawal,
                rmd_required=rmd,
                incremental_federal_tax=incremental_federal_tax(
                    inputs.annual_income, withdrawal, inputs.filing_status
                ),
                state_tax=state_tax(withdrawal, inputs.state_tax_rate),
                end_balance=available - withdrawal,
            )
        )
        prior = available - withdrawal
    total_tax = sum((y.incremental_federal_tax + y.state_tax for y in years), ZERO)
    withdrawn = sum((y.withdrawal for y in years), ZERO)
    return Scenario(name=name, years=years, total_tax=total_tax, after_tax_total=withdrawn - total_tax)


def simulate(
    balance: Decimal,
    decedent: Decedent,
    beneficiary: Beneficiary,
    account_type: str,
    inputs: HeirInputs,
) -> SimulationResult:
    """Run the four scenarios for one beneficiary's inherited share (``balance``)."""
    rules = rule_summary(beneficiary, decedent, account_type)
    factors = divisors(decedent, beneficiary)
    fill_rate = (
        parse_rate(inputs.bracket_to_fill) if inputs.bracket_to_fill
        else current_rate(inputs.annual_income, inputs.filing_status)
    )
    if rules.needs_specialist:
        return SimulationResult([], factors, rules, assumptions(), tax_year(), fill_rate)

    policies: dict[str, Policy] = {
        "lump_sum_now": lambda available, _left: available,
        "minimums_then_balloon": lambda _available, _left: ZERO,
        "even_spread": lambda available, left: available / left,
        "fill_bracket": _fill_bracket_policy(inputs, fill_rate),
    }
    scenarios = [
        _run(name, policies[name], balance, factors, rules.annual_rmds_required, inputs)
        for name in SCENARIO_NAMES
    ]
    return SimulationResult(scenarios, factors, rules, assumptions(), tax_year(), fill_rate)
