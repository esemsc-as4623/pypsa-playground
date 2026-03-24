# tests/test_scenario/test_components/test_storage.py

"""
Tests for StorageComponent and StorageParameters.

Covers:
- StorageBuilder fluent API
- StorageComponent.validate() error paths
- CSV round-trip (save → load → compare)
- ScenarioData.from_components() with storage
- ScenarioData.from_directory() with storage CSVs
- StorageParameters.validate() against OSeMOSYSSets
"""

import pytest
import tempfile
import os
import pandas as pd

from pyoscomp.scenario.components import (
    TopologyComponent,
    TimeComponent,
    DemandComponent,
    SupplyComponent,
    PerformanceComponent,
    EconomicsComponent,
    StorageComponent,
)
from pyoscomp.interfaces.containers import ScenarioData
from pyoscomp.interfaces.parameters import StorageParameters
from pyoscomp.interfaces.sets import OSeMOSYSSets


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmpdir():
    with tempfile.TemporaryDirectory() as d:
        yield d


@pytest.fixture
def base_components(tmpdir):
    """Topology + time prerequisites only."""
    topo = TopologyComponent(tmpdir)
    topo.add_nodes(["R1"])
    topo.save()

    time = TimeComponent(tmpdir)
    time.add_time_structure(
        years=[2025, 2030],
        seasons={"S1": 365},
        daytypes={"D1": 1},
        brackets={"H1": 24},
    )
    time.save()
    return topo, time


@pytest.fixture
def full_components(tmpdir, base_components):
    """Full component set including charge/discharge techs."""
    topo, time = base_components

    supply = SupplyComponent(tmpdir)
    supply.add_technology("R1", "BATT_CHG").with_operational_life(20).with_residual_capacity(0).as_conversion("ELEC", "BELEC")
    supply.add_technology("R1", "BATT_DIS").with_operational_life(20).with_residual_capacity(0).as_conversion("BELEC", "ELEC")
    supply.add_technology("R1", "GAS").with_operational_life(30).with_residual_capacity(0).as_conversion("GAS_F", "ELEC")
    supply.save()

    demand = DemandComponent(tmpdir)
    demand.add_annual_demand("R1", "ELEC", {2025: 100, 2030: 120})
    demand.process()
    demand.save()

    perf = PerformanceComponent(tmpdir)
    for tech in ["BATT_CHG", "BATT_DIS", "GAS"]:
        perf.set_efficiency("R1", tech, 0.9)
        perf.set_capacity_factor("R1", tech, 1.0)
        perf.set_availability_factor("R1", tech, 1.0)
        perf.set_capacity_to_activity_unit("R1", tech, 8760)
        perf.set_capacity_limits("R1", tech, max_capacity={2025: 500 / 8760, 2030: 500 / 8760}, min_capacity=0)
    perf.process()
    perf.save()

    econ = EconomicsComponent(tmpdir)
    econ.set_discount_rate("R1", 0.05)
    for tech in ["BATT_CHG", "BATT_DIS", "GAS"]:
        econ.set_capital_cost("R1", tech, 500)
        econ.set_variable_cost("R1", tech, "MODE1", 2)
        econ.set_fixed_cost("R1", tech, 0)
    econ.save()

    return topo, time, demand, supply, perf, econ


# ---------------------------------------------------------------------------
# StorageBuilder tests
# ---------------------------------------------------------------------------

class TestStorageBuilder:
    def test_full_build(self, tmpdir, base_components):
        stor = StorageComponent(tmpdir)
        stor.add_storage("R1", "BATT") \
            .with_operational_life(20) \
            .with_energy_ratio(4.0) \
            .with_capital_cost_storage({2025: 150_000, 2030: 120_000}) \
            .with_min_charge(0.1) \
            .with_charge_technology("BATT_CHG", mode="MODE1") \
            .with_discharge_technology("BATT_DIS", mode="MODE1") \
            .with_residual_capacity({2025: 0.0, 2030: 0.0})

        assert "BATT" in stor.storages
        assert len(stor.technology_to_storage) == 1
        assert len(stor.technology_from_storage) == 1
        assert len(stor.capital_cost_storage) == 2
        assert len(stor.operational_life_storage) == 1
        assert len(stor.min_storage_charge) == 2  # one row per model year
        assert stor.energy_ratio.iloc[0]["VALUE"] == 4.0

    def test_multiple_storages(self, tmpdir, base_components):
        stor = StorageComponent(tmpdir)
        stor.add_storage("R1", "BATT").with_operational_life(20).with_energy_ratio(4.0)
        stor.add_storage("R1", "HYDRO").with_operational_life(50).with_energy_ratio(200.0)
        assert set(stor.storages) == {"BATT", "HYDRO"}

    def test_invalid_region_raises(self, tmpdir, base_components):
        stor = StorageComponent(tmpdir)
        with pytest.raises(ValueError, match="Region"):
            stor.add_storage("INVALID_REGION", "BATT")

    def test_negative_operational_life_raises(self, tmpdir, base_components):
        stor = StorageComponent(tmpdir)
        builder = stor.add_storage("R1", "BATT")
        with pytest.raises(ValueError, match="positive"):
            builder.with_operational_life(-1)

    def test_zero_energy_ratio_raises(self, tmpdir, base_components):
        stor = StorageComponent(tmpdir)
        builder = stor.add_storage("R1", "BATT")
        with pytest.raises(ValueError, match="positive"):
            builder.with_energy_ratio(0.0)

    def test_negative_capital_cost_raises(self, tmpdir, base_components):
        stor = StorageComponent(tmpdir)
        builder = stor.add_storage("R1", "BATT")
        with pytest.raises(ValueError, match="negative"):
            builder.with_capital_cost_storage({2025: -100})

    def test_min_charge_out_of_range_raises(self, tmpdir, base_components):
        stor = StorageComponent(tmpdir)
        builder = stor.add_storage("R1", "BATT")
        with pytest.raises(ValueError, match=r"\[0, 1\]"):
            builder.with_min_charge(1.5)

    def test_capital_cost_step_interpolation(self, tmpdir, base_components):
        stor = StorageComponent(tmpdir)
        stor.add_storage("R1", "BATT").with_capital_cost_storage({2025: 150_000}, interpolation="step")
        # Both years should get the 2025 value (step)
        vals = dict(zip(
            stor.capital_cost_storage["YEAR"].astype(int),
            stor.capital_cost_storage["VALUE"]
        ))
        assert vals[2025] == 150_000
        assert vals[2030] == 150_000

    def test_capital_cost_linear_interpolation(self, tmpdir, base_components):
        stor = StorageComponent(tmpdir)
        stor.add_storage("R1", "BATT").with_capital_cost_storage(
            {2025: 150_000, 2030: 100_000}, interpolation="linear"
        )
        vals = dict(zip(
            stor.capital_cost_storage["YEAR"].astype(int),
            stor.capital_cost_storage["VALUE"]
        ))
        assert vals[2025] == 150_000
        assert vals[2030] == 100_000


# ---------------------------------------------------------------------------
# StorageComponent.validate() tests
# ---------------------------------------------------------------------------

class TestStorageValidation:
    def test_valid_storage_passes(self, tmpdir, base_components):
        stor = StorageComponent(tmpdir)
        stor.add_storage("R1", "BATT") \
            .with_energy_ratio(4.0) \
            .with_min_charge(0.1)
        stor.validate()  # Should not raise

    def test_invalid_min_charge_fails(self, tmpdir, base_components):
        stor = StorageComponent(tmpdir)
        stor.add_storage("R1", "BATT")
        # Manually corrupt to bypass builder validation
        stor.min_storage_charge = pd.DataFrame([
            {"REGION": "R1", "STORAGE": "BATT", "YEAR": 2025, "VALUE": 2.0}
        ])
        with pytest.raises(ValueError, match="MinStorageCharge"):
            stor.validate()

    def test_invalid_energy_ratio_fails(self, tmpdir, base_components):
        stor = StorageComponent(tmpdir)
        stor.add_storage("R1", "BATT")
        stor.energy_ratio = pd.DataFrame([
            {"REGION": "R1", "STORAGE": "BATT", "VALUE": -1.0}
        ])
        with pytest.raises(ValueError, match="StorageEnergyRatio"):
            stor.validate()


# ---------------------------------------------------------------------------
# CSV round-trip tests
# ---------------------------------------------------------------------------

class TestStorageRoundTrip:
    def test_save_and_load(self, tmpdir, base_components):
        stor = StorageComponent(tmpdir)
        stor.add_storage("R1", "BATT") \
            .with_operational_life(20) \
            .with_energy_ratio(4.0) \
            .with_capital_cost_storage({2025: 150_000, 2030: 120_000}) \
            .with_min_charge(0.1) \
            .with_charge_technology("BATT_CHG") \
            .with_discharge_technology("BATT_DIS") \
            .with_residual_capacity({2025: 0.0})
        stor.save()

        # All expected files should exist
        for fname in [
            "STORAGE.csv", "TechnologyToStorage.csv", "TechnologyFromStorage.csv",
            "CapitalCostStorage.csv", "OperationalLifeStorage.csv",
            "ResidualStorageCapacity.csv", "MinStorageCharge.csv",
            "StorageEnergyRatio.csv",
        ]:
            assert os.path.exists(os.path.join(tmpdir, fname)), f"{fname} missing"

        # Load back and compare key values
        stor2 = StorageComponent(tmpdir)
        stor2.load()
        assert set(stor2.storage_df["VALUE"]) == {"BATT"}
        assert len(stor2.technology_to_storage) == 1
        assert len(stor2.technology_from_storage) == 1
        assert stor2.energy_ratio.iloc[0]["VALUE"] == pytest.approx(4.0)
        assert len(stor2.capital_cost_storage) == 2

    def test_empty_storage_produces_no_files(self, tmpdir, base_components):
        """A StorageComponent with no storages defined saves nothing."""
        stor = StorageComponent(tmpdir)
        stor.save()
        for fname in ["STORAGE.csv", "TechnologyToStorage.csv"]:
            assert not os.path.exists(os.path.join(tmpdir, fname))


# ---------------------------------------------------------------------------
# ScenarioData integration tests
# ---------------------------------------------------------------------------

class TestScenarioDataWithStorage:
    def test_from_components_with_storage(self, tmpdir, full_components):
        topo, time, demand, supply, perf, econ = full_components
        stor = StorageComponent(tmpdir)
        stor.add_storage("R1", "BATT") \
            .with_operational_life(20) \
            .with_energy_ratio(4.0) \
            .with_capital_cost_storage({2025: 150_000}) \
            .with_min_charge(0.0) \
            .with_charge_technology("BATT_CHG") \
            .with_discharge_technology("BATT_DIS") \
            .with_residual_capacity(0.0)
        stor.save()

        data = ScenarioData.from_components(
            topo, time, demand, supply, perf, econ,
            storage_component=stor
        )
        assert "BATT" in data.sets.storages
        assert not data.storage.technology_to_storage.empty
        assert not data.storage.technology_from_storage.empty
        assert not data.storage.energy_ratio.empty
        assert data.storage.energy_ratio.iloc[0]["VALUE"] == pytest.approx(4.0)

    def test_from_components_without_storage(self, tmpdir, full_components):
        """Storage is optional — from_components works with storage_component=None."""
        topo, time, demand, supply, perf, econ = full_components
        data = ScenarioData.from_components(topo, time, demand, supply, perf, econ)
        assert len(data.sets.storages) == 0
        assert data.storage.technology_to_storage.empty

    def test_from_directory_with_storage(self, tmpdir, full_components):
        topo, time, demand, supply, perf, econ = full_components
        stor = StorageComponent(tmpdir)
        stor.add_storage("R1", "BATT") \
            .with_operational_life(20) \
            .with_energy_ratio(4.0) \
            .with_capital_cost_storage({2025: 150_000}) \
            .with_min_charge(0.0) \
            .with_charge_technology("BATT_CHG") \
            .with_discharge_technology("BATT_DIS") \
            .with_residual_capacity(0.0)
        stor.save()

        data = ScenarioData.from_directory(tmpdir, validate=False)
        assert "BATT" in data.sets.storages
        assert not data.storage.energy_ratio.empty

    def test_to_dict_includes_storage(self, tmpdir, full_components):
        topo, time, demand, supply, perf, econ = full_components
        stor = StorageComponent(tmpdir)
        stor.add_storage("R1", "BATT").with_energy_ratio(4.0).with_charge_technology("BATT_CHG").with_discharge_technology("BATT_DIS")
        stor.save()

        data = ScenarioData.from_components(topo, time, demand, supply, perf, econ, storage_component=stor)
        d = data.to_dict()
        assert "TechnologyToStorage" in d
        assert "StorageEnergyRatio" in d
        assert not d["StorageEnergyRatio"].empty

    def test_get_parameter_storage(self, tmpdir, full_components):
        topo, time, demand, supply, perf, econ = full_components
        stor = StorageComponent(tmpdir)
        stor.add_storage("R1", "BATT").with_energy_ratio(4.0).with_charge_technology("BATT_CHG").with_discharge_technology("BATT_DIS")
        stor.save()

        data = ScenarioData.from_components(topo, time, demand, supply, perf, econ, storage_component=stor)
        assert data.get_parameter("StorageEnergyRatio") is not None
        assert data["TechnologyToStorage"] is not None


# ---------------------------------------------------------------------------
# StorageParameters.validate() unit tests
# ---------------------------------------------------------------------------

class TestStorageParametersValidate:
    @pytest.fixture
    def sets_with_storage(self):
        return OSeMOSYSSets(
            regions=frozenset(["R1"]),
            years=frozenset([2025]),
            technologies=frozenset(["BATT_CHG", "BATT_DIS"]),
            fuels=frozenset(["ELEC"]),
            emissions=frozenset(),
            modes=frozenset(["MODE1"]),
            timeslices=frozenset(["S1_D1_H1"]),
            seasons=frozenset(["S1"]),
            daytypes=frozenset(["D1"]),
            dailytimebrackets=frozenset(["H1"]),
            storages=frozenset(["BATT"]),
        )

    def test_valid_params_pass(self, sets_with_storage):
        params = StorageParameters(
            technology_to_storage=pd.DataFrame([{
                "REGION": "R1", "TECHNOLOGY": "BATT_CHG",
                "STORAGE": "BATT", "MODE_OF_OPERATION": "MODE1", "VALUE": 1
            }]),
            technology_from_storage=pd.DataFrame([{
                "REGION": "R1", "TECHNOLOGY": "BATT_DIS",
                "STORAGE": "BATT", "MODE_OF_OPERATION": "MODE1", "VALUE": 1
            }]),
            energy_ratio=pd.DataFrame([{"REGION": "R1", "STORAGE": "BATT", "VALUE": 4.0}]),
        )
        params.validate(sets_with_storage)  # Should not raise

    def test_unknown_storage_in_tech_to_storage_raises(self, sets_with_storage):
        params = StorageParameters(
            technology_to_storage=pd.DataFrame([{
                "REGION": "R1", "TECHNOLOGY": "BATT_CHG",
                "STORAGE": "UNKNOWN_STOR", "MODE_OF_OPERATION": "MODE1", "VALUE": 1
            }]),
        )
        with pytest.raises(ValueError):
            params.validate(sets_with_storage)

    def test_unknown_tech_in_tech_from_storage_raises(self, sets_with_storage):
        params = StorageParameters(
            technology_from_storage=pd.DataFrame([{
                "REGION": "R1", "TECHNOLOGY": "UNKNOWN_TECH",
                "STORAGE": "BATT", "MODE_OF_OPERATION": "MODE1", "VALUE": 1
            }]),
        )
        with pytest.raises(ValueError):
            params.validate(sets_with_storage)

    def test_negative_capital_cost_raises(self, sets_with_storage):
        params = StorageParameters(
            capital_cost_storage=pd.DataFrame([{
                "REGION": "R1", "STORAGE": "BATT", "YEAR": 2025, "VALUE": -100
            }]),
        )
        with pytest.raises(ValueError, match="negative"):
            params.validate(sets_with_storage)

    def test_invalid_energy_ratio_raises(self, sets_with_storage):
        params = StorageParameters(
            energy_ratio=pd.DataFrame([{"REGION": "R1", "STORAGE": "BATT", "VALUE": 0.0}]),
        )
        with pytest.raises(ValueError, match="positive"):
            params.validate(sets_with_storage)

    def test_min_charge_out_of_range_raises(self, sets_with_storage):
        params = StorageParameters(
            min_storage_charge=pd.DataFrame([{
                "REGION": "R1", "STORAGE": "BATT", "YEAR": 2025, "VALUE": 1.5
            }]),
        )
        with pytest.raises(ValueError, match=r"\[0, 1\]"):
            params.validate(sets_with_storage)
