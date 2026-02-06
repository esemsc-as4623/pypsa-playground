# tests/test_translation/test_time/conftest.py

import pytest
import pandas as pd

from pyoscomp.scenario.components.time import TimeComponent


@pytest.fixture
def simple_osemosys_scenario(tmp_path):
    """
    Create a simple OSeMOSYS scenario directory with CSV files.
    
    Structure:
    - Single year (2025)
    - 2 seasons (Winter, Summer)
    - 2 daytypes (Weekday, Weekend)
    - 2 brackets (Day, Night)
    - Total: 8 timeslices
    """
    scenario_dir = tmp_path / "simple_scenario"
    scenario_dir.mkdir()
    
    years = [2025]
    timeslices = [
        'Winter_Weekday_Day', 'Winter_Weekday_Night',
        'Winter_Weekend_Day', 'Winter_Weekend_Night',
        'Summer_Weekday_Day', 'Summer_Weekday_Night',
        'Summer_Weekend_Day', 'Summer_Weekend_Night'
    ]
    
    # YEAR.csv
    pd.DataFrame({'VALUE': years}).to_csv(scenario_dir / "YEAR.csv", index=False)
    
    # TIMESLICE.csv
    pd.DataFrame({'VALUE': timeslices}).to_csv(scenario_dir / "TIMESLICE.csv", index=False)
    
    # SEASON.csv
    pd.DataFrame({'VALUE': ['Winter', 'Summer']}).to_csv(scenario_dir / "SEASON.csv", index=False)
    
    # DAYTYPE.csv
    pd.DataFrame({'VALUE': ['Weekday', 'Weekend']}).to_csv(scenario_dir / "DAYTYPE.csv", index=False)
    
    # DAILYTIMEBRACKET.csv
    pd.DataFrame({'VALUE': ['Day', 'Night']}).to_csv(scenario_dir / "DAILYTIMEBRACKET.csv", index=False)
    
    # YearSplit.csv - equal fractions (1/8 each)
    yearsplit_data = []
    for ts in timeslices:
        yearsplit_data.append({
            'TIMESLICE': ts,
            'YEAR': 2025,
            'VALUE': 1.0 / len(timeslices)
        })
    pd.DataFrame(yearsplit_data).to_csv(scenario_dir / "YearSplit.csv", index=False)
    
    # DaySplit.csv - equal 3 hours each (8 × 3 = 24 hours/day)
    daysplit_data = []
    for year in years:
        for ts in timeslices:
            daysplit_data.append({
                'TIMESLICE': ts,
                'YEAR': year,
                'VALUE': 3.0 / 24.0
            })
    pd.DataFrame(daysplit_data).to_csv(scenario_dir / "DaySplit.csv", index=False)
    
    # DaysInDayType.csv
    daysindaytype_data = [
        {'SEASON': 'Winter', 'DAYTYPE': 'Weekday', 'VALUE': 130},
        {'SEASON': 'Winter', 'DAYTYPE': 'Weekend', 'VALUE': 52},
        {'SEASON': 'Summer', 'DAYTYPE': 'Weekday', 'VALUE': 130},
        {'SEASON': 'Summer', 'DAYTYPE': 'Weekend', 'VALUE': 53}
    ]
    pd.DataFrame(daysindaytype_data).to_csv(scenario_dir / "DaysInDayType.csv", index=False)
    
    # Conversion tables - map timeslices to their components
    # Conversionls (timeslice to season)
    conversionls_data = []
    for ts in timeslices:
        season = 'Winter' if 'Winter' in ts else 'Summer'
        conversionls_data.append({'TIMESLICE': ts, 'SEASON': season, 'VALUE': 1.0})
    pd.DataFrame(conversionls_data).to_csv(scenario_dir / "Conversionls.csv", index=False)
    
    # Conversionld (timeslice to daytype)
    conversionld_data = []
    for ts in timeslices:
        daytype = 'Weekday' if 'Weekday' in ts else 'Weekend'
        conversionld_data.append({'TIMESLICE': ts, 'DAYTYPE': daytype, 'VALUE': 1.0})
    pd.DataFrame(conversionld_data).to_csv(scenario_dir / "Conversionld.csv", index=False)
    
    # Conversionlh (timeslice to daily time bracket)
    conversionlh_data = []
    for ts in timeslices:
        bracket = 'Day' if 'Day' in ts else 'Night'
        conversionlh_data.append({'TIMESLICE': ts, 'DAILYTIMEBRACKET': bracket, 'VALUE': 1.0})
    pd.DataFrame(conversionlh_data).to_csv(scenario_dir / "Conversionlh.csv", index=False)
    
    return str(scenario_dir)


@pytest.fixture
def complex_osemosys_scenario(tmp_path):
    """
    Create a complex multi-year OSeMOSYS scenario.
    
    Structure:
    - Multiple years (2025, 2030, 2035)
    - 4 seasons
    - 2 daytypes
    - 3 brackets
    - Total: 24 timeslices per year
    """
    scenario_dir = tmp_path / "complex_scenario"
    scenario_dir.mkdir()
    
    years = [2025, 2030, 2035]
    seasons = ['Winter', 'Spring', 'Summer', 'Fall']
    daytypes = ['Weekday', 'Weekend']
    brackets = ['Morning', 'Afternoon', 'Night']
    
    # Generate all timeslice names
    timeslices = []
    for season in seasons:
        for daytype in daytypes:
            for bracket in brackets:
                timeslices.append(f"{season}_{daytype}_{bracket}")
    
    # YEAR.csv
    pd.DataFrame({'VALUE': years}).to_csv(scenario_dir / "YEAR.csv", index=False)
    
    # TIMESLICE.csv
    pd.DataFrame({'VALUE': timeslices}).to_csv(scenario_dir / "TIMESLICE.csv", index=False)
    
    # SEASON.csv
    pd.DataFrame({'VALUE': seasons}).to_csv(scenario_dir / "SEASON.csv", index=False)
    
    # DAYTYPE.csv
    pd.DataFrame({'VALUE': daytypes}).to_csv(scenario_dir / "DAYTYPE.csv", index=False)
    
    # DAILYTIMEBRACKET.csv
    pd.DataFrame({'VALUE': brackets}).to_csv(scenario_dir / "DAILYTIMEBRACKET.csv", index=False)
    
    # YearSplit.csv - equal fractions
    yearsplit_data = []
    for year in years:
        for ts in timeslices:
            yearsplit_data.append({
                'TIMESLICE': ts,
                'YEAR': year,
                'VALUE': 1.0 / len(timeslices)
            })
    pd.DataFrame(yearsplit_data).to_csv(scenario_dir / "YearSplit.csv", index=False)
    
    # DaySplit.csv - 8 hours each (3 × 8 = 24)
    daysplit_data = []
    for year in years:
        for ts in timeslices:
            daysplit_data.append({
                'TIMESLICE': ts,
                'YEAR': year,
                'VALUE': 8.0 / 24.0
            })
    pd.DataFrame(daysplit_data).to_csv(scenario_dir / "DaySplit.csv", index=False)
    
    # DaysInDayType.csv - approximate distribution
    daysindaytype_data = []
    season_days = {'Winter': 90, 'Spring': 92, 'Summer': 92, 'Fall': 91}
    for season, days in season_days.items():
        weekday_days = int(days * 5 / 7)
        weekend_days = days - weekday_days
        daysindaytype_data.append({'SEASON': season, 'DAYTYPE': 'Weekday', 'VALUE': weekday_days})
        daysindaytype_data.append({'SEASON': season, 'DAYTYPE': 'Weekend', 'VALUE': weekend_days})
    pd.DataFrame(daysindaytype_data).to_csv(scenario_dir / "DaysInDayType.csv", index=False)
    
    # Conversion tables
    conversionls_data = []
    for ts in timeslices:
        season = ts.split('_')[0]
        conversionls_data.append({'TIMESLICE': ts, 'SEASON': season, 'VALUE': 1.0})
    pd.DataFrame(conversionls_data).to_csv(scenario_dir / "Conversionls.csv", index=False)
    
    conversionld_data = []
    for ts in timeslices:
        daytype = ts.split('_')[1]
        conversionld_data.append({'TIMESLICE': ts, 'DAYTYPE': daytype, 'VALUE': 1.0})
    pd.DataFrame(conversionld_data).to_csv(scenario_dir / "Conversionld.csv", index=False)
    
    conversionlh_data = []
    for ts in timeslices:
        bracket = ts.split('_')[2]
        conversionlh_data.append({'TIMESLICE': ts, 'DAILYTIMEBRACKET': bracket, 'VALUE': 1.0})
    pd.DataFrame(conversionlh_data).to_csv(scenario_dir / "Conversionlh.csv", index=False)
    
    return str(scenario_dir)


@pytest.fixture
def leap_year_osemosys_scenario(tmp_path):
    """
    Create OSeMOSYS scenario with leap year (2024).
    
    Structure:
    - Single leap year (2024)
    - 2 seasons (H1, H2)
    - 1 daytype (All)
    - 2 brackets (Day, Night)
    - Total: 4 timeslices
    - Total hours: 8784 (366 days × 24 hours)
    """
    scenario_dir = tmp_path / "leap_year_scenario"
    scenario_dir.mkdir()
    
    years = [2024]
    timeslices = ['H1_All_Day', 'H1_All_Night', 'H2_All_Day', 'H2_All_Night']
    
    # YEAR.csv
    pd.DataFrame({'VALUE': years}).to_csv(scenario_dir / "YEAR.csv", index=False)
    
    # TIMESLICE.csv
    pd.DataFrame({'VALUE': timeslices}).to_csv(scenario_dir / "TIMESLICE.csv", index=False)
    
    # SEASON.csv
    pd.DataFrame({'VALUE': ['H1', 'H2']}).to_csv(scenario_dir / "SEASON.csv", index=False)
    
    # DAYTYPE.csv
    pd.DataFrame({'VALUE': ['All']}).to_csv(scenario_dir / "DAYTYPE.csv", index=False)
    
    # DAILYTIMEBRACKET.csv
    pd.DataFrame({'VALUE': ['Day', 'Night']}).to_csv(scenario_dir / "DAILYTIMEBRACKET.csv", index=False)
    
    # YearSplit.csv - equal fractions (1/4 each)
    yearsplit_data = []
    for ts in timeslices:
        yearsplit_data.append({
            'TIMESLICE': ts,
            'YEAR': 2024,
            'VALUE': 0.25
        })
    pd.DataFrame(yearsplit_data).to_csv(scenario_dir / "YearSplit.csv", index=False)
    
    # DaySplit.csv - 12 hours each
    daysplit_data = []
    for ts in timeslices:
        daysplit_data.append({
            'TIMESLICE': ts,
            'YEAR': 2024,
            'VALUE': 0.5
        })
    pd.DataFrame(daysplit_data).to_csv(scenario_dir / "DaySplit.csv", index=False)
    
    # DaysInDayType.csv - 366 days total (leap year)
    daysindaytype_data = [
        {'SEASON': 'H1', 'DAYTYPE': 'All', 'VALUE': 183},
        {'SEASON': 'H2', 'DAYTYPE': 'All', 'VALUE': 183}
    ]
    pd.DataFrame(daysindaytype_data).to_csv(scenario_dir / "DaysInDayType.csv", index=False)
    
    # Conversion tables
    conversionls_data = []
    for ts in timeslices:
        season = 'H1' if 'H1' in ts else 'H2'
        conversionls_data.append({'TIMESLICE': ts, 'SEASON': season, 'VALUE': 1.0})
    pd.DataFrame(conversionls_data).to_csv(scenario_dir / "Conversionls.csv", index=False)
    
    conversionld_data = []
    for ts in timeslices:
        conversionld_data.append({'TIMESLICE': ts, 'DAYTYPE': 'All', 'VALUE': 1.0})
    pd.DataFrame(conversionld_data).to_csv(scenario_dir / "Conversionld.csv", index=False)
    
    conversionlh_data = []
    for ts in timeslices:
        bracket = 'Day' if 'Day' in ts else 'Night'
        conversionlh_data.append({'TIMESLICE': ts, 'DAILYTIMEBRACKET': bracket, 'VALUE': 1.0})
    pd.DataFrame(conversionlh_data).to_csv(scenario_dir / "Conversionlh.csv", index=False)
    
    return str(scenario_dir)


@pytest.fixture
def time_component_simple(tmp_path):
    """
    Create simple TimeComponent for programmatic testing.
    
    Returns TimeComponent with:
    - 1 year (2025)
    - 2 seasons
    - 2 daytypes
    - 2 brackets
    """
    scenario_dir = tmp_path / "time_component_simple"
    scenario_dir.mkdir()
    
    time = TimeComponent(str(scenario_dir))
    years = [2025]
    seasons = {"Winter": 182.5, "Summer": 182.5}
    daytypes = {"Weekday": 5, "Weekend": 2}
    brackets = {"Day": 12, "Night": 12}
    
    time.add_time_structure(years, seasons, daytypes, brackets)
    
    return time


@pytest.fixture
def time_component_complex(tmp_path):
    """
    Create complex TimeComponent for programmatic testing.
    
    Returns TimeComponent with:
    - 3 years (2025, 2030, 2035)
    - 4 seasons
    - 2 daytypes
    - 3 brackets
    """
    scenario_dir = tmp_path / "time_component_complex"
    scenario_dir.mkdir()
    
    time = TimeComponent(str(scenario_dir))
    years = [2025, 2030, 2035]
    seasons = {"Winter": 90, "Spring": 92, "Summer": 92, "Fall": 91}
    daytypes = {"Weekday": 5, "Weekend": 2}
    brackets = {"Morning": 8, "Afternoon": 8, "Night": 8}
    
    time.add_time_structure(years, seasons, daytypes, brackets)
    
    return time


@pytest.fixture
def mock_pypsa_network():
    """
    Create a mock PyPSA Network object for testing.
    
    Returns a simple mock object with snapshots and snapshot_weightings attributes.
    """
    class MockNetwork:
        def __init__(self):
            self.snapshots = None
            self.snapshot_weightings = {'objective': None, 'generators': None}
        
        def set_snapshots(self, snapshots):
            """Method to set snapshots (PyPSA-like interface)."""
            self.snapshots = snapshots
    
    return MockNetwork()
