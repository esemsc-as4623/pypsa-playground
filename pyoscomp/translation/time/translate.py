# pyoscomp/translation/time/translate.py

import pandas as pd
import numpy as np
from datetime import time, date, timedelta
from typing import List, Set, Dict, Tuple, Union
from dataclasses import dataclass, field

from .constants import TOL, ENDOFDAY, hours_in_year
from .structures import DayType, DailyTimeBracket, Timeslice

@dataclass
class TimesliceResult:
    """Container for timeslice conversion results."""
    years: List[int]
    seasons: Set[str] = field(default_factory=lambda: set("X"))  # Placeholder season
    daytypes: Set[DayType]
    dailytimebrackets: Set[DailyTimeBracket]
    timeslices: List[Timeslice]

    snapshot_to_timeslice: Dict[pd.Timestamp, List[Timeslice]]
    timeslice_to_snapshots: Dict[Timeslice, pd.Timestamp]
    snapshot_to_timeslice_index: Dict[int, List[int]]
    timeslice_to_snapshot_index: Dict[int, int]

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
    
def infer_temporal_resolution(snapshots: pd.DatetimeIndex) -> str:
    """
    Infer the temporal resolution of snapshots.
    
    Returns one of: 'annual', 'monthly', 'daily', 'hourly', 'subhourly'
    """
    if len(snapshots) < 2:
        return 'annual'
    
    delta = snapshots[1:] - snapshots[:-1]
    min_delta = delta.min()
    
    if min_delta >= pd.Timedelta(days=365):
        return 'annual'
    elif min_delta >= pd.Timedelta(days=28):
        return 'monthly'
    elif min_delta >= pd.Timedelta(days=1):
        return 'daily'
    elif min_delta >= pd.Timedelta(hours=1):
        return 'hourly'
    else:
        return 'subhourly'

def create_full_day_bracket() -> DailyTimeBracket:
    """Create a time bracket covering the full day."""
    return DailyTimeBracket(
        hour_start=time(0, 0, 0),
        hour_end=ENDOFDAY,
        name="DAY"
    )

def create_full_year_daytype() -> DayType:
    """Create a daytype covering the full year."""
    return DayType(
        month_start=1, day_start=1,
        month_end=12, day_end=31,
        name="YEAR"
    )

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
        else:
            end = ENDOFDAY
        
        brackets.add(DailyTimeBracket(hour_start=start, hour_end=end))
    
    return brackets

# YOU ARE HERE
def create_daytypes_from_dates(dates: List[date]) -> set[DayType]:
    """
    Create overlapping daytypes from a list of dates.
    
    The dates represent the START of each daytype.
    The last daytype extends to Dec 31.
    """
    daytypes = set()
    year = dates[0].year

    # Set same year for all dates to get highest resolution daytypes
    temp_dates = sorted(set(date(year, d.month, d.day) for d in dates))

    # Create a full list of boundary points for daytype intervals
    all_points = []
    for d in temp_dates:
        all_points.append(d)
        # Add the day after, if it's not a duplicate
        if d + timedelta(days=1) not in temp_dates:
            all_points.append(d + timedelta(days=1))

    # Add start and end of year boundaries
    start_of_year = date(year, 1, 1)
    end_of_year = date(year, 12, 31)
    
    all_points.append(start_of_year)
    all_points.append(end_of_year)
    
    # Remove duplicates and sort
    all_points = sorted(list(set(all_points)))
    
    # Create daytypes from consecutive points
    for i in range(len(all_points) - 1):
        start_date = all_points[i]
        end_date = all_points[i+1] - timedelta(days=1)

        # Skip if start_date is after end_date (can happen with adjacent dates)
        if start_date > end_date:
            continue

        daytypes.add(DayType(
            month_start=start_date.month,
            day_start=start_date.day,
            month_end=end_date.month,
            day_end=end_date.day
        ))

    # Add the last day of the year if it's not covered
    if all_points[-1] <= end_of_year:
        last_day = all_points[-1]
        daytypes.add(DayType(
            month_start=last_day.month,
            day_start=last_day.day,
            month_end=last_day.month,
            day_end=last_day.day
        ))

    return daytypes

def create_endpoints(snapshots: Union[pd.DatetimeIndex, pd.Index]) -> pd.DatetimeIndex:
    """Create snapshot endpoints by filling start and end of year for each year in snapshots."""
    years = sorted(snapshots.year.unique().tolist())
    endpoints = []
    for year in years:
        start_of_year = pd.Timestamp.combine(date(year, 1, 1), time(0, 0, 0))
        end_of_year = pd.Timestamp.combine(date(year, 12, 31), ENDOFDAY)
        endpoints.append(start_of_year)
        endpoints.append(end_of_year)
    endpoints = list(snapshots) + endpoints
    endpoints = sorted(set(endpoints))
    return pd.DatetimeIndex(endpoints)
    

def to_timeslices(
    snapshots: Union[pd.DatetimeIndex, pd.Index],
    max_daytypes: int = 365
) -> TimesliceResult:
    """
    Convert PyPSA snapshots to OSeMOSYS timeslice structure.
    
    Parameters
    ----------
    snapshots : pd.DatetimeIndex | pd.Index
        PyPSA snapshot timestamps
    max_daytypes : int
        Maximum number of daytypes to create (will aggregate if exceeded)
    
    Returns
    -------
    TimesliceResult
        Container with all timeslice components and mapping
    """
    # Handle empty input
    if len(snapshots) == 0:
        raise ValueError("snapshots cannot be empty")
    
    # Convert and sort
    snapshots = pd.to_datetime(snapshots).sort_values()
    years = sorted(snapshots.year.unique().tolist())
    resolution = infer_temporal_resolution(snapshots)
    
    # Initialize containers
    daytypes: Set[DayType] = set()
    dailytimebrackets: Set[DailyTimeBracket] = set()
    seasons: Set[str] = set()
    
    # Case 1: Annual or coarser resolution
    if resolution == 'annual':
        daytypes.add(create_full_year_daytype())
        dailytimebrackets.add(create_full_day_bracket())
    
    # Case 2: Monthly resolution
    elif resolution == 'monthly':
        # Create one daytype per month present in data
        unique_months = sorted(set((ts.month,) for ts in snapshots))
        for (month,) in unique_months:
            # Full month daytype
            if month == 12:
                daytypes.add(DayType(
                    month_start=month, day_start=1,
                    month_end=12, day_end=31
                ))
            else:
                # End at last day of month (use leap year for max days)
                from calendar import monthrange
                _, last_day = monthrange(2000, month)  # 2000 is a leap year
                daytypes.add(DayType(
                    month_start=month, day_start=1,
                    month_end=month, day_end=last_day
                ))
        dailytimebrackets.add(create_full_day_bracket())
    
    # Case 3: Daily resolution
    elif resolution == 'daily':
        # Extract unique (month, day) combinations
        unique_month_days = sorted(set((ts.month, ts.day) for ts in snapshots))
        
        if len(unique_month_days) > max_daytypes:
            # Aggregate to monthly resolution
            unique_months = sorted(set(md[0] for md in unique_month_days))
            for month in unique_months:
                from calendar import monthrange
                _, last_day = monthrange(2000, month)
                daytypes.add(DayType(
                    month_start=month, day_start=1,
                    month_end=month, day_end=last_day
                ))
        else:
            daytypes = create_daytypes_from_boundaries(unique_month_days)
        
        dailytimebrackets.add(create_full_day_bracket())
    
    # Case 4: Hourly or subhourly resolution
    else:
        # Extract unique (month, day) for daytypes
        unique_month_days = sorted(set((ts.month, ts.day) for ts in snapshots))
        
        if len(unique_month_days) > max_daytypes:
            # Aggregate to monthly
            unique_months = sorted(set(md[0] for md in unique_month_days))
            for month in unique_months:
                from calendar import monthrange
                _, last_day = monthrange(2000, month)
                daytypes.add(DayType(
                    month_start=month, day_start=1,
                    month_end=month, day_end=last_day
                ))
        else:
            daytypes = create_daytypes_from_boundaries(unique_month_days)
        
        # Extract unique times for brackets
        unique_times = sorted(set(ts.time() for ts in snapshots))
        dailytimebrackets = create_timebrackets_from_times(unique_times)
    
    # Build timeslices and mapping
    timeslices = []
    snapshot_to_timeslice = {}
    
    # Create timeslice for each combination
    for year in years:
        for dt in sorted(daytypes):
            # Find season for this daytype
            season = None
            for s in seasons:
                if dt in s.daytypes:
                    season = s
                    break
            
            for dtb in sorted(dailytimebrackets):
                ts = Timeslice(
                    year=year,
                    daytype=dt,
                    dailytimebracket=dtb,
                    season=season
                )
                timeslices.append(ts)
    
    # Map snapshots to timeslices
    for snapshot in snapshots:
        for ts in timeslices:
            if ts.contains_timestamp(snapshot):
                snapshot_to_timeslice[snapshot] = ts
                break
    
    return TimesliceResult(
        years=years,
        seasons=seasons,
        daytypes=daytypes,
        dailytimebrackets=dailytimebrackets,
        timeslices=timeslices,
        snapshot_to_timeslice=snapshot_to_timeslice
    )

def aggregate_snapshots(
    data: pd.Series,
    result: TimesliceResult,
    method: callable = np.mean
) -> pd.DataFrame:
    """
    Aggregate a PyPSA timeseries to OSeMOSYS timeslice resolution.
    
    Parameters
    ----------
    data : pd.Series
        Time series indexed by snapshots
    result : TimesliceResult
        Output from to_timeslices()
    method : callable
        Aggregation method, e.g. np.mean, np.sum, np.max, np.min
    
    Returns
    -------
    pd.DataFrame
        Aggregated values with columns [TIMESLICE, YEAR, VALUE]
    """    
    # Group by timeslice
    timeslice_values = {}
    for snapshot, value in data.items():
        ts = result.snapshot_to_timeslice.get(snapshot)
        if ts is not None:
            key = (ts.name, ts.year)
            if key not in timeslice_values:
                timeslice_values[key] = []
            timeslice_values[key].append(value)
    
    rows = []
    for (ts_name, year), values in timeslice_values.items():
        rows.append({
            'TIMESLICE': ts_name,
            'YEAR': year,
            'VALUE': method(values)
        })
    
    return pd.DataFrame(rows)

def to_snapshots(timeslices: Tuple[set, set, set]):
    """
    Docstring for to_snapshots
    
    :param timeslices: Description
    :type timeslices: Tuple[set, set, set]
    """

    pass