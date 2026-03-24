"""
pyoscomp.experiments — Experiment infrastructure for model comparison.

Provides helpers to build scenarios, run both PyPSA and OSeMOSYS, and
collect structured comparison results for the experimental ladder.
"""

import logging
import tempfile
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

import pandas as pd

from pyoscomp.interfaces import ScenarioData
from pyoscomp.interfaces.results import ModelResults, compare, divergence_analysis, DivergenceFlag
from pyoscomp.runners.pypsa import PyPSARunner
from pyoscomp.runners.osemosys import OSeMOSYSRunner
from pyoscomp.translation.osemosys_translator import OSeMOSYSOutputTranslator
from pyoscomp.scenario.components import (
    TopologyComponent,
    TimeComponent,
    DemandComponent,
    SupplyComponent,
    PerformanceComponent,
    EconomicsComponent,
)
from pyoscomp.scenario.components.storage import StorageComponent

logger = logging.getLogger(__name__)


@dataclass
class ExperimentResult:
    """Container for a single experiment's comparison results."""
    label: str
    scenario_data: ScenarioData
    pypsa_results: ModelResults
    osemosys_results: ModelResults
    comparison: Dict[str, pd.DataFrame]
    flags: List[DivergenceFlag]


def run_comparison(
    scenario_data: ScenarioData,
    label: str,
    solver_name: str = "highs",
) -> ExperimentResult:
    """
    Run both PyPSA and OSeMOSYS on the same ScenarioData and compare results.

    Parameters
    ----------
    scenario_data : ScenarioData
        Validated, frozen scenario to run.
    label : str
        Human-readable experiment label (e.g. "Exp 0: Gas Baseline").
    solver_name : str
        LP solver for PyPSA (default: "highs").

    Returns
    -------
    ExperimentResult
    """
    logger.info("Running experiment: %s", label)

    # --- PyPSA ---
    logger.info("  PyPSA: building and solving...")
    pypsa_runner = PyPSARunner(scenario_data, solver_name=solver_name)
    pypsa_runner.run()
    pypsa_results = pypsa_runner.get_results()

    # --- OSeMOSYS ---
    logger.info("  OSeMOSYS: translating, solving with glpsol...")
    osemosys_runner = OSeMOSYSRunner.from_scenario_data(scenario_data)
    results_dir = osemosys_runner.run()
    osemosys_results = OSeMOSYSOutputTranslator(results_dir).translate()

    # --- Compare ---
    logger.info("  Comparing results...")
    flags, tables = divergence_analysis(pypsa_results, osemosys_results)

    logger.info("  Done. %d divergence flags.", len(flags))
    return ExperimentResult(
        label=label,
        scenario_data=scenario_data,
        pypsa_results=pypsa_results,
        osemosys_results=osemosys_results,
        comparison=tables,
        flags=flags,
    )


def build_experiment_scenario(
    *,
    region: str = "HUB",
    years: List[int] = None,
    seasons: Dict[str, int] = None,
    daytypes: Dict[str, int] = None,
    brackets: Dict[str, int] = None,
    annual_demand: float = 100.0,
    demand_fuel: str = "ELEC",
    demand_by_year: Dict[int, float] = None,
    technologies: List[Dict[str, Any]] = None,
    storage: List[Dict[str, Any]] = None,
    discount_rate: float = 0.05,
) -> ScenarioData:
    """
    Build a ScenarioData from a declarative config.

    Parameters
    ----------
    region : str
        Single region name.
    years : list[int]
        Model years (default: [2030]).
    seasons : dict[str, int]
        Season name → days (default: {"S1": 365}).
    daytypes : dict[str, int]
        Daytype name → count (default: {"D1": 1}).
    brackets : dict[str, int]
        Bracket name → hours (default: {"H1": 24}).
    annual_demand : float
        Annual demand in model units (used if demand_by_year is None).
    demand_fuel : str
        Fuel name for demand.
    demand_by_year : dict[int, float], optional
        Year-specific demand. Overrides annual_demand.
    technologies : list[dict]
        Each dict: {name, type, capex, variable_cost, fixed_cost, oplife,
                     efficiency, capacity_factor, max_capacity, ...}
        type: "dispatchable" | "renewable"
    storage : list[dict], optional
        Each dict: {name, charge_tech, discharge_tech, energy_ratio, round_trip_eff,
                     capex_power, capex_energy, oplife, min_charge, ...}
    discount_rate : float
        Regional discount rate.

    Returns
    -------
    ScenarioData
    """
    if years is None:
        years = [2030]
    if seasons is None:
        seasons = {"S1": 365}
    if daytypes is None:
        daytypes = {"D1": 1}
    if brackets is None:
        brackets = {"H1": 24}
    if technologies is None:
        technologies = []

    with tempfile.TemporaryDirectory() as tmpdir:
        # Topology
        topo = TopologyComponent(tmpdir)
        topo.add_nodes([region])
        topo.save()

        # Time
        time_comp = TimeComponent(tmpdir)
        time_comp.add_time_structure(
            years=years, seasons=seasons, daytypes=daytypes, brackets=brackets,
        )
        time_comp.save()

        # Demand
        demand_comp = DemandComponent(tmpdir)
        if demand_by_year is not None:
            demand_comp.add_annual_demand(region, demand_fuel, demand_by_year)
        else:
            demand_comp.add_annual_demand(
                region, demand_fuel, {y: annual_demand for y in years}
            )
        demand_comp.process()
        demand_comp.save()

        # Supply
        supply_comp = SupplyComponent(tmpdir)
        for tech in technologies:
            builder = supply_comp.add_technology(region, tech["name"])
            builder.with_operational_life(tech.get("oplife", 25))
            builder.with_residual_capacity(tech.get("residual_capacity", 0))
            if tech.get("type") == "renewable":
                builder.as_resource(output_fuel=tech.get("output_fuel", "ELEC"))
            else:
                builder.as_conversion(
                    input_fuel=tech.get("input_fuel", "GAS"),
                    output_fuel=tech.get("output_fuel", "ELEC"),
                )

        # Add storage charge/discharge technologies
        if storage:
            for st in storage:
                # Charge tech
                charge_builder = supply_comp.add_technology(region, st["charge_tech"])
                charge_builder.with_operational_life(st.get("oplife", 20))
                charge_builder.with_residual_capacity(0)
                charge_builder.as_conversion(
                    input_fuel=st.get("input_fuel", "ELEC"),
                    output_fuel=st.get("storage_fuel", f"{st['name']}_STORED"),
                )
                # Discharge tech
                discharge_builder = supply_comp.add_technology(region, st["discharge_tech"])
                discharge_builder.with_operational_life(st.get("oplife", 20))
                discharge_builder.with_residual_capacity(0)
                discharge_builder.as_conversion(
                    input_fuel=st.get("storage_fuel", f"{st['name']}_STORED"),
                    output_fuel=st.get("output_fuel", "ELEC"),
                )
        supply_comp.save()

        # Performance
        perf_comp = PerformanceComponent(tmpdir)
        for tech in technologies:
            name = tech["name"]
            cf = tech.get("capacity_factor", 1.0)
            af = tech.get("availability_factor", 1.0)
            cau = tech.get("capacity_to_activity_unit", 8760)

            if tech.get("type") == "renewable":
                perf_comp.set_resource_output(region, name)
                # Support seasonal CF via weights
                if isinstance(cf, dict) and "season_weights" in cf:
                    perf_comp.set_capacity_factor(
                        region, name, cf["base"],
                        season_weights=cf["season_weights"],
                    )
                else:
                    perf_comp.set_capacity_factor(region, name, cf if not isinstance(cf, dict) else cf.get("base", 1.0))
            else:
                eff = tech.get("efficiency", 0.5)
                perf_comp.set_efficiency(region, name, eff)
                perf_comp.set_capacity_factor(region, name, cf if not isinstance(cf, dict) else cf.get("base", 1.0))

            perf_comp.set_availability_factor(region, name, af)
            perf_comp.set_capacity_to_activity_unit(region, name, cau)

            max_cap = tech.get("max_capacity")
            if max_cap is not None:
                if isinstance(max_cap, (int, float)):
                    max_cap = {y: max_cap for y in years}
                perf_comp.set_capacity_limits(region, name, max_capacity=max_cap, min_capacity=0)

        # Storage charge/discharge performance
        if storage:
            for st in storage:
                rt_eff = st.get("round_trip_eff", 0.9)
                charge_eff = rt_eff ** 0.5
                discharge_eff = rt_eff ** 0.5

                for tech_name in [st["charge_tech"], st["discharge_tech"]]:
                    is_charge = tech_name == st["charge_tech"]
                    eff = charge_eff if is_charge else discharge_eff
                    perf_comp.set_efficiency(region, tech_name, eff)
                    perf_comp.set_availability_factor(region, tech_name, 1.0)
                    perf_comp.set_capacity_factor(region, tech_name, 1.0)
                    perf_comp.set_capacity_to_activity_unit(region, tech_name, 8760)

        perf_comp.process()
        perf_comp.save()

        # Economics
        econ_comp = EconomicsComponent(tmpdir)
        econ_comp.set_discount_rate(region, discount_rate)
        for tech in technologies:
            name = tech["name"]
            capex = tech.get("capex", 1000)
            var_cost = tech.get("variable_cost", 0)
            fix_cost = tech.get("fixed_cost", 0)
            econ_comp.set_capital_cost(region, name, capex)
            econ_comp.set_variable_cost(region, name, "MODE1", var_cost)
            econ_comp.set_fixed_cost(region, name, fix_cost)

        if storage:
            for st in storage:
                capex_power = st.get("capex_power", 200_000)
                for tech_name in [st["charge_tech"], st["discharge_tech"]]:
                    econ_comp.set_capital_cost(region, tech_name, capex_power)
                    econ_comp.set_variable_cost(region, tech_name, "MODE1", 0)
                    econ_comp.set_fixed_cost(region, tech_name, 0)

        econ_comp.save()

        # Storage component
        components = [topo, time_comp, demand_comp, supply_comp, perf_comp, econ_comp]
        if storage:
            stor_comp = StorageComponent(tmpdir)
            for st in storage:
                builder = stor_comp.add_storage(region, st["name"])
                builder.with_operational_life(st.get("oplife", 20))
                builder.with_energy_ratio(st.get("energy_ratio", 4.0))
                capex_energy = st.get("capex_energy", 100_000)
                builder.with_capital_cost_storage({y: capex_energy for y in years})
                builder.with_min_charge(st.get("min_charge", 0.0))
                builder.with_charge_technology(st["charge_tech"])
                builder.with_discharge_technology(st["discharge_tech"])
                builder.with_residual_capacity({y: 0.0 for y in years})
            stor_comp.save()
            components.append(stor_comp)

        return ScenarioData.from_components(*components, validate=True)


def summarize_results(result: ExperimentResult) -> pd.DataFrame:
    """
    Create a one-row summary DataFrame for an experiment result.

    Columns: label, pypsa_objective, osemosys_objective, obj_rel_diff,
             n_flags, n_structural, n_unexplained, capacity_match, ...
    """
    tables = result.comparison
    pypsa_obj = result.pypsa_results.objective
    osemosys_obj = result.osemosys_results.objective
    scale = max(abs(pypsa_obj), abs(osemosys_obj), 1e-10)
    obj_rel = abs(pypsa_obj - osemosys_obj) / scale

    n_structural = sum(1 for f in result.flags if f.structural)
    n_unexplained = sum(1 for f in result.flags if not f.structural)

    # Capacity match rate
    supply_table = tables.get("supply", pd.DataFrame())
    if not supply_table.empty and "MATCH" in supply_table.columns:
        cap_match_rate = supply_table["MATCH"].mean()
    else:
        cap_match_rate = float("nan")

    return pd.DataFrame([{
        "label": result.label,
        "pypsa_objective": pypsa_obj,
        "osemosys_objective": osemosys_obj,
        "obj_rel_diff": obj_rel,
        "n_flags": len(result.flags),
        "n_structural": n_structural,
        "n_unexplained": n_unexplained,
        "capacity_match_rate": cap_match_rate,
    }])


def summarize_all(results: List[ExperimentResult]) -> pd.DataFrame:
    """Concatenate summaries of multiple experiments into one table."""
    return pd.concat(
        [summarize_results(r) for r in results], ignore_index=True
    )
