# pyoscomp/translation/time/structures.py

import pandas as pd
from datetime import time, date, datetime
from typing import Tuple, Optional, Union
from dataclasses import dataclass, field

from .constants import ENDOFDAY, days_in_month, is_leap_year, hours_in_year


@dataclass
class DailyTimeBracket:
    """
    Represents a time-of-day range (day- and year-agnostic).
    Uses half-open interval [start, end).
    ENDOFDAY means "up to and including 23:59:59.999999".
    """
    hour_start: time
    hour_end: time
    name: str = field(default="")

    def __post_init__(self):
        self.validate()
        if not self.name:
            if self.is_full_day():
                self.name = "DAY"
            end_str = "24:00" if self.hour_end == ENDOFDAY else self.hour_end.strftime('%H%M')
            self.name = f"T{self.hour_start.strftime('%H%M')}_{end_str}"
    
    def validate(self):
        """Validate hour_start is before hour_end."""
        if self.hour_end != ENDOFDAY:
            if self.hour_start >= self.hour_end:
                raise ValueError(
                    f"hour_start ({self.hour_start}) must be before hour_end ({self.hour_end})"
                )

    def is_full_day(self) -> bool:
        """Check if the time range covers the full day."""
        return (self.hour_start == time(0, 0, 0) and 
                self.hour_end == ENDOFDAY)
    
    def contains_time(self, t: time) -> bool:
        """Check if a time falls within this bracket [start, end)."""
        if self.hour_end == ENDOFDAY:
            return self.hour_start <= t
        return self.hour_start <= t < self.hour_end
    
    def duration_hours(self) -> float:
        """Return the duration of this bracket in hours."""
        start_seconds = self.hour_start.hour * 3600 + self.hour_start.minute * 60 + self.hour_start.second
        if self.hour_end == ENDOFDAY:
            end_seconds = 24 * 3600
        else:
            end_seconds = self.hour_end.hour * 3600 + self.hour_end.minute * 60 + self.hour_end.second
        return (end_seconds - start_seconds) / 3600
    
    def __hash__(self):
        """Compute hash based on start and end times."""
        return hash((self.hour_start, self.hour_end))
    
    def __eq__(self, other):
        """Check equality based on start and end times."""
        if not isinstance(other, DailyTimeBracket):
            return False
        return (self.hour_start == other.hour_start and 
                self.hour_end == other.hour_end)
    
    def __lt__(self, other):
        """Enable sorting by start time."""
        if not isinstance(other, DailyTimeBracket):
            return NotImplemented
        return self.hour_start < other.hour_start


@dataclass
class DayType:
    """
    Represents a day-of-year range (year-agnostic).
    Uses closed interval [start, end].
    """
    month_start: int 
    day_start: int
    month_end: int
    day_end: int
    name: str = field(default="")

    def __post_init__(self):
        self.validate()
        # Initialize the name attribute if not provided
        if not self.name:
            if self.is_full_year():
                self.name = "YEAR"
            else:
                self.name = f"{self.month_start:02d}-{self.day_start:02d} to {self.month_end:02d}-{self.day_end:02d}"

    def validate(self):
        """Validate month/day combinations."""
        # Month validation
        if not (1 <= self.month_start <= 12):
            raise ValueError(f"month_start must be 1-12, got {self.month_start}")
        if not (1 <= self.month_end <= 12):
            raise ValueError(f"month_end must be 1-12, got {self.month_end}")
        
        # Day validation (use max possible days, accounting for leap years)
        max_day_start = 29 if self.month_start == 2 else days_in_month(2000, self.month_start)
        max_day_end = 29 if self.month_end == 2 else days_in_month(2000, self.month_end)
        
        if not (1 <= self.day_start <= max_day_start):
            raise ValueError(f"day_start must be 1-{max_day_start} for month {self.month_start}, got {self.day_start}")
        if not (1 <= self.day_end <= max_day_end):
            raise ValueError(f"day_end must be 1-{max_day_end} for month {self.month_end}")
        
        # Prevent year-wrapping intervals
        start_ordinal = (self.month_start, self.day_start)
        end_ordinal = (self.month_end, self.day_end)
        if start_ordinal > end_ordinal:
            raise ValueError(
                f"Year-wrapping intervals not supported. "
                f"Start {start_ordinal} > End {end_ordinal}"
            )
        
    def is_full_year(self) -> bool:
        """Check if the day range covers the full year."""
        return (self.month_start == 1 and self.day_start == 1 and 
                self.month_end == 12 and self.day_end == 31)
    
    def to_dates(self, year: int) -> Tuple[date, date]:
        """Convert to actual dates for a specific year."""
        start = date(year, self.month_start, self.day_start)
        # Handle Feb 29 in non-leap years
        day_end = self.day_end
        if self.month_end == 2 and self.day_end == 29 and not is_leap_year(year):
            day_end = 28
        
        end = date(year, self.month_end, day_end)
        return start, end
    
    def contains_date(self, d: date) -> bool:
        """Check if a date falls within this daytype range."""
        start, end = self.to_dates(d.year)
        return start <= d <= end
    
    def duration_days(self, year: int) -> int:
        """Return the number of days covered by this daytype in a given year."""
        assert year >= 1, "Year must be a positive integer."
        start, end = self.to_dates(year)
        return (end - start).days + 1  # +1 for closed interval
    
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
    
    def __lt__(self, other):
        """Enable sorting by start date."""
        if not isinstance(other, DayType):
            return NotImplemented
        return (self.month_start, self.day_start) < (other.month_start, other.day_start)
    

@dataclass
class Timeslice:
    """
    Represents a specific temporal slice combining season, daytype, and time bracket.
    """
    season: Optional[str] = "X"  # Placeholder for no season
    daytype: DayType
    dailytimebracket: DailyTimeBracket
    
    @property
    def name(self) -> str:
        """Generate OSeMOSYS-compatible timeslice name."""
        return f"{self.season}_{self.daytype.name}_{self.dailytimebracket.name}"
    
    @property
    def hour_start(self) -> time:
        return self.dailytimebracket.hour_start
    
    @property
    def hour_end(self) -> time:
        return self.dailytimebracket.hour_end
    
    def get_day_start(self, d: date) -> date:
        return self.daytype.to_dates(d.year)[0]
    
    def get_day_end(self, d: date) -> date:
        return self.daytype.to_dates(d.year)[1]
    
    def duration_hours(self, year: int) -> float:
        """Return total duration in hours."""
        assert year >= 1, "Year must be a positive integer."
        days = self.daytype.duration_days(year)
        hours_per_day = self.dailytimebracket.duration_hours()
        return days * hours_per_day
    
    def year_fraction(self, year: int) -> float:
        """Return fraction of year (for OSeMOSYS YearSplit parameter)."""
        return self.duration_hours(year) / hours_in_year(year)
    
    def contains_timestamp(self, ts: Union[pd.Timestamp, datetime]) -> bool:
        """Check if a timestamp falls within this timeslice."""
        if hasattr(ts, 'to_pydatetime'):
            ts = ts.to_pydatetime()
        
        if not self.daytype.contains_date(ts.date()):
            return False
        if not self.dailytimebracket.contains_time(ts.time()):
            return False
        return True
    
    def __hash__(self):
        return hash((self.season, self.daytype, self.dailytimebracket))
    
    def __eq__(self, other):
        if not isinstance(other, Timeslice):
            return False
        return (self.season == other.season and
                self.daytype == other.daytype and 
                self.dailytimebracket == other.dailytimebracket)
    
    def __repr__(self):
        return f"Timeslice({self.name})"
    
    # def __len__(self) -> float:
    #     """Return duration in hours."""
    #     return self.duration_hours()