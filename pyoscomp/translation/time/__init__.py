# pyoscomp/translation/time/__init__.py

"""
Time translation handling submodule for PyPSA-OSeMOSYS Comparison Framework.
"""

from .structures import DayType, DailyTimeBracket, Timeslice
from .translate import to_timeslices, to_snapshots
from .results import TimesliceResult, SnapshotResult

__all__ = [
    'TOL',
    'TIMEPRECISION',
    'ENDOFDAY',
    'DayType', 
    'DailyTimeBracket', 
    'Timeslice', 
    'TimesliceResult',
    'SnapshotResult',
    'to_timeslices',
    'to_snapshots',
    'is_leap_year',
    'hours_in_year',
    'days_in_year',
    'days_in_month',
]