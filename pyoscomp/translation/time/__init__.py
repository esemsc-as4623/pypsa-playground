# pyoscomp/translation/time/__init__.py

"""
Time translation handling submodule for PyPSA-OSeMOSYS Comparison Framework.
"""

from .constants import TOL, TIMEPRECISION, ENDOFDAY, is_leap_year, hours_in_year, days_in_month
from .structures import DayType, DailyTimeBracket, Timeslice
from .translate import to_timeslices, to_snapshots

__all__ = [
    'TOL',
    'TIMEPRECISION',
    'ENDOFDAY',
    'DayType', 
    'DailyTimeBracket', 
    'Timeslice', 
    'to_timeslices',
    'to_snapshots',
    'is_leap_year',
    'hours_in_year',
    'days_in_month',
]