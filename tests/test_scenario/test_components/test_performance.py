# tests/test_scenario/test_components/test_performance.py

"""
Tests for PerformanceComponent (refactored).

Tests cover:
- Initialization (reads supply registry from disk)
- owned_files class attribute
- Properties (technologies, defined_fuels, modes)
- set_efficiency (conversion technologies)
- set_resource_output (renewables)
- set_capacity_factor (uniform, hierarchical weights)
- set_availability_factor (scalar, dict)
- set_capacity_to_activity_unit
- set_capacity_limits
- process (default fill for CF, AF, CAU)
- Validation (activity ratios, factor bounds)
- Load / save round-trip
- Edge cases (empty DataFrames, multiple technologies)
- Representation (__repr__)
"""

import math
import os
import pytest
import pandas as pd

from pyoscomp.scenario.components.performance import PerformanceComponent
from pyoscomp.scenario.components.supply import SupplyComponent


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def perf(supply_scenario_dir):
    """PerformanceComponent with supply prerequisites on disk."""
    return PerformanceComponent(supply_scenario_dir)


@pytest.fixture
def perf_with_efficiency(perf):
    """PerformanceComponent with GAS_CCGT efficiency set."""
    perf.set_efficiency('REGION1', 'GAS_CCGT', 0.55)
    return perf


@pytest.fixture
def perf_full(perf):
    """PerformanceComponent with efficiency, CF, AF, CAU for GAS_CCGT."""
    perf.set_efficiency('REGION1', 'GAS_CCGT', 0.55)
    perf.set_resource_output('REGION1', 'SOLAR_PV')
    perf.set_capacity_factor('REGION1', 'GAS_CCGT', 0.9)
    perf.set_capacity_factor('REGION1', 'SOLAR_PV', 0.25)
    perf.set_availability_factor('REGION1', 'GAS_CCGT', 0.95)
    perf.set_availability_factor('REGION1', 'SOLAR_PV', 1.0)
    perf.set_capacity_to_activity_unit('REGION1', 'GAS_CCGT', 8760)
    perf.set_capacity_to_activity_unit('REGION1', 'SOLAR_PV', 8760)
    perf.process()
    return perf


# =============================================================================
# Initialization Tests
# =============================================================================

class TestPerformanceInit:
    """Test PerformanceComponent initialization."""

    def test_init_loads_prerequisites(self, perf):
        """Initialization loads years, regions, timeslices."""
        assert perf.years is not None
        assert len(perf.years) == 6
        assert 'REGION1' in perf.regions
        assert len(perf.timeslices) > 0

    def test_init_missing_time_raises(self, topology_scenario_dir):
        """Missing time component raises AttributeError."""
        with pytest.raises(AttributeError):
            PerformanceComponent(topology_scenario_dir)

    def test_init_loads_supply_registry(self, perf):
        """Init loads TECHNOLOGY.csv from supply."""
        assert 'GAS_CCGT' in perf.technologies
        assert 'SOLAR_PV' in perf.technologies

    def test_init_loads_fuel_map(self, perf):
        """Init loads fuel assignments from supply metadata."""
        assert perf._fuel_map is not None
        key = ('REGION1', 'GAS_CCGT', 'MODE1')
        assert key in perf._fuel_map
        assert perf._fuel_map[key]['input'] == 'GAS'
        assert perf._fuel_map[key]['output'] == 'ELEC'

    def test_init_dataframes_empty(self, perf):
        """All DataFrames empty after init."""
        assert perf.capacity_to_activity_unit.empty
        assert perf.input_activity_ratio.empty
        assert perf.output_activity_ratio.empty
        assert perf.capacity_factor.empty
        assert perf.availability_factor.empty
        assert perf.total_annual_max_capacity.empty
        assert perf.total_annual_min_capacity.empty


# =============================================================================
# owned_files Tests
# =============================================================================

class TestOwnedFiles:
    """Test owned_files class attribute."""

    def test_owned_files_contents(self):
        """owned_files contains all seven performance CSV files."""
        expected = {
            'CapacityToActivityUnit.csv',
            'InputActivityRatio.csv',
            'OutputActivityRatio.csv',
            'CapacityFactor.csv',
            'AvailabilityFactor.csv',
            'TotalAnnualMaxCapacity.csv',
            'TotalAnnualMinCapacity.csv',
        }
        assert set(PerformanceComponent.owned_files) == expected

    def test_owned_files_count(self):
        """owned_files has exactly 7 entries."""
        assert len(PerformanceComponent.owned_files) == 7


# =============================================================================
# Properties Tests
# =============================================================================

class TestPerformanceProperties:
    """Test PerformanceComponent properties."""

    def test_technologies_from_supply(self, perf):
        """technologies matches supply registry."""
        assert set(perf.technologies) == {'GAS_CCGT', 'SOLAR_PV'}

    def test_defined_fuels_from_supply(self, perf):
        """defined_fuels loaded from supply's FUEL.csv."""
        assert 'GAS' in perf.defined_fuels
        assert 'ELEC' in perf.defined_fuels

    def test_modes_from_supply(self, perf):
        """modes loaded from supply's MODE_OF_OPERATION.csv."""
        assert 'MODE1' in perf.modes


# =============================================================================
# set_efficiency Tests
# =============================================================================

class TestSetEfficiency:
    """Test set_efficiency method."""

    def test_basic_efficiency(self, perf):
        """Set basic conversion efficiency."""
        perf.set_efficiency('REGION1', 'GAS_CCGT', 0.5)

        # Input ratio = 1/efficiency = 2.0
        inp = perf.input_activity_ratio
        assert len(inp) > 0
        row = inp[inp['TECHNOLOGY'] == 'GAS_CCGT'].iloc[0]
        assert math.isclose(row['VALUE'], 2.0, rel_tol=0.01)

        # Output ratio = 1.0
        out = perf.output_activity_ratio
        row = out[out['TECHNOLOGY'] == 'GAS_CCGT'].iloc[0]
        assert row['VALUE'] == 1.0

    def test_efficiency_populates_all_years(self, perf):
        """Efficiency generates rows for all model years."""
        perf.set_efficiency('REGION1', 'GAS_CCGT', 0.55)

        inp = perf.input_activity_ratio
        years_in_df = inp[inp['TECHNOLOGY'] == 'GAS_CCGT']['YEAR'].unique()
        assert set(years_in_df) == set(perf.years)

    def test_efficiency_trajectory(self, perf):
        """Set efficiency as year dict."""
        perf.set_efficiency(
            'REGION1', 'GAS_CCGT',
            efficiency={2025: 0.50, 2030: 0.55}
        )

        inp = perf.input_activity_ratio
        val_2025 = inp[
            (inp['TECHNOLOGY'] == 'GAS_CCGT') &
            (inp['YEAR'] == 2025)
        ]['VALUE'].iloc[0]
        val_2030 = inp[
            (inp['TECHNOLOGY'] == 'GAS_CCGT') &
            (inp['YEAR'] == 2030)
        ]['VALUE'].iloc[0]

        assert math.isclose(val_2025, 1.0 / 0.50, rel_tol=0.01)
        assert math.isclose(val_2030, 1.0 / 0.55, rel_tol=0.01)

    def test_resource_technology_raises(self, perf):
        """set_efficiency on resource (no input fuel) raises."""
        with pytest.raises(ValueError, match="resource"):
            perf.set_efficiency('REGION1', 'SOLAR_PV', 0.5)


# =============================================================================
# set_resource_output Tests
# =============================================================================

class TestSetResourceOutput:
    """Test set_resource_output method."""

    def test_resource_output(self, perf):
        """Set output for resource technology."""
        perf.set_resource_output('REGION1', 'SOLAR_PV')

        out = perf.output_activity_ratio
        row = out[out['TECHNOLOGY'] == 'SOLAR_PV'].iloc[0]
        assert row['VALUE'] == 1.0
        assert row['FUEL'] == 'ELEC'

    def test_resource_no_input(self, perf):
        """Resource technology has no input activity ratio."""
        perf.set_resource_output('REGION1', 'SOLAR_PV')
        inp = perf.input_activity_ratio
        assert inp.empty or \
            'SOLAR_PV' not in inp['TECHNOLOGY'].values


# =============================================================================
# set_capacity_factor Tests
# =============================================================================

class TestSetCapacityFactor:
    """Test set_capacity_factor method."""

    def test_uniform_capacity_factor(self, perf):
        """Uniform capacity factor stored for all years."""
        perf.set_efficiency('REGION1', 'GAS_CCGT', 0.5)
        perf.set_capacity_factor('REGION1', 'GAS_CCGT', 0.9)
        perf.process()

        cf = perf.capacity_factor
        ccgt_cf = cf[cf['TECHNOLOGY'] == 'GAS_CCGT']
        assert len(ccgt_cf) > 0
        assert (ccgt_cf['VALUE'] == 0.9).all()

    def test_capacity_factor_out_of_range_raises(self, perf):
        """Capacity factor > 1 raises ValueError."""
        perf.set_efficiency('REGION1', 'GAS_CCGT', 0.5)
        with pytest.raises(ValueError, match="\\[0, 1\\]"):
            perf.set_capacity_factor('REGION1', 'GAS_CCGT', 1.5)

    def test_capacity_factor_hierarchical_weights(self, perf):
        """Capacity factor with bracket weights."""
        perf.set_efficiency('REGION1', 'GAS_CCGT', 0.5)
        perf.set_capacity_factor(
            'REGION1', 'GAS_CCGT', 1.0,
            bracket_weights={'Day': 0.8, 'Night': 0.4}
        )
        perf.process()

        cf = perf.capacity_factor
        ccgt_cf = cf[cf['TECHNOLOGY'] == 'GAS_CCGT']
        assert not ccgt_cf.empty
        # Should have different values for Day vs Night timeslices


# =============================================================================
# set_availability_factor Tests
# =============================================================================

class TestSetAvailabilityFactor:
    """Test set_availability_factor method."""

    def test_scalar_availability(self, perf):
        """Set availability factor as scalar."""
        perf.set_efficiency('REGION1', 'GAS_CCGT', 0.5)
        perf.set_availability_factor('REGION1', 'GAS_CCGT', 0.95)

        af = perf.availability_factor
        ccgt_af = af[af['TECHNOLOGY'] == 'GAS_CCGT']
        assert (ccgt_af['VALUE'] == 0.95).all()

    def test_dict_availability(self, perf):
        """Set availability factor as year dict."""
        perf.set_efficiency('REGION1', 'GAS_CCGT', 0.5)
        perf.set_availability_factor(
            'REGION1', 'GAS_CCGT',
            availability={2025: 0.95, 2030: 0.90}
        )

        af = perf.availability_factor
        val_2025 = af[
            (af['TECHNOLOGY'] == 'GAS_CCGT') &
            (af['YEAR'] == 2025)
        ]['VALUE'].iloc[0]
        val_2030 = af[
            (af['TECHNOLOGY'] == 'GAS_CCGT') &
            (af['YEAR'] == 2030)
        ]['VALUE'].iloc[0]

        assert val_2025 == 0.95
        assert val_2030 == 0.90

    def test_availability_out_of_range_raises(self, perf):
        """Availability > 1 raises ValueError."""
        perf.set_efficiency('REGION1', 'GAS_CCGT', 0.5)
        with pytest.raises(ValueError, match="\\[0, 1\\]"):
            perf.set_availability_factor(
                'REGION1', 'GAS_CCGT', 1.5
            )


# =============================================================================
# set_capacity_to_activity_unit Tests
# =============================================================================

class TestSetCapacityToActivityUnit:
    """Test set_capacity_to_activity_unit method."""

    def test_default_cau(self, perf):
        """Default CAU value is 8760."""
        perf.set_efficiency('REGION1', 'GAS_CCGT', 0.5)
        perf.set_capacity_to_activity_unit('REGION1', 'GAS_CCGT')

        cau = perf.capacity_to_activity_unit
        row = cau[cau['TECHNOLOGY'] == 'GAS_CCGT']
        assert row['VALUE'].iloc[0] == 8760

    def test_custom_cau(self, perf):
        """Custom CAU stored correctly."""
        perf.set_efficiency('REGION1', 'GAS_CCGT', 0.5)
        perf.set_capacity_to_activity_unit(
            'REGION1', 'GAS_CCGT', 31.536
        )

        cau = perf.capacity_to_activity_unit
        row = cau[cau['TECHNOLOGY'] == 'GAS_CCGT']
        assert math.isclose(row['VALUE'].iloc[0], 31.536)

    def test_zero_cau_raises(self, perf):
        """Zero CAU raises ValueError."""
        perf.set_efficiency('REGION1', 'GAS_CCGT', 0.5)
        with pytest.raises(ValueError, match="positive"):
            perf.set_capacity_to_activity_unit(
                'REGION1', 'GAS_CCGT', 0
            )


# =============================================================================
# set_capacity_limits Tests
# =============================================================================

class TestSetCapacityLimits:
    """Test set_capacity_limits method."""

    def test_max_capacity_scalar(self, perf):
        """Set max capacity as scalar."""
        perf.set_efficiency('REGION1', 'GAS_CCGT', 0.5)
        perf.set_capacity_limits(
            'REGION1', 'GAS_CCGT',
            max_capacity=100
        )

        df = perf.total_annual_max_capacity
        assert len(df) > 0
        assert (df['VALUE'] == 100).all()

    def test_min_capacity_scalar(self, perf):
        """Set min capacity as scalar."""
        perf.set_efficiency('REGION1', 'GAS_CCGT', 0.5)
        perf.set_capacity_limits(
            'REGION1', 'GAS_CCGT',
            min_capacity=10
        )

        df = perf.total_annual_min_capacity
        assert len(df) > 0
        assert (df['VALUE'] == 10).all()

    def test_capacity_limit_trajectory(self, perf):
        """Set capacity limits as trajectory dict."""
        perf.set_efficiency('REGION1', 'GAS_CCGT', 0.5)
        perf.set_capacity_limits(
            'REGION1', 'GAS_CCGT',
            max_capacity={2025: 50, 2030: 100}
        )

        df = perf.total_annual_max_capacity
        assert len(df) == len(perf.years)


# =============================================================================
# process Tests
# =============================================================================

class TestProcess:
    """Test process method."""

    def test_process_generates_capacity_factors(self, perf):
        """process generates CF DataFrame."""
        perf.set_efficiency('REGION1', 'GAS_CCGT', 0.5)
        perf.process()

        assert not perf.capacity_factor.empty

    def test_process_default_capacity_factor(self, perf):
        """Default capacity factor is 1.0."""
        perf.set_resource_output('REGION1', 'SOLAR_PV')
        perf.process()

        cf = perf.capacity_factor
        solar_cf = cf[cf['TECHNOLOGY'] == 'SOLAR_PV']
        assert (solar_cf['VALUE'] == 1.0).all()

    def test_process_default_availability_factor(self, perf):
        """Default availability factor is 1.0."""
        perf.set_resource_output('REGION1', 'SOLAR_PV')
        perf.process()

        af = perf.availability_factor
        solar_af = af[af['TECHNOLOGY'] == 'SOLAR_PV']
        assert (solar_af['VALUE'] == 1.0).all()

    def test_process_default_cau(self, perf):
        """Default CAU is 8760."""
        perf.set_efficiency('REGION1', 'GAS_CCGT', 0.5)
        perf.process()

        cau = perf.capacity_to_activity_unit
        row = cau[cau['TECHNOLOGY'] == 'GAS_CCGT']
        assert row['VALUE'].iloc[0] == 8760


# =============================================================================
# Validation Tests
# =============================================================================

class TestValidation:
    """Test validate method."""

    def test_validate_empty_passes(self, perf):
        """Empty component passes validation."""
        perf.validate()

    def test_validate_with_data_passes(self, perf_full):
        """Fully populated component passes validation."""
        perf_full.validate()

    def test_non_positive_input_ratio_raises(self, perf_with_efficiency):
        """Non-positive input ratio fails."""
        perf_with_efficiency.input_activity_ratio.loc[0, 'VALUE'] = 0.0
        with pytest.raises(ValueError, match="Non-positive"):
            perf_with_efficiency.validate()

    def test_negative_output_ratio_raises(self, perf_with_efficiency):
        """Negative output ratio fails."""
        perf_with_efficiency.output_activity_ratio.loc[0, 'VALUE'] = -1.0
        with pytest.raises(ValueError, match="Non-positive"):
            perf_with_efficiency.validate()

    def test_capacity_factor_above_one_raises(self, perf_full):
        """CF > 1 fails validation."""
        perf_full.capacity_factor.loc[0, 'VALUE'] = 1.5
        with pytest.raises(ValueError, match="CapacityFactor"):
            perf_full.validate()

    def test_capacity_factor_below_zero_raises(self, perf_full):
        """CF < 0 fails validation."""
        perf_full.capacity_factor.loc[0, 'VALUE'] = -0.1
        with pytest.raises(ValueError, match="CapacityFactor"):
            perf_full.validate()

    def test_availability_factor_above_one_raises(self, perf_full):
        """AF > 1 fails validation."""
        perf_full.availability_factor.loc[0, 'VALUE'] = 1.01
        with pytest.raises(ValueError, match="AvailabilityFactor"):
            perf_full.validate()

    def test_availability_factor_below_zero_raises(self, perf_full):
        """AF < 0 fails validation."""
        perf_full.availability_factor.loc[0, 'VALUE'] = -0.01
        with pytest.raises(ValueError, match="AvailabilityFactor"):
            perf_full.validate()


# =============================================================================
# Load / Save Tests
# =============================================================================

class TestPerformanceSaveLoad:
    """Test save and load operations."""

    def test_save_creates_files(self, perf_full):
        """save creates all owned CSV files."""
        perf_full.save()

        for filename in PerformanceComponent.owned_files:
            path = os.path.join(perf_full.scenario_dir, filename)
            assert os.path.exists(path), f"Missing: {filename}"

    def test_save_empty_creates_files(self, perf):
        """save with empty DataFrames still creates files."""
        perf.save()

        for filename in PerformanceComponent.owned_files:
            path = os.path.join(perf.scenario_dir, filename)
            assert os.path.exists(path), f"Missing: {filename}"

    def test_round_trip(self, perf_full):
        """Save then load preserves key values."""
        perf_full.save()

        loaded = PerformanceComponent(perf_full.scenario_dir)
        loaded.load()

        # Check InputActivityRatio value
        iar = loaded.input_activity_ratio
        iar_row = iar[
            (iar['TECHNOLOGY'] == 'GAS_CCGT') &
            (iar['YEAR'] == 2025)
        ]
        assert math.isclose(
            iar_row['VALUE'].iloc[0], 1.0 / 0.55, rel_tol=1e-6
        )

        # Check CapacityFactor
        cf = loaded.capacity_factor
        ccgt_cf = cf[
            (cf['TECHNOLOGY'] == 'GAS_CCGT') &
            (cf['YEAR'] == 2025)
        ]
        assert (ccgt_cf['VALUE'] == 0.9).all()

        # Check AvailabilityFactor
        af = loaded.availability_factor
        ccgt_af = af[
            (af['TECHNOLOGY'] == 'GAS_CCGT') &
            (af['YEAR'] == 2025)
        ]
        assert ccgt_af['VALUE'].iloc[0] == 0.95

    def test_round_trip_validates(self, perf_full):
        """Loaded data passes validation."""
        perf_full.save()
        loaded = PerformanceComponent(perf_full.scenario_dir)
        loaded.load()
        loaded.validate()


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_validate_called_twice(self, perf_full):
        """Calling validate twice is idempotent."""
        perf_full.validate()
        perf_full.validate()

    def test_save_load_empty(self, perf):
        """Round-trip with empty DataFrames works."""
        perf.save()
        loaded = PerformanceComponent(perf.scenario_dir)
        loaded.load()


# =============================================================================
# Representation Tests
# =============================================================================

class TestPerformanceRepr:
    """Test __repr__ output."""

    def test_repr_has_classname(self, perf):
        """repr includes class name."""
        repr_str = repr(perf)
        assert "PerformanceComponent" in repr_str

    def test_repr_includes_dir(self, perf):
        """repr includes scenario_dir."""
        repr_str = repr(perf)
        assert "scenario_dir=" in repr_str


# =============================================================================
# Supply-Performance Integration
# =============================================================================

class TestSupplyPerformanceIntegration:
    """Test the supply → performance workflow."""

    def test_full_workflow(self, complete_scenario_dir):
        """Full workflow: supply save, performance config, save."""
        # Build supply
        supply = SupplyComponent(complete_scenario_dir)
        supply.add_technology('REGION1', 'GAS_CCGT') \
            .with_operational_life(30) \
            .as_conversion(input_fuel='GAS', output_fuel='ELEC')
        supply.add_technology('REGION1', 'SOLAR_PV') \
            .with_operational_life(25) \
            .as_resource(output_fuel='ELEC')
        supply.save()

        # Build performance
        perf = PerformanceComponent(complete_scenario_dir)
        perf.set_efficiency('REGION1', 'GAS_CCGT', 0.55)
        perf.set_resource_output('REGION1', 'SOLAR_PV')
        perf.set_capacity_factor('REGION1', 'SOLAR_PV', 0.25)
        perf.set_availability_factor('REGION1', 'GAS_CCGT', 0.95)
        perf.set_capacity_to_activity_unit('REGION1', 'GAS_CCGT', 8760)
        perf.process()
        perf.validate()
        perf.save()

        # Verify files exist
        for fname in PerformanceComponent.owned_files:
            assert os.path.exists(
                os.path.join(complete_scenario_dir, fname)
            )

        # Verify key values
        iar = pd.read_csv(
            os.path.join(
                complete_scenario_dir, 'InputActivityRatio.csv'
            )
        )
        ccgt_iar = iar[iar['TECHNOLOGY'] == 'GAS_CCGT']
        assert math.isclose(
            ccgt_iar['VALUE'].iloc[0], 1.0 / 0.55, rel_tol=0.01
        )
