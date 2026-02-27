# tests/test_scenario/test_components/test_time.py

"""
Tests for TimeComponent.

Tests cover:
- Initialization
- Properties (years, timeslices, seasons, daytypes, dailytimebrackets)
- add_time_structure with various configurations
- set_years method
- YearSplit normalization (sums to 1.0)
- Conversion tables (Conversionls, Conversionld, Conversionlh)
- load / save operations
- load_time_axis static method
- validate method
"""

import math
import os
import pytest
import pandas as pd

from pyoscomp.scenario.components.topology import TopologyComponent
from pyoscomp.scenario.components.time import TimeComponent


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def time_component(empty_scenario_dir):
    """Create TimeComponent with topology prerequisite."""
    # First create topology
    topology = TopologyComponent(empty_scenario_dir)
    topology.add_nodes(['REGION1'])
    topology.save()

    return TimeComponent(empty_scenario_dir)


# =============================================================================
# Initialization Tests
# =============================================================================

class TestTimeInit:
    """Test TimeComponent initialization."""

    def test_init_creates_empty_dfs(self, time_component):
        """Initialization creates empty DataFrames."""
        assert time_component.years_df.empty
        assert time_component.timeslices_df.empty
        assert time_component.seasons_df.empty

    def test_owned_files(self):
        """owned_files contains all time-related files."""
        expected = [
            'YEAR.csv', 'TIMESLICE.csv', 'SEASON.csv', 'DAYTYPE.csv',
            'DAILYTIMEBRACKET.csv', 'YearSplit.csv', 'DaySplit.csv',
            'Conversionls.csv', 'Conversionld.csv', 'Conversionlh.csv',
            'DaysInDayType.csv'
        ]
        assert set(TimeComponent.owned_files) == set(expected)


# =============================================================================
# Properties Tests
# =============================================================================

class TestTimeProperties:
    """Test time component properties."""

    def test_years_empty(self, time_component):
        """years property on empty component."""
        assert time_component.years == []

    def test_years_sorted(self, time_component):
        """years property returns sorted list."""
        time_component.add_time_structure(
            years=[2030, 2025, 2035],
            seasons={"S": 365},
            daytypes={"D": 1},
            brackets={"B": 24}
        )
        assert time_component.years == [2025, 2030, 2035]

    def test_timeslices(self, time_component):
        """timeslices property returns timeslice names."""
        time_component.add_time_structure(
            years=[2025],
            seasons={"Summer": 182, "Winter": 183},
            daytypes={"AllDays": 1},
            brackets={"Day": 12, "Night": 12}
        )
        # 2 seasons × 1 daytype × 2 brackets = 4 timeslices
        assert len(time_component.timeslices) == 4

    def test_seasons(self, time_component):
        """seasons property returns season names."""
        time_component.add_time_structure(
            years=[2025],
            seasons={"Spring": 91, "Summer": 92, "Fall": 91, "Winter": 91},
            daytypes={"D": 1},
            brackets={"B": 24}
        )
        assert set(time_component.seasons) == {"Spring", "Summer", "Fall", "Winter"}

    def test_daytypes(self, time_component):
        """daytypes property returns daytype names."""
        time_component.add_time_structure(
            years=[2025],
            seasons={"S": 365},
            daytypes={"Weekday": 5, "Weekend": 2},
            brackets={"B": 24}
        )
        assert set(time_component.daytypes) == {"Weekday", "Weekend"}

    def test_dailytimebrackets(self, time_component):
        """dailytimebrackets property returns bracket names."""
        time_component.add_time_structure(
            years=[2025],
            seasons={"S": 365},
            daytypes={"D": 1},
            brackets={"Morning": 6, "Afternoon": 6, "Evening": 6, "Night": 6}
        )
        assert set(time_component.dailytimebrackets) == {
            "Morning", "Afternoon", "Evening", "Night"
        }

    def test_num_timeslices(self, time_component):
        """num_timeslices returns correct count."""
        time_component.add_time_structure(
            years=[2025],
            seasons={"S1": 182, "S2": 183},
            daytypes={"D1": 5, "D2": 2},
            brackets={"B1": 12, "B2": 12}
        )
        # 2 × 2 × 2 = 8
        assert time_component.num_timeslices == 8


# =============================================================================
# add_time_structure Tests
# =============================================================================

class TestAddTimeStructure:
    """Test add_time_structure method."""

    def test_simple_structure(self, time_component):
        """Create simplest possible time structure."""
        time_component.add_time_structure(
            years=[2025],
            seasons={"Annual": 365},
            daytypes={"AllDays": 1},
            brackets={"AllHours": 24}
        )

        assert time_component.years == [2025]
        assert time_component.seasons == ["Annual"]
        assert time_component.num_timeslices == 1

    def test_years_as_tuple(self, time_component):
        """Years specified as (start, end, step) tuple."""
        time_component.add_time_structure(
            years=(2020, 2050, 10),
            seasons={"S": 365},
            daytypes={"D": 1},
            brackets={"B": 24}
        )

        assert time_component.years == [2020, 2030, 2040, 2050]

    def test_complex_structure(self, time_component):
        """Create complex time structure."""
        time_component.add_time_structure(
            years=[2025, 2030, 2035],
            seasons={"Peak": 120, "OffPeak": 245},
            daytypes={"Weekday": 5, "Weekend": 2},
            brackets={"Morning": 6, "Day": 10, "Evening": 4, "Night": 4}
        )

        assert len(time_component.years) == 3
        # 2 seasons × 2 daytypes × 4 brackets = 16 timeslices
        assert time_component.num_timeslices == 16

    def test_timeslice_naming(self, time_component):
        """Timeslice names follow Season_DayType_Bracket pattern."""
        time_component.add_time_structure(
            years=[2025],
            seasons={"Summer": 182, "Winter": 183},
            daytypes={"Weekday": 5},
            brackets={"Day": 12}
        )

        timeslices = time_component.timeslices
        assert "Summer_Weekday_Day" in timeslices
        assert "Winter_Weekday_Day" in timeslices

    def test_empty_seasons_raises(self, time_component):
        """Empty seasons dict should raise ValueError."""
        with pytest.raises(ValueError):
            time_component.add_time_structure(
                years=[2025],
                seasons={},
                daytypes={"D": 1},
                brackets={"B": 24}
            )

    def test_zero_weight_raises(self, time_component):
        """All-zero weights should raise ValueError."""
        with pytest.raises(ValueError):
            time_component.add_time_structure(
                years=[2025],
                seasons={"S1": 0, "S2": 0},
                daytypes={"D": 1},
                brackets={"B": 24}
            )


# =============================================================================
# YearSplit Normalization Tests
# =============================================================================

class TestYearSplitNormalization:
    """Test that YearSplit sums to 1.0 per year."""

    def test_yearsplit_sums_to_one(self, time_component):
        """YearSplit values sum to 1.0 for each year."""
        time_component.add_time_structure(
            years=[2025, 2030],
            seasons={"Summer": 182, "Winter": 183},
            daytypes={"Weekday": 5, "Weekend": 2},
            brackets={"Day": 16, "Night": 8}
        )

        for year in time_component.years:
            year_data = time_component.yearsplit_df[
                time_component.yearsplit_df['YEAR'] == year
            ]
            total = year_data['VALUE'].sum()
            assert math.isclose(total, 1.0, abs_tol=1e-9), f"Year {year}: {total}"

    def test_yearsplit_all_positive(self, time_component):
        """All YearSplit values should be positive."""
        time_component.add_time_structure(
            years=[2025],
            seasons={"S": 365},
            daytypes={"D": 1},
            brackets={"B": 24}
        )

        assert (time_component.yearsplit_df['VALUE'] > 0).all()

    def test_yearsplit_single_timeslice(self, time_component):
        """Single timeslice has YearSplit = 1.0."""
        time_component.add_time_structure(
            years=[2025],
            seasons={"Annual": 365},
            daytypes={"AllDays": 1},
            brackets={"AllHours": 24}
        )

        assert len(time_component.yearsplit_df) == 1
        assert time_component.yearsplit_df['VALUE'].iloc[0] == 1.0


# =============================================================================
# Conversion Tables Tests
# =============================================================================

class TestConversionTables:
    """Test conversion tables (Conversionls, Conversionld, Conversionlh)."""

    def test_conversionls_binary(self, time_component):
        """Conversionls maps timeslices to seasons (binary)."""
        time_component.add_time_structure(
            years=[2025],
            seasons={"Summer": 182, "Winter": 183},
            daytypes={"D": 1},
            brackets={"B": 24}
        )

        df = time_component.conversionls_df
        # Each timeslice maps to exactly one season
        for ts in time_component.timeslices:
            ts_rows = df[df['TIMESLICE'] == ts]
            assert ts_rows['VALUE'].sum() == 1.0

    def test_conversionld_binary(self, time_component):
        """Conversionld maps timeslices to daytypes (binary)."""
        time_component.add_time_structure(
            years=[2025],
            seasons={"S": 365},
            daytypes={"Weekday": 5, "Weekend": 2},
            brackets={"B": 24}
        )

        df = time_component.conversionld_df
        for ts in time_component.timeslices:
            ts_rows = df[df['TIMESLICE'] == ts]
            assert ts_rows['VALUE'].sum() == 1.0

    def test_conversionlh_binary(self, time_component):
        """Conversionlh maps timeslices to brackets (binary)."""
        time_component.add_time_structure(
            years=[2025],
            seasons={"S": 365},
            daytypes={"D": 1},
            brackets={"Day": 16, "Night": 8}
        )

        df = time_component.conversionlh_df
        for ts in time_component.timeslices:
            ts_rows = df[df['TIMESLICE'] == ts]
            assert ts_rows['VALUE'].sum() == 1.0


# =============================================================================
# DaysInDayType Tests
# =============================================================================

class TestDaysInDayType:
    """Test DaysInDayType parameter."""

    def test_daysindaytype_created(self, time_component):
        """DaysInDayType is created for each season-daytype combination."""
        time_component.add_time_structure(
            years=[2025, 2030],
            seasons={"Summer": 182, "Winter": 183},
            daytypes={"Weekday": 5, "Weekend": 2},
            brackets={"B": 24}
        )

        df = time_component.daysindaytype_df
        # Should have entries for each (season, daytype, year)
        expected_rows = 2 * 2 * 2  # 2 seasons × 2 daytypes × 2 years
        assert len(df) == expected_rows

    def test_daysindaytype_sums_to_season_days(self, time_component):
        """DaysInDayType for a season sums to season days."""
        time_component.add_time_structure(
            years=[2025],
            seasons={"Summer": 180, "Winter": 185},
            daytypes={"Weekday": 5, "Weekend": 2},
            brackets={"B": 24}
        )

        df = time_component.daysindaytype_df
        for season in ["Summer", "Winter"]:
            season_days = df[df['SEASON'] == season]['VALUE'].sum()
            expected = 180 if season == "Summer" else 185
            assert math.isclose(season_days, expected, abs_tol=1)


# =============================================================================
# Load / Save Tests
# =============================================================================

class TestTimeLoadSave:
    """Test load and save operations."""

    def test_save_creates_all_files(self, time_component):
        """save creates all owned CSV files."""
        time_component.add_time_structure(
            years=[2025],
            seasons={"S": 365},
            daytypes={"D": 1},
            brackets={"B": 24}
        )
        time_component.save()

        for filename in TimeComponent.owned_files:
            path = os.path.join(time_component.scenario_dir, filename)
            assert os.path.exists(path), f"Missing: {filename}"

    def test_round_trip(self, time_component):
        """Save and load preserves data."""
        time_component.add_time_structure(
            years=[2025, 2030, 2035],
            seasons={"Peak": 120, "OffPeak": 245},
            daytypes={"Weekday": 5, "Weekend": 2},
            brackets={"Day": 12, "Night": 12}
        )
        time_component.save()

        # Load in new instance
        loaded = TimeComponent(time_component.scenario_dir)
        loaded.load()

        assert loaded.years == time_component.years
        assert set(loaded.timeslices) == set(time_component.timeslices)
        assert set(loaded.seasons) == set(time_component.seasons)

    def test_load_yearsplit_preserved(self, time_scenario_dir):
        """Loading preserves YearSplit values."""
        loaded = TimeComponent(time_scenario_dir)
        loaded.load()

        # Should sum to 1.0
        for year in loaded.years:
            year_data = loaded.yearsplit_df[loaded.yearsplit_df['YEAR'] == year]
            assert math.isclose(year_data['VALUE'].sum(), 1.0, abs_tol=1e-9)


# =============================================================================
# load_time_axis Static Method Tests
# =============================================================================

class TestLoadTimeAxis:
    """Test load_time_axis static method."""

    def test_load_time_axis_returns_dict(self, time_scenario_dir):
        """load_time_axis returns dict with expected keys."""
        from pyoscomp.scenario.components.base import ScenarioComponent

        class DummyComponent(ScenarioComponent):
            def load(self): pass
            def save(self): pass

        component = DummyComponent(time_scenario_dir)
        result = TimeComponent.load_time_axis(component)

        assert 'yearsplit' in result
        assert 'slice_map' in result
        assert isinstance(result['yearsplit'], pd.DataFrame)
        assert isinstance(result['slice_map'], dict)

    def test_load_time_axis_slice_map_structure(self, osemosys_8ts_scenario):
        """slice_map maps timeslice to Season/DayType/DailyTimeBracket."""
        from pyoscomp.scenario.components.base import ScenarioComponent

        class DummyComponent(ScenarioComponent):
            def load(self): pass
            def save(self): pass

        component = DummyComponent(osemosys_8ts_scenario)
        result = TimeComponent.load_time_axis(component)

        slice_map = result['slice_map']
        # Check structure for one timeslice
        ts = "Summer_Weekday_Day"
        assert ts in slice_map
        assert slice_map[ts]['Season'] == 'Summer'
        assert slice_map[ts]['DayType'] == 'Weekday'
        assert slice_map[ts]['DailyTimeBracket'] == 'Day'


# =============================================================================
# set_years Method Tests
# =============================================================================

class TestSetYears:
    """Test set_years method."""

    def test_set_years_list(self, time_component):
        """set_years with list."""
        result = time_component.set_years([2020, 2025, 2030])

        assert result == [2020, 2025, 2030]
        assert time_component.years == [2020, 2025, 2030]

    def test_set_years_tuple(self, time_component):
        """set_years with tuple (start, end, step)."""
        result = time_component.set_years((2020, 2040, 5))

        assert result == [2020, 2025, 2030, 2035, 2040]


# =============================================================================
# Integration Tests
# =============================================================================

class TestTimeIntegration:
    """Integration tests for time component."""

    def test_full_workflow(self, empty_scenario_dir):
        """Complete workflow: topology → time → save → load → validate."""
        # Setup topology
        topology = TopologyComponent(empty_scenario_dir)
        topology.add_nodes(['R1'])
        topology.save()

        # Create time structure
        time = TimeComponent(empty_scenario_dir)
        time.add_time_structure(
            years=[2025, 2030, 2035],
            seasons={"Winter": 90, "Summer": 90, "Shoulder": 185},
            daytypes={"Weekday": 5, "Weekend": 2},
            brackets={"Peak": 8, "OffPeak": 16}
        )
        time.save()

        # Load in new instance
        loaded = TimeComponent(empty_scenario_dir)
        loaded.load()

        # Verify
        assert len(loaded.years) == 3
        assert len(loaded.seasons) == 3
        assert len(loaded.daytypes) == 2
        assert len(loaded.dailytimebrackets) == 2
        # 3 seasons × 2 daytypes × 2 brackets = 12 timeslices
        assert loaded.num_timeslices == 12

        # YearSplit validation
        for year in loaded.years:
            year_data = loaded.yearsplit_df[loaded.yearsplit_df['YEAR'] == year]
            assert math.isclose(year_data['VALUE'].sum(), 1.0, abs_tol=1e-9)

    def test_repr(self, time_component):
        """__repr__ shows component info."""
        repr_str = repr(time_component)
        assert "TimeComponent" in repr_str
