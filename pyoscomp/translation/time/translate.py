# pyoscomp/translation/time/translate.py

import pandas as pd
import numpy as np
from datetime import time
from typing import Tuple

from .structures import DayType, DailyTimeBracket, TIMEPRECISION

def to_timeslices(snapshots: pd.DatetimeIndex | pd.Index):
    """
    Docstring for to_timeslices
    
    :param snapshots: Description
    :type snapshots: pd.DatetimeIndex | pd.Index
    """
    seasons, daytypes, dailytimebrackets = {}, {}, {}
    snapshots = pd.to_datetime(snapshots).sort_values()
    years = sorted(snapshots.year.unique().tolist())

    # Case 1: One snapshot
    # 1 daytype per year, 1 dailytimebracket per year
    # timeslices = daytype x dailytimebracket = 1 
    if len(snapshots) < 2:
        daytypes.add(
            DayType(
                month_start=1,
                day_start=1,
                month_end=12,
                day_end=31,
                name="ALL-YEAR"
            )
        )
        dailytimebrackets.add(
                DailyTimeBracket(
                hour_start=time(0, 0, 0),
                hour_end=time(23, 59, 59, TIMEPRECISION),
                name="ALL-DAY"
            )
        )
        return years, {}, daytypes, dailytimebrackets
    
    delta = snapshots[1:] - snapshots[:-1]

    # Case 2: Annual or coarser
    # 1 daytype per year, 1 dailytimebracket per day = 1 timeslice per year
    min_delta_years = (delta / np.timedelta64(1, 'Y')).min()

    if min_delta_years >= 1:
        daytypes.add(
            DayType(
                month_start=1,
                day_start=1,
                month_end=12,
                day_end=31,
                name="ALL-YEAR"
            )
        )
        dailytimebrackets.add(
            DailyTimeBracket(
                hour_start=time(0, 0, 0),
                hour_end=time(23, 59, 59, TIMEPRECISION),
                name="ALL-DAY"
            )
        )
        return years, {}, daytypes, dailytimebrackets

    # Case 3: Daily or coarser
    # k daytype per year, 1 dailytimebracket per day = k timeslice per year
    min_delta_days = (delta / np.timedelta64(1, 'D')).min()

    # add year boundaries to discrete (month, day) tuples
    unique_month_days = sorted(set((ts.month, ts.day) for ts in snapshots))
    all_boundaries = [(1, 1)]  # start of year
    all_boundaries.extend(unique_month_days)
    if (12, 31) not in all_boundaries:
        all_boundaries.append((12, 31)) # end of year
    all_boundaries = sorted(set(all_boundaries))

    for i in range(len(all_boundaries)-1):
        start_month, start_day = all_boundaries[i]
        end_month, end_day = all_boundaries[i + 1]
        
        daytypes.add(
            DayType(
                month_start=start_month,
                day_start=start_day,
                month_end=end_month,
                day_end=end_day
            )
        )
    
    if min_delta_days >= 1:
        dailytimebrackets.add(
            DailyTimeBracket(
                hour_start=time(0, 0, 0),
                hour_end=time(23, 59, 59, TIMEPRECISION),
                name="ALL-DAY"
            )
        )
        return years, {}, daytypes, dailytimebrackets
    
    # Case 4: Subdaily
    # k daytype per year, m dailytimebracket per day = k*m timeslice per year
    
    # add day boundaries to discrete times
    unique_times = sorted(set(ts.time() for ts in snapshots))
    if time(0, 0, 0) not in unique_times:
        unique_times = [time(0, 0, 0)] + unique_times

    for i in range(len(unique_times)):
        start = unique_times[i]
        if i + 1 < len(unique_times):
            end = unique_times[i + 1]
        else:
            # Last bracket extends to end of day
            end = time(23, 59, 59, TIMEPRECISION)
        
        dailytimebrackets.add(
            DailyTimeBracket(
                hour_start=start,
                hour_end=end
            )
        )
    return years, seasons, daytypes, dailytimebrackets

def to_snapshots(timeslices: Tuple[set, set, set]):
    """
    Docstring for to_snapshots
    
    :param timeslices: Description
    :type timeslices: Tuple[set, set, set]
    """

    pass