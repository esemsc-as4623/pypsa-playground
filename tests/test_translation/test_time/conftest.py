# tests/test_translation/test_time/conftest.py

import pytest
import pandas as pd

from pyoscomp.scenario.components.time import TimeComponent
from pyoscomp.constants import hours_in_year


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
        'S1_D1_H1', 'S1_D1_H2',
        'S1_D2_H1', 'S1_D2_H2',
        'S2_D1_H1', 'S2_D1_H2',
        'S2_D2_H1', 'S2_D2_H2'
    ]
    
    # YEAR.csv
    pd.DataFrame({'VALUE': years}).to_csv(scenario_dir / "YEAR.csv", index=False)
    
    # TIMESLICE.csv
    pd.DataFrame({'VALUE': timeslices}).to_csv(scenario_dir / "TIMESLICE.csv", index=False)
    
    # SEASON.csv
    pd.DataFrame({'VALUE': ['S1', 'S2']}).to_csv(scenario_dir / "SEASON.csv", index=False)
    
    # DAYTYPE.csv
    pd.DataFrame({'VALUE': ['D1', 'D2']}).to_csv(scenario_dir / "DAYTYPE.csv", index=False)
    
    # DAILYTIMEBRACKET.csv
    pd.DataFrame({'VALUE': ['H1', 'H2']}).to_csv(scenario_dir / "DAILYTIMEBRACKET.csv", index=False)
    
    # YearSplit.csv - equal fractions
    yearsplit_data = []
    for ts in timeslices:
        yearsplit_data.append({
            'TIMESLICE': ts,
            'YEAR': 2025,
            'VALUE': 1.0 / len(timeslices)
        })
    pd.DataFrame(yearsplit_data).to_csv(scenario_dir / "YearSplit.csv", index=False)
    
    # DaySplit.csv - half day as fraction of year
    daysplit_data = []
    for year in years:
        for ts in timeslices:
            daysplit_data.append({
                'TIMESLICE': ts,
                'YEAR': year,
                'VALUE': 12.0 / (24.0*hours_in_year(year))
            })
    pd.DataFrame(daysplit_data).to_csv(scenario_dir / "DaySplit.csv", index=False)
    
    # DaysInDayType.csv
    daysindaytype_data = [
        {'SEASON': 'S1', 'DAYTYPE': 'D1', 'VALUE': 5},
        {'SEASON': 'S1', 'DAYTYPE': 'D2', 'VALUE': 2},
        {'SEASON': 'S2', 'DAYTYPE': 'D1', 'VALUE': 5},
        {'SEASON': 'S2', 'DAYTYPE': 'D2', 'VALUE': 2}
    ]
    pd.DataFrame(daysindaytype_data).to_csv(scenario_dir / "DaysInDayType.csv", index=False)
    
    # Conversion tables - map timeslices to their components
    # Conversionls (timeslice to season)
    conversionls_data = []
    for ts in timeslices:
        season = 'S1' if 'S1' in ts else 'S2'
        conversionls_data.append({'TIMESLICE': ts, 'SEASON': season, 'VALUE': 1.0})
    pd.DataFrame(conversionls_data).to_csv(scenario_dir / "Conversionls.csv", index=False)
    
    # Conversionld (timeslice to daytype)
    conversionld_data = []
    for ts in timeslices:
        daytype = 'D1' if 'D1' in ts else 'D2'
        conversionld_data.append({'TIMESLICE': ts, 'DAYTYPE': daytype, 'VALUE': 1.0})
    pd.DataFrame(conversionld_data).to_csv(scenario_dir / "Conversionld.csv", index=False)
    
    # Conversionlh (timeslice to daily time bracket)
    conversionlh_data = []
    for ts in timeslices:
        bracket = 'H1' if 'H1' in ts else 'H2'
        conversionlh_data.append({'TIMESLICE': ts, 'DAILYTIMEBRACKET': bracket, 'VALUE': 1.0})
    pd.DataFrame(conversionlh_data).to_csv(scenario_dir / "Conversionlh.csv", index=False)
    
    return str(scenario_dir)


@pytest.fixture
def complex_osemosys_scenario(tmp_path):
    """
    Create a complex multi-year OSeMOSYS scenario.
    
    Structure:
    - Multiple years (2025, 2030, 2035)
    - 4 seasons (single & multi-month)
    - 2 daytypes (single & multi-day)
    - 3 brackets (single & multi-hour)
    - Total: 24 timeslices per year
    """
    scenario_dir = tmp_path / "complex_scenario"
    scenario_dir.mkdir()
    
    years = [2025, 2030, 2035]
    seasons = {'Jan': 1,
               'Feb-Jun': 5,
               'Jul': 1,
               'Jul-Dec': 6}
    daytypes = {'Peak Day': 1, 'Rest-of-Week': 6}
    brackets = {'Peak-hour': 1, 'Some hours': 11, 'Other Hours': 12}
    
    # Generate all timeslice names
    timeslices = []
    for season in seasons.keys():
        for daytype in daytypes.keys():
            for bracket in brackets.keys():
                timeslices.append(f"{season}_{daytype}_{bracket}")
    
    # YEAR.csv
    pd.DataFrame({'VALUE': years}).to_csv(scenario_dir / "YEAR.csv", index=False)
    
    # TIMESLICE.csv
    pd.DataFrame({'VALUE': timeslices}).to_csv(scenario_dir / "TIMESLICE.csv", index=False)
    
    # SEASON.csv
    pd.DataFrame({'VALUE': list(seasons.keys())}).to_csv(scenario_dir / "SEASON.csv", index=False)
    
    # DAYTYPE.csv
    pd.DataFrame({'VALUE': list(daytypes.keys())}).to_csv(scenario_dir / "DAYTYPE.csv", index=False)
    
    # DAILYTIMEBRACKET.csv
    pd.DataFrame({'VALUE': list(brackets.keys())}).to_csv(scenario_dir / "DAILYTIMEBRACKET.csv", index=False)
    
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
    
    # YearSplit.csv
    yearsplit_data = []
    for year in years:
        for ts in timeslices:
            season = ts.split('_')[0]
            daytype = ts.split('_')[1]
            bracket = ts.split('_')[2]
            yearsplit_data.append({
                'TIMESLICE': ts,
                'YEAR': year,
                'VALUE': seasons[season]/12.0 * daytypes[daytype]/7.0 * brackets[bracket]/24.0
            })
    pd.DataFrame(yearsplit_data).to_csv(scenario_dir / "YearSplit.csv", index=False)
    
    # DaySplit.csv
    daysplit_data = []
    for year in years:
        for ts in timeslices:
            bracket = ts.split('_')[2]
            daysplit_data.append({
                'TIMESLICE': ts,
                'YEAR': year,
                'VALUE': brackets[bracket] / 24.0
            })
    pd.DataFrame(daysplit_data).to_csv(scenario_dir / "DaySplit.csv", index=False)
    
    # DaysInDayType.csv
    daysindaytype_data = []
    for season in seasons.keys():
        for daytype in daytypes.keys():
            daysindaytype_data.append({'SEASON': season, 'DAYTYPE': daytype, 'VALUE': daytypes[daytype]})
    pd.DataFrame(daysindaytype_data).to_csv(scenario_dir / "DaysInDayType.csv", index=False)
    
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
            'VALUE': 12.0 / (24.0 * hours_in_year(2024))
        })
    pd.DataFrame(daysplit_data).to_csv(scenario_dir / "DaySplit.csv", index=False)
    
    # DaysInDayType.csv
    daysindaytype_data = [
        {'SEASON': 'H1', 'DAYTYPE': 'All', 'VALUE': 7},
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
