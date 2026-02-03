# pyoscomp/translation/time/constants.py

from datetime import time
import calendar

TOL = 1e-8 # tolerance for floating point comparisons of total hours
TIMEPRECISION=999999 # microsecond precision for end of day
ENDOFDAY=time(23, 59, 59, TIMEPRECISION)
HOURS_PER_YEAR = 8760
HOURS_PER_LEAP_YEAR = 8784

def is_leap_year(year: int) -> bool:
    return calendar.isleap(year)

def hours_in_year(year: int) -> int:
    return HOURS_PER_LEAP_YEAR if is_leap_year(year) else HOURS_PER_YEAR

def days_in_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]