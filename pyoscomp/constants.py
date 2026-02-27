# pyoscomp/constants.py

"""
Constants and utility functions for time translation.

This module defines tolerance values, time precision settings, and helper
functions for year/date calculations used throughout the time translation.
"""

from datetime import time
import calendar

# Tolerance for floating point comparisons
TOL = 1e-8

# Microsecond precision for representing "end of day" timestamp
TIMEPRECISION = 999999

# End of day: 23:59:59.999999 (inclusive upper bound for daily brackets)
ENDOFDAY = time(23, 59, 59, TIMEPRECISION)

# Hours per day
HOURS_PER_DAY = 24

# Hours per year (non-leap and leap)
HOURS_PER_YEAR = 8760
HOURS_PER_LEAP_YEAR = 8784
DAYS_PER_YEAR = 365
DAYS_PER_LEAP_YEAR = 366

def is_leap_year(year: int) -> bool:
    return calendar.isleap(year)

def hours_in_year(year: int) -> int:
    return HOURS_PER_LEAP_YEAR if is_leap_year(year) else HOURS_PER_YEAR

def days_in_year(year: int) -> int:
    return DAYS_PER_LEAP_YEAR if is_leap_year(year) else DAYS_PER_YEAR

def days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]