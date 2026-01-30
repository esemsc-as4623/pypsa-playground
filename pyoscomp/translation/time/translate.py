# pyoscomp/translation/time/translate.py

import pandas as pd
from datetime import time, date, timedelta
from typing import List, Set, Dict, Union, Tuple
from dataclasses import dataclass, field

from .constants import TOL, ENDOFDAY, hours_in_year
from .structures import DayType, DailyTimeBracket, Timeslice


@dataclass
class TimesliceResult:
    """Container for timeslice conversion results."""
    years: List[int]
    daytypes: Set[DayType]
    dailytimebrackets: Set[DailyTimeBracket]
    timeslices: List[Timeslice]
    snapshot_to_timeslice: Dict[pd.Timestamp, List[Tuple[int, Timeslice]]]
    seasons: Set[str] = field(default_factory=lambda: set("X"))  # Placeholder season

    def validate_coverage(self) -> bool:
        """Validate that timeslices partition the year completely."""
        for year in self.years:
            total_hours = sum(
                ts.duration_hours(year) 
                for ts in self.timeslices
            )
            expected_hours = hours_in_year(year)
            if abs(total_hours - expected_hours) > TOL:
                return False
        return True
    
    def get_timeslices_for_year(self, year: int) -> List[Timeslice]:
        """Get all unique timeslices used in a specific year."""
        timeslices_in_year = set()
        for ts_list in self.snapshot_to_timeslice.values():
            for y, ts in ts_list:
                if y == year:
                    timeslices_in_year.add(ts)
        return list(timeslices_in_year)
    
    def export(self) -> Dict[str, pd.DataFrame]:
        """Generate OSeMOSYS-compatible CSV dataframes."""
        result = {}
        
        # YEAR.csv
        result['YEAR'] = pd.DataFrame({'VALUE': self.years})
        
        # SEASON.csv
        result['SEASON'] = pd.DataFrame({'VALUE': list(self.seasons)})
        
        # DAYTYPE.csv
        daytype_names = sorted(set(dt.name for dt in self.daytypes))
        result['DAYTYPE'] = pd.DataFrame({'VALUE': daytype_names})
        
        # DAILYTIMEBRACKET.csv
        bracket_names = sorted(set(dtb.name for dtb in self.dailytimebrackets))
        result['DAILYTIMEBRACKET'] = pd.DataFrame({'VALUE': bracket_names})

        # TIMESLICE.csv - unique timeslice names
        timeslice_names = sorted(set(ts.name for ts in self.timeslices))
        result['TIMESLICE'] = pd.DataFrame({'VALUE': timeslice_names})
        
        # YearSplit - fraction of year for each timeslice per year
        year_split_rows = []
        for year in self.years:
            for ts in self.timeslices:
                year_split_rows.append({
                    'TIMESLICE': ts.name,
                    'YEAR': year,
                    'VALUE': ts.year_fraction(year)
                })
        result[f'YearSplit'] = pd.DataFrame(year_split_rows)

        # DaySplit - length of one timebracket in one specific day as a fraction of the year
        day_split_rows = []
        for year in self.years:
            for ts in self.timeslices:
                day_split_rows.append({
                    'TIMESLICE': ts.name,
                    'YEAR': year,
                    'VALUE': ts.dailytimebracket.duration_hours() / hours_in_year(year)
                })
        result[f'DaySplit'] = pd.DataFrame(day_split_rows)
        
        return result


def create_timebrackets_from_times(times: List[time]) -> Set[DailyTimeBracket]:
    """
    Create non-overlapping dailytimebrackets from a list of times.
    
    The times represent the START of each bracket.
    The last bracket extends to ENDOFDAY.
    """
    brackets = set()
    times = sorted(set(times))
    
    # Ensure midnight is the first time
    if times[0] != time(0, 0, 0):
        times = [time(0, 0, 0)] + times
    
    for i in range(len(times)):
        start = times[i]
        
        if i + 1 < len(times):
            end = times[i + 1]
            # if within 1 minute of ENDOFDAY, assume ENDOFDAY
            if timedelta(ENDOFDAY.hour - end.hour, ENDOFDAY.minute - end.minute, ENDOFDAY.second - end.second) <= timedelta(minutes=1):
                end = ENDOFDAY
                break
        else:
            end = ENDOFDAY
        
        brackets.add(DailyTimeBracket(hour_start=start, hour_end=end))
    
    return brackets


def create_daytypes_from_dates(dates: List[date]) -> set[DayType]:
    """
    Create overlapping daytypes from a list of dates.
    
    The dates represent the START of each daytype.
    The last daytype extends to Dec 31.
    """
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
    Create snapshot endpoints.
    
    Add start of year and end of year for each year in snapshots.
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
    Map each PyPSA sequential snapshot to a list of (year, timeslice) tuples.
    
    :param snapshots: PyPSA snapshot timestamps
    :param timeslices: List of OSeMOSYS hierarchical timeslice structures

    :return: Dictionary mapping each PyPSA snapshot timestamp to list of (year, timeslice) tuples
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
                # Get start and end time based on timeslice definition and each valid_year
                start_date, end_date = ts.daytype.to_dates(y)
                start_time = pd.Timestamp.combine(start_date, ts.dailytimebracket.hour_start)
                end_time = pd.Timestamp.combine(end_date, ts.dailytimebracket.hour_end)
                timeslice_timedelta = end_time - start_time
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
                f"Representation Mismatch! snapshot duration = {snapshot_timedelta}, timeslice duration = {total_timedelta}"
                f"\n(year, timeslice) pairs = {[(y, timeslices[j]) for (y, j) in idx_list]}"
                f"\n(year, index) pairs = {idx_list}"
            )
        snapshot_to_timeslice[snapshots[i]] = [(y, timeslices[j]) for (y, j) in idx_list]

    return snapshot_to_timeslice


def to_timeslices(snapshots: Union[pd.DatetimeIndex, pd.Index]) -> TimesliceResult:
    """
    Convert PyPSA sequential snapshots to OSeMOSYS hierarchical timeslice structure.
    
    :param snapshots: PyPSA snapshot timestamps

    :return: TimesliceResult container with all timeslice components and mapping
    """
    # Handle empty input
    if len(snapshots) == 0:
        raise ValueError("snapshots cannot be empty")
    
    # Convert and sort
    snapshots = pd.DatetimeIndex(pd.to_datetime(snapshots)).sort_values()
    years = sorted(snapshots.year.unique().tolist())
    
    # Initialize containers
    daytypes: Set[DayType] = set()
    dailytimebrackets: Set[DailyTimeBracket] = set()
    seasons: Set[str] = set("X") # snapshots to timeslices never creates seasons
    
    # Remove time component and create daytypes from dates
    unique_dates = sorted(set(ts.date() for ts in snapshots))
    daytypes = create_daytypes_from_dates(unique_dates)

    # Remove date component and create dailytimebrackets from times
    unique_times = sorted(set(ts.time() for ts in snapshots))
    dailytimebrackets = create_timebrackets_from_times(unique_times)
    
    # Build timeslices and mapping
    timeslices = []
    
    # Create timeslice for each combination
    for dt in sorted(daytypes):
        for dtb in sorted(dailytimebrackets):
            ts = Timeslice(
                season="X",
                daytype=dt,
                dailytimebracket=dtb,
            )
            timeslices.append(ts)
    
    # Map snapshots to timeslices
    map = create_map(snapshots, timeslices)
    
    return TimesliceResult(
        years=years,
        seasons=seasons,
        daytypes=daytypes,
        dailytimebrackets=dailytimebrackets,
        timeslices=timeslices,
        snapshot_to_timeslice=map,
    )

# def aggregate_to_timeslices(
#     data: pd.Series,
#     result: TimesliceResult,
#     method: callable = np.mean
# ) -> pd.DataFrame:
#     """
#     Aggregate a PyPSA timeseries to OSeMOSYS timeslice resolution.
    
#     :param data: Time series indexed by snapshots
#     :param result: Output from to_timeslices()
#     :param method: Aggregation method, e.g. np.mean, np.sum, np.max, np.min
#     :return: Aggregated values with columns [TIMESLICE, YEAR, VALUE]
#     """ 
#     # Group by timeslice
#     timeslice_values = {}
#     for snapshot, value in data.items():
#         ts = result.snapshot_to_timeslice.get(snapshot)
#         if ts is not None:
#             key = (ts.name, ts.year)
#             if key not in timeslice_values:
#                 timeslice_values[key] = []
#             timeslice_values[key].append(value)
    
#     rows = []
#     for (ts_name, year), values in timeslice_values.items():
#         rows.append({
#             'TIMESLICE': ts_name,
#             'YEAR': year,
#             'VALUE': method(values)
#         })
    
#     return pd.DataFrame(rows)

# def to_snapshots(timeslices: Tuple[set, set, set]):
#     """
#     Docstring for to_snapshots
    
#     :param timeslices: Description
#     :type timeslices: Tuple[set, set, set]
#     """

#     pass