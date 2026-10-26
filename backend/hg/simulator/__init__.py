"""M4: deterministic inherited IRA tax simulator. No LLM is involved."""

from hg.simulator.rmd import divisors, rmd_schedule
from hg.simulator.rules import classify, deadline_year, rule_summary
from hg.simulator.scenarios import SCENARIO_NAMES, SimulationResult, simulate
from hg.simulator.tax import assumptions, incremental_federal_tax

__all__ = [
    "SCENARIO_NAMES",
    "SimulationResult",
    "assumptions",
    "classify",
    "deadline_year",
    "divisors",
    "incremental_federal_tax",
    "rmd_schedule",
    "rule_summary",
    "simulate",
]
