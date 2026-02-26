# pyoscomp/translation/time/translate.py

import pandas as pd
from datetime import datetime, time, date, timedelta
from typing import List, Set, Union

from ...constants import ENDOFDAY, hours_in_year
from .structures import Season, DayType, DailyTimeBracket, Timeslice
from .results import TimesliceResult, SnapshotResult
from ...interfaces.containers import ScenarioData


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


def create_seasons_from_dates(dates: List[date]) -> set[Season]:
    """
    Create non-overlapping Season objects from a list of dates.

    Takes a list of calendar dates and partitions the year into non-overlapping
    month(s)-of-year ranges. Each input date represents a SINGLE MONTH Season, with
    gaps between dates filled by multi-month Seasons. Start and end of year boundaries
    are handled automatically.

    Parameters
    ----------
    dates: List[date]
        List of datetime.date objects representing specific days of interest.
        If January or December are not included, boundary Seasons will be added
        automatically.

    Returns
    -------
    Set[Season]
        Set of Season objects that partition the year (Jan 1 - Dec 31).
        Includes:
        
        - Single-month Seasons for each input date
        - Multi-month Seasons for gaps between consecutive dates
        - Boundary Seasons for start/end of year if needed

    Notes
    -----
    Algorithm details:

    - Each input date becomes a 1-month Season
    - Non-consecutive dates are separated by multi-month Seasons covering the gap
    - Start-of-year (Jan 1) and end-of-year (Dec 31) boundaries are added if missing
    - The resulting Seasons form a complete, non-overlapping partition of the year

    The function ensures complete coverage of all 365/366 days with no gaps or overlaps.

    Examples
    --------
    Create Seasons from specific dates:

    >>> from datetime import date
    >>> dates = [date(2025, 1, 1), date(2025, 6, 1), date(2025, 12, 31)]
    >>> seasons = create_seasons_from_dates(dates)
    >>> for s in sorted(seasons):
    ...     print(f"{s.name}: {s.duration_months()} months")
    01 to 01: 1 months in 2025  # Jan (single month)
    02 to 05: 4 months in 2025  # Feb - May (gap)
    06 to 06: 1 months in 2025  # Jun (single month)
    07 to 12: 6 months in 2025  # Jul - Dec (gap)

    Consecutive dates (no gaps):

    >>> dates = [date(2025, 1, 1), date(2025, 2, 1), date(2025, 3, 1)]
    >>> seasons = create_seasons_from_dates(dates)
    >>> len(seasons)
    4  # Three 1-month Seasons + one multi-month Season for rest of year

    See Also
    --------
    Season : The month(s)-of-year range structure created by this function
    create_daytypes_from_dates : Analogous function for creating day(s)-of-month(s) ranges
    create_timebrackets_from_times : Analogous function for creating time-of-day ranges
    """
    seasons = set()
    
    unique_months = sorted(set(d.month for d in dates))

    # add start of year boundary
    if unique_months[0] != 1:
        seasons.add(Season(
            month_start=1,
            month_end=unique_months[0] - 1
        )) # min 1 month, max 11 months if dates[0].month = 12
    
    for i in range(len(unique_months)):
        # add each unique month as one season
        seasons.add(Season(
            month_start=unique_months[i],
            month_end=unique_months[i]
        )) # 1 month

        # if next month is not consecutive
        if i < len(unique_months) - 1 and unique_months[i+1] > unique_months[i] + 1:
            # add group of missing months as one season
            seasons.add(Season(
                month_start=unique_months[i] + 1,
                month_end=unique_months[i+1] - 1
            ))
    
    # add end of year boundary
    if unique_months[-1] != 12:
        seasons.add(Season(
            month_start=unique_months[-1] + 1,
            month_end=12
        )) # min 1 month, max 11 months if dates[-1].month = 1
    
    return seasons


def create_daytypes_from_dates(dates: List[date]) -> set[DayType]:
    """
    Create non-overlapping DayType objects from a list of dates.
    
    Takes a list of calendar dates and partitions the year into non-overlapping
    day(s)-of-month(s) ranges. Each input date represents a SINGLE DAY DayType, with
    gaps between dates filled by multi-day DayTypes. Start and end of month boundaries
    are handled automatically. Maximum duration of 7 days is enforced in DayType
    constructor.
    
    Parameters
    ----------
    dates : List[date]
        List of datetime.date objects representing specific days of interest.
        If the first or last day of a month are not included, boundary DayTypes will be
        added automatically.
    
    Returns
    -------
    Set[DayType]
        Set of DayType objects that partition a month.
        Includes:
        
        - Single-day DayTypes for each input date
        - Multi-day DayTypes for gaps between consecutive dates
        - Boundary DayTypes for start/end of month if needed
    
    Notes
    -----
    Algorithm details:
    
    - All dates are normalized to month January for maximum inclusivity (31 days)
    - Each input date becomes a 1-day DayType
    - Non-consecutive dates are separated by multi-day DayTypes covering the gap
    - Start-of-month (1st day) and end-of-month (last day) boundaries are added if missing
    - The resulting DayTypes form a complete, non-overlapping partition of a month
    
    The function ensures complete coverage of all 28/29/30/31 days with no gaps or overlaps.
    
    Examples
    --------
    Create DayTypes from specific dates:
    
    >>> from datetime import date
    >>> dates = [date(2025, 1, 1), date(2025, 6, 1), date(2025, 12, 31)]
    >>> daytypes = create_daytypes_from_dates(dates)
    >>> for dt in sorted(daytypes):
    ...     for y in set(d.year for d in dates):
    ...         for m in set(d.month for d in dates):
    ...             print(f"{dt.name}: {dt.duration_days(y, m)} days in {y}-{m:02d}")
    ...         print("---")
    01 to 01: 1 days in 2025-01  # Jan 1 (single day)
    02 to 08: 7 days in 2025-01  # Jan 2 - Jan 8 (gap)
    09 to 15: 7 days in 2025-01  # Jan 9 - Jan 15 (gap)
    16 to 22: 7 days in 2025-01  # Jan 16 - Jan 22 (gap)
    23 to 29: 7 days in 2025-01  # Jan 23 - Jan 29 (gap)
    30 to 30: 1 days in 2025-01  # Jan 30 - Jan 30 (gap)
    31 to 31: 1 days in 2025-01  # Jan 31 - Jan 31 (single day)
    ---
    01 to 01: 1 days in 2025-06  # Jun 1 (single day)
    02 to 08: 7 days in 2025-06  # Jun 2 - Jun 8 (gap)
    09 to 15: 7 days in 2025-06  # Jun 9 - Jun 15 (gap)
    16 to 22: 7 days in 2025-06  # Jun 16 - Jun 22 (gap)
    23 to 29: 7 days in 2025-06  # Jun 23 - Jun 29 (gap)
    30 to 31: 1 days in 2025-06  # Jun 30 - Jun 30 (gap)
    31 to 31: 0 days in 2025-06  # Jun 31 - Jun 31 (non-existent day, zero duration)
    ---
    01 to 01: 1 days in 2025-12  # Dec 1 (single day)
    02 to 08: 7 days in 2025-12  # Dec 2 - Dec 8 (gap)
    09 to 15: 7 days in 2025-12  # Dec 9 - Dec 15 (gap)
    16 to 22: 7 days in 2025-12  # Dec 16 - Dec 22 (gap)
    23 to 29: 7 days in 2025-12  # Dec 23 - Dec 29 (gap)
    30 to 30: 1 days in 2025-12   # Dec 30 - Dec 30 (gap)
    31 to 31: 1 days in 2025-12   # Dec 31 - Dec 31 (single day)
    ---
    
    Consecutive dates (no gaps):
    
    >>> dates = [date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 3)]
    >>> daytypes = create_daytypes_from_dates(dates)
    >>> len(daytypes)
    7 # Three 1-day DayTypes + four multi-day DayTypes for rest of month,
    # each with max duration of 7 days, i.e. 04 to 10, 11 to 17, 18 to 24, 25 to 31
    
    Handles leap years:
    
    >>> dates = [date(2024, 2, 29)]  # Leap day
    >>> daytypes = create_daytypes_from_dates(dates)
    >>> dt_feb29 = [dt for dt in daytypes if dt.month_start == 2 and dt.day_start == 29][0]
    >>> dt_feb29.duration_days(2024, 2)  # Leap year
    1
    >>> dt_feb29.duration_days(2025, 2)  # Non-leap year
    0
    
    See Also
    --------
    DayType : The day(s)-of-month(s) range structure created by this function
    create_seasons_from_dates : Analogous function for creating month(s)-of-year ranges
    create_timebrackets_from_times : Analogous function for creating time-of-day ranges
    """
    daytypes = set()

    unique_days = sorted(set(d.day for d in dates))

    # add start of month boundary
    if unique_days[0] != 1:
        start_day = 1
        end_day = min(start_day + 6, unique_days[0] - 1) # max 6 days to enforce max duration of 7 days in DayType
        while end_day < unique_days[0] and start_day <= end_day:
            daytypes.add(DayType(
                day_start=start_day,
                day_end=end_day
            )) # min 1 day, max 7 days
            start_day = end_day + 1
            # until and including day before first unique day
            end_day = min(start_day + 6, unique_days[0] - 1)

    for i in range(len(unique_days)):
        # add each unique day as one daytype
        daytypes.add(DayType(
            day_start=unique_days[i],
            day_end=unique_days[i]
        )) # 1 day

        # if next date is not consecutive
        if i < len(unique_days) - 1 and unique_days[i+1] > unique_days[i] + 1:
            # add group of missing days as one daytype, with max duration of 7 days
            start_day = unique_days[i] + 1
            end_day = min(start_day + 6, unique_days[i+1] - 1) # max 6 days to enforce max duration of 7 days in DayType
            while end_day < unique_days[i+1] and start_day <= end_day:
                daytypes.add(DayType(
                    day_start=start_day,
                    day_end=end_day
                )) # min 1 day, max 7 days
                start_day = end_day + 1
                # until and including day before next unique day
                end_day = min(start_day + 6, unique_days[i+1] - 1)

    # add end of month boundary
    if dates[-1] != 31:
        start_day = unique_days[-1] + 1
        end_day = min(start_day + 6, 31) # max 6 days to enforce max duration of 7 days in DayType
        while end_day <= 31 and start_day <= end_day:
            daytypes.add(DayType(
                day_start=start_day,
                day_end=end_day
            )) # min 1 day, max 7 days
            start_day = end_day + 1
            end_day = min(start_day + 6, 31)

    return daytypes


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
    Created 8 CSV files
    
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