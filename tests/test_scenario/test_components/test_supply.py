# tests/test_scenario/test_components/test_supply.py

"""
Tests for SupplyComponent.

Tests cover:
- Initialization and prerequisites
- Properties (technologies, fuels, modes)
- add_technology method
- set_conversion_technology (efficiency modeling)
- set_resource_technology (renewables)
- set_multimode_technology (CHP, storage)
- set_residual_capacity with interpolation
- set_capacity_factor (timeslice/hierarchical weights)
- set_availability_factor
- process method
- Activity ratio validation
- load / save operations
"""

import math
import os
import pytest
import pandas as pd
import numpy as np

from pyoscomp.scenario.components.topology import TopologyComponent
from pyoscomp.scenario.components.time import TimeComponent
from pyoscomp.scenario.components.supply import SupplyComponent


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def supply_component(complete_scenario_dir):
    """Create SupplyComponent with all prerequisites."""
    return SupplyComponent(complete_scenario_dir)


@pytest.fixture
def supply_with_tech(complete_scenario_dir):
    """Supply component with a registered technology."""
    supply = SupplyComponent(complete_scenario_dir)
    supply.add_technology('REGION1', 'GAS_CCGT', operational_life=30)
    return supply


# =============================================================================
# Initialization Tests
# =============================================================================

class TestSupplyInit:
    """Test SupplyComponent initialization."""

    def test_init_loads_prerequisites(self, supply_component):
        """Initialization loads years, regions, timeslices."""
        assert supply_component.years is not None
        assert supply_component.regions is not None
        assert supply_component.timeslices is not None

    def test_init_missing_time_raises(self, topology_scenario_dir):
        """Missing time component raises AttributeError."""
        with pytest.raises(AttributeError):
            SupplyComponent(topology_scenario_dir)

    def test_owned_files(self):
        """owned_files contains supply-related files."""
        expected = [
            'TECHNOLOGY.csv', 'FUEL.csv', 'MODE_OF_OPERATION.csv',
            'CapacityToActivityUnit.csv', 'OperationalLife.csv',
            'InputActivityRatio.csv', 'OutputActivityRatio.csv',
            'CapacityFactor.csv', 'AvailabilityFactor.csv', 'ResidualCapacity.csv'
        ]
        assert set(SupplyComponent.owned_files) == set(expected)


# =============================================================================
# Properties Tests
# =============================================================================

class TestSupplyProperties:
    """Test supply properties."""

    def test_technologies_empty(self, supply_component):
        """technologies empty initially."""
        assert supply_component.technologies == []

    def test_technologies_after_add(self, supply_with_tech):
        """technologies populated after add_technology."""
        assert 'GAS_CCGT' in supply_with_tech.technologies

    def test_fuels_empty(self, supply_component):
        """fuels empty initially."""
        assert supply_component.fuels == []

    def test_fuels_after_conversion(self, supply_with_tech):
        """fuels populated after set_conversion_technology."""
        supply_with_tech.set_conversion_technology(
            'REGION1', 'GAS_CCGT',
            input_fuel='GAS', output_fuel='ELEC',
            efficiency=0.5
        )
        assert 'GAS' in supply_with_tech.fuels
        assert 'ELEC' in supply_with_tech.fuels

    def test_modes_default(self, supply_with_tech):
        """modes returns default MODE1 initially."""
        assert supply_with_tech.modes == {'MODE1'}


# =============================================================================
# add_technology Tests
# =============================================================================

class TestAddTechnology:
    """Test add_technology method."""

    def test_add_technology_basic(self, supply_component):
        """Add technology with basic parameters."""
        supply_component.add_technology(
            'REGION1', 'SOLAR_PV',
            operational_life=25
        )

        assert ('REGION1', 'SOLAR_PV') in supply_component.defined_tech
        assert 'SOLAR_PV' in supply_component.technologies

    def test_add_technology_custom_cau(self, supply_component):
        """Add technology with custom capacity_to_activity_unit."""
        supply_component.add_technology(
            'REGION1', 'WIND',
            operational_life=25,
            capacity_to_activity_unit=8760
        )

        df = supply_component.capacity_to_activity_unit
        row = df[(df['TECHNOLOGY'] == 'WIND')]
        assert row['VALUE'].iloc[0] == 8760

    def test_add_technology_invalid_region_raises(self, supply_component):
        """Invalid region raises ValueError."""
        with pytest.raises(ValueError, match="not defined"):
            supply_component.add_technology(
                'INVALID', 'TECH1', operational_life=20
            )

    def test_add_technology_zero_life_raises(self, supply_component):
        """Zero operational life raises ValueError."""
        with pytest.raises(ValueError, match="positive"):
            supply_component.add_technology(
                'REGION1', 'TECH1', operational_life=0
            )

    def test_add_technology_negative_life_raises(self, supply_component):
        """Negative operational life raises ValueError."""
        with pytest.raises(ValueError, match="positive"):
            supply_component.add_technology(
                'REGION1', 'TECH1', operational_life=-5
            )

    def test_operational_life_stored(self, supply_with_tech):
        """OperationalLife stored correctly."""
        df = supply_with_tech.operational_life
        row = df[df['TECHNOLOGY'] == 'GAS_CCGT']
        assert row['VALUE'].iloc[0] == 30


# =============================================================================
# set_conversion_technology Tests
# =============================================================================

class TestSetConversionTechnology:
    """Test set_conversion_technology method."""

    def test_basic_conversion(self, supply_with_tech):
        """Set basic conversion technology."""
        supply_with_tech.set_conversion_technology(
            'REGION1', 'GAS_CCGT',
            input_fuel='NATURAL_GAS',
            output_fuel='ELECTRICITY',
            efficiency=0.55
        )

        # Check input activity ratio
        inp = supply_with_tech.input_activity_ratio
        assert len(inp) > 0
        row = inp[inp['TECHNOLOGY'] == 'GAS_CCGT'].iloc[0]
        # Input ratio = 1/efficiency = 1/0.55 ≈ 1.818
        assert math.isclose(row['VALUE'], 1.0 / 0.55, rel_tol=0.01)

        # Check output activity ratio
        out = supply_with_tech.output_activity_ratio
        row = out[out['TECHNOLOGY'] == 'GAS_CCGT'].iloc[0]
        assert row['VALUE'] == 1.0

    def test_efficiency_trajectory(self, supply_with_tech):
        """Set efficiency trajectory over years."""
        supply_with_tech.set_conversion_technology(
            'REGION1', 'GAS_CCGT',
            input_fuel='GAS', output_fuel='ELEC',
            efficiency={2025: 0.50, 2030: 0.55}
        )

        inp = supply_with_tech.input_activity_ratio
        # Check both values present
        val_2025 = inp[(inp['TECHNOLOGY'] == 'GAS_CCGT') &
                       (inp['YEAR'] == 2025)]['VALUE'].iloc[0]
        val_2030 = inp[(inp['TECHNOLOGY'] == 'GAS_CCGT') &
                       (inp['YEAR'] == 2030)]['VALUE'].iloc[0]

        assert math.isclose(val_2025, 1.0 / 0.50, rel_tol=0.01)
        assert math.isclose(val_2030, 1.0 / 0.55, rel_tol=0.01)

    def test_efficiency_zero_raises(self, supply_with_tech):
        """Zero efficiency raises ValueError."""
        with pytest.raises(ValueError, match="Efficiency"):
            supply_with_tech.set_conversion_technology(
                'REGION1', 'GAS_CCGT',
                input_fuel='GAS', output_fuel='ELEC',
                efficiency=0.0
            )

    def test_efficiency_over_one_raises(self, supply_with_tech):
        """Efficiency > 1 raises ValueError."""
        with pytest.raises(ValueError, match="Efficiency"):
            supply_with_tech.set_conversion_technology(
                'REGION1', 'GAS_CCGT',
                input_fuel='GAS', output_fuel='ELEC',
                efficiency=1.1
            )

    def test_same_input_output_raises(self, supply_with_tech):
        """Same input and output fuel raises ValueError."""
        with pytest.raises(ValueError, match="different"):
            supply_with_tech.set_conversion_technology(
                'REGION1', 'GAS_CCGT',
                input_fuel='ELEC', output_fuel='ELEC',
                efficiency=0.9
            )

    def test_unregistered_tech_raises(self, supply_component):
        """Setting conversion on unregistered tech raises ValueError."""
        with pytest.raises(ValueError, match="not registered"):
            supply_component.set_conversion_technology(
                'REGION1', 'UNKNOWN_TECH',
                input_fuel='GAS', output_fuel='ELEC',
                efficiency=0.5
            )


# =============================================================================
# set_resource_technology Tests
# =============================================================================

class TestSetResourceTechnology:
    """Test set_resource_technology method."""

    def test_resource_technology(self, supply_component):
        """Set resource/extraction technology."""
        supply_component.add_technology('REGION1', 'SOLAR_PV', operational_life=25)
        supply_component.set_resource_technology(
            'REGION1', 'SOLAR_PV', output_fuel='ELECTRICITY'
        )

        # Should have output only (no input)
        assert supply_component.input_activity_ratio.empty or \
               'SOLAR_PV' not in supply_component.input_activity_ratio['TECHNOLOGY'].values

        out = supply_component.output_activity_ratio
        row = out[out['TECHNOLOGY'] == 'SOLAR_PV'].iloc[0]
        assert row['VALUE'] == 1.0
        assert row['FUEL'] == 'ELECTRICITY'

    def test_resource_fuels_tracked(self, supply_component):
        """Resource technology fuel is tracked."""
        supply_component.add_technology('REGION1', 'WIND', operational_life=25)
        supply_component.set_resource_technology('REGION1', 'WIND', 'ELEC')

        assert 'ELEC' in supply_component.fuels


# =============================================================================
# set_multimode_technology Tests
# =============================================================================

class TestSetMultimodeTechnology:
    """Test set_multimode_technology method."""

    def test_multimode_basic(self, supply_component):
        """Set multimode technology (CHP example)."""
        supply_component.add_technology('REGION1', 'CHP', operational_life=30)
        supply_component.set_multimode_technology('REGION1', 'CHP', {
            'ELEC_ONLY': {
                'inputs': {'GAS': 1.8},
                'outputs': {'ELEC': 1.0}
            },
            'CHP_MODE': {
                'inputs': {'GAS': 1.5},
                'outputs': {'ELEC': 0.6, 'HEAT': 0.3}
            }
        })

        # Check modes registered
        assert 'ELEC_ONLY' in supply_component.modes
        assert 'CHP_MODE' in supply_component.modes

        # Check all fuels tracked
        assert {'GAS', 'ELEC', 'HEAT'}.issubset(set(supply_component.fuels))

    def test_multimode_missing_output_raises(self, supply_component):
        """Mode without outputs raises ValueError."""
        supply_component.add_technology('REGION1', 'CHP', operational_life=30)

        with pytest.raises(ValueError, match="at least one output"):
            supply_component.set_multimode_technology('REGION1', 'CHP', {
                'BAD_MODE': {'inputs': {'GAS': 1.0}}  # No outputs
            })

    def test_multimode_zero_ratio_raises(self, supply_component):
        """Zero ratio in mode config raises ValueError."""
        supply_component.add_technology('REGION1', 'CHP', operational_life=30)

        with pytest.raises(ValueError, match="positive"):
            supply_component.set_multimode_technology('REGION1', 'CHP', {
                'BAD_MODE': {'outputs': {'ELEC': 0}}  # Zero ratio
            })


# =============================================================================
# set_residual_capacity Tests
# =============================================================================

class TestSetResidualCapacity:
    """Test set_residual_capacity method."""

    def test_residual_capacity_step(self, supply_with_tech):
        """Set residual capacity with step interpolation."""
        supply_with_tech.set_residual_capacity(
            'REGION1', 'GAS_CCGT',
            trajectory={2025: 10, 2030: 5},
            interpolation='step'
        )

        df = supply_with_tech.residual_capacity
        # 2025-2029 should be 10, 2030 should be 5
        val_2027 = df[df['YEAR'] == 2027]['VALUE'].iloc[0]
        val_2030 = df[df['YEAR'] == 2030]['VALUE'].iloc[0]

        assert val_2027 == 10
        assert val_2030 == 5

    def test_residual_capacity_linear(self, supply_with_tech):
        """Set residual capacity with linear interpolation."""
        supply_with_tech.set_residual_capacity(
            'REGION1', 'GAS_CCGT',
            trajectory={2025: 10, 2030: 0},
            interpolation='linear'
        )

        df = supply_with_tech.residual_capacity
        # Linear: 10, 8, 6, 4, 2, 0
        val_2027 = df[df['YEAR'] == 2027]['VALUE'].iloc[0]
        assert math.isclose(val_2027, 6, abs_tol=0.5)

    def test_residual_capacity_empty_raises(self, supply_with_tech):
        """Empty trajectory raises ValueError."""
        with pytest.raises(ValueError, match="Empty"):
            supply_with_tech.set_residual_capacity(
                'REGION1', 'GAS_CCGT', trajectory={}
            )

    def test_residual_capacity_negative_raises(self, supply_with_tech):
        """Negative capacity raises ValueError."""
        with pytest.raises(ValueError, match="Negative"):
            supply_with_tech.set_residual_capacity(
                'REGION1', 'GAS_CCGT',
                trajectory={2025: -10}
            )


# =============================================================================
# set_capacity_factor Tests
# =============================================================================

class TestSetCapacityFactor:
    """Test set_capacity_factor method."""

    def test_capacity_factor_timeslice_weights(self, supply_with_tech):
        """Set capacity factor with timeslice weights."""
        ts = supply_with_tech.timeslices
        weights = {ts[0]: 0.8, ts[1]: 0.5}

        supply_with_tech.set_capacity_factor(
            'REGION1', 'GAS_CCGT',
            timeslice_weights=weights
        )

        # Check assignment stored
        assert len(supply_with_tech._capacity_factor_assignments) > 0

    def test_capacity_factor_hierarchical(self, supply_with_tech):
        """Set capacity factor with hierarchical weights."""
        supply_with_tech.set_capacity_factor(
            'REGION1', 'GAS_CCGT',
            bracket_weights={'Day': 1.0, 'Night': 0.0}
        )

        # Check assignment stored
        assert len(supply_with_tech._capacity_factor_assignments) > 0

    def test_capacity_factor_clamped(self, supply_with_tech):
        """Capacity factors clamped to [0, 1]."""
        supply_with_tech.set_capacity_factor(
            'REGION1', 'GAS_CCGT',
            timeslice_weights={supply_with_tech.timeslices[0]: 1.5}  # > 1
        )
        supply_with_tech.process()

        df = supply_with_tech.capacity_factor
        # All values should be ≤ 1
        assert (df['VALUE'] <= 1.0).all()


# =============================================================================
# set_availability_factor Tests
# =============================================================================

class TestSetAvailabilityFactor:
    """Test set_availability_factor method."""

    def test_availability_factor_scalar(self, supply_with_tech):
        """Set availability factor as scalar."""
        supply_with_tech.set_availability_factor(
            'REGION1', 'GAS_CCGT', availability=0.9
        )

        df = supply_with_tech.availability_factor
        assert (df['VALUE'] == 0.9).all()

    def test_availability_factor_dict(self, supply_with_tech):
        """Set availability factor as year dict."""
        supply_with_tech.set_availability_factor(
            'REGION1', 'GAS_CCGT',
            availability={2025: 0.95, 2030: 0.90}
        )

        df = supply_with_tech.availability_factor
        val_2025 = df[df['YEAR'] == 2025]['VALUE'].iloc[0]
        val_2030 = df[df['YEAR'] == 2030]['VALUE'].iloc[0]

        assert val_2025 == 0.95
        assert val_2030 == 0.90

    def test_availability_factor_out_of_range_raises(self, supply_with_tech):
        """Availability outside [0, 1] raises ValueError."""
        with pytest.raises(ValueError, match="\\[0, 1\\]"):
            supply_with_tech.set_availability_factor(
                'REGION1', 'GAS_CCGT', availability=1.5
            )


# =============================================================================
# process Tests
# =============================================================================

class TestProcess:
    """Test process method."""

    def test_process_generates_capacity_factors(self, supply_with_tech):
        """process generates capacity factor DataFrame."""
        supply_with_tech.set_conversion_technology(
            'REGION1', 'GAS_CCGT',
            input_fuel='GAS', output_fuel='ELEC',
            efficiency=0.5
        )
        supply_with_tech.process()

        assert not supply_with_tech.capacity_factor.empty

    def test_process_default_capacity_factor(self, supply_with_tech):
        """Default capacity factor is 1.0."""
        supply_with_tech.set_resource_technology(
            'REGION1', 'GAS_CCGT', output_fuel='ELEC'
        )
        supply_with_tech.process()

        df = supply_with_tech.capacity_factor
        # All values should be 1.0 (default)
        assert (df['VALUE'] == 1.0).all()

    def test_process_default_availability_factor(self, supply_with_tech):
        """Default availability factor is 1.0."""
        supply_with_tech.set_resource_technology(
            'REGION1', 'GAS_CCGT', output_fuel='ELEC'
        )
        supply_with_tech.process()

        df = supply_with_tech.availability_factor
        assert (df['VALUE'] == 1.0).all()


# =============================================================================
# Validation Tests
# =============================================================================

class TestSupplyValidation:
    """Test validate method and activity ratio validation."""

    def test_validate_success(self, supply_with_tech):
        """Valid supply passes validation."""
        supply_with_tech.set_conversion_technology(
            'REGION1', 'GAS_CCGT',
            input_fuel='GAS', output_fuel='ELEC',
            efficiency=0.5
        )

        # Should not raise
        supply_with_tech.validate()

    def test_validate_no_output_raises(self, supply_with_tech):
        """Technology without outputs fails validation."""
        # Technology registered but no conversion set

        with pytest.raises(ValueError, match="no outputs"):
            supply_with_tech.validate()


# =============================================================================
# Load / Save Tests
# =============================================================================

class TestSupplyLoadSave:
    """Test load and save operations."""

    def test_save_creates_files(self, supply_with_tech):
        """save creates all owned CSV files."""
        supply_with_tech.set_conversion_technology(
            'REGION1', 'GAS_CCGT',
            input_fuel='GAS', output_fuel='ELEC',
            efficiency=0.5
        )
        supply_with_tech.process()
        supply_with_tech.save()

        for filename in SupplyComponent.owned_files:
            path = os.path.join(supply_with_tech.scenario_dir, filename)
            assert os.path.exists(path), f"Missing: {filename}"

    def test_save_technology_csv(self, supply_with_tech):
        """TECHNOLOGY.csv generated from defined technologies."""
        supply_with_tech.set_resource_technology(
            'REGION1', 'GAS_CCGT', output_fuel='ELEC'
        )
        supply_with_tech.save()

        df = pd.read_csv(
            os.path.join(supply_with_tech.scenario_dir, 'TECHNOLOGY.csv')
        )
        assert 'GAS_CCGT' in df['VALUE'].values

    def test_save_fuel_csv(self, supply_with_tech):
        """FUEL.csv generated from defined fuels."""
        supply_with_tech.set_conversion_technology(
            'REGION1', 'GAS_CCGT',
            input_fuel='NATURAL_GAS', output_fuel='ELECTRICITY',
            efficiency=0.5
        )
        supply_with_tech.save()

        df = pd.read_csv(
            os.path.join(supply_with_tech.scenario_dir, 'FUEL.csv')
        )
        assert 'NATURAL_GAS' in df['VALUE'].values
        assert 'ELECTRICITY' in df['VALUE'].values

    def test_round_trip(self, supply_with_tech):
        """Save and load preserves data."""
        supply_with_tech.set_conversion_technology(
            'REGION1', 'GAS_CCGT',
            input_fuel='GAS', output_fuel='ELEC',
            efficiency=0.55
        )
        supply_with_tech.process()
        supply_with_tech.save()

        # Load in new instance
        loaded = SupplyComponent(supply_with_tech.scenario_dir)
        loaded.load()

        # Verify technologies
        assert 'GAS_CCGT' in loaded.technologies

        # Verify fuels
        assert set(loaded.fuels) == {'GAS', 'ELEC'}


# =============================================================================
# Integration Tests
# =============================================================================

class TestSupplyIntegration:
    """Integration tests for supply component."""

    def test_full_workflow(self, complete_scenario_dir):
        """Complete workflow: add technologies, set parameters, process, save."""
        supply = SupplyComponent(complete_scenario_dir)

        # Add technologies
        supply.add_technology('REGION1', 'GAS_CCGT', operational_life=30)
        supply.add_technology('REGION1', 'SOLAR_PV', operational_life=25)
        supply.add_technology('REGION1', 'WIND', operational_life=25)

        # Set conversions
        supply.set_conversion_technology(
            'REGION1', 'GAS_CCGT',
            input_fuel='GAS', output_fuel='ELEC',
            efficiency=0.55
        )
        supply.set_resource_technology('REGION1', 'SOLAR_PV', 'ELEC')
        supply.set_resource_technology('REGION1', 'WIND', 'ELEC')

        # Set capacity factors for renewables
        supply.set_capacity_factor(
            'REGION1', 'SOLAR_PV',
            bracket_weights={'Day': 0.4, 'Night': 0.0}
        )
        supply.set_capacity_factor(
            'REGION1', 'WIND',
            bracket_weights={'Day': 0.3, 'Night': 0.35}
        )

        # Set residual capacity for existing plant
        supply.set_residual_capacity(
            'REGION1', 'GAS_CCGT',
            trajectory={2025: 5, 2030: 3},
            interpolation='linear'
        )

        # Process and validate
        supply.process()
        supply.validate()

        # Save
        supply.save()

        # Verify files created
        assert os.path.exists(
            os.path.join(complete_scenario_dir, 'TECHNOLOGY.csv')
        )
        assert os.path.exists(
            os.path.join(complete_scenario_dir, 'CapacityFactor.csv')
        )

    def test_multiple_technologies(self, complete_scenario_dir):
        """Multiple technologies with different characteristics."""
        supply = SupplyComponent(complete_scenario_dir)

        # Thermal
        supply.add_technology('REGION1', 'COAL', operational_life=40)
        supply.set_conversion_technology(
            'REGION1', 'COAL',
            input_fuel='COAL', output_fuel='ELEC',
            efficiency=0.35
        )

        # Nuclear
        supply.add_technology('REGION1', 'NUCLEAR', operational_life=60)
        supply.set_conversion_technology(
            'REGION1', 'NUCLEAR',
            input_fuel='URANIUM', output_fuel='ELEC',
            efficiency=0.33
        )
        supply.set_availability_factor('REGION1', 'NUCLEAR', 0.90)

        # Renewable
        supply.add_technology('REGION1', 'HYDRO', operational_life=80)
        supply.set_resource_technology('REGION1', 'HYDRO', 'ELEC')

        supply.process()
        supply.validate()

        # Check all technologies present
        assert set(supply.technologies) == {'COAL', 'NUCLEAR', 'HYDRO'}

        # Check fuels collected
        assert {'COAL', 'URANIUM', 'ELEC'}.issubset(set(supply.fuels))

    def test_repr(self, supply_with_tech):
        """__repr__ shows component info."""
        repr_str = repr(supply_with_tech)
        assert "SupplyComponent" in repr_str
