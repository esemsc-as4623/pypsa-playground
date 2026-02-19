# tests/test_scenario/test_components/test_performance.py

"""
Tests for PerformanceComponent facade.

Tests cover:
- Initialization (with and without supply component)
- Facade properties (owned_files is empty)
- Delegation to SupplyComponent
- NotImplementedError for incomplete facade
- No-op load/save behavior
"""

import os
import pytest
import pandas as pd

from pyoscomp.scenario.components.supply import SupplyComponent
from pyoscomp.scenario.components.performance import PerformanceComponent


# =============================================================================
# Initialization Tests
# =============================================================================

class TestPerformanceInit:
    """Test PerformanceComponent initialization."""

    def test_init_without_supply(self, complete_scenario_dir):
        """Can initialize without supply component."""
        perf = PerformanceComponent(complete_scenario_dir)
        assert perf.supply is None

    def test_init_with_supply(self, complete_scenario_dir):
        """Can initialize with supply component."""
        supply = SupplyComponent(complete_scenario_dir)
        perf = PerformanceComponent(complete_scenario_dir, supply)
        assert perf.supply is supply

    def test_supply_setter(self, complete_scenario_dir):
        """Can set supply component after initialization."""
        perf = PerformanceComponent(complete_scenario_dir)
        supply = SupplyComponent(complete_scenario_dir)

        perf.supply = supply
        assert perf.supply is supply

    def test_owned_files_empty(self):
        """Facade owns no files."""
        assert PerformanceComponent.owned_files == []


# =============================================================================
# No-op Methods Tests
# =============================================================================

class TestPerformanceNoOps:
    """Test no-op load/save methods."""

    def test_load_no_op(self, complete_scenario_dir):
        """load is a no-op."""
        perf = PerformanceComponent(complete_scenario_dir)
        # Should not raise
        perf.load()

    def test_save_no_op(self, complete_scenario_dir):
        """save is a no-op."""
        perf = PerformanceComponent(complete_scenario_dir)
        # Should not raise
        perf.save()

    def test_save_creates_no_files(self, complete_scenario_dir):
        """save should not create any files."""
        files_before = set(os.listdir(complete_scenario_dir))

        perf = PerformanceComponent(complete_scenario_dir)
        perf.save()

        files_after = set(os.listdir(complete_scenario_dir))
        # No new files should be created by PerformanceComponent
        # (may have prerequisites from fixture)
        assert files_before == files_after


# =============================================================================
# set_efficiency Tests
# =============================================================================

class TestSetEfficiency:
    """Test set_efficiency method (stub)."""

    def test_set_efficiency_raises_not_implemented(self, complete_scenario_dir):
        """set_efficiency raises NotImplementedError."""
        perf = PerformanceComponent(complete_scenario_dir)

        with pytest.raises(NotImplementedError, match="SupplyComponent"):
            perf.set_efficiency('REGION1', 'GAS_CCGT', 0.55)

    def test_set_efficiency_with_supply_still_raises(self, complete_scenario_dir):
        """set_efficiency raises NotImplementedError even with supply."""
        supply = SupplyComponent(complete_scenario_dir)
        perf = PerformanceComponent(complete_scenario_dir, supply)

        with pytest.raises(NotImplementedError, match="SupplyComponent"):
            perf.set_efficiency('REGION1', 'GAS_CCGT', 0.55)


# =============================================================================
# Delegation Tests (set_capacity_factor)
# =============================================================================

class TestCapacityFactorDelegation:
    """Test set_capacity_factor delegation."""

    def test_delegate_without_supply_raises(self, complete_scenario_dir):
        """set_capacity_factor without supply raises NotImplementedError."""
        perf = PerformanceComponent(complete_scenario_dir)

        with pytest.raises(NotImplementedError, match="No SupplyComponent"):
            perf.set_capacity_factor(region='REGION1', technology='SOLAR_PV', bracket_weights={'Day': 0.25, 'Night': 0})

    def test_delegate_with_supply_calls_supply(self, complete_scenario_dir):
        """set_capacity_factor delegates to supply component."""
        supply = SupplyComponent(complete_scenario_dir)
        # Register technology first
        supply.add_technology(region='REGION1', technology='SOLAR_PV', operational_life=30)

        # Call through facade
        perf = PerformanceComponent(complete_scenario_dir, supply)
        perf.set_capacity_factor(region='REGION1', technology='SOLAR_PV', bracket_weights={'Day': 0.25, 'Night': 0})
        perf.process()
        
        # Verify values were set via supply
        df = supply.capacity_factor
        assert len(df) > 0
        assert (df['TECHNOLOGY'] == 'SOLAR_PV').any()


# =============================================================================
# Delegation Tests (set_availability_factor)
# =============================================================================

class TestAvailabilityFactorDelegation:
    """Test set_availability_factor delegation."""

    def test_delegate_without_supply_raises(self, complete_scenario_dir):
        """set_availability_factor without supply raises NotImplementedError."""
        perf = PerformanceComponent(complete_scenario_dir)

        with pytest.raises(NotImplementedError, match="No SupplyComponent"):
            perf.set_availability_factor('REGION1', 'GAS_CCGT', 0.9)

    def test_delegate_with_supply_calls_supply(self, complete_scenario_dir):
        """set_availability_factor delegates to supply component."""
        supply = SupplyComponent(complete_scenario_dir)
        perf = PerformanceComponent(complete_scenario_dir, supply)

        # Register technology first
        supply.add_technology(region='REGION1', technology='GAS_CCGT', operational_life=20)

        # Call through facade
        perf.set_availability_factor('REGION1', 'GAS_CCGT', 0.9)
        perf.process()

        # Verify values were set via supply
        df = supply.availability_factor
        assert len(df) > 0
        tech_rows = df[df['TECHNOLOGY'] == 'GAS_CCGT']
        assert len(tech_rows) > 0
        assert (tech_rows['VALUE'] == 0.9).all()


# =============================================================================
# Representation Tests
# =============================================================================

class TestPerformanceRepr:
    """Test __repr__ method."""

    def test_repr_without_supply(self, complete_scenario_dir):
        """__repr__ shows supply_attached=False."""
        perf = PerformanceComponent(complete_scenario_dir)
        repr_str = repr(perf)

        assert "PerformanceComponent" in repr_str
        assert "facade=True" in repr_str
        assert "supply_attached=False" in repr_str

    def test_repr_with_supply(self, complete_scenario_dir):
        """__repr__ shows supply_attached=True."""
        supply = SupplyComponent(complete_scenario_dir)
        perf = PerformanceComponent(complete_scenario_dir, supply)
        repr_str = repr(perf)

        assert "PerformanceComponent" in repr_str
        assert "facade=True" in repr_str
        assert "supply_attached=True" in repr_str


# =============================================================================
# Integration Tests
# =============================================================================

class TestPerformanceIntegration:
    """Integration tests for PerformanceComponent facade."""

    def test_facade_workflow(self, complete_scenario_dir):
        """Complete workflow using facade."""
        # Create components
        supply = SupplyComponent(complete_scenario_dir)
        perf = PerformanceComponent(complete_scenario_dir, supply)

        # Register technologies via supply
        supply.add_technology(region='REGION1', technology='SOLAR_PV', operational_life=30)
        supply.add_technology(region='REGION1', technology='WIND', operational_life=25)

        # Set performance via facade
        perf.set_capacity_factor(region='REGION1', technology='SOLAR_PV', bracket_weights={'Day': 0.2, 'Night': 0})
        perf.set_availability_factor(region='REGION1', technology='SOLAR_PV', availability=0.95)

        perf.set_capacity_factor(region='REGION1', technology='WIND', season_weights={'Summer': 0.3, 'Winter': 0.7})
        perf.set_availability_factor(region='REGION1', technology='WIND', availability=0.92)

        # Save via supply (facade save is no-op)
        supply.save()

        # Verify files created
        assert os.path.exists(
            os.path.join(complete_scenario_dir, 'CapacityFactor.csv')
        )
        assert os.path.exists(
            os.path.join(complete_scenario_dir, 'AvailabilityFactor.csv')
        )

    def test_facade_without_supply_is_read_only(self, complete_scenario_dir):
        """Facade without supply can only be read (no mutations)."""
        perf = PerformanceComponent(complete_scenario_dir)

        # load is no-op (allowed)
        perf.load()

        # save is no-op (allowed)
        perf.save()

        # Mutations should raise
        with pytest.raises(NotImplementedError):
            perf.set_efficiency(region='REGION1', technology='TECH', efficiency=0.5)

        with pytest.raises(NotImplementedError):
            perf.set_capacity_factor(region='REGION1', technology='TECH', daytype_weights={'AllDays': 0.5})

        with pytest.raises(NotImplementedError):
            perf.set_availability_factor(region='REGION1', technology='TECH', availability=0.9)

    def test_supply_assignment_enables_mutations(self, complete_scenario_dir):
        """Assigning supply enables mutation methods."""
        perf = PerformanceComponent(complete_scenario_dir)

        # Initially raises
        with pytest.raises(NotImplementedError):
            perf.set_availability_factor(region='REGION1', technology='TECH', availability=0.9)

        # Assign supply
        supply = SupplyComponent(complete_scenario_dir)
        supply.add_technology(region='REGION1', technology='TECH', operational_life=20)
        perf.supply = supply

        # Now works
        perf.set_availability_factor(region='REGION1', technology='TECH', availability=0.9)

        df = supply.availability_factor
        assert len(df) > 0
