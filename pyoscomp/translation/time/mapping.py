# pyoscomp/translation/time/mapping.py

"""
Snapshot-to-timeslice mapping for PyPSA-OSeMOSYS translation.

This module maps PyPSA sequential snapshots to OSeMOSYS hierarchical
timeslice structures using a period-based approach where each snapshot
represents data valid from its timestamp until the next snapshot.
"""

from typing import List, Tuple, Union, Dict, Optional
import pandas as pd
from datetime import date, time, datetime
from .structures import Timeslice

from ...constants import ENDOFDAY, TOL


def _get_canonical_start(
    ts: Timeslice, year: int
) -> Optional[pd.Timestamp]:
    """
    Get the earliest datetime of a timeslice in a given year.

    Finds the first valid date within the timeslice's season and daytype
    ranges, combined with the dailytimebracket start time. This canonical
    start uniquely identifies when the timeslice "begins" in a given year,
    enabling correct assignment to snapshot periods.

    Parameters
    ----------
    ts : Timeslice
        The timeslice to find the canonical start for.
    year : int
        The year to calculate for.

    Returns
    -------
    pd.Timestamp or None
        The earliest datetime of the timeslice in the given year,
        or None if the timeslice has no valid dates (e.g., DayType(29,29)
        with Season(2,2) in a non-leap year).

    Notes
    -----
    Iterates through months in the season range and returns the first month
    where the daytype has valid dates. For most timeslices this is the first
    month, but for edge cases (e.g., day 31 in February) it may skip ahead.

    Examples
    --------
    >>> from datetime import time
    >>> ts = Timeslice(
    ...     season=Season(6, 6),
    ...     daytype=DayType(15, 15),
    ...     dailytimebracket=DailyTimeBracket(time(12, 0), ENDOFDAY)
    ... )
    >>> _get_canonical_start(ts, 2020)
    Timestamp('2020-06-15 12:00:00')

    See Also
    --------
    create_map : Uses canonical starts for snapshot-to-timeslice assignment
    """
    for m in range(ts.season.month_start, ts.season.month_end + 1):
        start_date, _ = ts.daytype.to_dates(year, m)
        if start_date is not None:
            h = ts.dailytimebracket.hour_start
            return pd.Timestamp(
                year=year, month=m, day=start_date.day,
                hour=h.hour, minute=h.minute, second=h.second,
                microsecond=h.microsecond
            )
    return None


def create_endpoints(
    snapshots: Union[pd.DatetimeIndex, pd.Index,
                     List[pd.Timestamp], List[datetime]]
) -> List[pd.Timestamp]:
    """
    Create extended snapshot endpoint list including year boundaries.

    Augments PyPSA snapshots with start-of-year and end-of-year timestamps
    for every year from the earliest to the latest snapshot. These endpoints
    split snapshot periods at year boundaries for correct duration accounting.

    Parameters
    ----------
    snapshots : pd.DatetimeIndex or pd.Index or List[pd.Timestamp] or List[datetime]
        PyPSA snapshot timestamps.

    Returns
    -------
    List[pd.Timestamp]
        Sorted list of unique timestamps including all original snapshots
        and year boundary markers (Jan 1 00:00 and Dec 31 ENDOFDAY for
        every year in the range). Duplicates are removed automatically.

    Notes
    -----
    All years from min(snapshot years) to max(snapshot years) are included,
    even if no snapshot exists in an intermediate year. This ensures correct
    handling of snapshot periods that span year gaps (e.g., snapshots in
    2020 and 2022 will include 2021 boundaries).

    Examples
    --------
    >>> snapshots = pd.DatetimeIndex(['2025-06-15', '2027-03-01'])
    >>> endpoints = create_endpoints(snapshots)
    >>> # Includes boundaries for 2025, 2026, and 2027

    See Also
    --------
    create_map : Uses endpoints for snapshot-to-timeslice mapping
    """
    snapshots = pd.DatetimeIndex(pd.to_datetime(snapshots)).sort_values()
    min_year = int(snapshots.year.min())
    max_year = int(snapshots.year.max())

    # Include year boundaries for ALL years from min to max
    endpoints = []
    for year in range(min_year, max_year + 1):
        soy = pd.Timestamp(year=year, month=1, day=1)
        eoy = pd.Timestamp.combine(date(year, 12, 31), ENDOFDAY)
        endpoints.append(soy)
        endpoints.append(eoy)

    endpoints = list(snapshots) + endpoints
    endpoints = sorted(set(endpoints))
    return endpoints


def create_map(
    snapshots: Union[pd.DatetimeIndex, pd.Index,
                     List[pd.Timestamp], List[datetime]],
    timeslices: List[Timeslice]
) -> Dict[pd.Timestamp, List[Tuple[int, Timeslice]]]:
    """
    Map each PyPSA snapshot to corresponding OSeMOSYS (year, timeslice) pairs.

    Creates a period-based mapping where each snapshot is treated as data
    valid from its timestamp until the next snapshot (or end of year for
    the last). Timeslices are assigned to the snapshot whose valid period
    contains their canonical start (earliest datetime of the pattern).

    Parameters
    ----------
    snapshots : pd.DatetimeIndex or pd.Index or List[pd.Timestamp] or List[datetime]
        PyPSA snapshot timestamps. Each represents data valid until the
        next snapshot.
    timeslices : List[Timeslice]
        OSeMOSYS Timeslice objects (Season x DayType x DailyTimeBracket).

    Returns
    -------
    Dict[pd.Timestamp, List[Tuple[int, Timeslice]]]
        Dictionary mapping each snapshot to a list of (year, timeslice)
        tuples that fall within that snapshot's valid period.

    Raises
    ------
    ValueError
        If snapshots is empty, or if mapped timeslice hours don't match
        the snapshot period hours (within 1 second tolerance).
    TypeError
        If snapshots contains non-datetime objects.

    Notes
    -----
    Algorithm:

    1. Each snapshot's valid period is [t_i, t_{i+1}), or
       [t_n, end-of-year] for the final snapshot.
    2. Year boundaries split periods for per-year accounting.
    3. For each timeslice in each relevant year, compute its canonical
       start via ``_get_canonical_start`` (earliest datetime of the
       Season x DayType x DailyTimeBracket pattern in that year).
    4. Assign the timeslice to the snapshot whose period contains the
       canonical start: ``period_start <= canonical_start < period_end``.
    5. Validate that mapped durations match period durations.

    This correctly handles:

    - Snapshots coarser than timeslices (1:many mapping)
    - Year boundary crossings (multi-year periods)
    - Leap year differences (Feb 29 zero-duration skipping)
    - Non-existent days (e.g., day 31 in months with 30 days)

    The canonical start approach is correct when the timeslice structure is
    produced by ``to_timeslices()`` from the same snapshots, because the
    Season/DayType decomposition ensures all occurrences of a timeslice
    pattern fall within a single snapshot period.

    Examples
    --------
    >>> from pyoscomp.translation.time import to_timeslices, create_map
    >>> snapshots = pd.DatetimeIndex(['2025-01-01', '2025-07-01'])
    >>> result = to_timeslices(snapshots)
    >>> mapping = create_map(snapshots, result.timeslices)
    >>> len(mapping)
    2
    >>> # First snapshot maps to Jan-Jun timeslices
    >>> # Second snapshot maps to Jul-Dec timeslices

    See Also
    --------
    to_timeslices : Creates timeslice structure from snapshots
    create_endpoints : Augments snapshots with year boundaries
    _get_canonical_start : Computes earliest datetime of a timeslice
    """
    # 1. Validate input, convert, and sort
    if len(snapshots) == 0:
        raise ValueError("snapshots cannot be empty")
    try:
        snapshots = pd.DatetimeIndex(
            pd.to_datetime(snapshots)
        ).sort_values()
    except (TypeError, ValueError) as e:
        raise TypeError(
            f"snapshots must contain datetime-like values. "
            f"Original error: {e}"
        ) from e

    snapshot_to_timeslice: Dict[
        pd.Timestamp, List[Tuple[int, Timeslice]]
    ] = {}

    # 2. Data in each snapshot is valid until the next one;
    # data in last snapshot is valid until end of its year
    valid_until = list(snapshots) + [
        pd.Timestamp.combine(
            date(snapshots[-1].year, 12, 31), ENDOFDAY
        )
    ]
    endpoints = create_endpoints(snapshots)

    # 3. For each snapshot period [valid_until[i], valid_until[i+1])
    for i in range(len(valid_until) - 1):
        period_start = valid_until[i]
        period_end = valid_until[i + 1]

        # Get year-bounded segment
        i_lower = endpoints.index(period_start)
        i_upper = endpoints.index(period_end)
        segment = endpoints[i_lower:i_upper + 1]
        valid_years = sorted(set(e.year for e in segment))

        # Find matching timeslices via canonical start
        idx_list: List[Tuple[int, int]] = []
        total_hours = 0.0

        for j, ts in enumerate(timeslices):
            for y in valid_years:
                # Skip zero-duration timeslices
                ts_hours = ts.duration_hours(y)
                if ts_hours < TOL:
                    continue

                # Get canonical start of this timeslice in year y
                cs = _get_canonical_start(ts, y)
                if cs is None:
                    continue

                # Assign if canonical start is in [period_start, period_end)
                if period_start <= cs < period_end:
                    idx_list.append((y, j))
                    total_hours += ts_hours

        # 4. Validate: mapped hours should match snapshot period hours
        expected_hours = 0.0
        for k in range(len(segment) - 1):
            if segment[k + 1].year == segment[k].year:
                delta = segment[k + 1] - segment[k]
                expected_hours += delta.total_seconds() / 3600

        diff_seconds = abs(total_hours - expected_hours) * 3600
        if diff_seconds > 1:
            raise ValueError(
                f"Mismatch! snapshot duration = {expected_hours:.4f}"
                f" hours, timeslice duration = {total_hours:.4f}"
                f" hours"
                f"\n(year, timeslice) pairs = "
                f"{[(y, timeslices[j]) for (y, j) in idx_list]}"
            )

        snapshot_to_timeslice[snapshots[i]] = [
            (y, timeslices[j]) for (y, j) in idx_list
        ]

    return snapshot_to_timeslice