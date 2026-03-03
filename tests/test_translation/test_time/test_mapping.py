# tests/test_translation/test_time/test_mapping.py

"""
Tests for snapshot-to-timeslice mapping (mapping.py).

Tests the period-based mapping where each snapshot represents data valid
until the next snapshot. Uses to_timeslices() to generate structurally
correct timeslice sets, then validates create_map() against known invariants.
"""

import pytest
import pandas as pd
from datetime import time, date

from pyoscomp.constants import ENDOFDAY, TOL, hours_in_year
from pyoscomp.translation.time.structures import (
    Season, DayType, DailyTimeBracket, Timeslice
)
from pyoscomp.translation.time.mapping import (
    create_map, create_endpoints, _get_canonical_start
)
from pyoscomp.translation.time.translate import to_timeslices


# ---------------------------------------------------------------------------
# Unit tests: _get_canonical_start
# ---------------------------------------------------------------------------
class TestGetCanonicalStart:
    """Unit tests for the _get_canonical_start helper."""

    def test_single_month_single_day(self):
        """Canonical start of a single-day, single-month timeslice."""
        ts = Timeslice(
            season=Season(6, 6),
            daytype=DayType(15, 15),
            dailytimebracket=DailyTimeBracket(time(0, 0), ENDOFDAY)
        )
        assert _get_canonical_start(ts, 2020) == pd.Timestamp('2020-06-15')

    def test_includes_time_component(self):
        """Canonical start includes the dailytimebracket start time."""
        ts = Timeslice(
            season=Season(3, 3),
            daytype=DayType(10, 14),
            dailytimebracket=DailyTimeBracket(time(12, 0), ENDOFDAY)
        )
        assert _get_canonical_start(ts, 2020) == pd.Timestamp(
            '2020-03-10 12:00:00'
        )

    def test_full_year_season(self):
        """Full-year season returns January date."""
        ts = Timeslice(
            season=Season(1, 12),
            daytype=DayType(1, 1),
            dailytimebracket=DailyTimeBracket(time(0, 0), ENDOFDAY)
        )
        assert _get_canonical_start(ts, 2025) == pd.Timestamp('2025-01-01')

    def test_feb29_leap_year(self):
        """Feb 29 exists in a leap year."""
        ts = Timeslice(
            season=Season(2, 2),
            daytype=DayType(29, 29),
            dailytimebracket=DailyTimeBracket(time(0, 0), ENDOFDAY)
        )
        assert _get_canonical_start(ts, 2020) == pd.Timestamp('2020-02-29')

    def test_feb29_non_leap_year_returns_none(self):
        """Feb 29 does not exist in a non-leap year -> None."""
        ts = Timeslice(
            season=Season(2, 2),
            daytype=DayType(29, 29),
            dailytimebracket=DailyTimeBracket(time(0, 0), ENDOFDAY)
        )
        assert _get_canonical_start(ts, 2021) is None

    def test_day31_in_30day_month_returns_none(self):
        """Day 31 in April (30 days) -> None."""
        ts = Timeslice(
            season=Season(4, 4),
            daytype=DayType(31, 31),
            dailytimebracket=DailyTimeBracket(time(0, 0), ENDOFDAY)
        )
        assert _get_canonical_start(ts, 2020) is None

    def test_multi_month_season_skips_invalid_month(self):
        """Season(2,3) + DayType(31,31): Feb has no 31st, Mar does."""
        ts = Timeslice(
            season=Season(2, 3),
            daytype=DayType(31, 31),
            dailytimebracket=DailyTimeBracket(time(0, 0), ENDOFDAY)
        )
        result = _get_canonical_start(ts, 2020)
        assert result == pd.Timestamp('2020-03-31')

    def test_microsecond_precision(self):
        """DTB with microsecond start preserves precision."""
        ts = Timeslice(
            season=Season(1, 1),
            daytype=DayType(1, 1),
            dailytimebracket=DailyTimeBracket(
                time(12, 30, 45, 123456), ENDOFDAY
            )
        )
        result = _get_canonical_start(ts, 2020)
        assert result.microsecond == 123456


# ---------------------------------------------------------------------------
# Unit tests: create_endpoints
# ---------------------------------------------------------------------------
class TestCreateEndpoints:
    """Tests for the create_endpoints helper."""

    def test_single_year(self):
        """Endpoints include start/end of year plus snapshot."""
        snapshots = pd.DatetimeIndex(['2020-06-15'])
        eps = create_endpoints(snapshots)
        assert pd.Timestamp('2020-01-01') in eps
        assert pd.Timestamp('2020-06-15') in eps
        assert pd.Timestamp.combine(date(2020, 12, 31), ENDOFDAY) in eps

    def test_multi_year_includes_intermediate(self):
        """Snapshots in 2020 and 2022 include 2021 boundaries."""
        snapshots = pd.DatetimeIndex(['2020-01-01', '2022-01-01'])
        eps = create_endpoints(snapshots)
        assert pd.Timestamp('2021-01-01') in eps
        assert pd.Timestamp.combine(date(2021, 12, 31), ENDOFDAY) in eps

    def test_sorted_and_unique(self):
        """Endpoints are sorted with no duplicates."""
        snapshots = pd.DatetimeIndex([
            '2020-12-31', '2020-01-01', '2020-01-01'
        ])
        eps = create_endpoints(snapshots)
        assert eps == sorted(eps)
        assert len(eps) == len(set(eps))

    def test_snapshot_at_year_boundary_no_duplicate(self):
        """Snapshot at Jan 1 does not create a duplicate endpoint."""
        snapshots = pd.DatetimeIndex(['2020-01-01'])
        eps = create_endpoints(snapshots)
        assert eps.count(pd.Timestamp('2020-01-01')) == 1


# ---------------------------------------------------------------------------
# Integration tests: create_map with single snapshot
# ---------------------------------------------------------------------------
class TestCreateMapSingleSnapshot:
    """Tests for single-snapshot mapping (fills to end of year)."""

    def test_single_snapshot_all_timeslices_mapped(self):
        """Single Jan 1 snapshot maps to every non-zero timeslice."""
        snapshots = pd.DatetimeIndex(['2020-01-01'])
        result = to_timeslices(snapshots)
        mapping = create_map(snapshots, result.timeslices)

        assert len(mapping) == 1
        mapped_ts = {ts for (_, ts) in mapping[snapshots[0]]}
        non_zero = {
            ts for ts in result.timeslices
            if ts.duration_hours(2020) > TOL
        }
        assert mapped_ts == non_zero

    def test_single_snapshot_hours_equal_year(self):
        """Mapped hours equal hours-in-year."""
        snapshots = pd.DatetimeIndex(['2025-01-01'])
        result = to_timeslices(snapshots)
        mapping = create_map(snapshots, result.timeslices)
        total = sum(
            ts.duration_hours(y) for y, ts in mapping[snapshots[0]]
        )
        assert abs(total - hours_in_year(2025)) < 0.01

    def test_single_snapshot_mid_year(self):
        """Mid-year snapshot maps only to timeslices from that point on."""
        snapshots = pd.DatetimeIndex(['2020-07-01'])
        result = to_timeslices(snapshots)
        mapping = create_map(snapshots, result.timeslices)

        total = sum(
            ts.duration_hours(y) for y, ts in mapping[snapshots[0]]
        )
        expected = (
            pd.Timestamp.combine(date(2020, 12, 31), ENDOFDAY)
            - snapshots[0]
        ).total_seconds() / 3600
        assert abs(total - expected) < 1 / 3600

    def test_single_snapshot_correct_year(self):
        """All mapping entries reference the correct year."""
        snapshots = pd.DatetimeIndex(['2025-03-15'])
        result = to_timeslices(snapshots)
        mapping = create_map(snapshots, result.timeslices)
        assert all(y == 2025 for y, _ in mapping[snapshots[0]])


# ---------------------------------------------------------------------------
# Integration tests: create_map with multiple snapshots (same year)
# ---------------------------------------------------------------------------
class TestCreateMapMultipleSnapshots:
    """Tests for multiple snapshots within the same year."""

    def test_two_daily_snapshots(self):
        """First daily snapshot covers exactly 24 hours."""
        snapshots = pd.DatetimeIndex(['2020-06-15', '2020-06-16'])
        result = to_timeslices(snapshots)
        mapping = create_map(snapshots, result.timeslices)

        assert len(mapping) == 2
        dur_0 = sum(
            ts.duration_hours(y) for y, ts in mapping[snapshots[0]]
        )
        assert abs(dur_0 - 24.0) < 0.01

    def test_three_daily_snapshots(self):
        """Each non-final daily snapshot covers 24 hours."""
        snapshots = pd.DatetimeIndex([
            '2020-06-15', '2020-06-16', '2020-06-17'
        ])
        result = to_timeslices(snapshots)
        mapping = create_map(snapshots, result.timeslices)

        for i in range(2):
            dur = sum(
                ts.duration_hours(y)
                for y, ts in mapping[snapshots[i]]
            )
            assert abs(dur - 24.0) < 0.01

    def test_hourly_snapshots_one_hour_each(self):
        """Each hourly snapshot (except last) covers 1 hour."""
        snapshots = pd.date_range('2020-06-15', periods=24, freq='h')
        result = to_timeslices(snapshots)
        mapping = create_map(snapshots, result.timeslices)

        for i in range(23):
            dur = sum(
                ts.duration_hours(y)
                for y, ts in mapping[snapshots[i]]
            )
            assert abs(dur - 1.0) < 0.01, (
                f"Snapshot {i} duration {dur} != 1.0"
            )

    def test_gapped_snapshots(self):
        """Snapshots with large temporal gaps."""
        snapshots = pd.DatetimeIndex([
            '2020-01-15', '2020-06-15', '2020-11-15'
        ])
        result = to_timeslices(snapshots)
        mapping = create_map(snapshots, result.timeslices)

        dur_0 = sum(
            ts.duration_hours(y) for y, ts in mapping[snapshots[0]]
        )
        expected_0 = (snapshots[1] - snapshots[0]).total_seconds() / 3600
        assert abs(dur_0 - expected_0) < 0.01

    def test_sub_daily_12h_snapshots(self):
        """Morning and evening snapshots produce 12-hour periods."""
        snapshots = pd.DatetimeIndex([
            '2020-06-15 00:00', '2020-06-15 12:00',
            '2020-06-16 00:00'
        ])
        result = to_timeslices(snapshots)
        mapping = create_map(snapshots, result.timeslices)

        for i in range(2):
            dur = sum(
                ts.duration_hours(y)
                for y, ts in mapping[snapshots[i]]
            )
            assert abs(dur - 12.0) < 0.01


# ---------------------------------------------------------------------------
# Integration tests: create_map with multiple years
# ---------------------------------------------------------------------------
class TestCreateMapMultiYear:
    """Tests for snapshots spanning multiple years."""

    def test_two_consecutive_years(self):
        """Each annual snapshot covers its entire year."""
        snapshots = pd.DatetimeIndex(['2020-01-01', '2021-01-01'])
        result = to_timeslices(snapshots)
        mapping = create_map(snapshots, result.timeslices)

        years_0 = set(y for y, _ in mapping[snapshots[0]])
        assert years_0 == {2020}
        dur_0 = sum(
            ts.duration_hours(y) for y, ts in mapping[snapshots[0]]
        )
        assert abs(dur_0 - hours_in_year(2020)) < 0.01

        years_1 = set(y for y, _ in mapping[snapshots[1]])
        assert years_1 == {2021}

    def test_year_boundary_crossing(self):
        """Snapshot period crossing Dec 31 / Jan 1 maps to both years."""
        snapshots = pd.DatetimeIndex([
            '2020-12-31 12:00', '2021-01-01 12:00'
        ])
        result = to_timeslices(snapshots)
        mapping = create_map(snapshots, result.timeslices)

        years_0 = set(y for y, _ in mapping[snapshots[0]])
        assert years_0 == {2020, 2021}

        dur_0 = sum(
            ts.duration_hours(y) for y, ts in mapping[snapshots[0]]
        )
        assert abs(dur_0 - 24.0) < 0.01

    def test_multi_year_with_gap(self):
        """Snapshots in 2020 and 2022 cover intermediate 2021."""
        snapshots = pd.DatetimeIndex(['2020-01-01', '2022-01-01'])
        result = to_timeslices(snapshots)
        mapping = create_map(snapshots, result.timeslices)

        years_0 = set(y for y, _ in mapping[snapshots[0]])
        assert years_0 == {2020, 2021}

        dur_0 = sum(
            ts.duration_hours(y) for y, ts in mapping[snapshots[0]]
        )
        expected = hours_in_year(2020) + hours_in_year(2021)
        assert abs(dur_0 - expected) < 0.01

    def test_three_annual_snapshots(self):
        """Three annual snapshots each cover one year."""
        snapshots = pd.DatetimeIndex([
            '2020-01-01', '2021-01-01', '2022-01-01'
        ])
        result = to_timeslices(snapshots)
        mapping = create_map(snapshots, result.timeslices)

        for i, snap in enumerate(snapshots):
            years_i = set(y for y, _ in mapping[snap])
            assert years_i == {2020 + i}


# ---------------------------------------------------------------------------
# Edge-case tests: leap years
# ---------------------------------------------------------------------------
class TestCreateMapLeapYear:
    """Tests for leap-year edge cases."""

    def test_leap_year_hours(self):
        """Leap year mapped hours total 8784."""
        snapshots = pd.DatetimeIndex(['2020-01-01'])
        result = to_timeslices(snapshots)
        mapping = create_map(snapshots, result.timeslices)
        total = sum(
            ts.duration_hours(y) for y, ts in mapping[snapshots[0]]
        )
        assert abs(total - 8784) < 0.01

    def test_non_leap_year_hours(self):
        """Non-leap year mapped hours total 8760."""
        snapshots = pd.DatetimeIndex(['2021-01-01'])
        result = to_timeslices(snapshots)
        mapping = create_map(snapshots, result.timeslices)
        total = sum(
            ts.duration_hours(y) for y, ts in mapping[snapshots[0]]
        )
        assert abs(total - 8760) < 0.01

    def test_feb29_snapshot_24_hours(self):
        """Snapshot on Feb 29 -> Mar 1 covers exactly 24 hours."""
        snapshots = pd.DatetimeIndex(['2020-02-29', '2020-03-01'])
        result = to_timeslices(snapshots)
        mapping = create_map(snapshots, result.timeslices)
        dur = sum(
            ts.duration_hours(y) for y, ts in mapping[snapshots[0]]
        )
        assert abs(dur - 24.0) < 0.01

    def test_mixed_leap_and_non_leap(self):
        """Snapshot spanning from leap year into non-leap year."""
        snapshots = pd.DatetimeIndex(['2020-02-29', '2021-02-28'])
        result = to_timeslices(snapshots)
        mapping = create_map(snapshots, result.timeslices)

        years_0 = set(y for y, _ in mapping[snapshots[0]])
        assert 2020 in years_0
        assert 2021 in years_0


# ---------------------------------------------------------------------------
# Edge-case tests: errors and boundary conditions
# ---------------------------------------------------------------------------
class TestCreateMapEdgeCases:
    """Tests for error paths and boundary conditions."""

    def test_empty_snapshots_raises(self):
        """Empty snapshots raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            create_map(pd.DatetimeIndex([]), [])

    def test_mismatched_timeslices_raises(self):
        """Incomplete timeslice set triggers duration mismatch."""
        snapshots = pd.DatetimeIndex(['2020-01-01'])
        partial = [Timeslice(
            season=Season(6, 6), daytype=DayType(15, 15),
            dailytimebracket=DailyTimeBracket(time(0, 0), ENDOFDAY)
        )]
        with pytest.raises(ValueError, match="Mismatch"):
            create_map(snapshots, partial)

    def test_no_duplicate_pairs(self):
        """No duplicate (year, timeslice) pairs within any snapshot."""
        snapshots = pd.DatetimeIndex(['2020-06-15', '2020-07-15'])
        result = to_timeslices(snapshots)
        mapping = create_map(snapshots, result.timeslices)
        for snap in snapshots:
            pairs = [(y, ts.name) for y, ts in mapping[snap]]
            assert len(pairs) == len(set(pairs))

    def test_all_nonzero_timeslices_mapped(self):
        """Every non-zero timeslice appears exactly once across mapping."""
        snapshots = pd.date_range('2020-01-01', periods=12, freq='MS')
        result = to_timeslices(snapshots)
        mapping = create_map(snapshots, result.timeslices)

        all_mapped = []
        for snap in snapshots:
            all_mapped.extend(
                [(y, ts.name) for y, ts in mapping[snap]]
            )
        assert len(all_mapped) == len(set(all_mapped))

    def test_unsorted_snapshots_handled(self):
        """Out-of-order snapshots are sorted internally."""
        snapshots = pd.DatetimeIndex([
            '2020-06-20', '2020-06-15', '2020-06-18'
        ])
        result = to_timeslices(snapshots)
        mapping = create_map(snapshots, result.timeslices)
        assert len(mapping) == 3

    def test_duplicate_snapshots_handled(self):
        """Duplicate snapshot timestamps are deduplicated."""
        snapshots = pd.DatetimeIndex([
            '2020-06-15', '2020-06-15', '2020-06-16'
        ])
        result = to_timeslices(snapshots)
        mapping = create_map(snapshots, result.timeslices)
        assert len(mapping) == 2


# ---------------------------------------------------------------------------
# Integration tests: complex / real-world-like patterns
# ---------------------------------------------------------------------------
class TestCreateMapComplexPatterns:
    """Tests with realistic temporal patterns."""

    def test_quarterly_with_subdaily(self):
        """Quarterly dates with 3 times per day."""
        dates = pd.date_range('2020-01-01', periods=4, freq='QS')
        times_list = ['00:00', '08:00', '16:00']
        snapshots = pd.DatetimeIndex([
            f"{d.date()} {t}" for d in dates for t in times_list
        ])
        result = to_timeslices(snapshots)
        mapping = create_map(snapshots, result.timeslices)

        assert len(mapping) == len(snapshots)
        for snap in snapshots:
            assert len(mapping[snap]) >= 1

    def test_monthly_snapshots_durations(self):
        """Monthly snapshots: Jan covers 31 days, Feb 29 days (2020)."""
        snapshots = pd.date_range('2020-01-01', periods=12, freq='MS')
        result = to_timeslices(snapshots)
        mapping = create_map(snapshots, result.timeslices)

        dur_jan = sum(
            ts.duration_hours(y) for y, ts in mapping[snapshots[0]]
        )
        assert abs(dur_jan - 31 * 24) < 0.01

        dur_feb = sum(
            ts.duration_hours(y) for y, ts in mapping[snapshots[1]]
        )
        assert abs(dur_feb - 29 * 24) < 0.01

    def test_full_hourly_year(self):
        """Full hourly year: each snapshot covers exactly 1 hour."""
        snapshots = pd.date_range(
            '2021-01-01', periods=8760, freq='h'
        )
        result = to_timeslices(snapshots)
        mapping = create_map(snapshots, result.timeslices)

        for i in range(8759):
            dur = sum(
                ts.duration_hours(y)
                for y, ts in mapping[snapshots[i]]
            )
            assert abs(dur - 1.0) < 0.01, (
                f"Snapshot {i} at {snapshots[i]}: "
                f"expected 1.0h, got {dur:.4f}h"
            )

    def test_morning_evening_week(self):
        """Morning/evening snapshots for a week: no duplicate pairs."""
        morning = pd.date_range('2020-06-15 00:00', periods=7, freq='D')
        evening = pd.date_range('2020-06-15 18:00', periods=7, freq='D')
        snapshots = pd.DatetimeIndex(
            sorted(list(morning) + list(evening))
        )
        result = to_timeslices(snapshots)
        mapping = create_map(snapshots, result.timeslices)

        all_pairs = []
        for snap in snapshots:
            all_pairs.extend(
                [(y, ts.name) for y, ts in mapping[snap]]
            )
        assert len(all_pairs) == len(set(all_pairs))