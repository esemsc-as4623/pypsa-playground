# pyoscomp/translation/time/__init__.py

"""
Time translation handling submodule for PyPSA-OSeMOSYS Comparison Framework.
"""

from .structures import TIMEPRECISION, ENDOFDAY, DayType, DailyTimeBracket, Timeslice #, Conversion
from .translate import to_timeslices, to_snapshots

__all__ = [
    'TIMEPRECISION',
    'ENDOFDAY',
    'DayType', 
    'DailyTimeBracket', 
    'Timeslice', 
    'to_timeslices',
    'to_snapshots',
]