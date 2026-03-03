# pyoscomp/translation/time/translate.py

import pandas as pd
from datetime import datetime
from typing import List, Set, Union

from ...constants import hours_in_year
from .structures import Season, DayType, DailyTimeBracket, Timeslice
from .results import TimesliceResult, SnapshotResult
from .helpers import (
    create_seasons_from_dates,
    create_daytypes_from_dates,
    create_timebrackets_from_times
)
from ...interfaces.containers import ScenarioData


def to_timeslices(snapshots: Union[pd.DatetimeIndex, pd.Index, List[pd.Timestamp], List[datetime]]) -> TimesliceResult:
    """
    Convert PyPSA sequential snapshots to OSeMOSYS hierarchical timeslice structure.
    
    Transforms PyPSA's datetime-based sequential representation into OSeMOSYS's
    categorical hierarchical structure (seasons/daytypes/dailytimebrackets/timeslices).
    The conversion preserves temporal coverage and duration weightings.
    
    Parameters
    ----------
    snapshots : pd.DatetimeIndex or pd.Index or List[pd.Timestamp] or List[datetime]
        PyPSA snapshot timestamps. Must contain datetime-like values that can be
        converted to pd.DatetimeIndex. The function extracts unique dates and times
        to construct the OSeMOSYS time structure.

        - **pd.DatetimeIndex**: Native PyPSA format (recommended)
        - **pd.Index**: Will be converted if contains datetime-parseable values
        - **List[pd.Timestamp]**: List of pandas Timestamp objects
        - **List[datetime]**: List of Python datetime objects
    
    Returns
    -------
    TimesliceResult
        Container with hierarchical timeslice structure and mapping from snapshots
        to timeslices. Includes methods for validation and CSV export.
    
    Raises
    ------
    ValueError
        If snapshots is empty.
    ValueError
        If timeslice structure does not cover the entire year (validation fails).
        This can occur if snapshots have gaps or inconsistent temporal coverage.
    TypeError
        If snapshots contains non-datetime objects or cannot be converted.
    
    Notes
    -----
    Conversion algorithm:
    
    1. **Extract years**: Identify unique years from snapshot timestamps
    2. **Create Seasons**: Group snapshot dates into non-overlapping month(s)-of-year ranges
    3. **Create DayTypes**: Group snapshot dates into non-overlapping day(s)-of-month(s) ranges
    4. **Create DailyTimeBrackets**: Group snapshot times into non-overlapping time-of-day ranges
    5. **Form Timeslices**: Create cartesian product of Seasons x DayTypes × DailyTimeBrackets
    6. **Validate**: Ensure timeslices partition each year completely (sum to 8760/8784 hours)
    
    The resulting structure uses:
    
    - Seasons capturing month(s)-of-year granularity from snapshot dates
    - DayTypes capturing day(s)-of-month(s) granularity from snapshot dates
    - DailyTimeBrackets capturing time-of-day granularity from snapshot times
    
    Performance considerations:
    
    - Memory: O(n_dates × n_times) timeslices created
    - Time complexity: O(n_snapshots × n_timeslices) for mapping
    
    Examples
    --------
    Convert hourly snapshots for one year:
    
    >>> snapshots = pd.date_range('2025-01-01', periods=8760, freq='H')
    >>> result = to_timeslices(snapshots)
    >>> print(f"Created {len(result.timeslices)} timeslices")
    Created 8928 timeslices
    # Creates 12 Seasons, 31 DayTypes, 24 DailyTimeBrackets
    # Note that some Timeslices will have no duration
    >>> print(f"Years: {result.years}")
    Years: [2025]
    >>> result.validate_coverage()
    True
    
    Convert daily snapshots (two time-of-day samples per day):
    
    >>> snapshots = pd.DatetimeIndex([
    ...     '2025-01-01 06:00', '2025-01-01 18:00',
    ...     '2025-01-02 06:00', '2025-01-02 18:00',
    ...     # ... continue for full year
    ... ])
    >>> result = to_timeslices(snapshots)
    >>> print(f"Years: {result.years}")
    Years: [2025]
    >>> print(f"Seasons: {len(result.seasons)}")
    Seasons: 12  # One per month
    >>> print(f"DayTypes: {len(result.daytypes)}")
    DayTypes: 31  # One per day in longest month
    >>> print(f"DailyTimeBrackets: {len(result.dailytimebrackets)}")
    DailyTimeBrackets: 3  # 00:00 to 06:00, 06:00 to 18:00, 18:00-ENDOFDAY
    >>> print(f"Timeslices: {len(result.timeslices)}")
    Timeslices: 1116
    
    Export to OSeMOSYS CSV files:
    
    >>> result = to_timeslices(snapshots)
    >>> csv_dict = result.export()
    >>> import os
    >>> os.makedirs('osemosys_scenario', exist_ok=True)
    >>> for filename, df in csv_dict.items():
    ...     df.to_csv(f'osemosys_scenario/{filename}.csv', index=False)
    >>> print(f"Created {len(csv_dict)} CSV files")
    Created 11 CSV files
    
    Multi-year conversion:
    
    >>> snapshots = pd.date_range('2026-01-01', '2028-12-31', freq='D')
    >>> result = to_timeslices(snapshots)
    >>> print(f"Years: {result.years}")
    Years: [2026, 2027, 2028]
    >>> for year in result.years:
    ...     timeslices = result.timeslices
    ...     total_hours = sum(ts.duration_hours(year) for ts in timeslices)
    ...     print(f"{year}: {total_hours:.0f} hours")
    2026: 8760 hours
    2027: 8760 hours
    2028: 8784 hours
    
    
    See Also
    --------
    to_snapshots : Convert OSeMOSYS timeslices to PyPSA snapshots (inverse operation)
    TimesliceResult : Container class for conversion results
    create_seasons_from_dates : Helper for creating month(s)-of-year ranges
    create_daytypes_from_dates : Helper for creating day(s)-of-month(s) ranges
    create_timebrackets_from_times : Helper for creating time-of-day ranges
    Season : Month(s)-of-year range structure
    DayType : Day(s)-of-month(s) range structure
    DailyTimeBracket : Time-of-day range structure
    Timeslice : Combined temporal slice structure
    """
    # 1. Validate input, convert, and sort
    if len(snapshots) == 0:
        raise ValueError("snapshots cannot be empty")
    try:
        snapshots = pd.DatetimeIndex(pd.to_datetime(snapshots)).sort_values()
    except (TypeError, ValueError) as e:
        raise TypeError(
            f"snapshots must contain datetime-like values. "
            f"If you have date strings, convert them first with pd.to_datetime(). "
            f"Original error: {e}"
        ) from e
    years = sorted(snapshots.year.unique().tolist())
    
    # 2. Initialize containers
    seasons: Set[Season] = set()
    daytypes: Set[DayType] = set()
    dailytimebrackets: Set[DailyTimeBracket] = set()
    
    # 3. Remove time component and create seasons and daytypes from dates
    unique_dates = sorted(set(ts.date() for ts in snapshots))
    seasons = create_seasons_from_dates(unique_dates)
    daytypes = create_daytypes_from_dates(unique_dates)

    # 4. Remove date component and create dailytimebrackets from times
    unique_times = sorted(set(ts.time() for ts in snapshots))
    dailytimebrackets = create_timebrackets_from_times(unique_times)
    
    # 5. Create timeslice for each combination
    timeslices = []
    for s in sorted(seasons):
        for dt in sorted(daytypes):
            for dtb in sorted(dailytimebrackets):
                    ts = Timeslice(
                        season=s,
                        daytype=dt,
                        dailytimebracket=dtb,
                    )
                    timeslices.append(ts)

    result = TimesliceResult(
        years=years,
        seasons=seasons,
        daytypes=daytypes,
        dailytimebrackets=dailytimebrackets,
        timeslices=timeslices,
        snapshots=snapshots,
    )

    if not result.validate_coverage():
        raise ValueError(
            "Timeslice structure does not cover the entire year"
        )

    return result

def to_snapshots(source: ScenarioData) -> SnapshotResult:
    """
    Convert OSeMOSYS hierarchical timeslice structure to PyPSA snapshots.
    
    Transforms OSeMOSYS's categorical time representation (timeslices with
    hierarchical season/daytype/bracket structure) into PyPSA's sequential
    snapshot representation with duration weightings.
    
    Parameters
    ----------
    source : ScenarioData
        Source of OSeMOSYS time structure.
        
        - If **ScenarioData**: Uses an initialized ScenarioData object.
          Recommended when building scenarios programmatically.

    Returns
    -------
    SnapshotResult
        Container with snapshots (time indices) and weightings (durations in hours),
        ready for application to a PyPSA Network.
    
    Raises
    ------
    TypeError
        If source is not ScenarioData.
    ValueError
        If snapshot weightings do not sum to correct hours per year.
    
    Examples
    --------
    Convert from programmatic TimeParameters:
    
    >>> result = to_snapshots(ScenarioData.time)
    >>> result.apply_to_network(network)
    
    See Also
    --------
    to_timeslices : Convert PyPSA snapshots to OSeMOSYS timeslices (inverse operation)
    SnapshotResult : Container class for conversion results
    TimeComponent : OSeMOSYS time structure builder
    """
    # 1. Extract time parameters from ScenarioData
    years = sorted(source.sets.years)
    timeslice_names = sorted(source.sets.timeslices)
    yearsplit_df = source.time.year_split

    # 2. Create multi-index snapshots
    snapshots = pd.MultiIndex.from_product(
        [years, timeslice_names],
        names=['period', 'timestep']
    )

    # 3. Create weightings (duration in hours)
    weightings_dict = {}
    for _, row in yearsplit_df.iterrows():
        year = row['YEAR']
        timeslice = row['TIMESLICE']
        fraction = row['VALUE']
        hours = fraction * hours_in_year(year)
        
        key = (year, timeslice)
        weightings_dict[key] = hours
    
    weightings = pd.Series(weightings_dict)
    weightings = weightings.reindex(snapshots)  # Ensure alignment
    
    # 4. Create and validate result
    result = SnapshotResult(
        years=years,
        snapshots=snapshots,
        weightings=weightings,
        timeslice_names=timeslice_names
    )
    
    if not result.validate_coverage():
        raise ValueError(
            "Snapshot weightings do not sum to correct hours per year"
        )
    
    return result