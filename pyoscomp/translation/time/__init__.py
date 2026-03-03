# pyoscomp/translation/time/__init__.py

"""
Time translation handling submodule for PyPSA-OSeMOSYS Comparison Framework.
"""

from .structures import Season, DayType, DailyTimeBracket, Timeslice
from .translate import to_timeslices, to_snapshots
from .results import TimesliceResult, SnapshotResult
from .helpers import (
    create_seasons_from_dates,
    create_daytypes_from_dates,
    create_timebrackets_from_times
)
from .mapping import create_map, create_endpoints

__all__ = [
    # Structures
    'Season',
    'DayType', 
    'DailyTimeBracket', 
    'Timeslice', 
    # Results
    'TimesliceResult',
    'SnapshotResult',
    # Functions
    'to_timeslices',
    'to_snapshots',
    # Helpers
    'create_seasons_from_dates',
    'create_daytypes_from_dates',
    'create_timebrackets_from_times',
    # Mapping
    'create_map',
    'create_endpoints',
]