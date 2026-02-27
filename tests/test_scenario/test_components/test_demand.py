# tests/test_scenario/test_components/test_demand.py

"""
Tests for DemandComponent.

Tests cover:
- Initialization and prerequisites
- Properties (defined_fuels, fuels)
- add_annual_demand with trajectory and interpolation
- add_flexible_demand
- set_profile (timeslice weights, hierarchical weights)
- process method (profile generation)
- Profile normalization (sums to 1.0)
- load / save operations
- validate method
- Interpolation methods (step, linear, cagr)
"""

import math
import os
import pytest
import pandas as pd
import numpy as np

from pyoscomp.scenario.components.topology import TopologyComponent
from pyoscomp.scenario.components.time import TimeComponent
from pyoscomp.scenario.components.demand import DemandComponent


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def demand_component(complete_scenario_dir):
    """Create DemandComponent with all prerequisites."""
    return DemandComponent(complete_scenario_dir)


# =============================================================================
# Initialization Tests
# =============================================================================

class TestDemandInit:
    """Test DemandComponent initialization."""

    def test_init_loads_prerequisites(self, demand_component):
        """Initialization loads years, regions, timeslices."""
        assert demand_component.years is not None
        assert demand_component.regions is not None
        assert demand_component.timeslices is not None

    def test_init_missing_time_raises(self, topology_scenario_dir):
        """Missing time component raises AttributeError."""
        with pytest.raises(AttributeError, match="YEAR.csv required"):
            DemandComponent(topology_scenario_dir)

    def test_init_missing_topology_raises(self, empty_scenario_dir):
        """Missing topology raises AttributeError."""
        # Create YEAR.csv only
        pd.DataFrame({"VALUE": [2025]}).to_csv(
            os.path.join(empty_scenario_dir, "YEAR.csv"), index=False
        )

        with pytest.raises(AttributeError, match="REGION.csv required"):
            DemandComponent(empty_scenario_dir)

    def test_owned_files(self):
        """owned_files contains demand-related files."""
        expected = [
            'SpecifiedAnnualDemand.csv',
            'SpecifiedDemandProfile.csv',
            'AccumulatedAnnualDemand.csv'
        ]
        assert set(DemandComponent.owned_files) == set(expected)


# =============================================================================
# Properties Tests
# =============================================================================

class TestDemandProperties:
    """Test demand properties."""

    def test_defined_fuels_empty(self, demand_component):
        """defined_fuels empty initially."""
        assert demand_component.defined_fuels == []

    def test_defined_fuels_after_add(self, demand_component):
        """defined_fuels populated after add_annual_demand."""
        demand_component.add_annual_demand('REGION1', 'ELEC', {2025: 100})
        demand_component.add_annual_demand('REGION1', 'HEAT', {2025: 50})

        assert ('REGION1', 'ELEC') in demand_component.defined_fuels
        assert ('REGION1', 'HEAT') in demand_component.defined_fuels

    def test_fuels_property(self, demand_component):
        """fuels returns unique fuel names."""
        demand_component.add_annual_demand('REGION1', 'ELEC', {2025: 100})
        demand_component.add_annual_demand('REGION1', 'HEAT', {2025: 50})

        assert demand_component.fuels == {'ELEC', 'HEAT'}


# =============================================================================
# add_annual_demand Tests
# =============================================================================

class TestAddAnnualDemand:
    """Test add_annual_demand method."""

    def test_simple_demand(self, demand_component):
        """Add simple demand for single year."""
        demand_component.add_annual_demand('REGION1', 'ELEC', {2025: 100})

        df = demand_component.annual_demand_df
        row = df[(df['REGION'] == 'REGION1') & (df['FUEL'] == 'ELEC') &
                 (df['YEAR'] == 2025)]
        assert len(row) == 1
        assert row['VALUE'].iloc[0] == 100

    def test_demand_trajectory(self, demand_component):
        """Add demand with multi-year trajectory."""
        demand_component.add_annual_demand(
            'REGION1', 'ELEC',
            trajectory={2025: 100, 2030: 150}
        )

        df = demand_component.annual_demand_df
        assert len(df) == len(demand_component.years)

    def test_invalid_region_raises(self, demand_component):
        """Invalid region raises ValueError."""
        with pytest.raises(ValueError, match="not defined"):
            demand_component.add_annual_demand('INVALID', 'ELEC', {2025: 100})

    def test_empty_trajectory_raises(self, demand_component):
        """Empty trajectory raises ValueError."""
        with pytest.raises(ValueError, match="Empty trajectory"):
            demand_component.add_annual_demand('REGION1', 'ELEC', {})

    def test_negative_demand_raises(self, demand_component):
        """Negative demand value raises ValueError."""
        with pytest.raises(ValueError, match="Negative demand"):
            demand_component.add_annual_demand('REGION1', 'ELEC', {2025: -100})


# =============================================================================
# Interpolation Tests
# =============================================================================

class TestDemandInterpolation:
    """Test demand trajectory interpolation methods."""

    def test_step_interpolation(self, demand_component):
        """Step interpolation holds value constant."""
        demand_component.add_annual_demand(
            'REGION1', 'ELEC',
            trajectory={2025: 100, 2030: 200},
            interpolation='step'
        )

        df = demand_component.annual_demand_df
        # Years 2025-2029 should all be 100
        for year in [2025, 2026, 2027, 2028, 2029]:
            val = df[df['YEAR'] == year]['VALUE'].iloc[0]
            assert val == 100, f"Year {year}: expected 100, got {val}"

        # Year 2030 should be 200
        val_2030 = df[df['YEAR'] == 2030]['VALUE'].iloc[0]
        assert val_2030 == 200

    def test_linear_interpolation(self, demand_component):
        """Linear interpolation creates even increments."""
        demand_component.add_annual_demand(
            'REGION1', 'ELEC',
            trajectory={2025: 100, 2030: 200},
            interpolation='linear'
        )

        df = demand_component.annual_demand_df
        # Check linear progression: 100, 120, 140, 160, 180, 200
        expected = {2025: 100, 2026: 120, 2027: 140, 2028: 160, 2029: 180, 2030: 200}
        for year, expected_val in expected.items():
            actual = df[df['YEAR'] == year]['VALUE'].iloc[0]
            assert math.isclose(actual, expected_val, abs_tol=0.1), \
                f"Year {year}: expected {expected_val}, got {actual}"

    def test_cagr_interpolation(self, demand_component):
        """CAGR interpolation creates compound growth."""
        demand_component.add_annual_demand(
            'REGION1', 'ELEC',
            trajectory={2025: 100, 2030: 161.0510},  # ~10% CAGR
            interpolation='cagr'
        )

        df = demand_component.annual_demand_df
        # With ~10% CAGR: 100, 110, 121, 133.1, 146.4, 161
        val_2026 = df[df['YEAR'] == 2026]['VALUE'].iloc[0]
        assert 109 < val_2026 < 111  # ~110

    def test_extrapolation_before_first(self, demand_component):
        """Values before first trajectory point use first value."""
        # Model years are 2025-2030, trajectory starts at 2027
        demand_component.add_annual_demand(
            'REGION1', 'ELEC',
            trajectory={2027: 100, 2030: 130},
            interpolation='step'
        )

        df = demand_component.annual_demand_df
        # 2025, 2026 should equal the 2027 value
        assert df[df['YEAR'] == 2025]['VALUE'].iloc[0] == 100
        assert df[df['YEAR'] == 2026]['VALUE'].iloc[0] == 100

    def test_extrapolation_after_last(self, demand_component):
        """Values after last trajectory point use last value."""
        # Use trajectory ending before model end
        demand_component.add_annual_demand(
            'REGION1', 'ELEC',
            trajectory={2025: 100, 2028: 130},
            interpolation='step'
        )

        df = demand_component.annual_demand_df
        # 2029, 2030 should equal the 2028 value
        assert df[df['YEAR'] == 2029]['VALUE'].iloc[0] == 130
        assert df[df['YEAR'] == 2030]['VALUE'].iloc[0] == 130


# =============================================================================
# add_flexible_demand Tests
# =============================================================================

class TestAddFlexibleDemand:
    """Test add_flexible_demand method."""

    def test_add_flexible_demand(self, demand_component):
        """Add flexible demand entry."""
        demand_component.add_flexible_demand('REGION1', 'STORAGE', 2025, 50)

        df = demand_component.accumulated_demand_df
        assert len(df) == 1
        assert df.iloc[0]['VALUE'] == 50

    def test_negative_flexible_demand_raises(self, demand_component):
        """Negative flexible demand raises ValueError."""
        with pytest.raises(ValueError, match="cannot be negative"):
            demand_component.add_flexible_demand('REGION1', 'ELEC', 2025, -10)


# =============================================================================
# set_profile Tests
# =============================================================================

class TestSetProfile:
    """Test set_profile method."""

    def test_set_timeslice_weights(self, demand_component):
        """Set profile with direct timeslice weights."""
        demand_component.add_annual_demand('REGION1', 'ELEC', {2025: 100})

        # Get timeslices from component
        ts = demand_component.timeslices
        weights = {ts[0]: 0.5, ts[1]: 0.3}  # Partial weights

        demand_component.set_profile(
            'REGION1', 'ELEC',
            year=2025,
            timeslice_weights=weights
        )

        assert ('REGION1', 'ELEC', 2025) in demand_component._profile_assignments

    def test_set_hierarchical_weights(self, demand_component):
        """Set profile with hierarchical weights."""
        demand_component.add_annual_demand('REGION1', 'ELEC', {2025: 100})

        demand_component.set_profile(
            'REGION1', 'ELEC',
            season_weights={'Summer': 1.2, 'Winter': 0.8}
        )

        # Should apply to all years
        for year in demand_component.years:
            assert ('REGION1', 'ELEC', year) in demand_component._profile_assignments

    def test_set_profile_undefined_fuel_raises(self, demand_component):
        """Setting profile for undefined fuel raises ValueError."""
        with pytest.raises(ValueError, match="not defined"):
            demand_component.set_profile(
                'REGION1', 'UNDEFINED_FUEL',
                timeslice_weights={'ts': 1.0}
            )


# =============================================================================
# process Tests
# =============================================================================

class TestProcess:
    """Test process method for profile generation."""

    def test_process_generates_profiles(self, demand_component):
        """process generates profile DataFrame."""
        demand_component.add_annual_demand('REGION1', 'ELEC', {2025: 100})
        demand_component.process()

        assert not demand_component.profile_demand_df.empty

    def test_process_flat_profile_uses_yearsplit(self, demand_component):
        """Flat profile uses YearSplit values."""
        demand_component.add_annual_demand('REGION1', 'ELEC', {2025: 100})
        # No set_profile call = flat profile
        demand_component.process()

        df = demand_component.profile_demand_df
        year_2025 = df[df['YEAR'] == 2025]

        # Should sum to 1.0
        assert math.isclose(year_2025['VALUE'].sum(), 1.0, abs_tol=1e-6)

    def test_profiles_normalized_to_one(self, demand_component):
        """All profiles sum to 1.0 per (region, fuel, year)."""
        demand_component.add_annual_demand('REGION1', 'ELEC', {2025: 100})
        demand_component.add_annual_demand('REGION1', 'HEAT', {2025: 50})
        demand_component.process()

        df = demand_component.profile_demand_df
        grouped = df.groupby(['REGION', 'FUEL', 'YEAR'])['VALUE'].sum()

        for idx, total in grouped.items():
            assert math.isclose(total, 1.0, abs_tol=1e-6), \
                f"{idx}: profile sums to {total}, expected 1.0"


# =============================================================================
# Validation Tests
# =============================================================================

class TestDemandValidation:
    """Test validate method."""

    def test_validate_success(self, demand_component):
        """Valid demand passes validation."""
        demand_component.add_annual_demand('REGION1', 'ELEC', {2025: 100})
        demand_component.process()

        # Should not raise
        demand_component.validate()

    def test_validate_non_normalized_raises(self, demand_component):
        """Profiles not summing to 1.0 fail validation."""
        demand_component.add_annual_demand('REGION1', 'ELEC', {2025: 100})
        demand_component.process()

        # Manually corrupt profile
        demand_component.profile_demand_df['VALUE'] = 0.1  # All equal, won't sum to 1

        with pytest.raises(ValueError, match="sums to"):
            demand_component.validate()


# =============================================================================
# Load / Save Tests
# =============================================================================

class TestDemandLoadSave:
    """Test load and save operations."""

    def test_save_creates_files(self, demand_component):
        """save creates all owned CSV files."""
        demand_component.add_annual_demand('REGION1', 'ELEC', {2025: 100})
        demand_component.process()
        demand_component.save()

        for filename in DemandComponent.owned_files:
            path = os.path.join(demand_component.scenario_dir, filename)
            assert os.path.exists(path), f"Missing: {filename}"

    def test_round_trip(self, demand_component):
        """Save and load preserves data."""
        demand_component.add_annual_demand('REGION1', 'ELEC', {2025: 100.0, 2030: 150.0})
        demand_component.process()
        demand_component.save()

        # Load in new instance
        loaded = DemandComponent(demand_component.scenario_dir)
        loaded.load()

        # Verify annual demand preserved
        orig_df = demand_component.annual_demand_df.sort_values(
            ['REGION', 'FUEL', 'YEAR']
        ).reset_index(drop=True)
        load_df = loaded.annual_demand_df.sort_values(
            ['REGION', 'FUEL', 'YEAR']
        ).reset_index(drop=True)

        pd.testing.assert_frame_equal(orig_df, load_df)


# =============================================================================
# Integration Tests
# =============================================================================

class TestDemandIntegration:
    """Integration tests for demand component."""

    def test_full_workflow(self, complete_scenario_dir):
        """Complete workflow: add demands, set profiles, process, validate, save."""
        demand = DemandComponent(complete_scenario_dir)

        # Add multiple demands
        demand.add_annual_demand(
            'REGION1', 'ELECTRICITY',
            trajectory={2025: 100, 2030: 150},
            interpolation='linear'
        )
        demand.add_annual_demand(
            'REGION1', 'HEATING',
            trajectory={2025: 50, 2030: 60},
            interpolation='step'
        )

        # Set profiles
        demand.set_profile(
            'REGION1', 'ELECTRICITY',
            season_weights={'Summer': 0.8, 'Winter': 1.2}
        )
        demand.set_profile(
            'REGION1', 'HEATING',
            season_weights={'Summer': 0.5, 'Winter': 1.5}
        )

        # Process and validate
        demand.process()
        demand.validate()

        # Save
        demand.save()

        # Reload and verify
        loaded = DemandComponent(complete_scenario_dir)
        loaded.load()

        assert len(loaded.annual_demand_df) > 0
        assert len(loaded.profile_demand_df) > 0

    def test_multiple_regions(self, multi_region_time_dir):
        """Demand across multiple regions."""
        demand = DemandComponent(multi_region_time_dir)

        for region in ['North', 'South', 'East']:
            demand.add_annual_demand(region, 'ELEC', {2025: 100})

        demand.process()

        # Should have profiles for all regions
        regions_in_profile = demand.profile_demand_df['REGION'].unique()
        assert set(regions_in_profile) == {'North', 'South', 'East'}

    def test_repr(self, demand_component):
        """__repr__ shows component info."""
        repr_str = repr(demand_component)
        assert "DemandComponent" in repr_str
