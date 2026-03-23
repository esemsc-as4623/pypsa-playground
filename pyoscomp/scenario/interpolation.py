"""
Shared trajectory interpolation utilities for scenario components.

This module provides unified interpolation functions used across the
scenario package for handling trajectory data (year-based parameters with
multiple interpolation methods). It replaces duplicated implementations
in individual components and ensures consistent behavior.

Main Functions
--------------
interpolate_trajectory : Full trajectory covering all years with extrapolation
interpolate_value : Single-year point interpolation from a trajectory
step_interpolate_dict : Step-interpolate sparse dict to all years

Interpolation Methods
---------------------
'step' : Constant value (default), uses previous point
'linear' : Linear interpolation between points
'cagr' : Compound Annual Growth Rate extrapolation
"""

from typing import Dict, List, Union, Literal
import numpy as np


InterpolationMethod = Literal['step', 'linear', 'cagr']
ExtrapolationMethod = Literal['extend', 'zero', 'error']


def interpolate_value(
    year: int,
    trajectory: Dict[int, float],
    sorted_years: List[int],
    method: InterpolationMethod = 'step'
) -> float:
    """
    Interpolate a single value for a given year from a trajectory.

    Given a sparse trajectory dict (year -> value) and a target year,
    returns the interpolated value using the specified method.
    Handles boundary cases (before first year, after last year, exact match).

    Parameters
    ----------
    year : int
        The year to interpolate for.
    trajectory : Dict[int, float]
        Mapping from year to value.
    sorted_years : List[int]
        Pre-sorted list of keys in trajectory. Avoids repeated sorting.
    method : {'step', 'linear'}, default 'step'
        Interpolation method:
        - 'step': Return value from most recent point (backward-fill)
        - 'linear': Linear interpolation between adjacent points

    Returns
    -------
    float
        Interpolated value for the given year.

    Notes
    -----
    - If year is before first trajectory year: returns value at first year
    - If year is after last trajectory year: returns value at last year
    - If year is exact key in trajectory: returns exact value
    - Between points: uses method to interpolate
    """
    first_yr = sorted_years[0]
    last_yr = sorted_years[-1]

    # Before first point
    if year < first_yr:
        return trajectory[first_yr]

    # After last point
    if year > last_yr:
        return trajectory[last_yr]

    # Exact match
    if year in trajectory:
        return trajectory[year]

    # Between points: find the interval and interpolate
    for i in range(len(sorted_years) - 1):
        y_start = sorted_years[i]
        y_end = sorted_years[i + 1]
        if y_start <= year < y_end:
            v_start = trajectory[y_start]
            v_end = trajectory[y_end]

            if method == 'linear':
                ratio = (year - y_start) / (y_end - y_start)
                return v_start + ratio * (v_end - v_start)
            else:  # step or other
                return v_start

    # Fallback (should not reach here if sorted_years is correct)
    return trajectory[last_yr]


def step_interpolate_dict(
    data: Dict[int, float],
    all_years: List[int]
) -> Dict[int, float]:
    """
    Step-interpolate a sparse {year: value} dict to cover all years.

    Uses step (backward-fill) interpolation to expand sparse year->value
    mappings to all model years. Each year takes the value of the most
    recent defined year.

    Parameters
    ----------
    data : Dict[int, float]
        Sparse mapping from year to value (may have gaps).
    all_years : List[int]
        List of all model years (sorted).

    Returns
    -------
    Dict[int, float]
        Mapping from all model years to interpolated values.

    Notes
    -----
    - Years before first data point use first data value (forward-fill)
    - Years after last data point use last data value (carry-forward)
    - Step interpolation preserves exact values at defined points
    """
    sorted_years = sorted(data.keys())
    result = {}

    for y in all_years:
        # Find all defined years <= current year
        prev = [ey for ey in sorted_years if ey <= y]
        if prev:
            # Use most recent year before or at y
            result[y] = data[max(prev)]
        else:
            # Before first point: use first value
            result[y] = data[min(sorted_years)]

    return result


def interpolate_trajectory(
    region: str,
    fuel: str,
    trajectory: Dict[int, float],
    all_years: List[int],
    method: InterpolationMethod = 'step',
    extrapolation: ExtrapolationMethod = 'extend'
) -> List[Dict]:
    """
    Interpolate a trajectory to cover all model years with extrapolation.

    Expands a sparse trajectory dict to all model years using the specified
    interpolation method, with optional extrapolation beyond the trajectory
    bounds. Returns a list of records suitable for DataFrame insertion.

    Parameters
    ----------
    region : str
        Region identifier (stored in each record).
    fuel : str
        Fuel type identifier (stored in each record).
    trajectory : Dict[int, float]
        Mapping from year to value (may have gaps).
    all_years : List[int]
        List of all model years (should be sorted).
    method : {'step', 'linear', 'cagr'}, default 'step'
        Interpolation method:
        - 'step': Constant between points (default)
        - 'linear': Linear interpolation between points
        - 'cagr': Compound Annual Growth Rate (for forward extrapolation)
    extrapolation : {'extend', 'zero', 'error'}, default 'extend'
        How to handle years outside trajectory bounds:
        - 'extend': Use nearest boundary value (default)
        - 'zero': Use 0.0
        - 'error': Raise error if year outside bounds

    Returns
    -------
    List[Dict]
        List of records with keys 'REGION', 'FUEL', 'YEAR', 'VALUE'.

    Notes
    -----
    Extrapolation behavior:
    
    - **Before first year** (always 'extend' method):
        Uses value at first trajectory year (carry-backward)
    
    - **After last year** (respects `extrapolation` method):
        - 'extend': Use last trajectory value
        - 'linear': Continue linear trend from last two points
        - 'cagr': Continue CAGR trend from last two points
    
    - **CAGR special cases**:
        - If start value is zero: falls back to linear
        - Requires at least 2 points for trend computation
        - Negative growth rates are supported
    
    Examples
    --------
    Simple step interpolation:
    
    >>> trajectory = {2025: 100.0, 2030: 110.0}
    >>> all_years = [2025, 2026, 2027, 2028, 2029, 2030]
    >>> records = interpolate_trajectory('R1', 'ELEC', trajectory, all_years, method='step')
    >>> print(records)
    [{'REGION': 'R1', 'FUEL': 'ELEC', 'YEAR': 2025, 'VALUE': 100.0},
     {'REGION': 'R1', 'FUEL': 'ELEC', 'YEAR': 2026, 'VALUE': 100.0},
     ...
     {'REGION': 'R1', 'FUEL': 'ELEC', 'YEAR': 2030, 'VALUE': 110.0}]
    
    Linear interpolation with extrapolation:
    
    >>> trajectory = {2025: 100.0, 2030: 110.0}
    >>> all_years = [2024, 2025, 2026, 2030, 2031]
    >>> records = interpolate_trajectory(
    ...     'R1', 'ELEC', trajectory, all_years,
    ...     method='linear', extrapolation='extend'
    ... )
    >>> # 2024 (before): 100.0, 2031 (after): 110.0
    
    CAGR growth:
    
    >>> trajectory = {2020: 100.0, 2025: 121.55}  # ~4% annual growth
    >>> all_years = [2020, 2021, 2025, 2030]
    >>> records = interpolate_trajectory(
    ...     'R1', 'ELEC', trajectory, all_years, method='cagr'
    ... )
    >>> # 2030 continues ~4% growth: ~148.0
    """
    records = []
    sorted_years = sorted(trajectory.keys())
    first_yr, last_yr = sorted_years[0], sorted_years[-1]

    # Step 1: Preceding years (extrapolate backward) - always extend
    for y in [yr for yr in all_years if yr < first_yr]:
        records.append({
            "REGION": region,
            "FUEL": fuel,
            "YEAR": y,
            "VALUE": trajectory[first_yr]
        })

    # Step 2: Interpolate between defined points
    for i in range(len(sorted_years) - 1):
        y_start, y_end = sorted_years[i], sorted_years[i + 1]
        v_start, v_end = trajectory[y_start], trajectory[y_end]

        years_to_fill = [yr for yr in all_years if y_start <= yr < y_end]

        if method == 'linear':
            values = np.linspace(v_start, v_end, len(years_to_fill) + 1)[:-1]
        elif method == 'cagr':
            if v_start == 0:
                # CAGR undefined for zero start; fall back to linear
                values = np.linspace(v_start, v_end, len(years_to_fill) + 1)[:-1]
            else:
                steps = y_end - y_start
                rate = (v_end / v_start) ** (1 / steps) - 1
                values = [v_start * ((1 + rate) ** (yr - y_start)) for yr in years_to_fill]
        else:  # step or other
            values = [v_start] * len(years_to_fill)

        for yr, val in zip(years_to_fill, values):
            records.append({
                "REGION": region,
                "FUEL": fuel,
                "YEAR": yr,
                "VALUE": val
            })

    # Step 3: Final point (if in all_years)
    if last_yr in all_years:
        records.append({
            "REGION": region,
            "FUEL": fuel,
            "YEAR": last_yr,
            "VALUE": trajectory[last_yr]
        })

    # Step 4: Extrapolate forward using the same interpolation method
    remaining = [yr for yr in all_years if yr > last_yr]
    if remaining:
        if extrapolation == 'error':
            raise ValueError(
                f"Years {remaining} are beyond trajectory range "
                f"[{first_yr}, {last_yr}] and extrapolation='error'"
            )

        last_val = trajectory[last_yr]

        if extrapolation == 'zero':
            extrap_values = [0.0] * len(remaining)
        elif method == 'step' or len(sorted_years) < 2:
            # No trend to extrapolate
            extrap_values = [last_val] * len(remaining)
        else:
            # Use trend from last two points
            prev_yr = sorted_years[-2]
            prev_val = trajectory[prev_yr]
            y_diff = last_yr - prev_yr

            if method == 'cagr' and prev_val > 0:
                rate = (last_val / prev_val) ** (1 / y_diff) - 1
                extrap_values = [
                    last_val * ((1 + rate) ** (yr - last_yr))
                    for yr in remaining
                ]
            elif method == 'linear':
                # Continue linear trend
                v_slope = (last_val - prev_val) / y_diff
                extrap_values = [
                    last_val + v_slope * (yr - last_yr)
                    for yr in remaining
                ]
            else:
                # Fallback to constant for step
                extrap_values = [last_val] * len(remaining)

        for yr, val in zip(remaining, extrap_values):
            records.append({
                "REGION": region,
                "FUEL": fuel,
                "YEAR": yr,
                "VALUE": val
            })

    return records
