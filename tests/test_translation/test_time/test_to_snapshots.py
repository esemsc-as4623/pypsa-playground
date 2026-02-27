# tests/test_translation/test_time/test_to_snapshots.py

"""
Tests for to_snapshots(): OSeMOSYS timeslice → PyPSA snapshot conversion.

The function now accepts ScenarioData as its sole input type. Tests build
minimal ScenarioData objects containing only the time-related fields that
to_snapshots() actually reads (sets.years, sets.timeslices, time.year_split).
"""

import pytest
import pandas as pd

from pyoscomp.translation.time.translate import to_snapshots, SnapshotResult
from pyoscomp.constants import hours_in_year
from pyoscomp.interfaces.containers import ScenarioData
from pyoscomp.interfaces.sets import OSeMOSYSSets
from pyoscomp.interfaces.parameters import (
    TimeParameters,
    DemandParameters,
    SupplyParameters,
    PerformanceParameters,
    EconomicsParameters,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scenario_data(
    years,
    timeslice_names,
    yearsplit_df,
    seasons=None,
    daytypes=None,
    dailytimebrackets=None,
):
    """
    Build a minimal ScenarioData for time-translation tests.

    Only the fields read by ``to_snapshots()`` are populated; everything
    else gets safe empty defaults with validation skipped.
    """
    sets = OSeMOSYSSets(
        regions=frozenset(['REGION1']),
        years=frozenset(years),
        technologies=frozenset(['DUMMY']),
        fuels=frozenset(['DUMMY']),
        emissions=frozenset(),
        modes=frozenset(['MODE1']),
        timeslices=frozenset(timeslice_names),
        seasons=frozenset(seasons or ['X']),
        daytypes=frozenset(daytypes or ['D1']),
        dailytimebrackets=frozenset(dailytimebrackets or ['B1']),
        storages=frozenset(),
    )
    return ScenarioData(
        sets=sets,
        time=TimeParameters(year_split=yearsplit_df),
        demand=DemandParameters(),
        supply=SupplyParameters(),
        performance=PerformanceParameters(),
        economics=EconomicsParameters(),
        _skip_validation=True,
    )


def _make_time_scenario_data(years, seasons, daytypes, brackets):
    """
    Build ScenarioData from the same arguments as
    ``TimeComponent.add_time_structure()``.

    Generates timeslice names (Season_DayType_Bracket) and computes
    YearSplit fractions so they sum to 1.0 per year.
    """
    total_season_days = sum(seasons.values())
    total_daytype_weight = sum(daytypes.values())
    total_bracket_hours = sum(brackets.values())

    timeslice_names = []
    yearsplit_rows = []
    for s_name, s_days in seasons.items():
        for d_name, d_weight in daytypes.items():
            for b_name, b_hours in brackets.items():
                ts_name = f"{s_name}_{d_name}_{b_name}"
                timeslice_names.append(ts_name)
                fraction = (
                    (s_days / total_season_days)
                    * (d_weight / total_daytype_weight)
                    * (b_hours / total_bracket_hours)
                )
                for year in years:
                    yearsplit_rows.append({
                        'TIMESLICE': ts_name,
                        'YEAR': year,
                        'VALUE': fraction,
                    })

    yearsplit_df = pd.DataFrame(yearsplit_rows)
    return _make_scenario_data(
        years=years,
        timeslice_names=timeslice_names,
        yearsplit_df=yearsplit_df,
        seasons=list(seasons.keys()),
        daytypes=list(daytypes.keys()),
        dailytimebrackets=list(brackets.keys()),
    )


# ---------------------------------------------------------------------------
# Tests – SnapshotResult validation (unit tests)
# ---------------------------------------------------------------------------

class TestSnapshotResultValidation:
    """Tests for SnapshotResult validation methods."""

    def test_validate_coverage_single_year_valid(self):
        """Test validation passes for correctly weighted single year."""
        years = [2025]
        timeslices = ['Winter_Day', 'Winter_Night', 'Summer_Day', 'Summer_Night']
        snapshots = pd.MultiIndex.from_product([years, timeslices], names=['period', 'timestep'])

        total_hours = hours_in_year(2025)
        weightings = pd.Series(
            [total_hours / 4] * 4,
            index=snapshots,
        )

        result = SnapshotResult(
            years=years,
            snapshots=snapshots,
            weightings=weightings,
            timeslice_names=timeslices,
        )
        assert result.validate_coverage()

    def test_validate_coverage_single_year_invalid(self):
        """Test validation fails for incorrectly weighted single year."""
        years = [2025]
        timeslices = ['Winter_Day', 'Winter_Night']
        snapshots = pd.MultiIndex.from_product([years, timeslices], names=['period', 'timestep'])

        total_hours = hours_in_year(2025)
        weightings = pd.Series(
            [total_hours / 4] * 2,  # Only half the hours
            index=snapshots,
        )

        result = SnapshotResult(
            years=years,
            snapshots=snapshots,
            weightings=weightings,
            timeslice_names=timeslices,
        )
        assert not result.validate_coverage()

    def test_validate_coverage_multi_year_valid(self):
        """Test validation passes for multi-year model."""
        years = [2024, 2025]  # Include leap year
        timeslices = ['Winter', 'Summer']
        snapshots = pd.MultiIndex.from_product(
            [years, timeslices],
            names=['period', 'timestep'],
        )

        weightings_dict = {}
        for year in years:
            year_hours = hours_in_year(year)
            for ts in timeslices:
                weightings_dict[(year, ts)] = year_hours / 2
        weightings = pd.Series(weightings_dict)

        result = SnapshotResult(
            years=years,
            snapshots=snapshots,
            weightings=weightings,
            timeslice_names=timeslices,
        )
        assert result.validate_coverage()

    def test_validate_coverage_leap_year(self):
        """Test validation handles leap year correctly (8784 hours)."""
        years = [2024]
        timeslices = ['TS1', 'TS2']
        snapshots = pd.MultiIndex.from_product([years, timeslices], names=['period', 'timestep'])

        total_hours = hours_in_year(2024)
        assert total_hours == 8784

        weightings = pd.Series(
            [total_hours / 2] * 2,
            index=snapshots,
        )

        result = SnapshotResult(
            years=years,
            snapshots=snapshots,
            weightings=weightings,
            timeslice_names=timeslices,
        )
        assert result.validate_coverage()

    def test_validate_coverage_multiple_years(self):
        """Test that single-period index with multiple years raises error."""
        years = [2025, 2026]
        timeslices = ['TS1']
        snapshots = pd.MultiIndex.from_product([years, timeslices], names=['period', 'timestep'])
        weightings = pd.Series([8760.0] * 2, index=snapshots)

        result = SnapshotResult(
            years=years,
            snapshots=snapshots,
            weightings=weightings,
            timeslice_names=timeslices,
        )
        assert result.validate_coverage()


# ---------------------------------------------------------------------------
# Tests – to_snapshots with ScenarioData built from time-structure dicts
# ---------------------------------------------------------------------------

class TestToSnapshotsFromScenarioData:
    """Tests for to_snapshots using programmatically built ScenarioData."""

    def test_simple_time_structure_multi_period(self):
        """Test conversion from simple time structure with multi-period index."""
        years = [2025, 2030]
        data = _make_time_scenario_data(
            years,
            seasons={"Winter": 182.5, "Summer": 182.5},
            daytypes={"Weekday": 5, "Weekend": 2},
            brackets={"Day": 12, "Night": 12},
        )

        result = to_snapshots(data)

        assert isinstance(result, SnapshotResult)
        assert sorted(result.years) == sorted(years)
        assert isinstance(result.snapshots, pd.MultiIndex)
        assert result.snapshots.names == ['period', 'timestep']

        expected_timeslices = 2 * 2 * 2
        assert len(set(result.timeslice_names)) == expected_timeslices
        assert len(result.snapshots) == len(years) * expected_timeslices
        assert result.validate_coverage()

    def test_simple_time_structure_single_period(self):
        """Test conversion from simple time structure with single-period index."""
        years = [2025]
        data = _make_time_scenario_data(
            years,
            seasons={"Winter": 182.5, "Summer": 182.5},
            daytypes={"All": 7},
            brackets={"Day": 12, "Night": 12},
        )

        result = to_snapshots(data)

        assert isinstance(result, SnapshotResult)
        assert sorted(result.years) == years
        assert isinstance(result.snapshots, pd.MultiIndex)
        assert result.snapshots.names == ['period', 'timestep']

        expected_timeslices = 2 * 1 * 2
        assert len(result.snapshots) == expected_timeslices
        assert result.validate_coverage()

    def test_hourly_resolution(self):
        """Test conversion with hourly resolution (24 brackets)."""
        brackets = {f"H{i:02d}": 1 for i in range(24)}
        data = _make_time_scenario_data(
            [2025],
            seasons={"Winter": 90, "Spring": 92, "Summer": 92, "Fall": 91},
            daytypes={"Weekday": 5, "Weekend": 2},
            brackets=brackets,
        )

        result = to_snapshots(data)

        expected = 4 * 2 * 24
        assert len(result.snapshots) == expected
        assert result.validate_coverage()

    def test_weightings_sum_correctly(self):
        """Test that weightings sum to correct total hours."""
        years = [2024, 2025]  # Mix leap and non-leap
        data = _make_time_scenario_data(
            years,
            seasons={"S1": 182.5, "S2": 182.5},
            daytypes={"D1": 7},
            brackets={"B1": 12, "B2": 12},
        )

        result = to_snapshots(data)

        for year in years:
            year_mask = result.snapshots.get_level_values('period') == year
            year_total = result.weightings[year_mask].sum()
            expected_hours = hours_in_year(year)
            assert abs(year_total - expected_hours) < 1e-6


# ---------------------------------------------------------------------------
# Tests – to_snapshots with ScenarioData loaded from CSV directory
# ---------------------------------------------------------------------------

class TestToSnapshotsFromCSV:
    """Tests for to_snapshots using ScenarioData.from_directory()."""

    @staticmethod
    def _make_scenario_data_from_yearsplit(years, timeslice_names, yearsplit_data):
        """Build ScenarioData directly from raw YearSplit rows."""
        yearsplit_df = pd.DataFrame(yearsplit_data)
        return _make_scenario_data(
            years=years,
            timeslice_names=timeslice_names,
            yearsplit_df=yearsplit_df,
        )

    def test_single_year_equal_fractions(self):
        """Test equal-fraction timeslices for single year."""
        years = [2025]
        timeslices = ['TS1', 'TS2', 'TS3', 'TS4']
        yearsplit = [
            {'TIMESLICE': ts, 'YEAR': 2025, 'VALUE': 0.25}
            for ts in timeslices
        ]

        data = self._make_scenario_data_from_yearsplit(
            years, timeslices, yearsplit,
        )
        result = to_snapshots(data)

        assert sorted(result.years) == years
        assert len(result.snapshots) == 4
        assert result.validate_coverage()

    def test_multi_year(self):
        """Test with multiple years."""
        years = [2025, 2030, 2035]
        timeslices = ['Winter', 'Summer']
        yearsplit = [
            {'TIMESLICE': ts, 'YEAR': y, 'VALUE': 0.5}
            for y in years for ts in timeslices
        ]

        data = self._make_scenario_data_from_yearsplit(
            years, timeslices, yearsplit,
        )
        result = to_snapshots(data)

        assert sorted(result.years) == years
        assert len(result.snapshots) == len(years) * len(timeslices)
        assert isinstance(result.snapshots, pd.MultiIndex)
        assert result.validate_coverage()

    def test_unequal_fractions(self):
        """Test with unequal timeslice fractions."""
        years = [2025]
        timeslices = ['Peak', 'OffPeak']
        yearsplit = [
            {'TIMESLICE': 'Peak', 'YEAR': 2025, 'VALUE': 0.25},
            {'TIMESLICE': 'OffPeak', 'YEAR': 2025, 'VALUE': 0.75},
        ]

        data = self._make_scenario_data_from_yearsplit(
            years, timeslices, yearsplit,
        )
        result = to_snapshots(data)

        peak_hours = result.weightings[result.snapshots == (2025, 'Peak')].iloc[0]
        offpeak_hours = result.weightings[result.snapshots == (2025, 'OffPeak')].iloc[0]

        total_hours = hours_in_year(2025)
        assert abs(peak_hours - 0.25 * total_hours) < 1e-6
        assert abs(offpeak_hours - 0.75 * total_hours) < 1e-6
        assert result.validate_coverage()


# ---------------------------------------------------------------------------
# Tests – edge cases
# ---------------------------------------------------------------------------

class TestToSnapshotsEdgeCases:
    """Edge case tests for to_snapshots."""

    def test_invalid_source_type_raises_error(self):
        """Test that non-ScenarioData input raises AttributeError."""
        with pytest.raises(AttributeError):
            to_snapshots(123)

        with pytest.raises(AttributeError):
            to_snapshots(['not', 'valid'])

    def test_single_timeslice(self):
        """Test with single timeslice (entire year)."""
        data = _make_time_scenario_data(
            [2025],
            seasons={"All": 365},
            daytypes={"All": 7},
            brackets={"All": 24},
        )
        result = to_snapshots(data)

        assert len(result.snapshots) == 1
        assert abs(result.weightings.iloc[0] - hours_in_year(2025)) < 1e-6
        assert result.validate_coverage()

    def test_many_timeslices(self):
        """Test with many timeslices (high resolution)."""
        seasons = {f"M{i:02d}": 365 / 12 for i in range(1, 13)}
        daytypes = {f"D{i}": 1 for i in range(1, 8)}
        brackets = {f"H{i:02d}": 1 for i in range(24)}

        data = _make_time_scenario_data(
            [2025], seasons, daytypes, brackets,
        )
        result = to_snapshots(data)

        expected_count = 12 * 7 * 24
        assert len(result.snapshots) == expected_count
        assert result.validate_coverage()


# ---------------------------------------------------------------------------
# Tests – apply_to_network (tests SnapshotResult directly)
# ---------------------------------------------------------------------------

class TestSnapshotResultApplyToNetwork:
    """Tests for applying SnapshotResult to PyPSA Network."""

    def test_apply_to_network_structure(self):
        """Test that apply_to_network sets correct attributes (mock network)."""

        class MockNetwork:
            def __init__(self):
                self.snapshots = None
                self.snapshot_weightings = {
                    'objective': None,
                    'generators': None,
                    'stores': None,
                }

            def set_snapshots(self, snapshots):
                self.snapshots = snapshots

        network = MockNetwork()

        years = [2025]
        timeslices = ['TS1', 'TS2']
        snapshots = pd.Index(timeslices, name='timestep')
        weightings = pd.Series([4380.0, 4380.0], index=snapshots)

        result = SnapshotResult(
            years=years,
            snapshots=snapshots,
            weightings=weightings,
            timeslice_names=timeslices,
        )
        result.apply_to_network(network)

        assert network.snapshots is not None
        pd.testing.assert_index_equal(network.snapshots, snapshots)
        weightings.name = "objective"
        pd.testing.assert_series_equal(
            network.snapshot_weightings['objective'], weightings,
        )
        weightings.name = "generators"
        pd.testing.assert_series_equal(
            network.snapshot_weightings['generators'], weightings,
        )
        weightings.name = "stores"
        pd.testing.assert_series_equal(
            network.snapshot_weightings['stores'], weightings,
        )

# ---------------------------------------------------------------------------
# Tests – round-trip consistency
# ---------------------------------------------------------------------------

class TestRoundTripConsistency:
    """Tests for consistency between to_snapshots and to_timeslices."""

    def test_roundtrip_simple_structure(self):
        """Test that to_snapshots preserves time structure information."""
        years = [2025]
        data = _make_time_scenario_data(
            years,
            seasons={"Winter": 182.5, "Summer": 182.5},
            daytypes={"Weekday": 5, "Weekend": 2},
            brackets={"Day": 12, "Night": 12},
        )

        result = to_snapshots(data)

        assert result.validate_coverage()

        expected_timeslices = 2 * 2 * 2
        assert len(set(result.timeslice_names)) == expected_timeslices
        assert len(result.snapshots) == expected_timeslices
