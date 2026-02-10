# tests/test_scenario/test_components/test_economics.py

"""
Tests for EconomicsComponent.

Tests cover:
- Initialization and prerequisites
- set_discount_rate method
- set_capital_cost with trajectory and interpolation
- set_fixed_cost with trajectory and interpolation
- set_variable_cost with mode parameter
- Cost validation (non-negative)
- load / save operations
"""

import math
import os
import pytest
import pandas as pd
import numpy as np

from pyoscomp.scenario.components.topology import TopologyComponent
from pyoscomp.scenario.components.time import TimeComponent
from pyoscomp.scenario.components.economics import EconomicsComponent


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def econ_component(complete_scenario_dir):
    """Create EconomicsComponent with all prerequisites."""
    return EconomicsComponent(complete_scenario_dir)


# =============================================================================
# Initialization Tests
# =============================================================================

class TestEconomicsInit:
    """Test EconomicsComponent initialization."""

    def test_init_loads_prerequisites(self, econ_component):
        """Initialization loads years and regions."""
        assert econ_component.years is not None
        assert econ_component.regions is not None

    def test_init_missing_time_raises(self, topology_scenario_dir):
        """Missing time component raises AttributeError."""
        with pytest.raises(AttributeError):
            EconomicsComponent(topology_scenario_dir)

    def test_owned_files(self):
        """owned_files contains economics-related files."""
        expected = [
            'DiscountRate.csv', 'CapitalCost.csv',
            'FixedCost.csv', 'VariableCost.csv'
        ]
        assert set(EconomicsComponent.owned_files) == set(expected)


# =============================================================================
# set_discount_rate Tests
# =============================================================================

class TestSetDiscountRate:
    """Test set_discount_rate method."""

    def test_set_discount_rate(self, econ_component):
        """Set discount rate for a region."""
        econ_component.set_discount_rate('REGION1', 0.05)

        df = econ_component.discount_rate
        row = df[df['REGION'] == 'REGION1']
        assert len(row) == 1
        assert row['VALUE'].iloc[0] == 0.05

    def test_discount_rate_update(self, econ_component):
        """Setting discount rate again updates value."""
        econ_component.set_discount_rate('REGION1', 0.05)
        econ_component.set_discount_rate('REGION1', 0.08)

        df = econ_component.discount_rate
        row = df[df['REGION'] == 'REGION1']
        assert len(row) == 1
        assert row['VALUE'].iloc[0] == 0.08

    def test_discount_rate_invalid_region_raises(self, econ_component):
        """Invalid region raises ValueError."""
        with pytest.raises(ValueError, match="not defined"):
            econ_component.set_discount_rate('INVALID_REGION', 0.05)

    def test_discount_rate_negative_raises(self, econ_component):
        """Negative discount rate raises ValueError."""
        with pytest.raises(ValueError, match="\\[0, 1\\]"):
            econ_component.set_discount_rate('REGION1', -0.05)

    def test_discount_rate_over_one_raises(self, econ_component):
        """Discount rate > 1 raises ValueError."""
        with pytest.raises(ValueError, match="\\[0, 1\\]"):
            econ_component.set_discount_rate('REGION1', 1.5)

    def test_discount_rate_zero_valid(self, econ_component):
        """Zero discount rate is valid."""
        econ_component.set_discount_rate('REGION1', 0.0)
        df = econ_component.discount_rate
        assert df['VALUE'].iloc[0] == 0.0

    def test_discount_rate_one_valid(self, econ_component):
        """Discount rate of 1.0 is valid (edge case)."""
        econ_component.set_discount_rate('REGION1', 1.0)
        df = econ_component.discount_rate
        assert df['VALUE'].iloc[0] == 1.0


# =============================================================================
# set_capital_cost Tests
# =============================================================================

class TestSetCapitalCost:
    """Test set_capital_cost method."""

    def test_capital_cost_scalar(self, econ_component):
        """Set capital cost as scalar (all years)."""
        econ_component.set_capital_cost('REGION1', 'GAS_CCGT', 500)

        df = econ_component.capital_cost
        # Should have entry for each year
        assert len(df) == len(econ_component.years)
        assert (df['VALUE'] == 500).all()

    def test_capital_cost_trajectory(self, econ_component):
        """Set capital cost with trajectory dict."""
        econ_component.set_capital_cost(
            'REGION1', 'GAS_CCGT',
            cost_trajectory={2025: 500, 2030: 450}
        )

        df = econ_component.capital_cost
        val_2025 = df[df['YEAR'] == 2025]['VALUE'].iloc[0]
        val_2030 = df[df['YEAR'] == 2030]['VALUE'].iloc[0]

        assert val_2025 == 500
        assert val_2030 == 450

    def test_capital_cost_step_interpolation(self, econ_component):
        """Step interpolation holds previous value."""
        econ_component.set_capital_cost(
            'REGION1', 'SOLAR_PV',
            cost_trajectory={2025: 300, 2030: 200},
            interpolation='step'
        )

        df = econ_component.capital_cost
        # 2025-2029 should be 300
        val_2027 = df[df['YEAR'] == 2027]['VALUE'].iloc[0]
        assert val_2027 == 300

    def test_capital_cost_linear_interpolation(self, econ_component):
        """Linear interpolation creates smooth transition."""
        econ_component.set_capital_cost(
            'REGION1', 'SOLAR_PV',
            cost_trajectory={2025: 300, 2030: 200},
            interpolation='linear'
        )

        df = econ_component.capital_cost
        # Should decrease by 20 per year
        val_2027 = df[df['YEAR'] == 2027]['VALUE'].iloc[0]
        # Expected: 260 (300 - 2*20)
        assert math.isclose(val_2027, 260, abs_tol=1)

    def test_capital_cost_invalid_region_raises(self, econ_component):
        """Invalid region raises ValueError."""
        with pytest.raises(ValueError, match="not defined"):
            econ_component.set_capital_cost('INVALID', 'TECH', 100)


# =============================================================================
# set_fixed_cost Tests
# =============================================================================

class TestSetFixedCost:
    """Test set_fixed_cost method."""

    def test_fixed_cost_scalar(self, econ_component):
        """Set fixed cost as scalar."""
        econ_component.set_fixed_cost('REGION1', 'GAS_CCGT', 10)

        df = econ_component.fixed_cost
        assert len(df) == len(econ_component.years)
        assert (df['VALUE'] == 10).all()

    def test_fixed_cost_trajectory(self, econ_component):
        """Set fixed cost with trajectory."""
        econ_component.set_fixed_cost(
            'REGION1', 'GAS_CCGT',
            cost_trajectory={2025: 10, 2030: 12},
            interpolation='linear'
        )

        df = econ_component.fixed_cost
        val_2025 = df[df['YEAR'] == 2025]['VALUE'].iloc[0]
        val_2030 = df[df['YEAR'] == 2030]['VALUE'].iloc[0]

        assert val_2025 == 10
        assert val_2030 == 12


# =============================================================================
# set_variable_cost Tests
# =============================================================================

class TestSetVariableCost:
    """Test set_variable_cost method."""

    def test_variable_cost_scalar(self, econ_component):
        """Set variable cost as scalar."""
        econ_component.set_variable_cost('REGION1', 'GAS_CCGT', 'MODE1', 2.5)

        df = econ_component.variable_cost
        assert len(df) == len(econ_component.years)
        assert (df['VALUE'] == 2.5).all()
        assert (df['MODE_OF_OPERATION'] == 'MODE1').all()

    def test_variable_cost_trajectory(self, econ_component):
        """Set variable cost with trajectory."""
        econ_component.set_variable_cost(
            'REGION1', 'GAS_CCGT', 'MODE1',
            cost_trajectory={2025: 2.0, 2030: 3.0}
        )

        df = econ_component.variable_cost
        val_2025 = df[df['YEAR'] == 2025]['VALUE'].iloc[0]
        val_2030 = df[df['YEAR'] == 2030]['VALUE'].iloc[0]

        assert val_2025 == 2.0
        assert val_2030 == 3.0

    def test_variable_cost_multiple_modes(self, econ_component):
        """Set variable costs for multiple modes."""
        econ_component.set_variable_cost('REGION1', 'CHP', 'ELEC_MODE', 2.0)
        econ_component.set_variable_cost('REGION1', 'CHP', 'HEAT_MODE', 1.5)

        df = econ_component.variable_cost
        elec_rows = df[df['MODE_OF_OPERATION'] == 'ELEC_MODE']
        heat_rows = df[df['MODE_OF_OPERATION'] == 'HEAT_MODE']

        assert len(elec_rows) > 0
        assert len(heat_rows) > 0

    def test_variable_cost_mode_conversion(self, econ_component):
        """Mode parameter converted to string."""
        econ_component.set_variable_cost('REGION1', 'TECH', 1, 2.0)  # int mode

        df = econ_component.variable_cost
        assert df['MODE_OF_OPERATION'].dtype == object  # string type


# =============================================================================
# Load / Save Tests
# =============================================================================

class TestEconomicsLoadSave:
    """Test load and save operations."""

    def test_save_creates_files(self, econ_component):
        """save creates all owned CSV files."""
        econ_component.set_discount_rate('REGION1', 0.05)
        econ_component.set_capital_cost('REGION1', 'TECH', 100)
        econ_component.save()

        for filename in EconomicsComponent.owned_files:
            path = os.path.join(econ_component.scenario_dir, filename)
            assert os.path.exists(path), f"Missing: {filename}"

    def test_save_empty_dataframes(self, econ_component):
        """save handles empty DataFrames."""
        econ_component.set_discount_rate('REGION1', 0.05)
        # Don't set any costs
        econ_component.save()

        # Should create files even if empty
        assert os.path.exists(
            os.path.join(econ_component.scenario_dir, 'CapitalCost.csv')
        )

    def test_round_trip(self, econ_component):
        """Save and load preserves data."""
        econ_component.set_discount_rate('REGION1', 0.05)
        econ_component.set_capital_cost('REGION1', 'SOLAR', {2025: 300, 2030: 200})
        econ_component.set_fixed_cost('REGION1', 'SOLAR', 5)
        econ_component.set_variable_cost('REGION1', 'GAS', 'MODE1', 2.5)
        econ_component.save()

        # Load in new instance
        loaded = EconomicsComponent(econ_component.scenario_dir)
        loaded.load()

        # Verify discount rate
        dr = loaded.discount_rate[loaded.discount_rate['REGION'] == 'REGION1']
        assert dr['VALUE'].iloc[0] == 0.05

        # Verify capital cost
        cc = loaded.capital_cost[(loaded.capital_cost['TECHNOLOGY'] == 'SOLAR') &
                                  (loaded.capital_cost['YEAR'] == 2030)]
        assert cc['VALUE'].iloc[0] == 200


# =============================================================================
# Integration Tests
# =============================================================================

class TestEconomicsIntegration:
    """Integration tests for economics component."""

    def test_full_workflow(self, complete_scenario_dir):
        """Complete workflow: set all parameters and save."""
        econ = EconomicsComponent(complete_scenario_dir)

        # Discount rate
        econ.set_discount_rate('REGION1', 0.05)

        # Multiple technologies
        techs = {
            'GAS_CCGT': {'capital': 500, 'fixed': 15, 'variable': 3},
            'SOLAR_PV': {'capital': 300, 'fixed': 8, 'variable': 0},
            'WIND': {'capital': 400, 'fixed': 12, 'variable': 0}
        }

        for tech, costs in techs.items():
            econ.set_capital_cost('REGION1', tech, costs['capital'])
            econ.set_fixed_cost('REGION1', tech, costs['fixed'])
            econ.set_variable_cost('REGION1', tech, 'MODE1', costs['variable'])

        econ.save()

        # Verify all files created
        for filename in EconomicsComponent.owned_files:
            assert os.path.exists(
                os.path.join(complete_scenario_dir, filename)
            )

    def test_cost_decline_trajectory(self, complete_scenario_dir):
        """Model technology cost decline over time."""
        econ = EconomicsComponent(complete_scenario_dir)

        # Solar PV with declining costs
        econ.set_capital_cost(
            'REGION1', 'SOLAR_PV',
            cost_trajectory={2025: 400, 2030: 250},
            interpolation='linear'
        )

        df = econ.capital_cost
        costs = df.sort_values('YEAR')['VALUE'].tolist()

        # Should be declining
        for i in range(len(costs) - 1):
            assert costs[i] >= costs[i + 1], "Costs should decline"

    def test_multiple_regions(self, multi_region_time_dir):
        """Economics across multiple regions."""
        econ = EconomicsComponent(multi_region_time_dir)

        regions = ['North', 'South', 'East']
        rates = [0.05, 0.06, 0.04]

        for region, rate in zip(regions, rates):
            econ.set_discount_rate(region, rate)

        df = econ.discount_rate
        assert len(df) == 3

        # Verify different rates
        for region, rate in zip(regions, rates):
            row = df[df['REGION'] == region]
            assert row['VALUE'].iloc[0] == rate

    def test_repr(self, econ_component):
        """__repr__ shows component info."""
        repr_str = repr(econ_component)
        assert "EconomicsComponent" in repr_str
