# tests/test_simple/conftest.py

"""
Shared fixtures and helpers for test_simple tests.

Builds ScenarioData objects in-memory (no CSV files) using from_components().
"""

import tempfile
import os
import pytest

from pyoscomp.scenario.components import (
    TopologyComponent,
    TimeComponent,
    DemandComponent,
    SupplyComponent,
    PerformanceComponent,
    EconomicsComponent,
)
from pyoscomp.interfaces import ScenarioData


def build_scenario(
    years,
    seasons,
    daytypes,
    brackets,
    annual_demand=100.0,
    region="R1",
    technologies=None,
    validate=True,
):
    """
    Build a minimal ScenarioData with two generators (GAS_CCGT, GAS_PEAKER).

    Parameters
    ----------
    years : list[int]
    seasons : dict[str, int]   e.g. {'S1': 365}
    daytypes : dict[str, int]  e.g. {'D1': 1}
    brackets : dict[str, int]  e.g. {'H1': 24}
    annual_demand : float  GWh/yr (MWh in unit system with CAU=8760)
    region : str
    technologies : list[str] or None  defaults to ['GAS_CCGT', 'GAS_PEAKER']
    validate : bool

    Returns
    -------
    ScenarioData
    """
    if technologies is None:
        technologies = ["GAS_CCGT", "GAS_PEAKER"]

    with tempfile.TemporaryDirectory() as tmpdir:
        topology = TopologyComponent(tmpdir)
        topology.add_nodes([region])
        topology.save()

        time = TimeComponent(tmpdir)
        time.add_time_structure(
            years=years,
            seasons=seasons,
            daytypes=daytypes,
            brackets=brackets,
        )
        time.save()

        demand = DemandComponent(tmpdir)
        demand.add_annual_demand(region, "ELEC", {y: annual_demand for y in years})
        demand.process()
        demand.save()

        supply = SupplyComponent(tmpdir)
        for tech in technologies:
            eff = 0.5 if "CCGT" in tech else 0.4
            life = 30 if "CCGT" in tech else 25
            (
                supply.add_technology(region, tech)
                .with_operational_life(life)
                .with_residual_capacity(0)
                .as_conversion(input_fuel="GAS", output_fuel="ELEC")
            )
        supply.save()

        performance = PerformanceComponent(tmpdir)
        for tech in technologies:
            eff = 0.5 if "CCGT" in tech else 0.4
            performance.set_efficiency(region, tech, eff)
            performance.set_capacity_factor(region, tech, 1.0)
            performance.set_availability_factor(region, tech, 1.0)
            performance.set_capacity_to_activity_unit(region, tech, 8760)
            max_cap = {y: 1000 / 8760 for y in years}
            performance.set_capacity_limits(region, tech, max_capacity=max_cap, min_capacity=0)
        performance.process()
        performance.save()

        economics = EconomicsComponent(tmpdir)
        economics.set_discount_rate(region, 0.05)
        for tech in technologies:
            capex = 500 if "CCGT" in tech else 400
            opex = 2 if "CCGT" in tech else 5
            economics.set_capital_cost(region, tech, capex)
            economics.set_variable_cost(region, tech, "MODE1", opex)
            economics.set_fixed_cost(region, tech, 0)
        economics.save()

        return ScenarioData.from_components(
            topology,
            time,
            demand,
            supply,
            performance,
            economics,
            validate=validate,
        )
