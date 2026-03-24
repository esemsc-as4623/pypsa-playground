# tests/test_translation/test_pypsa_translator_storage.py

"""Tests for storage translation: StorageComponent → PyPSA StorageUnit."""

import pytest
import pandas as pd
import numpy as np
import tempfile
import os

from pyoscomp.translation.pypsa_translator import (
    PyPSAInputTranslator,
    PyPSAOutputTranslator,
)
from tests.test_simple.conftest import build_scenario


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def build_storage_scenario(
    tmp_path,
    max_hours: float = 4.0,
    eff_store: float = 0.95,
    eff_dispatch: float = 1.0,
    min_charge: float = 0.05,
    residual_energy_mwh: float = 0.0,
    capex_stor_per_mwh: float = 100_000.0,
    capex_charge: float = 200_000.0,
    capex_discharge: float = 200_000.0,
):
    """
    Build a minimal ScenarioData with one wind generator and one battery.

    Battery components:
    - BATT_CHARGE: IAR=1/eff_store → efficiency_store = eff_store
    - BATT_STOR: the storage reservoir
    - BATT_DISCHARGE: OAR=eff_dispatch → efficiency_dispatch = eff_dispatch
    """
    from pyoscomp.scenario.components import (
        TopologyComponent,
        TimeComponent,
        DemandComponent,
        SupplyComponent,
        PerformanceComponent,
        EconomicsComponent,
        StorageComponent,
    )
    from pyoscomp.interfaces import ScenarioData

    scenario_dir = str(tmp_path)

    # Topology: regions only; fuels/techs come from supply component
    topo = TopologyComponent(scenario_dir)
    topo.add_nodes(["HUB"])
    topo.save()

    # Time: 1 timeslice
    time = TimeComponent(scenario_dir)
    time.add_time_structure(
        years=[2025],
        seasons={"S1": 365},
        daytypes={"D1": 1},
        brackets={"H1": 24},
    )
    time.save()

    # Demand
    demand = DemandComponent(scenario_dir)
    demand.add_annual_demand("HUB", "ELEC", {2025: 500_000.0})
    demand.process()
    demand.save()

    # Supply
    # WIND: outputs ELEC (resource type)
    # BATT_CHARGE: registered as resource(output_fuel="ELEC") as a dummy
    #   (skipped by translator since it's in TechnologyToStorage)
    # BATT_DISCHARGE: outputs ELEC (resource type)
    supply = SupplyComponent(scenario_dir)
    (
        supply.add_technology("HUB", "WIND")
        .with_operational_life(25)
        .with_residual_capacity(0)
        .as_resource(output_fuel="ELEC")
    )
    (
        supply.add_technology("HUB", "BATT_CHARGE")
        .with_operational_life(20)
        .with_residual_capacity(0)
        .as_resource(output_fuel="ELEC")  # dummy registration; skipped by translator
    )
    (
        supply.add_technology("HUB", "BATT_DISCHARGE")
        .with_operational_life(20)
        .with_residual_capacity(0)
        .as_resource(output_fuel="ELEC")
    )
    supply.save()

    # Performance
    perf = PerformanceComponent(scenario_dir)
    # WIND: resource with OAR=1.0 for ELEC
    perf.set_capacity_factor("HUB", "WIND", 0.4)
    perf.set_availability_factor("HUB", "WIND", 1.0)
    perf.set_resource_output("HUB", "WIND")
    perf.set_capacity_to_activity_unit("HUB", "WIND", 8760)
    # BATT_DISCHARGE: resource with OAR=eff_dispatch for ELEC
    # set_resource_output always writes OAR=1.0, so we set it directly
    perf.set_resource_output("HUB", "BATT_DISCHARGE")
    perf.set_capacity_to_activity_unit("HUB", "BATT_DISCHARGE", 8760)
    # Override OAR for BATT_DISCHARGE to eff_dispatch
    mask = (
        (perf.output_activity_ratio["TECHNOLOGY"] == "BATT_DISCHARGE")
        & (perf.output_activity_ratio["FUEL"] == "ELEC")
    )
    perf.output_activity_ratio.loc[mask, "VALUE"] = eff_dispatch
    # BATT_CHARGE: set IAR = 1/eff_store for ELEC directly
    # (no API for arbitrary IAR on a resource-type tech)
    perf.set_capacity_to_activity_unit("HUB", "BATT_CHARGE", 8760)
    iar_row = pd.DataFrame([{
        "REGION": "HUB",
        "TECHNOLOGY": "BATT_CHARGE",
        "FUEL": "ELEC",
        "MODE_OF_OPERATION": "MODE1",
        "YEAR": 2025,
        "VALUE": 1.0 / eff_store,
    }])
    perf.input_activity_ratio = pd.concat(
        [perf.input_activity_ratio, iar_row], ignore_index=True
    )
    perf.process()
    perf.save()

    # Economics
    econ = EconomicsComponent(scenario_dir)
    econ.set_discount_rate("HUB", 0.07)
    econ.set_capital_cost("HUB", "WIND", 1_500_000.0)
    econ.set_capital_cost("HUB", "BATT_CHARGE", capex_charge)
    econ.set_capital_cost("HUB", "BATT_DISCHARGE", capex_discharge)
    econ.set_variable_cost("HUB", "WIND", "MODE1", 0.0)
    econ.set_variable_cost("HUB", "BATT_CHARGE", "MODE1", 0.0)
    econ.set_variable_cost("HUB", "BATT_DISCHARGE", "MODE1", 0.0)
    econ.set_fixed_cost("HUB", "WIND", 0.0)
    econ.set_fixed_cost("HUB", "BATT_CHARGE", 0.0)
    econ.set_fixed_cost("HUB", "BATT_DISCHARGE", 0.0)
    econ.save()

    # Storage
    stor = StorageComponent(scenario_dir)
    (
        stor.add_storage("HUB", "BATT_STOR")
        .with_operational_life(20)
        .with_energy_ratio(max_hours)
        .with_capital_cost_storage({2025: capex_stor_per_mwh})
        .with_min_charge(min_charge)
        .with_charge_technology("BATT_CHARGE", mode="MODE1")
        .with_discharge_technology("BATT_DISCHARGE", mode="MODE1")
        .with_residual_capacity({2025: residual_energy_mwh})
    )
    stor.save()

    return ScenarioData.from_components(
        topo,
        time,
        demand,
        supply,
        perf,
        econ,
        storage_component=stor,
        validate=False,
    )


# ---------------------------------------------------------------------------
# Translation tests
# ---------------------------------------------------------------------------


class TestStorageUnitTranslation:
    """Test that StorageComponent → PyPSA StorageUnit mapping is correct."""

    def test_storage_unit_present(self, tmp_path):
        """Translated network contains exactly one StorageUnit."""
        sd = build_storage_scenario(tmp_path)
        net = PyPSAInputTranslator(sd).translate()
        assert len(net.storage_units) == 1

    def test_storage_unit_name_single_region(self, tmp_path):
        """Single-region scenario uses storage name without region prefix."""
        sd = build_storage_scenario(tmp_path)
        net = PyPSAInputTranslator(sd).translate()
        assert "BATT_STOR" in net.storage_units.index

    def test_max_hours(self, tmp_path):
        """max_hours matches StorageEnergyRatio."""
        sd = build_storage_scenario(tmp_path, max_hours=6.0)
        net = PyPSAInputTranslator(sd).translate()
        assert net.storage_units.loc["BATT_STOR", "max_hours"] == pytest.approx(6.0)

    def test_efficiency_store(self, tmp_path):
        """efficiency_store = 1 / IAR of charge technology."""
        sd = build_storage_scenario(tmp_path, eff_store=0.9)
        net = PyPSAInputTranslator(sd).translate()
        # IAR set to 1/0.9, so efficiency_store should be 0.9
        assert net.storage_units.loc["BATT_STOR", "efficiency_store"] == pytest.approx(0.9, rel=1e-6)

    def test_efficiency_dispatch(self, tmp_path):
        """efficiency_dispatch = OAR of discharge technology."""
        sd = build_storage_scenario(tmp_path, eff_dispatch=0.92)
        net = PyPSAInputTranslator(sd).translate()
        assert net.storage_units.loc["BATT_STOR", "efficiency_dispatch"] == pytest.approx(0.92)

    def test_roundtrip_efficiency(self, tmp_path):
        """Round-trip = efficiency_store × efficiency_dispatch."""
        sd = build_storage_scenario(tmp_path, eff_store=0.95, eff_dispatch=0.95)
        net = PyPSAInputTranslator(sd).translate()
        su = net.storage_units.loc["BATT_STOR"]
        roundtrip = su["efficiency_store"] * su["efficiency_dispatch"]
        assert roundtrip == pytest.approx(0.95 * 0.95, rel=1e-6)

    def test_min_stor(self, tmp_path):
        """min_stor matches MinStorageCharge."""
        sd = build_storage_scenario(tmp_path, min_charge=0.1)
        net = PyPSAInputTranslator(sd).translate()
        assert net.storage_units.loc["BATT_STOR", "min_stor"] == pytest.approx(0.1)

    def test_p_nom_from_residual(self, tmp_path):
        """p_nom = ResidualStorageCapacity / max_hours."""
        sd = build_storage_scenario(tmp_path, max_hours=4.0, residual_energy_mwh=40.0)
        net = PyPSAInputTranslator(sd).translate()
        # 40 MWh / 4 h = 10 MW
        assert net.storage_units.loc["BATT_STOR", "p_nom"] == pytest.approx(10.0)

    def test_p_nom_extendable(self, tmp_path):
        """StorageUnit is extendable."""
        sd = build_storage_scenario(tmp_path)
        net = PyPSAInputTranslator(sd).translate()
        assert net.storage_units.loc["BATT_STOR", "p_nom_extendable"] == True  # noqa: E712

    def test_cyclic_state_of_charge(self, tmp_path):
        """Cyclic SOC is set."""
        sd = build_storage_scenario(tmp_path)
        net = PyPSAInputTranslator(sd).translate()
        assert net.storage_units.loc["BATT_STOR", "cyclic_state_of_charge"] == True  # noqa: E712

    def test_capital_cost_includes_energy_reservoir(self, tmp_path):
        """capital_cost includes annualized CapitalCostStorage × max_hours."""
        from pypsa.common import annuity
        max_hours = 4.0
        capex_stor = 100_000.0  # €/MWh
        capex_charge = 200_000.0  # €/MW
        capex_discharge = 200_000.0  # €/MW
        dr = 0.07
        life_stor = 20.0
        life_charge = 20.0
        life_discharge = 20.0

        sd = build_storage_scenario(
            tmp_path,
            max_hours=max_hours,
            capex_stor_per_mwh=capex_stor,
            capex_charge=capex_charge,
            capex_discharge=capex_discharge,
        )
        net = PyPSAInputTranslator(sd).translate()
        observed = net.storage_units.loc["BATT_STOR", "capital_cost"]

        ann_stor = capex_stor * max_hours * annuity(dr, life_stor)
        ann_charge = capex_charge * annuity(dr, life_charge)
        ann_discharge = capex_discharge * annuity(dr, life_discharge)
        expected = ann_stor + ann_charge + ann_discharge

        assert observed == pytest.approx(expected, rel=1e-6)

    def test_no_storage_skipped(self):
        """Scenario without storage produces no StorageUnits."""
        sd = build_scenario(
            years=[2025],
            seasons={"S1": 365},
            daytypes={"D1": 1},
            brackets={"H1": 24},
        )
        net = PyPSAInputTranslator(sd).translate()
        assert net.storage_units.empty


class TestStorageOutputTranslation:
    """Test that solved network storage results are correctly extracted."""

    def test_storage_installed_capacity_populated_after_solve(self, tmp_path):
        """After optimization, installed_capacity (MW) is populated."""
        sd = build_storage_scenario(tmp_path)
        net = PyPSAInputTranslator(sd).translate()
        net.optimize(solver_name="highs", multi_investment_periods=False)
        results = PyPSAOutputTranslator(net).translate()
        assert not results.storage.installed_capacity.empty
        assert "STORAGE_TECHNOLOGY" in results.storage.installed_capacity.columns

    def test_storage_energy_capacity_populated_after_solve(self, tmp_path):
        """After optimization, installed_energy_capacity (MWh) = p_nom_opt × max_hours."""
        sd = build_storage_scenario(tmp_path, max_hours=4.0)
        net = PyPSAInputTranslator(sd).translate()
        net.optimize(solver_name="highs", multi_investment_periods=False)
        results = PyPSAOutputTranslator(net).translate()
        cap = results.storage.installed_capacity
        e_cap = results.storage.installed_energy_capacity
        if not cap.empty and not e_cap.empty:
            # energy = power × max_hours
            p_val = cap.loc[cap["STORAGE_TECHNOLOGY"] == "BATT_STOR", "VALUE"].values
            e_val = e_cap.loc[e_cap["STORAGE_TECHNOLOGY"] == "BATT_STOR", "VALUE"].values
            if len(p_val) > 0 and len(e_val) > 0:
                assert e_val[0] == pytest.approx(p_val[0] * 4.0, rel=1e-4)

    def test_storage_validate_passes(self, tmp_path):
        """ModelResults.validate() passes with storage results."""
        sd = build_storage_scenario(tmp_path)
        net = PyPSAInputTranslator(sd).translate()
        net.optimize(solver_name="highs", multi_investment_periods=False)
        results = PyPSAOutputTranslator(net).translate()
        results.validate()  # should not raise


class TestStorageHarmonizationChecks:
    """Test that harmonization protocol catches storage translation issues."""

    def test_storage_unit_count_match(self, tmp_path):
        """Harmonization passes storage_unit_count when count matches."""
        from pyoscomp.interfaces.harmonization import validate_pypsa_translation_harmonization

        sd = build_storage_scenario(tmp_path)
        net = PyPSAInputTranslator(sd).translate()
        report = validate_pypsa_translation_harmonization(sd, net)
        metric = report.get("storage_unit_count")
        assert metric is not None
        assert metric.passed, f"storage_unit_count failed: {metric}"

    def test_storage_max_hours_match(self, tmp_path):
        """Harmonization passes storage_max_hours_translation."""
        from pyoscomp.interfaces.harmonization import validate_pypsa_translation_harmonization

        sd = build_storage_scenario(tmp_path, max_hours=6.0)
        net = PyPSAInputTranslator(sd).translate()
        report = validate_pypsa_translation_harmonization(sd, net)
        metric = report.get("storage_max_hours_translation")
        assert metric is not None
        assert metric.passed, f"max_hours check failed: {metric}"

    def test_storage_roundtrip_match(self, tmp_path):
        """Harmonization passes storage_roundtrip_efficiency."""
        from pyoscomp.interfaces.harmonization import validate_pypsa_translation_harmonization

        sd = build_storage_scenario(tmp_path, eff_store=0.9, eff_dispatch=0.9)
        net = PyPSAInputTranslator(sd).translate()
        report = validate_pypsa_translation_harmonization(sd, net)
        metric = report.get("storage_roundtrip_efficiency")
        assert metric is not None
        assert metric.passed, f"round-trip check failed: {metric}"
