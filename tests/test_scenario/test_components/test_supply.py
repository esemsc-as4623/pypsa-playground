# tests/test_scenario/test_components/test_supply.py

"""
Tests for SupplyComponent (refactored).

Tests cover:
- Initialization and prerequisites
- Properties (technologies, fuels, modes, fuel_assignments)
- TechnologyBuilder fluent API
  * with_operational_life
  * with_residual_capacity (step and linear interpolation)
  * as_conversion
  * as_resource
  * as_multimode
- Validation
- Load / save operations (including _fuel_assignments.json)
- Representation (__repr__)
"""

import json
import math
import os
import pytest
import pandas as pd

from pyoscomp.scenario.components.supply import SupplyComponent


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def supply(complete_scenario_dir):
    """Create SupplyComponent with all prerequisites."""
    return SupplyComponent(complete_scenario_dir)


@pytest.fixture
def supply_with_tech(complete_scenario_dir):
    """Supply component with a registered conversion technology."""
    s = SupplyComponent(complete_scenario_dir)
    s.add_technology('REGION1', 'GAS_CCGT') \
        .with_operational_life(30) \
        .as_conversion(input_fuel='GAS', output_fuel='ELEC')
    return s


# =============================================================================
# Initialization Tests
# =============================================================================

class TestSupplyInit:
    """Test SupplyComponent initialization."""

    def test_init_loads_prerequisites(self, supply):
        """Initialization loads years and regions."""
        assert supply.years is not None
        assert len(supply.years) > 0
        assert supply.regions is not None
        assert 'REGION1' in supply.regions

    def test_init_missing_time_raises(self, topology_scenario_dir):
        """Missing time component raises AttributeError."""
        with pytest.raises(AttributeError):
            SupplyComponent(topology_scenario_dir)

    def test_owned_files(self):
        """owned_files contains supply-related files."""
        expected = {
            'TECHNOLOGY.csv', 'FUEL.csv', 'MODE_OF_OPERATION.csv',
            'OperationalLife.csv', 'ResidualCapacity.csv',
        }
        assert set(SupplyComponent.owned_files) == expected


# =============================================================================
# Properties Tests
# =============================================================================

class TestSupplyProperties:
    """Test supply properties."""

    def test_technologies_empty(self, supply):
        """technologies empty initially."""
        assert supply.technologies == []

    def test_technologies_after_add(self, supply_with_tech):
        """technologies populated after add_technology."""
        assert 'GAS_CCGT' in supply_with_tech.technologies

    def test_fuels_empty(self, supply):
        """fuels empty initially."""
        assert supply.fuels == []

    def test_fuels_after_conversion(self, supply_with_tech):
        """fuels populated after as_conversion."""
        assert 'GAS' in supply_with_tech.fuels
        assert 'ELEC' in supply_with_tech.fuels

    def test_modes_default(self, supply):
        """modes returns default MODE1 when nothing defined."""
        assert supply.modes == {'MODE1'}

    def test_modes_after_conversion(self, supply_with_tech):
        """modes contains MODE1 after as_conversion."""
        assert 'MODE1' in supply_with_tech.modes

    def test_fuel_assignments(self, supply_with_tech):
        """fuel_assignments tracks conversion mappings."""
        fa = supply_with_tech.fuel_assignments
        key = ('REGION1', 'GAS_CCGT', 'MODE1')
        assert key in fa
        assert fa[key] == {'input': 'GAS', 'output': 'ELEC'}


# =============================================================================
# TechnologyBuilder Tests
# =============================================================================

class TestTechnologyBuilder:
    """Test fluent TechnologyBuilder API."""

    def test_add_technology_returns_builder(self, supply):
        """add_technology returns a TechnologyBuilder."""
        from pyoscomp.scenario.components.supply import TechnologyBuilder
        builder = supply.add_technology('REGION1', 'WIND')
        assert isinstance(builder, TechnologyBuilder)

    def test_builder_chaining(self, supply):
        """Builder methods return self for chaining."""
        result = supply.add_technology('REGION1', 'GAS_CCGT') \
            .with_operational_life(30) \
            .with_residual_capacity(0) \
            .as_conversion(input_fuel='GAS', output_fuel='ELEC')

        from pyoscomp.scenario.components.supply import TechnologyBuilder
        assert isinstance(result, TechnologyBuilder)

    def test_invalid_region_raises(self, supply):
        """Invalid region raises ValueError."""
        with pytest.raises(ValueError, match="not defined"):
            supply.add_technology('INVALID', 'TECH1')

    def test_with_operational_life_scalar(self, supply):
        """with_operational_life stores operational life."""
        supply.add_technology('REGION1', 'WIND') \
            .with_operational_life(25)

        df = supply.operational_life
        row = df[df['TECHNOLOGY'] == 'WIND']
        assert len(row) == 1
        assert row['VALUE'].iloc[0] == 25

    def test_with_operational_life_zero_raises(self, supply):
        """Zero operational life raises ValueError."""
        with pytest.raises(ValueError, match="positive"):
            supply.add_technology('REGION1', 'WIND') \
                .with_operational_life(0)

    def test_with_operational_life_negative_raises(self, supply):
        """Negative operational life raises ValueError."""
        with pytest.raises(ValueError, match="positive"):
            supply.add_technology('REGION1', 'WIND') \
                .with_operational_life(-5)

    def test_with_residual_capacity_scalar(self, supply):
        """with_residual_capacity scalar fills all years."""
        supply.add_technology('REGION1', 'WIND') \
            .with_residual_capacity(10)

        df = supply.residual_capacity
        wind_rows = df[df['TECHNOLOGY'] == 'WIND']
        assert len(wind_rows) == len(supply.years)
        assert (wind_rows['VALUE'] == 10).all()

    def test_with_residual_capacity_dict(self, supply):
        """with_residual_capacity with dict trajectory."""
        supply.add_technology('REGION1', 'GAS') \
            .with_residual_capacity({2025: 10, 2030: 5})

        df = supply.residual_capacity
        gas_rows = df[df['TECHNOLOGY'] == 'GAS']
        assert len(gas_rows) == len(supply.years)

    def test_with_residual_capacity_negative_raises(self, supply):
        """Negative residual capacity raises ValueError."""
        with pytest.raises(ValueError, match="Negative"):
            supply.add_technology('REGION1', 'GAS') \
                .with_residual_capacity(-1)

    def test_as_conversion_basic(self, supply):
        """as_conversion registers fuels and mode."""
        supply.add_technology('REGION1', 'GAS_CCGT') \
            .as_conversion(input_fuel='GAS', output_fuel='ELEC')

        assert 'GAS' in supply.fuels
        assert 'ELEC' in supply.fuels
        assert 'MODE1' in supply.modes

    def test_as_conversion_same_fuel_raises(self, supply):
        """Same input and output fuel raises ValueError."""
        with pytest.raises(ValueError, match="different"):
            supply.add_technology('REGION1', 'TECH') \
                .as_conversion(input_fuel='ELEC', output_fuel='ELEC')

    def test_as_resource(self, supply):
        """as_resource registers output fuel only."""
        supply.add_technology('REGION1', 'SOLAR_PV') \
            .as_resource(output_fuel='ELEC')

        assert 'ELEC' in supply.fuels
        fa = supply.fuel_assignments
        key = ('REGION1', 'SOLAR_PV', 'MODE1')
        assert fa[key]['output'] == 'ELEC'
        assert fa[key]['input'] is None

    def test_as_multimode(self, supply):
        """as_multimode registers multiple modes and fuels."""
        supply.add_technology('REGION1', 'CHP') \
            .as_multimode({
                'ELEC_ONLY': {
                    'inputs': {'GAS': 1.0},
                    'outputs': {'ELEC': 1.0},
                },
                'CHP_MODE': {
                    'inputs': {'GAS': 1.0},
                    'outputs': {'ELEC': 0.6, 'HEAT': 0.3},
                },
            })

        assert 'ELEC_ONLY' in supply.modes
        assert 'CHP_MODE' in supply.modes
        assert {'GAS', 'ELEC', 'HEAT'}.issubset(set(supply.fuels))

    def test_as_multimode_missing_output_raises(self, supply):
        """Mode without outputs raises ValueError."""
        with pytest.raises(ValueError, match="at least one output"):
            supply.add_technology('REGION1', 'CHP') \
                .as_multimode({
                    'BAD_MODE': {'inputs': {'GAS': 1.0}},
                })


# =============================================================================
# Residual Capacity Interpolation Tests
# =============================================================================

class TestResidualCapacity:
    """Test residual capacity with interpolation."""

    def test_residual_step(self, supply):
        """Step interpolation keeps constant until next point."""
        supply.add_technology('REGION1', 'GAS') \
            .with_residual_capacity(
                {2025: 10, 2030: 5}, interpolation='step'
            )

        df = supply.residual_capacity
        val_2027 = df[df['YEAR'] == 2027]['VALUE'].iloc[0]
        val_2030 = df[df['YEAR'] == 2030]['VALUE'].iloc[0]
        assert val_2027 == 10
        assert val_2030 == 5

    def test_residual_linear(self, supply):
        """Linear interpolation between defined points."""
        supply.add_technology('REGION1', 'GAS') \
            .with_residual_capacity(
                {2025: 10, 2030: 0}, interpolation='linear'
            )

        df = supply.residual_capacity
        val_2027 = df[df['YEAR'] == 2027]['VALUE'].iloc[0]
        assert math.isclose(val_2027, 6, abs_tol=0.5)


# =============================================================================
# Validation Tests
# =============================================================================

class TestSupplyValidation:
    """Test validate method."""

    def test_validate_success(self, supply_with_tech):
        """Valid supply passes validation."""
        supply_with_tech.validate()

    def test_validate_missing_operational_life_raises(self, supply):
        """Technology without operational life fails validation."""
        supply.add_technology('REGION1', 'TECH1')
        # No with_operational_life call
        with pytest.raises(ValueError, match="no operational life"):
            supply.validate()


# =============================================================================
# Save / Load Tests
# =============================================================================

class TestSupplySaveLoad:
    """Test save and load operations."""

    def test_save_creates_files(self, supply_with_tech):
        """save creates all owned CSV files."""
        supply_with_tech.save()

        for filename in SupplyComponent.owned_files:
            path = os.path.join(
                supply_with_tech.scenario_dir, filename
            )
            assert os.path.exists(path), f"Missing: {filename}"

    def test_save_creates_fuel_assignments_json(self, supply_with_tech):
        """save creates _fuel_assignments.json sidecar."""
        supply_with_tech.save()
        fa_path = os.path.join(
            supply_with_tech.scenario_dir, "_fuel_assignments.json"
        )
        assert os.path.exists(fa_path)

        with open(fa_path) as f:
            data = json.load(f)
        assert 'REGION1|GAS_CCGT|MODE1' in data

    def test_save_technology_csv(self, supply_with_tech):
        """TECHNOLOGY.csv matches defined technologies."""
        supply_with_tech.save()
        df = pd.read_csv(
            os.path.join(
                supply_with_tech.scenario_dir, 'TECHNOLOGY.csv'
            )
        )
        assert 'GAS_CCGT' in df['VALUE'].values

    def test_save_fuel_csv(self, supply_with_tech):
        """FUEL.csv matches defined fuels."""
        supply_with_tech.save()
        df = pd.read_csv(
            os.path.join(
                supply_with_tech.scenario_dir, 'FUEL.csv'
            )
        )
        assert 'GAS' in df['VALUE'].values
        assert 'ELEC' in df['VALUE'].values

    def test_round_trip(self, supply_with_tech):
        """Save and load preserves data."""
        supply_with_tech.save()

        loaded = SupplyComponent(supply_with_tech.scenario_dir)
        loaded.load()

        assert 'GAS_CCGT' in loaded.technologies
        assert set(loaded.fuels) == {'GAS', 'ELEC'}


# =============================================================================
# Integration Tests
# =============================================================================

class TestSupplyIntegration:
    """Integration tests for supply component."""

    def test_full_workflow(self, complete_scenario_dir):
        """Add technologies, set parameters, validate, save."""
        supply = SupplyComponent(complete_scenario_dir)

        supply.add_technology('REGION1', 'GAS_CCGT') \
            .with_operational_life(30) \
            .with_residual_capacity(
                {2025: 5, 2030: 3}, interpolation='linear'
            ) \
            .as_conversion(input_fuel='GAS', output_fuel='ELEC')

        supply.add_technology('REGION1', 'SOLAR_PV') \
            .with_operational_life(25) \
            .as_resource(output_fuel='ELEC')

        supply.add_technology('REGION1', 'WIND') \
            .with_operational_life(25) \
            .as_resource(output_fuel='ELEC')

        supply.validate()
        supply.save()

        # Verify written files
        assert os.path.exists(
            os.path.join(complete_scenario_dir, 'TECHNOLOGY.csv')
        )
        df = pd.read_csv(
            os.path.join(complete_scenario_dir, 'TECHNOLOGY.csv')
        )
        assert set(df['VALUE']) == {'GAS_CCGT', 'SOLAR_PV', 'WIND'}

    def test_multiple_technologies(self, complete_scenario_dir):
        """Multiple technologies with different characteristics."""
        supply = SupplyComponent(complete_scenario_dir)

        supply.add_technology('REGION1', 'COAL') \
            .with_operational_life(40) \
            .as_conversion(input_fuel='COAL', output_fuel='ELEC')

        supply.add_technology('REGION1', 'NUCLEAR') \
            .with_operational_life(60) \
            .as_conversion(input_fuel='URANIUM', output_fuel='ELEC')

        supply.add_technology('REGION1', 'HYDRO') \
            .with_operational_life(80) \
            .as_resource(output_fuel='ELEC')

        assert set(supply.technologies) == {'COAL', 'NUCLEAR', 'HYDRO'}
        assert {'COAL', 'URANIUM', 'ELEC'}.issubset(set(supply.fuels))

    def test_repr(self, supply_with_tech):
        """__repr__ shows component info."""
        repr_str = repr(supply_with_tech)
        assert "SupplyComponent" in repr_str
