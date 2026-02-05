# pyoscomp/translation/time/translate.py

import pandas as pd
from datetime import time, date, timedelta, datetime
from typing import List, Set, Dict, Union, Tuple

from .constants import ENDOFDAY, hours_in_year
from .structures import DayType, DailyTimeBracket, Timeslice
from .results import TimesliceResult, SnapshotResult
from ...scenario.components.time import TimeComponent

SnapshotInput = Union[
    pd.DatetimeIndex,
    pd.Index,
    List[pd.Timestamp],
    List[datetime],
]

def create_timebrackets_from_times(times: List[time]) -> Set[DailyTimeBracket]:
    """
    Create non-overlapping DailyTimeBracket objects from a list of times.
    
    Takes a list of time-of-day values and partitions the 24-hour day into
    non-overlapping brackets. Each input time represents the START of a bracket,
    with the bracket extending until the next time (or end of day for the last bracket).
    
    Parameters
    ----------
    times : List[time]
        List of datetime.time objects representing bracket start times.
        Times will be sorted automatically. If midnight (00:00:00) is not
        included, it will be prepended automatically.
    
    Returns
    -------
    Set[DailyTimeBracket]
        Set of non-overlapping DailyTimeBracket objects that partition the
        24-hour day. Each bracket has half-open interval [start, end), except
        the final bracket which extends to ENDOFDAY (inclusive 23:59:59.999999).
    
    Notes
    -----
    Special handling:
    
    - If the first time is within 1 second of midnight, it's adjusted to 00:00:00
    - If any time is within 1 second of ENDOFDAY (23:59:59.999999), it's adjusted
      and becomes the final bracket
    - The last bracket always extends to ENDOFDAY (inclusive)
    - Duplicate times are automatically removed
    
    The function ensures complete coverage of the 24-hour day with no gaps or overlaps.
    
    Examples
    --------
    Create day/night brackets:
    
    >>> from datetime import time
    >>> times = [time(0, 0), time(6, 0), time(18, 0)]
    >>> brackets = create_timebrackets_from_times(times)
    >>> for b in sorted(brackets):
    ...     print(f"{b.hour_start} - {b.hour_end}: {b.duration_hours():.1f} hours")
    00:00:00 - 06:00:00: 6.0 hours
    06:00:00 - 18:00:00: 12.0 hours
    18:00:00 - 23:59:59.999999: 6.0 hours
    
    Midnight is added automatically:
    
    >>> times = [time(12, 0)]  # Only noon
    >>> brackets = create_timebrackets_from_times(times)
    >>> len(brackets)
    2  # 00:00-12:00 and 12:00-24:00
    
    See Also
    --------
    DailyTimeBracket : The time-of-day range structure created by this function
    create_daytypes_from_dates : Analogous function for creating day-of-year ranges
    """
    brackets = set()
    times = sorted(set(times))
    
    # Ensure midnight is the first time
    if times[0] != time(0, 0, 0):
        # if within 1 second of midnight, assume midnight
        if timedelta(hours=times[0].hour, minutes=times[0].minute, seconds=times[0].second) <= timedelta(seconds=1):
            times[0] = time(0, 0, 0)
        else:
            times = [time(0, 0, 0)] + times
    
    for i in range(len(times)):
        start = times[i]
        
        if i + 1 < len(times):
            end = times[i + 1]
            # if within 1 second of ENDOFDAY, assume ENDOFDAY
            if timedelta(hours=ENDOFDAY.hour - end.hour, minutes=ENDOFDAY.minute - end.minute, seconds=ENDOFDAY.second - end.second) <= timedelta(seconds=1):
                end = ENDOFDAY
                brackets.add(DailyTimeBracket(hour_start=start, hour_end=end))
                break
        else:
            end = ENDOFDAY
        
        brackets.add(DailyTimeBracket(hour_start=start, hour_end=end))
    
    return brackets


def create_daytypes_from_dates(dates: List[date]) -> set[DayType]:
    """
    Create non-overlapping DayType objects from a list of dates.
    
    Takes a list of calendar dates and partitions the year into non-overlapping
    day-of-year ranges. Each input date represents a SINGLE DAY DayType, with
    gaps between dates filled by range DayTypes. Start and end of year boundaries
    are handled automatically.
    
    Parameters
    ----------
    dates : List[date]
        List of datetime.date objects representing specific days of interest.
        Dates will be normalized to year 2000 (leap year) and sorted automatically.
        If January 1 or December 31 are not included, boundary DayTypes will be
        added automatically.
    
    Returns
    -------
    Set[DayType]
        Set of DayType objects that partition the year (Jan 1 - Dec 31).
        Includes:
        
        - Single-day DayTypes for each input date
        - Range DayTypes for gaps between consecutive dates
        - Boundary DayTypes for start/end of year if needed
    
    Notes
    -----
    Algorithm details:
    
    - All dates are normalized to year 2000 (leap year) for maximum inclusivity
    - Each input date becomes a 1-day DayType
    - Non-consecutive dates are separated by range DayTypes covering the gap
    - Start-of-year (Jan 1) and end-of-year (Dec 31) boundaries are added if missing
    - The resulting DayTypes form a complete, non-overlapping partition of the year
    
    The function ensures complete coverage of all 365/366 days with no gaps or overlaps.
    
    Examples
    --------
    Create DayTypes from specific dates:
    
    >>> from datetime import date
    >>> dates = [date(2025, 1, 1), date(2025, 6, 1), date(2025, 12, 31)]
    >>> daytypes = create_daytypes_from_dates(dates)
    >>> for dt in sorted(daytypes):
    ...     print(f"{dt.name}: {dt.duration_days(2025)} days in 2025")
    01-01 to 01-01: 1 days in 2025  # Jan 1 (single day)
    01-02 to 05-31: 150 days in 2025  # Jan 2 - May 31 (gap)
    06-01 to 06-01: 1 days in 2025  # Jun 1 (single day)
    06-02 to 12-30: 212 days in 2025  # Jun 2 - Dec 30 (gap)
    12-31 to 12-31: 1 days in 2025  # Dec 31 (single day)
    
    Consecutive dates (no gaps):
    
    >>> dates = [date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 3)]
    >>> daytypes = create_daytypes_from_dates(dates)
    >>> len(daytypes)
    4  # Three 1-day DayTypes + one range for rest of year
    
    Handles leap years:
    
    >>> dates = [date(2024, 2, 29)]  # Leap day
    >>> daytypes = create_daytypes_from_dates(dates)
    >>> dt_feb29 = [dt for dt in daytypes if dt.month_start == 2 and dt.day_start == 29][0]
    >>> dt_feb29.duration_days(2024)  # Leap year
    1
    >>> dt_feb29.duration_days(2025)  # Non-leap year
    0
    
    See Also
    --------
    DayType : The day-of-year range structure created by this function
    create_timebrackets_from_times : Analogous function for creating time-of-day ranges
    """
    if not dates:
        raise ValueError("dates list cannot be empty")
    
    daytypes = set()
    year = 2000 # use leap year for most inclusive daytype definitions

    # Set same year for all dates to get highest resolution daytypes
    dates = sorted(set(date(year, d.month, d.day) for d in dates))

    # Add start of year boundary
    start_of_year = date(year, 1, 1)

    if dates[0] != start_of_year:
        end_date = dates[0] - timedelta(days=1)
        daytypes.add(DayType(
            month_start=start_of_year.month,
            day_start=start_of_year.day,
            month_end=end_date.month,
            day_end=end_date.day
        )) # min 1 day, max 364/5 days if dates[0] = Dec 31
    else:
        daytypes.add(DayType(
            month_start=start_of_year.month,
            day_start=start_of_year.day,
            month_end=dates[0].month,
            day_end=dates[0].day
        )) # 1 day

    for i in range(len(dates)-1):
        # Add each date as one daytype
        daytypes.add(DayType(
            month_start=dates[i].month,
            day_start=dates[i].day,
            month_end=dates[i].month,
            day_end=dates[i].day
        )) # 1 day

        start_date = dates[i] + timedelta(days=1)

        # if next date is not consecutive
        if dates[i+1] > start_date:
            end_date = dates[i+1] - timedelta(days=1)
            # add group of missing dates as one daytype
            daytypes.add(DayType(
                month_start=start_date.month,
                day_start=start_date.day,
                month_end=end_date.month,
                day_end=end_date.day
            )) # min 1 day, max 363/4 days if dates[0] = Jan 01, dates[-1] = Dec 31
    
    # Add final date as one daytype
    daytypes.add(DayType(
        month_start=dates[-1].month,
        day_start=dates[-1].day,
        month_end=dates[-1].month,
        day_end=dates[-1].day
    )) # 1 day

    # Add end of year boundary
    end_of_year = date(year, 12, 31)

    if dates[-1] != end_of_year:
        end_date = dates[-1] + timedelta(days=1)
        daytypes.add(DayType(
            month_start=end_date.month,
            day_start=end_date.day,
            month_end=end_of_year.month,
            day_end=end_of_year.day
        )) # min 1 day, max 364/5 days if dates[-1] = Jan 01

    return daytypes


def create_endpoints(snapshots: Union[pd.DatetimeIndex, pd.Index]) -> List[pd.Timestamp]:
    """
    Create extended snapshot endpoint list including year boundaries.
    
    Takes PyPSA snapshots and augments them with start-of-year and end-of-year
    timestamps for each year present in the snapshots. These endpoints are used
    to properly align snapshots with OSeMOSYS timeslice boundaries.
    
    Parameters
    ----------
    snapshots : pd.DatetimeIndex or pd.Index
        PyPSA snapshot timestamps. Will be converted to DatetimeIndex if needed.
    
    Returns
    -------
    List[pd.Timestamp]
        Sorted list of unique timestamps including:
        
        - All original snapshot timestamps
        - Start of year (Jan 1 00:00:00) for each year in snapshots
        - End of year (Dec 31 23:59:59.999999) for each year in snapshots
        
        Duplicates are removed automatically.
    
    Notes
    -----
    This function is used internally by create_map() to ensure proper handling
    of snapshot periods that span year boundaries. The year boundaries allow
    accurate calculation of snapshot durations when mapping to timeslices.
    
    Examples
    --------
    >>> snapshots = pd.DatetimeIndex([
    ...     '2025-03-15 12:00',
    ...     '2025-09-20 08:00',
    ...     '2026-02-10 16:00'
    ... ])
    >>> endpoints = create_endpoints(snapshots)
    >>> print([str(ep) for ep in endpoints])
    ['2025-01-01 00:00:00',  # Added: start of 2025
     '2025-03-15 12:00:00',  # Original snapshot
     '2025-09-20 08:00:00',  # Original snapshot
     '2025-12-31 23:59:59.999999',  # Added: end of 2025
     '2026-01-01 00:00:00',  # Added: start of 2026
     '2026-02-10 16:00:00',  # Original snapshot
     '2026-12-31 23:59:59.999999']  # Added: end of 2026
    
    See Also
    --------
    create_map : Uses endpoints for snapshot-to-timeslice mapping
    """
    snapshots = pd.DatetimeIndex(pd.to_datetime(snapshots)).sort_values()    
    years = sorted(snapshots.year.unique().tolist())

    endpoints = []
    for year in years:
        start_of_year = pd.Timestamp.combine(date(year, 1, 1), time(0, 0, 0))
        end_of_year = pd.Timestamp.combine(date(year, 12, 31), ENDOFDAY)
        endpoints.append(start_of_year)
        endpoints.append(end_of_year)

    endpoints = list(snapshots) + endpoints
    endpoints = sorted(set(endpoints))
    return endpoints


def create_map(snapshots: Union[pd.DatetimeIndex, pd.Index],
               timeslices: List[Timeslice]) -> Dict[pd.Timestamp, List[Tuple[int, Timeslice]]]:
    """
    Map each PyPSA snapshot to corresponding OSeMOSYS (year, timeslice) pairs.
    
    Creates a mapping from PyPSA's sequential snapshot representation to OSeMOSYS's
    hierarchical timeslice structure. Each snapshot is mapped to one or more
    (year, timeslice) tuples, accounting for snapshots that may represent periods
    spanning multiple timeslices or years.
    
    Parameters
    ----------
    snapshots : pd.DatetimeIndex or pd.Index
        PyPSA snapshot timestamps. Each snapshot represents a period that extends
        until the next snapshot (or end of year for the final snapshot).
    timeslices : List[Timeslice]
        List of OSeMOSYS Timeslice objects representing the hierarchical time
        structure (season/daytype/dailytimebracket combinations).
    
    Returns
    -------
    Dict[pd.Timestamp, List[Tuple[int, Timeslice]]]
        Dictionary mapping each snapshot timestamp to a list of (year, timeslice)
        tuples that fall within that snapshot's valid period. A snapshot may map to:
        
        - Single timeslice: snapshot period perfectly aligns with one timeslice
        - Multiple timeslices: snapshot period spans several timeslices
        - Multiple years: snapshot period crosses year boundary
    
    Raises
    ------
    ValueError
        If total duration of mapped timeslices doesn't match the snapshot period
        duration (within 1 second tolerance). This indicates structural mismatch
        between PyPSA snapshots and OSeMOSYS timeslices.
    
    Notes
    -----
    Algorithm:
    
    1. Each snapshot's valid period extends from its timestamp to the next snapshot
       (or to end-of-year for the final snapshot in each year)
    2. For each snapshot period, find all timeslices that fall entirely within it
    3. Validate that timeslice durations sum to snapshot period duration
    4. Skip timeslices with zero duration (e.g., Feb 29 in non-leap years)
    
    The validation ensures lossless conversion between PyPSA and OSeMOSYS time
    representations.
    
    Examples
    --------
    Simple case - one snapshot per timeslice:
    
    >>> snapshots = pd.DatetimeIndex(['2025-01-01', '2025-06-01'])
    >>> # Assume timeslices cover Jan-May and Jun-Dec
    >>> mapping = create_map(snapshots, timeslices)
    >>> mapping[pd.Timestamp('2025-01-01')]
    [(2025, Timeslice(X_01-01 to 05-31_DAY))]
    >>> mapping[pd.Timestamp('2025-06-01')]
    [(2025, Timeslice(X_06-01 to 12-31_DAY))]
    
    Complex case - snapshot spans multiple timeslices:
    
    >>> snapshots = pd.DatetimeIndex(['2025-01-01 00:00', '2025-01-02 00:00'])
    >>> # Assume hourly timeslices
    >>> mapping = create_map(snapshots, timeslices)
    >>> len(mapping[pd.Timestamp('2025-01-01')])
    24  # Maps to 24 hourly timeslices
    
    Error case - duration mismatch:
    
    >>> # If timeslices don't cover the full snapshot period
    >>> mapping = create_map(snapshots, incomplete_timeslices)
    ValueError: Mismatch! snapshot duration = 1 days, timeslice duration = 20 hours
    
    See Also
    --------
    to_timeslices : Uses this function for PyPSA → OSeMOSYS conversion
    create_endpoints : Helper for handling year boundaries
    Timeslice.duration_hours : Used to calculate timeslice durations
    """
    snapshot_to_timeslice = {}
    snapshots = pd.DatetimeIndex(pd.to_datetime(snapshots)).sort_values()   
    # Data in each snapshot is valid until the next one
    valid_until = list(snapshots)
    # Data in last snapshot is valid until the end of the last year
    valid_until += [pd.Timestamp.combine(date(snapshots[-1].year, 12, 31), ENDOFDAY)]
    # Add start of year and end of year endpoints for each year in snapshots
    endpoints = create_endpoints(snapshots)

    for i in range(len(valid_until) - 1):
        # Get annual lower and upper bounds of valid_until period
        i_lower = endpoints.index(valid_until[i])
        i_upper = endpoints.index(valid_until[i+1])
        segment = endpoints[i_lower:i_upper+1]
        # Get valid_years that are represented in snapshots
        valid_years = set([e.year for e in segment])

        # List all timeslices between lower and upper bounds
        idx_list, total_timedelta = [], timedelta()
        for j, ts in enumerate(timeslices):
            for y in valid_years:
                # Skip if timeslice doesn't exist in this year (e.g., Feb 29 in non-leap year)
                if ts.daytype.duration_days(y) == 0:
                    continue
                
                # Get start and end datetime based on timeslice definition and each valid_year
                start_date, end_date = ts.daytype.to_dates(y)
                start_time = pd.Timestamp.combine(start_date, ts.dailytimebracket.hour_start)
                end_time = pd.Timestamp.combine(end_date, ts.dailytimebracket.hour_end)
                
                # Calculate timeslice duration: duration_days * duration_hours
                duration_days = ts.daytype.duration_days(y)
                duration_hours = ts.dailytimebracket.duration_hours()
                timeslice_timedelta = timedelta(hours=duration_days * duration_hours)
                
                # Check if timeslice is within valid_until period
                if start_time >= valid_until[i] and end_time <= valid_until[i+1]:
                    idx_list.append((y, j))
                    total_timedelta += timeslice_timedelta

        # Compare with timedelta represented by snapshot
        snapshot_timedelta = timedelta()
        for j in range(len(segment)-1):
            if segment[j+1].year == segment[j].year:
                snapshot_timedelta += segment[j+1] - segment[j]

        diff_seconds = abs((snapshot_timedelta - total_timedelta).total_seconds())
        if diff_seconds > 1:
            raise ValueError(
                f"Mismatch! snapshot duration = {snapshot_timedelta}, timeslice duration = {total_timedelta}"
                f"\n(year, timeslice) pairs = {[(y, timeslices[j]) for (y, j) in idx_list]}"
                f"\n(year, index) pairs = {idx_list}"
            )
        snapshot_to_timeslice[snapshots[i]] = [(y, timeslices[j]) for (y, j) in idx_list]

    return snapshot_to_timeslice


def to_timeslices(snapshots: SnapshotInput) -> TimesliceResult:
    """
    Convert PyPSA sequential snapshots to OSeMOSYS hierarchical timeslice structure.
    
    Transforms PyPSA's datetime-based sequential representation into OSeMOSYS's
    categorical hierarchical structure (seasons/daytypes/dailytimebrackets/timeslices).
    The conversion preserves temporal coverage and duration weightings.
    
    Parameters
    ----------
    snapshots : pd.DatetimeIndex or pd.Index
        PyPSA snapshot timestamps. Must contain datetime-like values that can be
        converted to pd.DatetimeIndex. The function extracts unique dates and times
        to construct the OSeMOSYS time structure.
    
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
    
    Notes
    -----
    Conversion algorithm:
    
    1. **Extract years**: Identify unique years from snapshot timestamps
    2. **Create DayTypes**: Group snapshot dates into non-overlapping day-of-year ranges
    3. **Create DailyTimeBrackets**: Group snapshot times into non-overlapping time-of-day ranges
    4. **Form Timeslices**: Create cartesian product of DayTypes × DailyTimeBrackets
    5. **Map snapshots**: Associate each snapshot with corresponding (year, timeslice) pairs
    6. **Validate**: Ensure timeslices partition each year completely (sum to 8760/8784 hours)
    
    The resulting structure uses:
    
    - Placeholder season 'X' (PyPSA snapshots don't inherently contain seasonal structure)
    - DayTypes capturing day-of-year granularity from snapshot dates
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
    Created 8760 timeslices
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
    >>> print(f"DayTypes: {len(result.daytypes)}")
    DayTypes: 365  # One per day
    >>> print(f"DailyTimeBrackets: {len(result.dailytimebrackets)}")
    DailyTimeBrackets: 2  # 06:00-18:00 and 18:00-06:00
    >>> print(f"Timeslices: {len(result.timeslices)}")
    Timeslices: 730  # 365 days × 2 brackets
    
    Export to OSeMOSYS CSV files:
    
    >>> result = to_timeslices(snapshots)
    >>> csv_dict = result.export()
    >>> import os
    >>> os.makedirs('osemosys_scenario', exist_ok=True)
    >>> for filename, df in csv_dict.items():
    ...     df.to_csv(f'osemosys_scenario/{filename}.csv', index=False)
    >>> print(f"Created {len(csv_dict)} CSV files")
    Created 7 CSV files
    
    Multi-year conversion:
    
    >>> snapshots = pd.date_range('2025-01-01', '2027-12-31', freq='D')
    >>> result = to_timeslices(snapshots)
    >>> print(f"Years: {result.years}")
    Years: [2025, 2026, 2027]
    >>> for year in result.years:
    ...     timeslices = result.get_timeslices_for_year(year)
    ...     total_hours = sum(ts.duration_hours(year) for ts in timeslices)
    ...     print(f"{year}: {total_hours:.0f} hours")
    2025: 8760 hours
    2026: 8760 hours
    2027: 8760 hours
    
    Handle mapping for downstream use:
    
    >>> result = to_timeslices(snapshots)
    >>> # Map PyPSA time-series data to OSeMOSYS timeslices
    >>> pypsa_generation = network.generators_t.p  # Time-indexed Series
    >>> for snapshot, value in pypsa_generation.items():
    ...     year_timeslice_pairs = result.snapshot_to_timeslice[snapshot]
    ...     for year, timeslice in year_timeslice_pairs:
    ...         # Process mapping
    ...         pass
    
    See Also
    --------
    to_snapshots : Convert OSeMOSYS timeslices to PyPSA snapshots (inverse operation)
    TimesliceResult : Container class for conversion results
    create_daytypes_from_dates : Helper for creating day-of-year ranges
    create_timebrackets_from_times : Helper for creating time-of-day ranges
    create_map : Helper for mapping snapshots to timeslices
    DayType : Day-of-year range structure
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
    daytypes: Set[DayType] = set()
    dailytimebrackets: Set[DailyTimeBracket] = set()
    seasons: Set[str] = set("X") # snapshots to timeslices never creates seasons
    
    # 3. Remove time component and create daytypes from dates
    unique_dates = sorted(set(ts.date() for ts in snapshots))
    daytypes = create_daytypes_from_dates(unique_dates)

    # 4. Remove date component and create dailytimebrackets from times
    unique_times = sorted(set(ts.time() for ts in snapshots))
    dailytimebrackets = create_timebrackets_from_times(unique_times)
    
    # 5. Create timeslice for each combination
    timeslices = []
    for dt in sorted(daytypes):
        for dtb in sorted(dailytimebrackets):
            ts = Timeslice(
                season="X",
                daytype=dt,
                dailytimebracket=dtb,
            )
            timeslices.append(ts)
    
    # 6. Map snapshots to timeslices
    snapshot_map = create_map(snapshots, timeslices)
    
    result = TimesliceResult(
        years=years,
        seasons=seasons,
        daytypes=daytypes,
        dailytimebrackets=dailytimebrackets,
        timeslices=timeslices,
        snapshot_to_timeslice=snapshot_map,
    )

    if not result.validate_coverage():
        raise ValueError(
            "Timeslice structure does not cover the entire year"
        )

    return result

def to_snapshots(source: Union[TimeComponent, str],
                 multi_investment_periods: bool = True) -> SnapshotResult:
    """
    Convert OSeMOSYS hierarchical timeslice structure to PyPSA snapshots.
    
    Transforms OSeMOSYS's categorical time representation (timeslices with
    hierarchical season/daytype/bracket structure) into PyPSA's sequential
    snapshot representation with duration weightings.
    
    Parameters
    ----------
    source : TimeComponent or str
        Source of OSeMOSYS time structure.
        
        - If **TimeComponent**: Uses an initialized TimeComponent object.
          Recommended when building scenarios programmatically.
        - If **str**: Path to directory containing OSeMOSYS CSV files.
          Required files: YEAR.csv, TIMESLICE.csv, YearSplit.csv.
          Recommended for converting existing CSV-based scenarios.
    
    multi_investment_periods : bool, default True
        Whether to create multi-period snapshots.
        
        - If True: Creates MultiIndex with ('period', 'timestep') levels,
          enabling multi-year capacity expansion modeling.
        - If False: Creates flat Index with 'timestep' level only.
          Requires single year in source data.
    
    Returns
    -------
    SnapshotResult
        Container with snapshots (time indices) and weightings (durations in hours),
        ready for application to a PyPSA Network.
    
    Raises
    ------
    TypeError
        If source is neither TimeComponent nor str.
    ValueError
        If multi_investment_periods=False but multiple years are present.
    ValueError
        If snapshot weightings do not sum to correct hours per year.
    FileNotFoundError
        If source is str but required CSV files are missing.
    
    Examples
    --------
    Convert from programmatic TimeComponent:
    
    >>> from pyoscomp.scenario.components.time import TimeComponent
    >>> time = TimeComponent('scenario/')
    >>> time.add_time_structure(
    ...     years=[2025, 2030],
    ...     seasons={'Winter': 182, 'Summer': 183},
    ...     daytypes={'Weekday': 5, 'Weekend': 2},
    ...     brackets={'Day': 12, 'Night': 12}
    ... )
    >>> result = to_snapshots(time)
    >>> result.apply_to_network(network)
    
    Convert from existing CSV files:
    
    >>> result = to_snapshots('path/to/osemosys_scenario/')
    >>> print(result.snapshots)
    MultiIndex([(2025, 'Winter_Weekday_Day'), ...])
    >>> print(result.weightings.sum())
    17520.0  # 2 years × 8760 hours
    
    Single-period model:
    
    >>> result = to_snapshots('single_year_scenario/', multi_investment_periods=False)
    >>> print(result.snapshots)
    Index(['Winter_Weekday_Day', 'Winter_Weekday_Night', ...], dtype='object', name='timestep')
    
    See Also
    --------
    to_timeslices : Convert PyPSA snapshots to OSeMOSYS timeslices (inverse operation)
    SnapshotResult : Container class for conversion results
    TimeComponent : OSeMOSYS time structure builder
    """
    # 1. Normalize input to TimeComponent
    if isinstance(source, str):
        time_component = TimeComponent(source)
        time_component.load()
    elif isinstance(source, TimeComponent):
        time_component = source
    else:
        raise TypeError(
            f"source must be TimeComponent or str path to scenario directory, got {type(source)}"
        )
    
    # 2. Extract data from TimeComponent
    years = time_component.years_df['VALUE'].tolist()
    timeslice_names = time_component.timeslices_df['VALUE'].tolist()
    yearsplit_df = time_component.yearsplit_df

    # 3. Create multi-index snapshots
    if multi_investment_periods:
        snapshots = pd.MultiIndex.from_product(
            [years, timeslice_names],
            names=['period', 'timestep']
        )
    else:
        # Single period, flat index
        if len(years) > 1:
            raise ValueError(
                "multi_investment_periods=False requires single year, "
                f"got {len(years)} years"
            )
        snapshots = pd.Index(timeslice_names, name='timestep')

    # 4. Create weightings (duration in hours)
    weightings_dict = {}
    for _, row in yearsplit_df.iterrows():
        year = row['YEAR']
        timeslice = row['TIMESLICE']
        fraction = row['VALUE']
        hours = fraction * hours_in_year(year)
        
        if multi_investment_periods:
            key = (year, timeslice)
        else:
            key = timeslice
        
        weightings_dict[key] = hours
    
    weightings = pd.Series(weightings_dict)
    weightings = weightings.reindex(snapshots)  # Ensure alignment
    
    # 5. Create and validate result
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