# tests/test_translation/test_helpers.py

import pytest
from datetime import time, date, timedelta

from pyoscomp.constants import ENDOFDAY, days_in_month
from pyoscomp.translation.time.structures import Season, DayType, DailyTimeBracket
from pyoscomp.translation.time.translate import create_seasons_from_dates, create_daytypes_from_dates, create_timebrackets_from_times


class TestCreateSeasonsFromDates:
    """Tests for create_seasons_from_dates helper function."""
    
    # ========== Single Date ==========
    
    def test_single_date_mid_year(self):
        """Test single date in middle of year."""
        dates = [date(2020, 6, 15)]
        seasons = create_seasons_from_dates(dates)
        
        # Should create 3 seasons: Jan to May, Jun, Jul to Dec
        assert len(seasons) == 3
        
        # Verify coverage
        season_list = sorted(seasons)
        assert season_list[0] == Season(1, 5)  # Before
        assert season_list[1] == Season(6, 6)  # Target date
        assert season_list[2] == Season(7, 12)  # After
    
    def test_single_date_jan_1(self):
        """Test single date on Jan 1."""
        dates = [date(2020, 1, 1)]
        seasons = create_seasons_from_dates(dates)
        
        # Should create 2 seasons: Jan, Feb to Dec
        assert len(seasons) == 2
        
        season_list = sorted(seasons)
        assert season_list[0] == Season(1, 1)  # Jan
        assert season_list[1] == Season(2, 12)  # Rest of year
    
    def test_single_date_dec_31(self):
        """Test single date on Dec 31."""
        dates = [date(2020, 12, 31)]
        seasons = create_seasons_from_dates(dates)
        
        # Should create 2 seasons: Jan to Nov, Dec
        assert len(seasons) == 2
        
        season_list = sorted(seasons)
        assert season_list[0] == Season(1, 11)  # Most of year
        assert season_list[1] == Season(12, 12)  # Dec
    
    # ========== Consecutive Dates ==========
    
    def test_consecutive_dates(self):
        """Test consecutive dates create individual seasons."""
        dates = [date(2020, 6, 15), date(2020, 6, 16), date(2020, 6, 17)]
        seasons = create_seasons_from_dates(dates)
        
        # Should create 3 seasons: before, Jun, after
        assert len(seasons) == 3
        
        season_list = sorted(seasons)
        assert season_list[0] == Season(1, 5)  # Before
        assert season_list[1] == Season(6, 6)  # Jun
        assert season_list[2] == Season(7, 12)  # After
    
    def test_consecutive_dates_full_week(self):
        """Test full week of consecutive dates."""
        dates = [date(2020, 3, i) for i in range(1, 8)]  # March 1-7
        seasons = create_seasons_from_dates(dates)
        
        # Should create: before, Mar, after
        assert len(seasons) == 3
        
        # Check individual days exist
        season_list = sorted(seasons)
        assert season_list[0] == Season(1, 2)  # Before
        assert season_list[1] == Season(3, 3)  # Mar
        assert season_list[2] == Season(4, 12)  # After
    
    # ========== Gapped Dates ==========
    
    def test_gapped_dates_simple(self):
        """Test gapped dates create gap-fill seasons."""
        dates = [date(2020, 6, 1), date(2020, 6, 5)]
        seasons = create_seasons_from_dates(dates)
        
        # Should create: before, Jun, after
        assert len(seasons) == 3
        
        season_list = sorted(seasons)
        assert season_list[0] == Season(1, 5)  # Before
        assert season_list[1] == Season(6, 6)  # Jun
        assert season_list[2] == Season(7, 12)  # After
    
    def test_gapped_dates_large_gap(self):
        """Test large gap between dates."""
        dates = [date(2020, 1, 15), date(2020, 12, 15)]
        seasons = create_seasons_from_dates(dates)
        
        # Should create: Jan, middle months, Dec
        assert len(seasons) == 3
        
        season_list = sorted(seasons)
        assert season_list[0] == Season(1, 1)  # Jan
        assert season_list[1] == Season(2, 11)  # Middle months
        assert season_list[2] == Season(12, 12)  # Dec

    def test_gapped_dates_multiple_gaps(self):
        """Test multiple gaps create multiple gap-fill seasons."""
        dates = [date(2020, 3, 1), date(2020, 3, 5), date(2020, 3, 10)]
        seasons = create_seasons_from_dates(dates)
        
        # Should create: before, Mar, after
        assert len(seasons) == 3
        
        season_list = sorted(seasons)
        assert season_list[0] == Season(1, 2)  # Before Mar 1
        assert season_list[1] == Season(3, 3)  # Mar
        assert season_list[2] == Season(4, 12)  # After Mar 10

    # ========== Multi-month Dates ==========

    def test_multi_month_consecutive(self):
        """Test consecutive multi-month dates create individual seasons."""
        dates = [date(2020, 3, 1), date(2020, 4, 1), date(2020, 5, 1)]
        seasons = create_seasons_from_dates(dates)
        
        # Should create: before, Mar, Apr, May, after
        assert len(seasons) == 5
        
        season_list = sorted(seasons)
        assert season_list[0] == Season(1, 2)  # Before Mar
        assert season_list[1] == Season(3, 3)  # Mar
        assert season_list[2] == Season(4, 4)  # Apr
        assert season_list[3] == Season(5, 5)  # May
        assert season_list[4] == Season(6, 12)  # After May

    def test_multi_month_gapped(self):
        """Test multi-month dates with gaps create correct seasons."""
        dates = [date(2020, 3, 1), date(2020, 6, 1)]
        seasons = create_seasons_from_dates(dates)
        
        # Should create: before, Mar, gap (Apr-May), Jun, after
        assert len(seasons) == 5
        
        season_list = sorted(seasons)
        assert season_list[0] == Season(1, 2)  # Before Mar
        assert season_list[1] == Season(3, 3)  # Mar
        assert season_list[2] == Season(4, 5)  # Gap: Apr-May
        assert season_list[3] == Season(6, 6)  # Jun
        assert season_list[4] == Season(7, 12)  # After Jun

    def test_multi_month_multi_day_gapped(self):
        """Test multi-month dates with multiple days and gaps create correct seasons."""
        dates = [date(2020, 3, 1), date(2020, 3, 15), date(2020, 6, 1), date(2020, 6, 15)]
        seasons = create_seasons_from_dates(dates)

        # Should create: before, Mar, gap (Apr-May), Jun, after
        assert len(seasons) == 5

        season_list = sorted(seasons)
        assert season_list[0] == Season(1, 2)  # Before Mar
        assert season_list[1] == Season(3, 3)  # Mar
        assert season_list[2] == Season(4, 5)  # Gap: Apr-May
        assert season_list[3] == Season(6, 6)  # Jun
        assert season_list[4] == Season(7, 12)  # After Jun

    # ========== Start of Year Boundary ==========
    
    def test_start_of_year_jan_1(self):
        """Test that Jan 1 start doesn't create empty before-season."""
        dates = [date(2020, 1, 1), date(2020, 1, 15)]
        seasons = create_seasons_from_dates(dates)
        
        # Should create: Jan, after
        assert len(seasons) == 2
        
        season_list = sorted(seasons)
        assert season_list[0] == Season(1, 1)  # Jan
        assert season_list[1] == Season(2, 12)  # After Jan

    def test_start_of_year_jan_15(self):
        """Test that Jan 15 start doesn't create empty before-season."""
        dates = [date(2020, 1, 15)]
        seasons = create_seasons_from_dates(dates)
        
        # Should create: Jan, after
        assert len(seasons) == 2
        
        season_list = sorted(seasons)
        assert season_list[0] == Season(1, 1)  # Jan
        assert season_list[1] == Season(2, 12) # After
    
    def test_start_of_year_mid_year(self):
        """Test mid-year start creates full before-season."""
        dates = [date(2020, 6, 1)]
        seasons = create_seasons_from_dates(dates)
        
        # Should create: before, Jun, after
        assert len(seasons) == 3
        
        season_list = sorted(seasons)
        assert season_list[0] == Season(1, 5)  # Full before
        assert season_list[1] == Season(6, 6)  # Jun
        assert season_list[2] == Season(7, 12)  # After
    
    # ========== End of Year Boundary ==========
    
    def test_end_of_year_dec_31(self):
        """Test that Dec 31 end doesn't create empty after-season."""
        dates = [date(2020, 12, 15), date(2020, 12, 31)]
        seasons = create_seasons_from_dates(dates)
        
        # Should create: before, Dec
        assert len(seasons) == 2
        
        season_list = sorted(seasons)
        assert season_list[0] == Season(1, 11)  # Before Dec
        assert season_list[1] == Season(12, 12)  # Dec
        
    def test_end_of_year_dec_20(self):
        """Test that Dec 20 end doesn't create empty after-season."""
        dates = [date(2020, 12, 20)]
        seasons = create_seasons_from_dates(dates)

        # Should create: before, Dec
        assert len(seasons) == 2
        
        season_list = sorted(seasons)
        assert season_list[0] == Season(1, 11)  # Before
        assert season_list[1] == Season(12, 12)  # Dec
    
    def test_end_of_year_mid_year(self):
        """Test mid-year end creates full after-season."""
        dates = [date(2020, 6, 30)]
        seasons = create_seasons_from_dates(dates)
        
        # Should create: before, Jun, after
        assert len(seasons) == 3
        
        season_list = sorted(seasons)
        assert season_list[0] == Season(1, 5)  # Before Jun
        assert season_list[1] == Season(6, 6)  # Jun
        assert season_list[2] == Season(7, 12)  # After Jun
    
    # ========== Year-Wrapping Prevention ==========
    
    def test_year_wrapping_dec_to_jan(self):
        """Test that Dec 31 doesn't wrap to Jan 1."""
        dates = [date(2020, 12, 31), date(2021, 1, 1)]
        seasons = create_seasons_from_dates(dates)
        
        # Function takes unique months regardless of years
        assert len(seasons) == 3

        # Should create Jan, gap, Dec
        season_list = sorted(seasons)
        assert season_list[0] == Season(1, 1)  # Jan
        assert season_list[1] == Season(2, 11)  # Gap
        assert season_list[2] == Season(12, 12)  # Dec
    
    def test_year_wrapping_validation(self):
        """Test that seasons don't attempt year wrapping."""
        # Any dates that would cause year-wrapping should be prevented
        # by the function's selection of unique months
        dates = [date(2020, 12, 25), date(2021, 1, 5)]
        seasons = create_seasons_from_dates(dates)
        
        for s in seasons:
            # Verify no season wraps year
            start_ordinal = date(2000, s.month_start, 1).toordinal()
            end_ordinal = date(2000, s.month_end, days_in_month(2000, s.month_end)).toordinal()
            assert start_ordinal <= end_ordinal, f"Season {s} wraps year"
    
    # ========== Leap Year Dates ==========
    
    def test_leap_year_feb_29(self):
        """Test Feb 29 handling in leap year context."""
        dates = [date(2020, 2, 29)]
        seasons = create_seasons_from_dates(dates)
        
        # Should create: before, Feb, after
        assert len(seasons) == 3
        
        season_list = sorted(seasons)
        assert season_list[0] == Season(1, 1)  # Before
        assert season_list[1] == Season(2, 2)  # Feb
        assert season_list[2] == Season(3, 12)  # After
    
    def test_leap_year_feb_28_29(self):
        """Test consecutive dates around Feb 29."""
        dates = [date(2020, 2, 28), date(2020, 2, 29)]
        seasons = create_seasons_from_dates(dates)
        
        # Should create: before, Feb, after
        assert len(seasons) == 3
        
        season_list = sorted(seasons)
        assert season_list[0] == Season(1, 1)  # Before
        assert season_list[1] == Season(2, 2)  # Feb
        assert season_list[2] == Season(3, 12)  # After
    
    def test_leap_year_normalization(self):
        """Test that function uses leap year (2000) for normalization."""
        # Input dates from non-leap year, but Feb 29 should still be valid
        dates = [date(2021, 2, 28), date(2021, 3, 1)]
        seasons = create_seasons_from_dates(dates)
        
        # Should create: before, Feb, Mar, after
        assert len(seasons) == 4

        season_list = sorted(seasons)
        assert season_list[0] == Season(1, 1)  # Before
        assert season_list[1] == Season(2, 2)  # Feb
        assert season_list[2] == Season(3, 3)  # Mar
        assert season_list[3] == Season(4, 12)  # After
    
    # ========== Edge Cases ==========
    
    def test_duplicate_dates_ignored(self):
        """Test that duplicate dates are handled correctly."""
        dates = [date(2020, 6, 15), date(2020, 6, 15), date(2020, 6, 15)]
        seasons = create_seasons_from_dates(dates)
        
        # Should be same as single date
        assert len(seasons) == 3
        assert Season(6, 6) in seasons
    
    def test_unsorted_dates(self):
        """Test that unsorted dates are handled correctly."""
        dates = [date(2020, 7, 20), date(2020, 6, 10), date(2020, 6, 15)]
        seasons = create_seasons_from_dates(dates)
        
        # Should produce same result as sorted dates
        season_list = sorted(seasons)
        assert season_list[0] == Season(1, 5)  # Before
        assert season_list[1] == Season(6, 6)  # Ju
        assert season_list[2] == Season(7, 7)  # Jul
        assert season_list[3] == Season(8, 12)  # After
    
    def test_different_input_years_normalized(self):
        """Test that dates from different years are normalized."""
        dates = [date(2020, 6, 15), date(2021, 9, 20), date(2025, 3, 10)]
        seasons = create_seasons_from_dates(dates)
        
        # Creates: before, Mar, gap, Jun, gap, Sep, after
        assert len(seasons) == 7
        season_list = sorted(seasons)
        assert season_list[0] == Season(1, 2)  # Before
        assert season_list[1] == Season(3, 3)  # Mar
        assert season_list[2] == Season(4, 5)  # Gap: Apr-May
        assert season_list[3] == Season(6, 6)  # Jun
        assert season_list[4] == Season(7, 8)  # Gap: Jul-Aug
        assert season_list[5] == Season(9, 9)  # Sep
        assert season_list[6] == Season(10, 12)  # After
    
    # ========== Coverage Validation ==========
    
    def test_coverage_full_year_single_date(self):
        """Test that single date produces full year coverage."""
        dates = [date(2020, 6, 15)]
        seasons = create_seasons_from_dates(dates)
        
        # Sum durations should equal full year
        total_months = sum(season.duration_months() for season in seasons)
        assert total_months == 12  # Full year in months
    
    def test_coverage_full_year_multiple_dates(self):
        """Test that multiple dates produce full year coverage."""
        dates = [date(2020, 3, 10), date(2020, 6, 15), date(2020, 9, 20)]
        seasons = create_seasons_from_dates(dates)
        
        # Sum durations should equal full year
        total_months = sum(season.duration_months() for season in seasons)
        assert total_months == 12  # Full year in months
    
    def test_coverage_no_overlaps(self):
        """Test that seasons don't overlap."""
        dates = [date(2020, 3, 10), date(2020, 6, 15), date(2020, 9, 20)]
        seasons = create_seasons_from_dates(dates)
        
        # Check each month in year 2000 is covered by exactly one season
        coverage = {}
        for m in range(1, 13):  # All months in leap year
            test_date = date(2000, m, 1)
            covering_seasons = [season for season in seasons if season.contains_date(test_date)]
            coverage[test_date] = len(covering_seasons)
            assert len(covering_seasons) == 1, f"Date {test_date} covered by {len(covering_seasons)} seasons"


class TestCreateDaytypesFromDates:
    """Tests for create_daytypes_from_dates helper function."""
    
    # ========== Single Date ==========
    
    def test_single_date_mid_year(self):
        """Test single date in middle of year."""
        dates = [date(2020, 6, 15)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create 6 daytypes: 1-7, 8-14, 15, 16-22, 23-29, 30-31
        assert len(daytypes) == 6
        
        # Verify coverage
        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 7)
        assert daytype_list[1] == DayType(8, 14)
        assert daytype_list[2] == DayType(15, 15)  # Target date
        assert daytype_list[3] == DayType(16, 22)
        assert daytype_list[4] == DayType(23, 29)
        assert daytype_list[5] == DayType(30, 31)
    
    def test_single_date_jan_1(self):
        """Test single date on Jan 1."""
        dates = [date(2020, 1, 1)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create 6 daytypes: 1, 2-8, 9-15, 16-22, 23-29, 30-31
        assert len(daytypes) == 6
        
        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 1)
        assert daytype_list[1] == DayType(2, 8)
        assert daytype_list[2] == DayType(9, 15)
        assert daytype_list[3] == DayType(16, 22)
        assert daytype_list[4] == DayType(23, 29)
        assert daytype_list[5] == DayType(30, 31)
    
    def test_single_date_dec_31(self):
        """Test single date on Dec 31."""
        dates = [date(2020, 12, 31)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create 6 daytypes: 1-7, 8-14, 15-21, 22-28, 29-30, 31
        assert len(daytypes) == 6
        
        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 7)
        assert daytype_list[1] == DayType(8, 14)
        assert daytype_list[2] == DayType(15, 21)
        assert daytype_list[3] == DayType(22, 28)
        assert daytype_list[4] == DayType(29, 30)
        assert daytype_list[5] == DayType(31, 31)
    
    # ========== Consecutive Dates ==========
    
    def test_consecutive_dates(self):
        """Test consecutive dates create individual daytypes."""
        dates = [date(2020, 6, 15), date(2020, 6, 16), date(2020, 6, 17)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create 7 daytypes: 1-7, 8-14, 15, 16, 17, 18-24, 25-31
        assert len(daytypes) == 7
        
        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 7)
        assert daytype_list[1] == DayType(8, 14)
        assert daytype_list[2] == DayType(15, 15)
        assert daytype_list[3] == DayType(16, 16)
        assert daytype_list[4] == DayType(17, 17)
        assert daytype_list[5] == DayType(18, 24)
        assert daytype_list[6] == DayType(25, 31)
    
    def test_consecutive_dates_full_week(self):
        """Test full week of consecutive dates."""
        dates = [date(2020, 3, i) for i in range(1, 8)]  # March 1-7
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create 11 daytypes: 1, 2, 3, 4, 5, 6, 7, 8-14, 15-21, 22-28, 29-31
        assert len(daytypes) == 11
        
        # Check individual days exist
        daytype_list = sorted(daytypes)
        for d in range(1, 8):
            assert daytype_list[d-1] == DayType(d, d)
    
    # ========== Gapped Dates ==========
    
    def test_gapped_dates_simple(self):
        """Test gapped dates create gap-fill daytypes."""
        dates = [date(2020, 6, 1), date(2020, 6, 5)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create: 1, 2-4 (gap), 5, 6-12, 13-19, 20-26, 27-31
        assert len(daytypes) == 7
        
        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 1)
        assert daytype_list[1] == DayType(2, 4)
        assert daytype_list[2] == DayType(5, 5)
        assert daytype_list[3] == DayType(6, 12)
        assert daytype_list[4] == DayType(13, 19)
        assert daytype_list[5] == DayType(20, 26)
        assert daytype_list[6] == DayType(27, 31)
    
    def test_gapped_dates_large_gap(self):
        """Test large gap between dates."""
        dates = [date(2020, 1, 15), date(2020, 12, 15)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create 6 daytypes: 1-7, 8-14, 15, 16-22, 23-29, 30-31
        assert len(daytypes) == 6
        
        # Verify coverage
        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 7)
        assert daytype_list[1] == DayType(8, 14)
        assert daytype_list[2] == DayType(15, 15)
        assert daytype_list[3] == DayType(16, 22)
        assert daytype_list[4] == DayType(23, 29)
        assert daytype_list[5] == DayType(30, 31)
    
    def test_gapped_dates_multiple_gaps(self):
        """Test multiple gaps create multiple gap-fill daytypes."""
        dates = [date(2020, 3, 1), date(2020, 3, 5), date(2020, 3, 10)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create: 1, 2-4 (gap), 5, 6-9 (gap), 10, 11-17, 18-24, 25-31
        assert len(daytypes) == 8
        
        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 1)
        assert daytype_list[1] == DayType(2, 4)
        assert daytype_list[2] == DayType(5, 5)
        assert daytype_list[3] == DayType(6, 9)
        assert daytype_list[4] == DayType(10, 10)
        assert daytype_list[5] == DayType(11, 17)
        assert daytype_list[6] == DayType(18, 24)
        assert daytype_list[7] == DayType(25, 31)
    
    # ========== Start of Year Boundary ==========
    
    def test_start_of_year_jan_1(self):
        """Test that Jan 1 start doesn't create empty before-daytype."""
        dates = [date(2020, 1, 1), date(2020, 1, 15)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create: 1, 2-8, 9-14, 15, 16-22, 23-29, 30-31
        assert len(daytypes) == 7
        
        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 1)
        assert daytype_list[1] == DayType(2, 8)
        assert daytype_list[2] == DayType(9, 14)
        assert daytype_list[3] == DayType(15, 15)
        assert daytype_list[4] == DayType(16, 22)
        assert daytype_list[5] == DayType(23, 29)
        assert daytype_list[6] == DayType(30, 31)
    
    def test_start_of_year_jan_15(self):
        """Test that Jan 15 start creates before-daytype from Jan 1."""
        dates = [date(2020, 1, 15)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create 6 daytypes: 1-7, 8-14, 15, 16-22, 23-29, 30-31
        assert len(daytypes) == 6
        
        # Verify coverage
        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 7)
        assert daytype_list[1] == DayType(8, 14)
        assert daytype_list[2] == DayType(15, 15)
        assert daytype_list[3] == DayType(16, 22)
        assert daytype_list[4] == DayType(23, 29)
        assert daytype_list[5] == DayType(30, 31)
    
    def test_start_of_year_mid_year(self):
        """Test mid-year start creates full before-daytype."""
        dates = [date(2020, 6, 1)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create: 1, 2-8, 9-15, 16-22, 23-29, 30-31
        assert len(daytypes) == 6
        
        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 1)
        assert daytype_list[1] == DayType(2, 8)
        assert daytype_list[2] == DayType(9, 15)
        assert daytype_list[3] == DayType(16, 22)
        assert daytype_list[4] == DayType(23, 29)
        assert daytype_list[5] == DayType(30, 31)
    
    # ========== End of Year Boundary ==========
    
    def test_end_of_year_dec_31(self):
        """Test that Dec 31 end doesn't create empty after-daytype."""
        dates = [date(2020, 12, 15), date(2020, 12, 31)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create: 1-7, 8-14, 15, 16-22, 23-29, 30, 31
        assert len(daytypes) == 7
        
        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 7)
        assert daytype_list[1] == DayType(8, 14)
        assert daytype_list[2] == DayType(15, 15)
        assert daytype_list[3] == DayType(16, 22)
        assert daytype_list[4] == DayType(23, 29)
        assert daytype_list[5] == DayType(30, 30)
        assert daytype_list[6] == DayType(31, 31)
    
    def test_end_of_year_dec_20(self):
        """Test that Dec 20 end creates after-daytype to Dec 31."""
        dates = [date(2020, 12, 20)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create: 1-7, 8-14, 15-19, 20, 21-27, 28-31
        assert len(daytypes) == 6
        
        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 7)
        assert daytype_list[1] == DayType(8, 14)
        assert daytype_list[2] == DayType(15, 19)
        assert daytype_list[3] == DayType(20, 20)
        assert daytype_list[4] == DayType(21, 27)
        assert daytype_list[5] == DayType(28, 31)
    
    def test_end_of_year_mid_year(self):
        """Test mid-year end creates full after-daytype."""
        dates = [date(2020, 6, 30)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create: 1-7, 8-14, 15-21, 22-28, 29, 30, 31
        assert len(daytypes) == 7
        
        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 7)
        assert daytype_list[1] == DayType(8, 14)
        assert daytype_list[2] == DayType(15, 21)
        assert daytype_list[3] == DayType(22, 28)
        assert daytype_list[4] == DayType(29, 29)
        assert daytype_list[5] == DayType(30, 30)
        assert daytype_list[6] == DayType(31, 31)
    
    # ========== Year-Wrapping Prevention ==========
    
    def test_year_wrapping_dec_to_jan(self):
        """Test that Dec 31 doesn't wrap to Jan 1."""
        dates = [date(2020, 12, 31), date(2021, 1, 1)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Function takes unique days regardless of years
        assert len(daytypes) == 7

        # Should create: 1, 2-8, 9-15, 16-22, 23-29, 30, 31
        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 1)
        assert daytype_list[1] == DayType(2, 8)
        assert daytype_list[2] == DayType(9, 15)
        assert daytype_list[3] == DayType(16, 22)
        assert daytype_list[4] == DayType(23, 29)
        assert daytype_list[5] == DayType(30, 30)
        assert daytype_list[6] == DayType(31, 31)
    
    def test_year_wrapping_validation(self):
        """Test that daytypes don't attempt year wrapping."""
        # Any dates that would cause year-wrapping should be prevented
        # by the function's selection of unique days
        dates = [date(2020, 12, 25), date(2021, 1, 5)]
        daytypes = create_daytypes_from_dates(dates)
        
        for dt in daytypes:
            # Verify no daytype wraps year
            start_ordinal = date(2000, 12, dt.day_start).toordinal()
            end_ordinal = date(2000, 12, dt.day_end).toordinal()
            assert start_ordinal <= end_ordinal, f"Daytype {dt} wraps year"
    
    # ========== Leap Year Dates ==========
    
    def test_leap_year_feb_29(self):
        """Test Feb 29 handling in leap year context."""
        dates = [date(2020, 2, 29)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create: 1-7, 8-14, 15-21, 22-28, 29, 30-31
        assert len(daytypes) == 6
        
        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 7)
        assert daytype_list[1] == DayType(8, 14)
        assert daytype_list[2] == DayType(15, 21)
        assert daytype_list[3] == DayType(22, 28)
        assert daytype_list[4] == DayType(29, 29)
        assert daytype_list[5] == DayType(30, 31)
    
    def test_leap_year_feb_28_29(self):
        """Test consecutive dates around Feb 29."""
        dates = [date(2020, 2, 28), date(2020, 2, 29)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create: 1-7, 8-14, 15-21, 22-27, 28, 29, 30-31
        assert len(daytypes) == 7
        
        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 7)
        assert daytype_list[1] == DayType(8, 14)
        assert daytype_list[2] == DayType(15, 21)
        assert daytype_list[3] == DayType(22, 27)
        assert daytype_list[4] == DayType(28, 28)
        assert daytype_list[5] == DayType(29, 29)
        assert daytype_list[6] == DayType(30, 31)
    
    def test_leap_year_normalization(self):
        """Test that function uses leap year (2000) for normalization."""
        # Input dates from non-leap year, but Feb 29 should still be valid
        dates = [date(2021, 2, 28), date(2021, 3, 1)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create: 1, 2-8, 9-15, 16-22, 23-27, 28, 29-31
        assert len(daytypes) == 7

        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 1)
        assert daytype_list[1] == DayType(2, 8)
        assert daytype_list[2] == DayType(9, 15)
        assert daytype_list[3] == DayType(16, 22)
        assert daytype_list[4] == DayType(23, 27)
        assert daytype_list[5] == DayType(28, 28)
        assert daytype_list[6] == DayType(29, 31)
    
    # ========== Edge Cases ==========
    
    def test_duplicate_dates_ignored(self):
        """Test that duplicate dates are handled correctly."""
        dates = [date(2020, 6, 15), date(2020, 6, 15), date(2020, 6, 15)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should be same as single date
        assert len(daytypes) == 6

        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 7)
        assert daytype_list[1] == DayType(8, 14)
        assert daytype_list[2] == DayType(15, 15)  # Target date
        assert daytype_list[3] == DayType(16, 22)
        assert daytype_list[4] == DayType(23, 29)
        assert daytype_list[5] == DayType(30, 31)
    
    def test_unsorted_dates(self):
        """Test that unsorted dates are handled correctly."""
        dates = [date(2020, 6, 20), date(2020, 6, 10), date(2020, 6, 15)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create: 1-7, 8-9, 10, 11-14, 15, 16-19, 20, 21-27, 28-31
        assert len(daytypes) == 9

        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 7)
        assert daytype_list[1] == DayType(8, 9)
        assert daytype_list[2] == DayType(10, 10)
        assert daytype_list[3] == DayType(11, 14)
        assert daytype_list[4] == DayType(15, 15)
        assert daytype_list[5] == DayType(16, 19)
        assert daytype_list[6] == DayType(20, 20)
        assert daytype_list[7] == DayType(21, 27)
        assert daytype_list[8] == DayType(28, 31)
    
    def test_different_input_years_normalized(self):
        """Test that dates from different years are normalized."""
        dates = [date(2020, 6, 15), date(2021, 9, 20), date(2025, 3, 10)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Should create: 1-7, 8-9, 10, 11-14, 15, 16-19, 20, 21-27, 28-31
        assert len(daytypes) == 9

        daytype_list = sorted(daytypes)
        assert daytype_list[0] == DayType(1, 7)
        assert daytype_list[1] == DayType(8, 9)
        assert daytype_list[2] == DayType(10, 10)
        assert daytype_list[3] == DayType(11, 14)
        assert daytype_list[4] == DayType(15, 15)
        assert daytype_list[5] == DayType(16, 19)
        assert daytype_list[6] == DayType(20, 20)
        assert daytype_list[7] == DayType(21, 27)
        assert daytype_list[8] == DayType(28, 31)
    
    # ========== Coverage Validation ==========
    
    def test_coverage_full_year_single_date(self):
        """Test that single date produces full year coverage."""
        dates = [date(2020, 6, 15)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Sum durations should equal full leap year
        total_days = sum(dt.duration_days(2000, m) for dt in daytypes for m in range(1, 13))
        assert total_days == 366  # Leap year
    
    def test_coverage_full_year_multiple_dates(self):
        """Test that multiple dates produce full year coverage."""
        dates = [date(2020, 3, 10), date(2020, 6, 15), date(2020, 9, 20)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Sum durations should equal full leap year
        total_days = sum(dt.duration_days(2000, m) for dt in daytypes for m in range(1, 13))
        assert total_days == 366
    
    def test_coverage_no_overlaps(self):
        """Test that daytypes don't overlap."""
        dates = [date(2020, 3, 10), date(2020, 6, 15), date(2020, 9, 20)]
        daytypes = create_daytypes_from_dates(dates)
        
        # Check each date in year 2000 is covered by exactly one daytype
        coverage = {}
        for d in range(1, 367):  # All days in leap year
            test_date = date(2000, 1, 1) + timedelta(days=d-1)
            covering_daytypes = [dt for dt in daytypes if dt.contains_date(test_date)]
            coverage[test_date] = len(covering_daytypes)
            assert len(covering_daytypes) == 1, f"Date {test_date} covered by {len(covering_daytypes)} daytypes"


class TestCreateTimebracketsFromTimes:
    """Tests for create_timebrackets_from_times helper function."""
    
    # ========== Single Time ==========
    
    def test_single_time_midnight(self):
        """Test single time at midnight creates full day."""
        times = [time(0, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        # Should create one bracket: 00:00 to ENDOFDAY
        assert len(brackets) == 1
        bracket = list(brackets)[0]
        assert bracket.hour_start == time(0, 0, 0)
        assert bracket.hour_end == ENDOFDAY
        assert bracket.is_full_day()
        assert bracket.duration_hours() == 24.0
    
    def test_single_time_not_midnight(self):
        """Test single time not at midnight adds midnight bracket."""
        times = [time(12, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        # Should create two brackets: 00:00-12:00, 12:00-ENDOFDAY
        assert len(brackets) == 2
        
        bracket_list = sorted(brackets)
        assert bracket_list[0].hour_start == time(0, 0, 0)
        assert bracket_list[0].hour_end == time(12, 0, 0)
        assert bracket_list[1].hour_start == time(12, 0, 0)
        assert bracket_list[1].hour_end == ENDOFDAY
    
    def test_single_time_morning(self):
        """Test single time in morning."""
        times = [time(6, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        # Should create: 00:00-06:00, 06:00-ENDOFDAY
        assert len(brackets) == 2
        
        bracket_list = sorted(brackets)
        assert bracket_list[0].duration_hours() == 6.0
        assert bracket_list[1].duration_hours() == 18.0
    
    # ========== Multiple Times ==========
    
    def test_multiple_times_hourly(self):
        """Test hourly time brackets."""
        times = [time(h, 0, 0) for h in range(24)]
        brackets = create_timebrackets_from_times(times)
        
        # Should create 24 one-hour brackets
        assert len(brackets) == 24
        
        bracket_list = sorted(brackets)
        for i, bracket in enumerate(bracket_list):
            assert bracket.hour_start == time(i, 0, 0)
            if i < 23:
                assert bracket.hour_end == time(i + 1, 0, 0)
            else:
                assert bracket.hour_end == ENDOFDAY
            assert bracket.duration_hours() == 1.0
    
    def test_multiple_times_irregular(self):
        """Test irregular time intervals."""
        times = [time(6, 0, 0), time(9, 30, 0), time(17, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        # Should create: 00:00-06:00, 06:00-09:30, 09:30-17:00, 17:00-ENDOFDAY
        assert len(brackets) == 4
        
        bracket_list = sorted(brackets)
        assert bracket_list[0].hour_start == time(0, 0, 0)
        assert bracket_list[0].hour_end == time(6, 0, 0)
        assert bracket_list[1].hour_start == time(6, 0, 0)
        assert bracket_list[1].hour_end == time(9, 30, 0)
        assert bracket_list[2].hour_start == time(9, 30, 0)
        assert bracket_list[2].hour_end == time(17, 0, 0)
        assert bracket_list[3].hour_start == time(17, 0, 0)
        assert bracket_list[3].hour_end == ENDOFDAY
    
    def test_multiple_times_quarter_day(self):
        """Test quarter-day time brackets."""
        times = [time(0, 0, 0), time(6, 0, 0), time(12, 0, 0), time(18, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        # Should create 4 six-hour brackets
        assert len(brackets) == 4
        
        for bracket in brackets:
            assert bracket.duration_hours() == 6.0
    
    # ========== Midnight Not Included ==========
    
    def test_midnight_not_included_morning_start(self):
        """Test that midnight is auto-added when not in list."""
        times = [time(8, 0, 0), time(16, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        # Should create: 00:00-08:00, 08:00-16:00, 16:00-ENDOFDAY
        assert len(brackets) == 3
        
        bracket_list = sorted(brackets)
        assert bracket_list[0].hour_start == time(0, 0, 0)
        assert bracket_list[0].hour_end == time(8, 0, 0)
    
    def test_midnight_not_included_afternoon_start(self):
        """Test midnight auto-add with afternoon start."""
        times = [time(14, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        # Should create: 00:00-14:00, 14:00-ENDOFDAY
        assert len(brackets) == 2
        
        bracket_list = sorted(brackets)
        assert bracket_list[0].hour_start == time(0, 0, 0)
        assert bracket_list[0].duration_hours() == 14.0
        assert bracket_list[1].duration_hours() == 10.0
    
    def test_midnight_already_included(self):
        """Test that explicit midnight doesn't create duplicate."""
        times = [time(0, 0, 0), time(12, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        # Should create: 00:00-12:00, 12:00-ENDOFDAY (no duplicate midnight)
        assert len(brackets) == 2
    
    # ========== ENDOFDAY for Last Bracket ==========
    
    def test_endofday_single_time(self):
        """Test ENDOFDAY used for last bracket with single time."""
        times = [time(18, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        bracket_list = sorted(brackets)
        last_bracket = bracket_list[-1]
        
        assert last_bracket.hour_start == time(18, 0, 0)
        assert last_bracket.hour_end == ENDOFDAY
        assert last_bracket.duration_hours() == 6.0
    
    def test_endofday_multiple_times(self):
        """Test ENDOFDAY used for last bracket with multiple times."""
        times = [time(6, 0, 0), time(12, 0, 0), time(18, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        bracket_list = sorted(brackets)
        last_bracket = bracket_list[-1]
        
        assert last_bracket.hour_start == time(18, 0, 0)
        assert last_bracket.hour_end == ENDOFDAY
    
    def test_endofday_late_evening_start(self):
        """Test ENDOFDAY with late evening start time."""
        times = [time(23, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        bracket_list = sorted(brackets)
        last_bracket = bracket_list[-1]
        
        assert last_bracket.hour_start == time(23, 0, 0)
        assert last_bracket.hour_end == ENDOFDAY
        assert last_bracket.duration_hours() == 1.0
    
    def test_endofday_inclusive(self):
        """Test that ENDOFDAY makes bracket inclusive to last moment of day."""
        times = [time(22, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        bracket_list = sorted(brackets)
        last_bracket = bracket_list[-1]
        
        # Should contain time 23:59:59
        assert last_bracket.contains_time(time(23, 59, 59))
    
    # ========== Edge Cases ==========
    
    def test_duplicate_times_ignored(self):
        """Test that duplicate times are handled correctly."""
        times = [time(6, 0, 0), time(6, 0, 0), time(12, 0, 0), time(12, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        # Should be same as without duplicates
        assert len(brackets) == 3
    
    def test_unsorted_times(self):
        """Test that unsorted times are handled correctly."""
        times = [time(18, 0, 0), time(6, 0, 0), time(12, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        # Should produce correct sorted brackets
        bracket_list = sorted(brackets)
        assert bracket_list[0].hour_start == time(0, 0, 0)
        assert bracket_list[1].hour_start == time(6, 0, 0)
        assert bracket_list[2].hour_start == time(12, 0, 0)
        assert bracket_list[3].hour_start == time(18, 0, 0)
    
    def test_sub_hourly_precision(self):
        """Test sub-hourly time precision."""
        times = [time(9, 15, 0), time(9, 30, 0), time(9, 45, 0)]
        brackets = create_timebrackets_from_times(times)
        
        # Should create fine-grained brackets
        bracket_list = sorted(brackets)
        
        # Find the 15-minute brackets
        for i in range(len(bracket_list) - 1):
            if bracket_list[i].hour_start == time(9, 15, 0):
                assert bracket_list[i].hour_end == time(9, 30, 0)
                assert bracket_list[i].duration_hours() == 0.25
    
    def test_seconds_precision(self):
        """Test second-level time precision."""
        times = [time(10, 0, 0), time(10, 0, 30)]
        brackets = create_timebrackets_from_times(times)
        
        bracket_list = sorted(brackets)
        
        # Find the 30-second bracket
        for bracket in bracket_list:
            if bracket.hour_start == time(10, 0, 0) and bracket.hour_end == time(10, 0, 30):
                assert abs(bracket.duration_hours() - 30/3600) < 1e-10
    
    # ========== Coverage Validation ==========
    
    def test_coverage_full_day_single_time(self):
        """Test that single time produces full 24-hour coverage."""
        times = [time(12, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        total_hours = sum(b.duration_hours() for b in brackets)
        assert abs(total_hours - 24.0) < 1e-10
    
    def test_coverage_full_day_multiple_times(self):
        """Test that multiple times produce full 24-hour coverage."""
        times = [time(3, 0, 0), time(9, 0, 0), time(15, 0, 0), time(21, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        total_hours = sum(b.duration_hours() for b in brackets)
        assert abs(total_hours - 24.0) < 1e-10
    
    def test_coverage_no_overlaps(self):
        """Test that brackets don't overlap."""
        times = [time(6, 0, 0), time(12, 0, 0), time(18, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        bracket_list = sorted(brackets)
        
        # Each bracket's end should equal next bracket's start
        for i in range(len(bracket_list) - 1):
            assert bracket_list[i].hour_end == bracket_list[i + 1].hour_start
    
    def test_coverage_no_gaps(self):
        """Test that brackets cover all times in day."""
        times = [time(4, 0, 0), time(8, 0, 0), time(16, 0, 0), time(20, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        # Check a sample of times throughout the day
        test_times = [
            time(0, 0, 0), time(5, 0, 0), time(10, 0, 0), 
            time(15, 0, 0), time(18, 0, 0), time(22, 0, 0), time(23, 59, 59)
        ]
        
        for t in test_times:
            covering = [b for b in brackets if b.contains_time(t)]
            assert len(covering) == 1, f"Time {t} covered by {len(covering)} brackets"
    
    def test_coverage_contiguous_half_open(self):
        """Test that brackets form contiguous half-open intervals."""
        times = [time(8, 0, 0), time(12, 0, 0), time(16, 0, 0)]
        brackets = create_timebrackets_from_times(times)
        
        bracket_list = sorted(brackets)
        
        # Test boundary times
        assert bracket_list[0].contains_time(time(0, 0, 0))
        assert not bracket_list[0].contains_time(time(8, 0, 0))  # Boundary belongs to next
        assert bracket_list[1].contains_time(time(8, 0, 0))
        assert not bracket_list[1].contains_time(time(12, 0, 0))
        assert bracket_list[2].contains_time(time(12, 0, 0))
        assert not bracket_list[2].contains_time(time(16, 0, 0))
        assert bracket_list[3].contains_time(time(16, 0, 0))
        assert bracket_list[3].contains_time(time(23, 59, 59))  # ENDOFDAY is inclusive
