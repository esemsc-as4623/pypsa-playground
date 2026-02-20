# tests/test_scenario/test_components/conftest.py

"""
Shared fixtures for scenario component tests.

Provides pre-configured scenario directories at various stages:
- Empty scenario directory
- Scenario with topology (REGION.csv)
- Scenario with topology + time structure
- Scenario with topology + time + demand
- Scenario with topology + time + supply
- Complete scenario with all prerequisites
"""

import os
import pytest
import pandas as pd

from pyoscomp.scenario.components.topology import TopologyComponent
from pyoscomp.scenario.components.time import TimeComponent
from pyoscomp.scenario.components.supply import SupplyComponent


# =============================================================================
# Directory Fixtures
# =============================================================================

@pytest.fixture
def empty_scenario_dir(tmp_path):
    """Create an empty temporary scenario directory."""
    scenario_dir = tmp_path / "empty_scenario"
    scenario_dir.mkdir()
    return str(scenario_dir)


@pytest.fixture
def topology_scenario_dir(tmp_path):
    """
    Create scenario directory with topology (REGION.csv).

    Regions: ['REGION1', 'REGION2']
    """
    scenario_dir = tmp_path / "topology_scenario"
    scenario_dir.mkdir()

    # Create REGION.csv
    pd.DataFrame({"VALUE": ["REGION1", "REGION2"]}).to_csv(
        scenario_dir / "REGION.csv", index=False
    )

    return str(scenario_dir)


@pytest.fixture
def time_scenario_dir(tmp_path):
    """
    Create scenario directory with topology and time structure.

    Regions: ['REGION1']
    Years: [2025, 2030]
    Timeslices: Simple 2-season × 2-bracket = 4 timeslices
    """
    scenario_dir = tmp_path / "time_scenario"
    scenario_dir.mkdir()

    # Topology
    topology = TopologyComponent(str(scenario_dir))
    topology.add_nodes(["REGION1"])
    topology.save()

    # Time structure
    time = TimeComponent(str(scenario_dir))
    time.add_time_structure(
        years=[2025, 2030],
        seasons={"Summer": 182, "Winter": 183},
        daytypes={"AllDays": 1},
        brackets={"Day": 12, "Night": 12}
    )
    time.save()

    return str(scenario_dir)


@pytest.fixture
def multi_region_time_dir(tmp_path):
    """
    Scenario with multiple regions and time structure.

    Regions: ['North', 'South', 'East']
    Years: [2025, 2030, 2035, 2040]
    """
    scenario_dir = tmp_path / "multi_region_scenario"
    scenario_dir.mkdir()

    # Topology
    topology = TopologyComponent(str(scenario_dir))
    topology.add_nodes(["North", "South", "East"])
    topology.save()

    # Time structure
    time = TimeComponent(str(scenario_dir))
    time.add_time_structure(
        years=[2025, 2030, 2035, 2040],
        seasons={"Peak": 120, "OffPeak": 245},
        daytypes={"Weekday": 5, "Weekend": 2},
        brackets={"Morning": 6, "Day": 10, "Evening": 4, "Night": 4}
    )
    time.save()

    return str(scenario_dir)


@pytest.fixture
def complete_scenario_dir(tmp_path):
    """
    Complete scenario ready for all component tests.

    Regions: ['REGION1']
    Years: [2025, 2026, 2027, 2028, 2029, 2030]
    Timeslices: 4 timeslices (2 seasons × 2 brackets)
    """
    scenario_dir = tmp_path / "complete_scenario"
    scenario_dir.mkdir()

    # Topology
    topology = TopologyComponent(str(scenario_dir))
    topology.add_nodes(["REGION1"])
    topology.save()

    # Time structure with multiple years for interpolation tests
    time = TimeComponent(str(scenario_dir))
    time.add_time_structure(
        years=[2025, 2026, 2027, 2028, 2029, 2030],
        seasons={"Summer": 182, "Winter": 183},
        daytypes={"AllDays": 1},
        brackets={"Day": 16, "Night": 8}
    )
    time.save()

    return str(scenario_dir)


@pytest.fixture
def supply_scenario_dir(complete_scenario_dir):
    """
    Complete scenario with supply component saved to disk.

    Includes a GAS_CCGT conversion technology and a SOLAR_PV resource,
    with TECHNOLOGY.csv, FUEL.csv, MODE_OF_OPERATION.csv,
    OperationalLife.csv, ResidualCapacity.csv, and
    _fuel_assignments.json all written to disk.

    This is the minimum prerequisite for PerformanceComponent tests
    that need to read the supply registry from disk.
    """
    supply = SupplyComponent(complete_scenario_dir)
    supply.add_technology('REGION1', 'GAS_CCGT') \
        .with_operational_life(30) \
        .as_conversion(input_fuel='GAS', output_fuel='ELEC')
    supply.add_technology('REGION1', 'SOLAR_PV') \
        .with_operational_life(25) \
        .as_resource(output_fuel='ELEC')
    supply.save()
    return complete_scenario_dir


# =============================================================================
# Simple OSeMOSYS Scenario (8 timeslices)
# =============================================================================

@pytest.fixture
def osemosys_8ts_scenario(tmp_path):
    """
    Standard OSeMOSYS scenario with 8 timeslices.

    Structure:
    - Years: [2025, 2030, 2035]
    - 2 seasons (Summer, Winter) × 2 daytypes (Weekday, Weekend) × 2 brackets (Day, Night)
    - Total: 8 timeslices

    This matches common OSeMOSYS modeling practice.
    """
    scenario_dir = tmp_path / "osemosys_8ts"
    scenario_dir.mkdir()

    years = [2025, 2030, 2035]

    # Build timeslice names: Season_DayType_Bracket
    seasons = ["Summer", "Winter"]
    daytypes = ["Weekday", "Weekend"]
    brackets = ["Day", "Night"]

    timeslices = []
    for s in seasons:
        for d in daytypes:
            for b in brackets:
                timeslices.append(f"{s}_{d}_{b}")

    # REGION.csv
    pd.DataFrame({"VALUE": ["REGION1"]}).to_csv(
        scenario_dir / "REGION.csv", index=False
    )

    # YEAR.csv
    pd.DataFrame({"VALUE": years}).to_csv(
        scenario_dir / "YEAR.csv", index=False
    )

    # TIMESLICE.csv
    pd.DataFrame({"VALUE": timeslices}).to_csv(
        scenario_dir / "TIMESLICE.csv", index=False
    )

    # SEASON.csv
    pd.DataFrame({"VALUE": seasons}).to_csv(
        scenario_dir / "SEASON.csv", index=False
    )

    # DAYTYPE.csv
    pd.DataFrame({"VALUE": daytypes}).to_csv(
        scenario_dir / "DAYTYPE.csv", index=False
    )

    # DAILYTIMEBRACKET.csv
    pd.DataFrame({"VALUE": brackets}).to_csv(
        scenario_dir / "DAILYTIMEBRACKET.csv", index=False
    )

    # YearSplit.csv - equal distribution (1/8)
    yearsplit_data = []
    for y in years:
        for ts in timeslices:
            yearsplit_data.append({
                "TIMESLICE": ts, "YEAR": y, "VALUE": 1.0 / len(timeslices)
            })
    pd.DataFrame(yearsplit_data).to_csv(
        scenario_dir / "YearSplit.csv", index=False
    )

    # DaySplit.csv
    daysplit_data = []
    for y in years:
        for b in brackets:
            # Day = 12 hours, Night = 12 hours
            daysplit_data.append({
                "DAILYTIMEBRACKET": b, "YEAR": y, "VALUE": 12 / 24
            })
    pd.DataFrame(daysplit_data).to_csv(
        scenario_dir / "DaySplit.csv", index=False
    )

    # DaysInDayType.csv
    daysindaytype_data = []
    for s in seasons:
        for d in daytypes:
            if s == "Summer":
                days = 130 if d == "Weekday" else 52  # ~182 days
            else:
                days = 131 if d == "Weekday" else 52  # ~183 days
            for y in years:
                daysindaytype_data.append({
                    "SEASON": s, "DAYTYPE": d, "YEAR": y, "VALUE": days
                })
    pd.DataFrame(daysindaytype_data).to_csv(
        scenario_dir / "DaysInDayType.csv", index=False
    )

    # Conversionls.csv (timeslice to season)
    conversionls_data = []
    for ts in timeslices:
        for s in seasons:
            val = 1.0 if s in ts else 0.0
            conversionls_data.append({
                "TIMESLICE": ts, "SEASON": s, "VALUE": val
            })
    pd.DataFrame(conversionls_data).to_csv(
        scenario_dir / "Conversionls.csv", index=False
    )

    # Conversionld.csv (timeslice to daytype)
    conversionld_data = []
    for ts in timeslices:
        for d in daytypes:
            val = 1.0 if d in ts else 0.0
            conversionld_data.append({
                "TIMESLICE": ts, "DAYTYPE": d, "VALUE": val
            })
    pd.DataFrame(conversionld_data).to_csv(
        scenario_dir / "Conversionld.csv", index=False
    )

    # Conversionlh.csv (timeslice to bracket)
    conversionlh_data = []
    for ts in timeslices:
        for b in brackets:
            val = 1.0 if b in ts else 0.0
            conversionlh_data.append({
                "TIMESLICE": ts, "DAILYTIMEBRACKET": b, "VALUE": val
            })
    pd.DataFrame(conversionlh_data).to_csv(
        scenario_dir / "Conversionlh.csv", index=False
    )

    return str(scenario_dir)


# =============================================================================
# Utility Fixtures
# =============================================================================

@pytest.fixture
def sample_trajectory():
    """Sample demand/cost trajectory for interpolation tests."""
    return {2025: 100, 2030: 150}


@pytest.fixture
def linear_trajectory():
    """Trajectory with known linear interpolation result."""
    return {2025: 100, 2030: 200}  # 20/year growth rate


@pytest.fixture
def multi_point_trajectory():
    """Multi-point trajectory for complex interpolation."""
    return {
        2025: 100,
        2028: 130,
        2032: 200,
        2040: 180  # Decline at end
    }
