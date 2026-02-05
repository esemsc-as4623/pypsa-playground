# tests/test_translation/test_time/test_to_snapshots.py

import pytest
import pandas as pd
import tempfile
import shutil

from pyoscomp.translation.time.translate import to_snapshots, SnapshotResult
from pyoscomp.translation.time.constants import hours_in_year
from pyoscomp.scenario.components.time import TimeComponent


class TestSnapshotResultValidation:
    """Tests for SnapshotResult validation methods."""
    
    def test_validate_coverage_single_year_valid(self):
        """Test validation passes for correctly weighted single year."""
        years = [2025]
        timeslices = ['Winter_Day', 'Winter_Night', 'Summer_Day', 'Summer_Night']
        snapshots = pd.Index(timeslices, name='timestep')
        
        # Create weightings that sum to correct hours
        total_hours = hours_in_year(2025)
        weightings = pd.Series(
            [total_hours / 4] * 4,
            index=snapshots
        )
        
        result = SnapshotResult(
            years=years,
            snapshots=snapshots,
            weightings=weightings,
            timeslice_names=timeslices
        )
        
        assert result.validate_coverage()
    
    def test_validate_coverage_single_year_invalid(self):
        """Test validation fails for incorrectly weighted single year."""
        years = [2025]
        timeslices = ['Winter_Day', 'Winter_Night']
        snapshots = pd.Index(timeslices, name='timestep')
        
        # Create weightings that don't sum correctly (missing half the year)
        total_hours = hours_in_year(2025)
        weightings = pd.Series(
            [total_hours / 4] * 2,  # Only half the hours
            index=snapshots
        )
        
        result = SnapshotResult(
            years=years,
            snapshots=snapshots,
            weightings=weightings,
            timeslice_names=timeslices
        )
        
        assert not result.validate_coverage()
    
    def test_validate_coverage_multi_year_valid(self):
        """Test validation passes for multi-year model."""
        years = [2024, 2025]  # Include leap year
        timeslices = ['Winter', 'Summer']
        snapshots = pd.MultiIndex.from_product(
            [years, timeslices],
            names=['period', 'timestep']
        )
        
        # Create weightings with correct hours per year
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
            timeslice_names=timeslices
        )
        
        assert result.validate_coverage()
    
    def test_validate_coverage_leap_year(self):
        """Test validation handles leap year correctly (8784 hours)."""
        years = [2024]  # Leap year
        timeslices = ['TS1', 'TS2']
        snapshots = pd.Index(timeslices, name='timestep')
        
        total_hours = hours_in_year(2024)  # Should be 8784
        assert total_hours == 8784
        
        weightings = pd.Series(
            [total_hours / 2] * 2,
            index=snapshots
        )
        
        result = SnapshotResult(
            years=years,
            snapshots=snapshots,
            weightings=weightings,
            timeslice_names=timeslices
        )
        
        assert result.validate_coverage()
    
    def test_validate_coverage_raises_on_single_index_multiple_years(self):
        """Test that single-period index with multiple years raises error."""
        years = [2025, 2026]  # Multiple years
        timeslices = ['TS1']
        snapshots = pd.Index(timeslices, name='timestep')  # But single-level index
        
        weightings = pd.Series([8760.0], index=snapshots)
        
        result = SnapshotResult(
            years=years,
            snapshots=snapshots,
            weightings=weightings,
            timeslice_names=timeslices
        )
        
        with pytest.raises(ValueError, match="Single-period snapshots must have exactly one year"):
            result.validate_coverage()


class TestToSnapshotsFromTimeComponent:
    """Tests for to_snapshots using TimeComponent programmatically."""
    
    @pytest.fixture
    def temp_scenario_dir(self):
        """Create temporary scenario directory."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_simple_time_structure_multi_period(self, temp_scenario_dir):
        """Test conversion from simple time structure with multi-period index."""
        time = TimeComponent(temp_scenario_dir)
        years = [2025, 2030]
        seasons = {"Winter": 182.5, "Summer": 182.5}
        daytypes = {"Weekday": 5, "Weekend": 2}
        brackets = {"Day": 12, "Night": 12}
        
        time.add_time_structure(years, seasons, daytypes, brackets)
        
        result = to_snapshots(time, multi_investment_periods=True)
        
        # Verify result structure
        assert isinstance(result, SnapshotResult)
        assert result.years == years
        assert isinstance(result.snapshots, pd.MultiIndex)
        assert result.snapshots.names == ['period', 'timestep']
        
        # Verify number of snapshots
        expected_timeslices = 2 * 2 * 2  # 2 seasons × 2 daytypes × 2 brackets
        assert len(result.timeslice_names) == expected_timeslices
        assert len(result.snapshots) == len(years) * expected_timeslices
        
        # Verify coverage
        assert result.validate_coverage()
    
    def test_simple_time_structure_single_period(self, temp_scenario_dir):
        """Test conversion from simple time structure with single-period index."""
        time = TimeComponent(temp_scenario_dir)
        years = [2025]
        seasons = {"Winter": 182.5, "Summer": 182.5}
        daytypes = {"All": 7}
        brackets = {"Day": 12, "Night": 12}
        
        time.add_time_structure(years, seasons, daytypes, brackets)
        
        result = to_snapshots(time, multi_investment_periods=False)
        
        # Verify result structure
        assert isinstance(result, SnapshotResult)
        assert result.years == years
        assert isinstance(result.snapshots, pd.Index)
        assert result.snapshots.name == 'timestep'
        
        # Verify number of snapshots
        expected_timeslices = 2 * 1 * 2  # 2 seasons × 1 daytype × 2 brackets
        assert len(result.snapshots) == expected_timeslices
        
        # Verify coverage
        assert result.validate_coverage()
    
    def test_multi_year_requires_multi_period_flag(self, temp_scenario_dir):
        """Test that multi-year with single-period flag raises error."""
        time = TimeComponent(temp_scenario_dir)
        years = [2025, 2030]
        seasons = {"S1": 182.5, "S2": 182.5}
        daytypes = {"D1": 7}
        brackets = {"B1": 24}
        
        time.add_time_structure(years, seasons, daytypes, brackets)
        
        with pytest.raises(ValueError, match="multi_investment_periods=False requires single year"):
            to_snapshots(time, multi_investment_periods=False)
    
    def test_hourly_resolution(self, temp_scenario_dir):
        """Test conversion with hourly resolution (24 brackets)."""
        time = TimeComponent(temp_scenario_dir)
        years = [2025]
        seasons = {"Winter": 90, "Spring": 92, "Summer": 92, "Fall": 91}
        daytypes = {"Weekday": 5, "Weekend": 2}
        
        # Create 24 hourly brackets
        brackets = {f"H{i:02d}": 1 for i in range(24)}
        
        time.add_time_structure(years, seasons, daytypes, brackets)
        
        result = to_snapshots(time, multi_investment_periods=False)
        
        # Verify timeslice count
        expected = 4 * 2 * 24  # 4 seasons × 2 daytypes × 24 brackets
        assert len(result.snapshots) == expected
        assert result.validate_coverage()
    
    def test_weightings_sum_correctly(self, temp_scenario_dir):
        """Test that weightings sum to correct total hours."""
        time = TimeComponent(temp_scenario_dir)
        years = [2024, 2025]  # Mix leap and non-leap
        seasons = {"S1": 182.5, "S2": 182.5}
        daytypes = {"D1": 7}
        brackets = {"B1": 12, "B2": 12}
        
        time.add_time_structure(years, seasons, daytypes, brackets)
        
        result = to_snapshots(time, multi_investment_periods=True)
        
        # Check total hours per year
        for year in years:
            year_mask = result.snapshots.get_level_values('period') == year
            year_total = result.weightings[year_mask].sum()
            expected_hours = hours_in_year(year)
            assert abs(year_total - expected_hours) < 1e-6


class TestToSnapshotsFromCSV:
    """Tests for to_snapshots using CSV file paths."""
    
    @pytest.fixture
    def temp_scenario_dir(self):
        """Create temporary scenario directory with CSV files."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def _create_csv_files(self, scenario_dir, years, timeslices, yearsplit_data):
        """Helper to create minimal OSeMOSYS CSV files."""
        # YEAR.csv - SET (single column named VALUE)
        year_df = pd.DataFrame({'VALUE': years})
        year_df.to_csv(f"{scenario_dir}/YEAR.csv", index=False)
        
        # TIMESLICE.csv - SET (single column named VALUE)
        ts_df = pd.DataFrame({'VALUE': timeslices})
        ts_df.to_csv(f"{scenario_dir}/TIMESLICE.csv", index=False)
        
        # YearSplit.csv - PARAMETER (has TIMESLICE, YEAR, VALUE columns)
        yearsplit_df = pd.DataFrame(yearsplit_data)
        yearsplit_df.to_csv(f"{scenario_dir}/YearSplit.csv", index=False)
        
        # Other required files (minimal) - SETS (single column named VALUE)
        pd.DataFrame({'VALUE': ['X']}).to_csv(f"{scenario_dir}/SEASON.csv", index=False)
        pd.DataFrame({'VALUE': ['D1']}).to_csv(f"{scenario_dir}/DAYTYPE.csv", index=False)
        pd.DataFrame({'VALUE': ['B1']}).to_csv(f"{scenario_dir}/DAILYTIMEBRACKET.csv", index=False)
        
        # Conversion tables (minimal - all 1.0)
        for name in ['Conversionls', 'Conversionld', 'Conversionlh']:
            conv_df = pd.DataFrame({
                'TIMESLICE': timeslices,
                'SEASON' if 'ls' in name else 'DAYTYPE' if 'ld' in name else 'DAILYTIMEBRACKET': 
                    ['X'] * len(timeslices) if 'ls' in name else ['D1'] * len(timeslices) if 'ld' in name else ['B1'] * len(timeslices),
                'VALUE': [1.0] * len(timeslices)
            })
            conv_df.to_csv(f"{scenario_dir}/{name}.csv", index=False)
        
        # DaySplit.csv (minimal)
        daysplit_rows = []
        for year in years:
            daysplit_rows.append({
                'DAILYTIMEBRACKET': 'B1',
                'YEAR': year,
                'VALUE': 1.0  # B1 bracket covers full day
            })
        pd.DataFrame(daysplit_rows).to_csv(f"{scenario_dir}/DaySplit.csv", index=False)
        
        # DaysInDayType.csv (minimal)
        daysindaytype = pd.DataFrame({
            'SEASON': ['X'] * len(years),
            'DAYTYPE': ['D1'] * len(years),
            'YEAR': years,
            'VALUE': [365.25] * len(years)
        })
        daysindaytype.to_csv(f"{scenario_dir}/DaysInDayType.csv", index=False)
    
    def test_load_from_csv_single_year(self, temp_scenario_dir):
        """Test loading from CSV files for single year."""
        years = [2025]
        timeslices = ['TS1', 'TS2', 'TS3', 'TS4']
        
        # Create YearSplit data with equal fractions
        yearsplit_data = []
        for ts in timeslices:
            yearsplit_data.append({
                'TIMESLICE': ts,
                'YEAR': 2025,
                'VALUE': 0.25
            })
        
        self._create_csv_files(temp_scenario_dir, years, timeslices, yearsplit_data)
        
        result = to_snapshots(temp_scenario_dir, multi_investment_periods=False)
        
        assert result.years == years
        assert len(result.snapshots) == 4
        assert result.validate_coverage()
    
    def test_load_from_csv_multi_year(self, temp_scenario_dir):
        """Test loading from CSV files for multiple years."""
        years = [2025, 2030, 2035]
        timeslices = ['Winter', 'Summer']
        
        # Create YearSplit data
        yearsplit_data = []
        for year in years:
            for ts in timeslices:
                yearsplit_data.append({
                    'TIMESLICE': ts,
                    'YEAR': year,
                    'VALUE': 0.5
                })
        
        self._create_csv_files(temp_scenario_dir, years, timeslices, yearsplit_data)
        
        result = to_snapshots(temp_scenario_dir, multi_investment_periods=True)
        
        assert result.years == years
        assert len(result.snapshots) == len(years) * len(timeslices)
        assert isinstance(result.snapshots, pd.MultiIndex)
        assert result.validate_coverage()
    
    def test_load_from_csv_unequal_fractions(self, temp_scenario_dir):
        """Test loading with unequal timeslice fractions."""
        years = [2025]
        timeslices = ['Peak', 'OffPeak']
        
        # Peak is 25% of year, OffPeak is 75%
        yearsplit_data = [
            {'TIMESLICE': 'Peak', 'YEAR': 2025, 'VALUE': 0.25},
            {'TIMESLICE': 'OffPeak', 'YEAR': 2025, 'VALUE': 0.75}
        ]
        
        self._create_csv_files(temp_scenario_dir, years, timeslices, yearsplit_data)
        
        result = to_snapshots(temp_scenario_dir, multi_investment_periods=False)
        
        # Verify weightings
        peak_hours = result.weightings[result.snapshots == 'Peak'].iloc[0]
        offpeak_hours = result.weightings[result.snapshots == 'OffPeak'].iloc[0]
        
        total_hours = hours_in_year(2025)
        assert abs(peak_hours - 0.25 * total_hours) < 1e-6
        assert abs(offpeak_hours - 0.75 * total_hours) < 1e-6
        assert result.validate_coverage()
    
    def test_missing_csv_raises_error(self, temp_scenario_dir):
        """Test that missing required CSV files raise FileNotFoundError."""
        # Don't create any files
        with pytest.raises(FileNotFoundError):
            to_snapshots(temp_scenario_dir, multi_investment_periods=False)


class TestToSnapshotsEdgeCases:
    """Edge case tests for to_snapshots."""
    
    @pytest.fixture
    def temp_scenario_dir(self):
        """Create temporary scenario directory."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_invalid_source_type_raises_error(self):
        """Test that invalid source type raises TypeError."""
        with pytest.raises(TypeError, match="source must be TimeComponent or str"):
            to_snapshots(123, multi_investment_periods=True)
        
        with pytest.raises(TypeError, match="source must be TimeComponent or str"):
            to_snapshots(['not', 'valid'], multi_investment_periods=True)
    
    def test_single_timeslice(self, temp_scenario_dir):
        """Test with single timeslice (entire year)."""
        time = TimeComponent(temp_scenario_dir)
        years = [2025]
        seasons = {"All": 365}
        daytypes = {"All": 7}
        brackets = {"All": 24}
        
        time.add_time_structure(years, seasons, daytypes, brackets)
        
        result = to_snapshots(time, multi_investment_periods=False)
        
        assert len(result.snapshots) == 1
        assert result.weightings.iloc[0] == hours_in_year(2025)
        assert result.validate_coverage()
    
    def test_many_timeslices(self, temp_scenario_dir):
        """Test with many timeslices (high resolution)."""
        time = TimeComponent(temp_scenario_dir)
        years = [2025]
        
        # 12 months, 7 daytypes, 24 hours = 2016 timeslices
        seasons = {f"M{i:02d}": 365/12 for i in range(1, 13)}
        daytypes = {f"D{i}": 1 for i in range(1, 8)}
        brackets = {f"H{i:02d}": 1 for i in range(24)}
        
        time.add_time_structure(years, seasons, daytypes, brackets)
        
        result = to_snapshots(time, multi_investment_periods=False)
        
        expected_count = 12 * 7 * 24
        assert len(result.snapshots) == expected_count
        assert result.validate_coverage()


class TestSnapshotResultApplyToNetwork:
    """Tests for applying SnapshotResult to PyPSA Network."""
    
    def test_apply_to_network_structure(self):
        """Test that apply_to_network sets correct attributes (mock network)."""
        # Create a mock network object
        class MockNetwork:
            def __init__(self):
                self.snapshots = None
                self.snapshot_weightings = {'objective': None, 'generators': None}
            
            def set_snapshots(self, snapshots):
                self.snapshots = snapshots
        
        network = MockNetwork()
        
        # Create SnapshotResult
        years = [2025]
        timeslices = ['TS1', 'TS2']
        snapshots = pd.Index(timeslices, name='timestep')
        weightings = pd.Series([4380.0, 4380.0], index=snapshots)
        
        result = SnapshotResult(
            years=years,
            snapshots=snapshots,
            weightings=weightings,
            timeslice_names=timeslices
        )
        
        # Apply to network
        result.apply_to_network(network)
        
        # Verify network attributes
        assert network.snapshots is not None
        pd.testing.assert_index_equal(network.snapshots, snapshots)
        pd.testing.assert_series_equal(network.snapshot_weightings['objective'], weightings)
        pd.testing.assert_series_equal(network.snapshot_weightings['generators'], weightings)


class TestRoundTripConsistency:
    """Tests for consistency between to_snapshots and to_timeslices."""
    
    @pytest.fixture
    def temp_scenario_dir(self):
        """Create temporary scenario directory."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_roundtrip_simple_structure(self, temp_scenario_dir):
        """Test that to_snapshots preserves time structure information."""
        time = TimeComponent(temp_scenario_dir)
        years = [2025]
        seasons = {"Winter": 182.5, "Summer": 182.5}
        daytypes = {"Weekday": 5, "Weekend": 2}
        brackets = {"Day": 12, "Night": 12}
        
        time.add_time_structure(years, seasons, daytypes, brackets)
        
        result = to_snapshots(time, multi_investment_periods=False)
        
        # Verify that total hours are preserved
        assert result.validate_coverage()
        
        # Verify timeslice count matches expected structure
        expected_timeslices = 2 * 2 * 2  # seasons × daytypes × brackets
        assert len(result.timeslice_names) == expected_timeslices
        
        # Verify snapshot count equals timeslice count (single year, single period)
        assert len(result.snapshots) == expected_timeslices
