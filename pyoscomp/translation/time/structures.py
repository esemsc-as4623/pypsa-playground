# pyoscomp/translation/time/structures.py

import pandas as pd
from datetime import time, date, datetime
from typing import Tuple, Union
from dataclasses import dataclass, field

from ...constants import ENDOFDAY, days_in_month, hours_in_year


@dataclass
class DailyTimeBracket:
    """
    Time-of-day range structure (day- and year-agnostic).
    
    Represents a bracket within a 24-hour day using half-open interval [start, end),
    except when end=ENDOFDAY which represents inclusive 23:59:59.999999.
    
    Attributes
    ----------
    hour_start : time
        Start time of the bracket (inclusive).
    hour_end : time
        End time of the bracket (exclusive, unless ENDOFDAY).
    name : str, optional
        Bracket name. Auto-generated if not provided (e.g., "T0600_1200").
    """
    hour_start: time
    hour_end: time
    name: str = field(default="")

    def __post_init__(self):
        self.validate()
        if not self.name:
            if self.is_full_day():
                self.name = "DAY"
            else:
                end_str = "24:00" if self.hour_end == ENDOFDAY else self.hour_end.strftime('%H%M')
                self.name = f"{self.hour_start.strftime('%H:%M')} to {end_str}"
    
    def validate(self):
        """
        Validate hour_start is before hour_end.
        
        Raises
        ------
        ValueError
            If hour_start >= hour_end (excluding ENDOFDAY case).
        """
        if self.hour_end != ENDOFDAY:
            if self.hour_start >= self.hour_end:
                raise ValueError(
                    f"hour_start ({self.hour_start}) must be before hour_end ({self.hour_end})"
                )

    @classmethod
    def from_string(cls, time_str: str) -> 'DailyTimeBracket':
        """
        Create DailyTimeBracket from string like "06:00-18:00".
        
        Parameters
        ----------
        time_str : str
            Time range in format "HH:MM-HH:MM"
        
        Returns
        -------
        DailyTimeBracket
        
        Examples
        --------
        >>> bracket = DailyTimeBracket.from_string("06:00-18:00")
        >>> bracket.duration_hours()
        12.0
        """
        start_str, end_str = time_str.split('-')
        hour_start = time.fromisoformat(start_str)
        if end_str == "24:00":
            hour_end = ENDOFDAY
        else:
            hour_end = time.fromisoformat(end_str)
        return cls(hour_start=hour_start, hour_end=hour_end)

    def is_full_day(self) -> bool:
        """
        Check if bracket covers full 24-hour day.
        
        Returns
        -------
        bool
            True if bracket is 00:00:00 to 23:59:59.999999.
        """
        return (self.hour_start == time(0, 0, 0) and 
                self.hour_end == ENDOFDAY)
    
    def contains_time(self, t: time) -> bool:
        """
        Check if a time falls within this bracket.
        
        Parameters
        ----------
        t : time
            Time to check.
        
        Returns
        -------
        bool
            True if t is in [hour_start, hour_end).
        """
        if self.hour_end == ENDOFDAY:
            return self.hour_start <= t
        return self.hour_start <= t < self.hour_end
    
    def duration_hours(self) -> float:
        """
        Calculate bracket duration in hours.
        
        Returns
        -------
        float
            Duration in hours (e.g., 12.0 for noon to midnight).
        """
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
    
    def __repr__(self):
        return f"DailyTimeBracket({self.hour_start!r}, {self.hour_end!r}, name={self.name!r})"


@dataclass
class DayType:
    """
    Day-of-month range structure (year-agnostic).
    
    Represents a date range within a month, season, group of months using closed interval [start, end].
    Automatically handles days-in-month and leap year adjustments.
    
    Attributes
    ----------
    day_start : int
        Start day (1-31).
    day_end : int
        End day (1-31).
    name : str, optional
        DayType name. Auto-generated if not provided (e.g., "01-01 to 08-15").
    """
    day_start: int
    day_end: int
    max_days = 7 # Max days represented by a DayType
    name: str = field(default="")

    def __post_init__(self):
        self.validate()
        # Initialize the name attribute if not provided
        if not self.name:
            self.name = f"{self.day_start:02d} to {self.day_end:02d}"

    def validate(self):
        """Validate month/day combinations."""
        if not (1 <= self.day_start <= 31):
            raise ValueError(f"day_start must be 1-31, got {self.day_start}")
        if not (1 <= self.day_end <= 31):
            raise ValueError(f"day_end must be 1-31, got {self.day_end}")
        if self.day_start > self.day_end:
            raise ValueError("Start day must be less than or equal to end day." \
            "Month-wrapping day types not supported.")
        if self.day_end - self.day_start > self.max_days:
            raise ValueError(f"DayType range cannot exceed {self.max_days} days. Got {self.day_start} to {self.day_end}.")
    
    @classmethod
    def from_string(cls, s: str) -> 'DayType':
        """
        Create DayType from string like "01-15" or "01 to 15".
    
        Parameters
        ----------
        s : str
            String in format "DD-DD" or "DD to DD" (e.g., "01-15" or "01 to 15").
    
        Returns
        -------
        DayType
            DayType instance for the given range.
    
        Examples
        --------
        >>> DayType.from_string("15-15")
        DayType(15 to 15) # single-day
        >>> DayType.from_string("03-06")
        DayType(03 to 06) # multi-day
        """
        try:
            if "to" in s:
                d1, d2 = s.split('to')
            else:
                d1, d2 = s.split('-')
            d1 = d1.strip()
            d2 = d2.strip()
        except Exception as e:
            raise ValueError(f"Invalid DayType string: '{s}'. Expected format 'DD-DD' or 'DD to DD'.") from e
        return cls(day_start=int(d1), day_end=int(d2))
    
    def is_one_day(self) -> bool:
        """Check if the day range represents a single day."""
        return self.day_start == self.day_end
    
    def to_dates(self, year: int, month: int) -> Union[Tuple[date, date], Tuple[int, int]]:
        """
        Convert to actual date objects for a specific year.
        
        ----------
        year : int
            Year to generate dates for.
        month: int
            Month to generate dates for (1-12).
        
        Returns
        -------
        Tuple[date, date] or Tuple[int, int]
            (start_date, end_date) for the specified year and month.
            (-1, -1) if the day range is invalid for that month/year (e.g., Feb 29 in non-leap year, Apr 31, etc.).
        """
        # Get actual maximum number of days in year and month
        max_day = days_in_month(year, month)

        if self.day_start > max_day:
            return -1, -1
        
        day_start = self.day_start
        day_end = min(max_day, self.day_end)
        
        return date(year, month, day_start), date(year, month, day_end)
    
    def contains_date(self, d: date) -> bool:
        """
        Check if a date falls within this DayType range.
        
        Parameters
        ----------
        d : date
            Date to check.
        
        Returns
        -------
        bool
            True if d is within [start, end] for that year.
        """
        return d.day >= self.day_start and d.day <= self.day_end
    
    def duration_days(self, year: int, month: int) -> int:
        """
        Calculate number of days in this DayType for a specific year and month.
        
        Parameters
        ----------
        year : int
            Year to calculate for.
        month: int
            Month to calculate for (1-12).
        
        Returns
        -------
        int
            Number of days (0 if Feb 29 DayType in non-leap year).
        """
        assert year >= 1, "Year must be a positive integer."
        
        start, end = self.to_dates(year, month)
        if start == -1:
            return 0
        return (end - start).days + 1  # +1 for closed interval
    
    def __hash__(self):
        """Compute hash based on start and end day."""
        return hash((self.day_start, self.day_end))
    
    def __eq__(self, other):
        """Check equality based on start and end month/day."""
        if not isinstance(other, DayType):
            return False
        return (self.day_start == other.day_start and
                self.day_end == other.day_end)
    
    def __lt__(self, other):
        """Enable sorting by start date."""
        if not isinstance(other, DayType):
            return NotImplemented
        return (self.day_start) < (other.day_start)
    
    def __repr__(self):
        return f"DayType({self.day_start} to {self.day_end})"


@dataclass
class Season:
    """
    Month(s)-of-year structure (year-agnostic).
    
    Represents a month range within a calendar year using closed interval [start, end].
    
    Attributes
    ----------
    month_start : int
        Start month (1-12).
    month_end : int
        End month (1-12).
    name : str, optional
        Season name. Auto-generated if not provided (e.g., "01 to 03").
    """
    month_start: int
    month_end: int
    name: str = field(default="")

    def __post_init__(self):
        self.validate()
        if not self.name:
            if self.is_full_year():
                self.name = "YEAR"
            else:
                self.name = f"{self.month_start:02d} to {self.month_end:02d}"

    def validate(self):
        """Validate month range."""
        if not (1 <= self.month_start <= 12):
            raise ValueError("month_start must be between 1 and 12.")
        if not (1 <= self.month_end <= 12):
            raise ValueError("month_end must be between 1 and 12.")
        if self.month_start > self.month_end:
            raise ValueError("Start month must be less than or equal to end month." \
            "Year-wrapping seasons not supported.")
        
    @classmethod
    def from_string(cls, s: str) -> 'Season':
        """
        Create Season from string like "01-03" or "01 to 03".

        Parameters
        ----------
        s : str
            String in format "MM-MM" or "MM to MM" (e.g., "01-03" or "01 to 03").

        Returns
        -------
        Season
            Season instance for the given range.

        Examples
        --------
        >>> Season.from_string("03-03")
        Season(03 to 03) # single-month
        >>> Season.from_string("06 to 10")
        Season(06 to 10) # multi-month
        >>> Season.from_string("01 to 12")
        Season(01 to 12) # full-year
        """
        try:
            if "to" in s:
                m1, m2 = s.split('to')
            else:
                m1, m2 = s.split('-')
            m1 = m1.strip()
            m2 = m2.strip()
        except Exception as e:
            raise ValueError(f"Invalid Season string: '{s}'. Expected format 'MM-MM' or 'MM to MM'.") from e
        return cls(month_start=int(m1), month_end=int(m2))
    
    def is_full_year(self) -> bool:
        """Check if the month range covers the full year."""
        return (self.month_start == 1 and self.month_end == 12)
    
    def is_one_month(self) -> bool:
        """Check if the month range represents a single month."""
        return self.month_start == self.month_end
    
    def duration_months(self) -> int:
        """
        Calculate number of months in this Season.
        
        Returns
        -------
        int
            Number of months (e.g., 3 for Jan-Mar).
        """
        return self.month_end - self.month_start + 1
    
    def __hash__(self):
        """Compute hash based on start and end months"""
        return hash((self.month_start, self.month_end))
    
    def __eq__(self, other):
        """Check equality based on start and end months"""
        if not isinstance(other, Season):
            return False
        return (self.month_start == other.month_start and
                self.month_end == other.month_end)
    
    def __lt__(self, other):
        """Enable sorting by start month"""
        if not isinstance(other, Season):
            return NotImplemented
        return (self.month_start) < (other.month_start)
    
    def __repr__(self):
        return f"Season({self.month_start} to {self.month_end})"


@dataclass
class Timeslice:
    """
    OSeMOSYS temporal slice combining month(s)-of-year, day(s)-of-month(s), and time-of-day(s).
    
    Represents the hierarchical time structure in OSeMOSYS models:
    Season → DayType → DailyTimeBracket.
    
    Attributes
    ----------
    daytype : DayType
        Day-of-year range component.
    dailytimebracket : DailyTimeBracket
        Time-of-day range component.
    season : str, default "X"
        Season identifier ("X" used as placeholder when no seasons defined).
    """
    daytype: DayType
    dailytimebracket: DailyTimeBracket
    season: Season
    
    @property
    def name(self) -> str:
        """
        Generate OSeMOSYS-compatible timeslice name.
        
        Returns
        -------
        str
            Format: "[Season]_[DayType]_[DailyTimeBracket]" (e.g., "[01 to 01]_[10 to 15]_[06:00 to 12:00]").
        """
        return f"[{self.season.name}]_[{self.daytype.name}]_[{self.dailytimebracket.name}]"
    
    @property
    def hour_start(self) -> time:
        return self.dailytimebracket.hour_start
    
    @property
    def hour_end(self) -> time:
        return self.dailytimebracket.hour_end
    
    def duration_hours(self, year: int) -> float:
        """
        Calculate total duration of this timeslice in a specific year.
        
        Parameters
        ----------
        year : int
            Year to calculate for.
        
        Returns
        -------
        float
            Duration in hours (days × hours_per_day).
        """
        assert year >= 1, "Year must be a positive integer."
        
        total_days = 0
        for month in range(self.season.month_start, self.season.month_end + 1):
            total_days += self.daytype.duration_days(year, month)
        hours_per_day = self.dailytimebracket.duration_hours()
        return total_days * hours_per_day
    
    def year_fraction(self, year: int) -> float:
        """
        Calculate fraction of year for OSeMOSYS YearSplit parameter.
        
        Parameters
        ----------
        year : int
            Year to calculate for.
        
        Returns
        -------
        float
            Fraction of total year hours (duration_hours / 8760 or 8784).
        """
        return self.duration_hours(year) / hours_in_year(year)
    
    def contains_timestamp(self, ts: Union[pd.Timestamp, datetime]) -> bool:
        """
        Check if a timestamp falls within this timeslice.
        
        Parameters
        ----------
        ts : pd.Timestamp or datetime
            Timestamp to check.
        
        Returns
        -------
        bool
            True if timestamp's date is in daytype AND time is in dailytimebracket.
        """
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