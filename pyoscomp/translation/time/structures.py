# pyoscomp/translation/time/structures.py

import pandas as pd
from datetime import time, date, datetime, timedelta
from typing import Tuple, Optional, Union
from dataclasses import dataclass, field

TIMEPRECISION=999999
ENDOFDAY=time(23, 59, 59, TIMEPRECISION)

@dataclass
class DayType:
    """
    Represents a day-of-year range (year-agnostic).
    Uses half-open interval [start, end).
    """
    month_start: int 
    day_start: int
    month_end: int
    day_end: int
    name: str = field(default="")

    def __post_init__(self):
        # Attribute validation
        if not (1 <= self.month_start <= 12):
            raise ValueError(f"month_start must be 1-12, got {self.month_start}")
        if not (1 <= self.month_end <= 12):
            raise ValueError(f"month_end must be 1-12, got {self.month_end}")
        if self.month_start in [1,3,5,7,8,10,12]:
            max_day_start = 31
        elif self.month_start in [4,6,9,11]:
            max_day_start = 30
        elif self.month_start == 2:
            max_day_start = 29
        else:
            raise ValueError(f"Invalid month_start: {self.month_start}")
        if not (1 <= self.day_start <= max_day_start):
            raise ValueError(f"day_start must be 1-{max_day_start} for month {self.month_start}, got {self.day_start}")
        if self.month_end in [1,3,5,7,8,10,12]:
            max_day_end = 31
        elif self.month_end in [4,6,9,11]:
            max_day_end = 30
        elif self.month_end == 2:
            max_day_end = 29
        else:
            raise ValueError(f"Invalid month_end: {self.month_end}")
        if not (1 <= self.day_end <= max_day_end):
            raise ValueError(f"day_end must be 1-{max_day_end} for month {self.month_end}, got {self.day_end}")
        
        # Initialize the name attribute if not provided
        if not self.name:
            if self.is_full_year():
                self.name = "ALL-YEAR"
            else:
                self.name = f"{self.month_start:02d}-{self.day_start:02d} to {self.month_end:02d}-{self.day_end:02d}"

    def is_full_year(self) -> bool:
        """Check if the day range covers the full year."""
        return (self.month_start == 1 and self.day_start == 1 and 
                self.month_end == 12 and self.day_end == 31)
    
    def to_dates(self, year: int) -> Tuple[date, date]:
        """Convert to actual dates for a specific year."""
        start = date(year, self.month_start, self.day_start)
        # Handle end date carefully for month boundaries
        try:
            end = date(year, self.month_end, self.day_end)
        except ValueError:
            # Handle Feb 29 in non-leap years
            if self.month_end == 2 and self.day_end == 29:
                end = date(year, 2, 28)
            else:
                raise
        return start, end
    
    def contains_date(self, d: date) -> bool:
        """Check if a date falls within this daytype range."""
        start, end = self.to_dates(d.year)
        # explicitly only works for non-wrapping intervals
        return start <= d < end
    
    def __hash__(self):
        """Compute hash based on start and end month/day."""
        return hash((self.month_start, self.day_start, self.month_end, self.day_end))
    
    def __eq__(self, other):
        """Check equality based on start and end month/day."""
        if not isinstance(other, DayType):
            return False
        return (self.month_start == other.month_start and 
                self.day_start == other.day_start and
                self.month_end == other.month_end and 
                self.day_end == other.day_end)

@dataclass
class DailyTimeBracket:
    """
    Represents a time-of-day range (day- and year-agnostic).
    Uses half-open interval [start, end).
    """
    hour_start: time
    hour_end: time
    name: str = field(default="")

    def __post_init__(self):
        # Attribute validation
        if self.hour_end != ENDOFDAY:
            if self.hour_start >= self.hour_end:
                raise ValueError(
                    f"hour_start ({self.hour_start}) must be before hour_end ({self.hour_end})"
                )
        if not self.name:
            if self.is_full_day():
                self.name = "ALL-DAY"
            else:
                self.name = f"{self.hour_start.strftime('%H:%M')} to {self.hour_end.strftime('%H:%M')}"
    
    def is_full_day(self) -> bool:
        """Check if the time range covers the full day."""
        return (self.hour_start == time(0, 0, 0) and 
                self.hour_end == ENDOFDAY)
    
    def contains_time(self, t: time) -> bool:
        """Check if a time falls within this bracket [start, end)."""
        # Handle end-of-day
        if self.hour_end == ENDOFDAY:
            return self.hour_start <= t
        return self.hour_start <= t < self.hour_end
    
    def __hash__(self):
        """Compute hash based on start and end times."""
        return hash((self.hour_start, self.hour_end))
    
    def __eq__(self, other):
        """Check equality based on start and end times."""
        if not isinstance(other, DailyTimeBracket):
            return False
        return (self.hour_start == other.hour_start and 
                self.hour_end == other.hour_end)
    
@dataclass
class Timeslice:
    """
    Represents a specific temporal slice combining daytype, and time bracket.
    """
    year: int
    daytype: DayType
    dailytimebracket: DailyTimeBracket
    season: Optional[str] = None
    
    @property
    def day_start(self) -> date:
        """Get actual start date for this timeslice."""
        return self.daytype.to_dates(self.year)[0]
    
    @property
    def day_end(self) -> date:
        """Get actual end date for this timeslice."""
        return self.daytype.to_dates(self.year)[1]
    
    @property
    def hour_start(self) -> time:
        return self.dailytimebracket.hour_start
    
    @property
    def hour_end(self) -> time:
        return self.dailytimebracket.hour_end
    
    def __post_init__(self):
        # Attribute validation
        if not self.year > 0:
            raise ValueError(f"year must be positive, got {self.year}")
    
    def __len__(self) -> int:
        # YOU ARE CHECKING THIS
        """Return duration in hours."""
        dt_start = datetime.combine(self.day_start, self.hour_start)
        dt_end = datetime.combine(self.day_end, self.hour_end)
        if self.hour_end == ENDOFDAY:
            # Treat as full end of day
            dt_end = datetime.combine(self.day_end, time(0, 0, 0)) + timedelta(days=1)
        return int((dt_end - dt_start).total_seconds() // 3600)
    
    def contains_timestamp(self, ts: Union[pd.Timestamp, datetime]) -> bool:
        """Check if a timestamp falls within this timeslice."""
        if hasattr(ts, 'to_pydatetime'):
            ts = ts.to_pydatetime()

        # Check year
        if ts.year != self.year:
            return False
        
        # Check daytype
        if not self.daytype.contains_date(ts.date()):
            return False
        
        # Check dailytimebracket
        if not self.dailytimebracket.contains_time(ts.time()):
            return False
        
        return True
    
    def __hash__(self):
        return hash((self.year, self.daytype, self.dailytimebracket, self.season))
    
    def __eq__(self, other):
        if not isinstance(other, Timeslice):
            return False
        return (self.year == other.year and 
                self.daytype == other.daytype and 
                self.dailytimebracket == other.dailytimebracket and
                self.season == other.season)
    
    def __repr__(self):
        return (f"Timeslice(year={self.year}, daytype={self.daytype.name}, "
                f"bracket={self.dailytimebracket.name}, season={self.season})")

# @dataclass
# class Conversion:
#     """Container for the conversion result."""
#     years: List[int]
#     daytypes: List[DayType]
#     timebrackets: List[DailyTimeBracket]
#     timeslices: List[Timeslice]
#     mapping: Dict[int, int]  # snapshot_index -> timeslice_index