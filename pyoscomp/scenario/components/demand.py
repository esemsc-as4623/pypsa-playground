# pyoscomp/scenario/components/demand.py

"""
Demand component for scenario building in PyPSA-OSeMOSYS Comparison Framework.

This component handles energy demand definitions:
- SpecifiedAnnualDemand (total annual volume per fuel/region)
- SpecifiedDemandProfile (sub-annual shape across timeslices)
- AccumulatedAnnualDemand (flexible demand without specified profile)

OSeMOSYS Terminology: SpecifiedAnnualDemand, SpecifiedDemandProfile
PyPSA Terminology: Load (p_set for fixed demand)

Prerequisites:
- TimeComponent (years, timeslices must be defined)
- TopologyComponent (regions must be defined)
"""

import math
import numpy as np
import pandas as pd
from typing import Callable, Dict, List, Optional, Tuple, Union

from .base import ScenarioComponent
from .time import TimeComponent


class DemandComponent(ScenarioComponent):
    """
    Demand component for load/demand definitions.

    Handles OSeMOSYS demand parameters including annual volumes and
    sub-annual profiles. Profiles must sum to 1.0 per (region, fuel, year).

    Attributes
    ----------
    years : list of int
        Model years (loaded from prerequisites).
    regions : list of str
        Region identifiers (loaded from prerequisites).
    annual_demand_df : pd.DataFrame
        SpecifiedAnnualDemand (REGION, FUEL, YEAR, VALUE).
    profile_demand_df : pd.DataFrame
        SpecifiedDemandProfile (REGION, FUEL, TIMESLICE, YEAR, VALUE).
    accumulated_demand_df : pd.DataFrame
        AccumulatedAnnualDemand (REGION, FUEL, YEAR, VALUE).

    Owned Files
    -----------
    - SpecifiedAnnualDemand.csv
    - SpecifiedDemandProfile.csv
    - AccumulatedAnnualDemand.csv

    Example
    -------
    Define annual demand with a trajectory::

        demand = DemandComponent(scenario_dir)
        demand.add_annual_demand(
            region='REGION1',
            fuel='ELECTRICITY',
            trajectory={2025: 100, 2030: 120, 2040: 150},
            interpolation='linear'
        )
        demand.process()  # Generate profiles
        demand.save()

    See Also
    --------
    component_mapping.md : Full documentation of demand ownership
    """

    owned_files = [
        'SpecifiedAnnualDemand.csv',
        'SpecifiedDemandProfile.csv',
        'AccumulatedAnnualDemand.csv'
    ]

    def __init__(self, scenario_dir: str):
        """
        Initialize demand component.

        Parameters
        ----------
        scenario_dir : str
            Path to the scenario directory.

        Raises
        ------
        AttributeError
            If TimeComponent or TopologyComponent not initialized.
        """
        super().__init__(scenario_dir)

        # Check prerequisites
        prereqs = self.check_prerequisites(
            require_years=True,
            require_regions=True,
            require_timeslices=True
        )
        self.years = prereqs['years']
        self.regions = prereqs['regions']
        self.timeslices = prereqs['timeslices']

        # Load time axis data for profile calculations
        self._time_axis = self._load_time_axis()

        # Demand parameters
        self.annual_demand_df = self.init_dataframe("SpecifiedAnnualDemand")
        self.profile_demand_df = self.init_dataframe("SpecifiedDemandProfile")
        self.accumulated_demand_df = self.init_dataframe("AccumulatedAnnualDemand")

        # Tracking
        self._defined_fuels: set = set()  # (region, fuel) pairs
        self._profile_assignments: Dict[Tuple, Dict] = {}  # (region, fuel, year) -> assignment

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def defined_fuels(self) -> List[Tuple[str, str]]:
        """Get list of defined (region, fuel) pairs."""
        return list(self._defined_fuels)

    @property
    def fuels(self) -> set:
        """Get set of unique fuel identifiers."""
        return {fuel for _, fuel in self._defined_fuels}

    # =========================================================================
    # Load and Save
    # =========================================================================

    def load(self) -> None:
        """
        Load all demand parameter CSV files.

        Raises
        ------
        FileNotFoundError
            If any required file is missing.
        ValueError
            If any file fails schema validation.
        """
        self.annual_demand_df = self.read_csv("SpecifiedAnnualDemand.csv")
        self.profile_demand_df = self.read_csv("SpecifiedDemandProfile.csv")
        self.accumulated_demand_df = self.read_csv("AccumulatedAnnualDemand.csv")

        # Update tracking
        self._defined_fuels = set(
            zip(self.annual_demand_df["REGION"], self.annual_demand_df["FUEL"])
        )

    def save(self) -> None:
        """
        Save all demand parameter DataFrames to CSV.

        Raises
        ------
        ValueError
            If any DataFrame fails schema validation.
        """
        # Sort before saving
        cols_annual = ["REGION", "FUEL", "YEAR", "VALUE"]
        cols_profile = ["REGION", "FUEL", "TIMESLICE", "YEAR", "VALUE"]
        cols_accum = ["REGION", "FUEL", "YEAR", "VALUE"]

        df = self.annual_demand_df[cols_annual].sort_values(
            by=["REGION", "FUEL", "YEAR"]
        )
        self.write_dataframe("SpecifiedAnnualDemand.csv", df)

        df = self.profile_demand_df[cols_profile].sort_values(
            by=["REGION", "FUEL", "TIMESLICE", "YEAR"]
        )
        self.write_dataframe("SpecifiedDemandProfile.csv", df)

        df = self.accumulated_demand_df[cols_accum].sort_values(
            by=["REGION", "FUEL", "YEAR"]
        )
        self.write_dataframe("AccumulatedAnnualDemand.csv", df)

    # =========================================================================
    # User Input Methods
    # =========================================================================

    def add_annual_demand(
        self,
        region: str,
        fuel: str,
        trajectory: Dict[int, float],
        trend_function: Optional[Callable[[int], float]] = None,
        interpolation: str = 'step'
    ) -> None:
        """
        Define annual demand for a region and fuel over model years.

        Parameters
        ----------
        region : str
            Region identifier.
        fuel : str
            Fuel/demand type identifier.
        trajectory : dict
            Known demand points {year: value}.
        trend_function : callable, optional
            Function f(year) -> value for years not in trajectory.
            Takes precedence over interpolation if provided.
        interpolation : {'step', 'linear', 'cagr'}
            Method for filling years between trajectory points.
            - 'step': Hold previous value constant
            - 'linear': Linear interpolation
            - 'cagr': Compound annual growth rate

        Raises
        ------
        ValueError
            If region not defined, trajectory empty, or negative values.

        Example
        -------
        >>> demand.add_annual_demand(
        ...     region='REGION1',
        ...     fuel='ELEC',
        ...     trajectory={2025: 100, 2035: 150},
        ...     interpolation='linear'
        ... )
        """
        # Validation
        if region not in self.regions:
            raise ValueError(f"Region '{region}' not defined. Initialize topology first.")
        if not trajectory:
            raise ValueError(f"Empty trajectory for {region}/{fuel}")
        for y, val in trajectory.items():
            if val < 0:
                raise ValueError(f"Negative demand {val} in year {y} for {region}/{fuel}")
        if interpolation not in ['step', 'linear', 'cagr']:
            interpolation = 'step'

        self._defined_fuels.add((region, fuel))
        records = []

        if trend_function:
            # Use function for all years
            for y in self.years:
                val = trajectory.get(y, trend_function(y))
                if val < 0:
                    raise ValueError(f"Negative demand {val} from trend_function in year {y}")
                records.append({
                    "REGION": region, "FUEL": fuel, "YEAR": y, "VALUE": val
                })
        else:
            # Interpolation-based
            records = self._interpolate_trajectory(
                region, fuel, trajectory, interpolation
            )

        self.annual_demand_df = self.add_to_dataframe(
            self.annual_demand_df, records,
            key_columns=["REGION", "FUEL", "YEAR"]
        )

    def add_flexible_demand(
        self,
        region: str,
        fuel: str,
        year: int,
        value: float
    ) -> None:
        """
        Add flexible (accumulated) demand for a region, fuel, and year.

        Flexible demand can be met at any time during the year.

        Parameters
        ----------
        region : str
            Region identifier.
        fuel : str
            Fuel/demand type identifier.
        year : int
            Model year.
        value : float
            Flexible demand value.

        Raises
        ------
        ValueError
            If value is negative.
        """
        if value < 0:
            raise ValueError(f"Flexible demand cannot be negative: {value}")

        record = [{"REGION": region, "FUEL": fuel, "YEAR": year, "VALUE": value}]
        self.accumulated_demand_df = self.add_to_dataframe(
            self.accumulated_demand_df, record,
            key_columns=["REGION", "FUEL", "YEAR"]
        )

    def set_profile(
        self,
        region: str,
        fuel: str,
        year: Optional[Union[int, List[int]]] = None,
        timeslice_weights: Optional[Dict[str, float]] = None,
        season_weights: Optional[Dict[str, float]] = None,
        daytype_weights: Optional[Dict[str, float]] = None,
        bracket_weights: Optional[Dict[str, float]] = None
    ) -> None:
        """
        Set demand profile for a region/fuel combination.

        Profiles can be specified directly via timeslice weights or
        hierarchically via season/daytype/bracket weights.

        Parameters
        ----------
        region : str
            Region identifier.
        fuel : str
            Fuel identifier.
        year : int, list of int, or None
            Year(s) to apply profile. None applies to all years.
        timeslice_weights : dict, optional
            Direct {timeslice: weight} mapping. Takes precedence if provided.
        season_weights : dict, optional
            {season: weight} for hierarchical specification.
        daytype_weights : dict, optional
            {daytype: weight} for hierarchical specification.
        bracket_weights : dict, optional
            {dailytimebracket: weight} for hierarchical specification.

        Raises
        ------
        ValueError
            If region/fuel not defined or year invalid.

        Notes
        -----
        Weights are normalized internally to sum to 1.0.
        Missing entries default to proportional (YearSplit) values.
        """
        # Validation
        if region not in self.regions:
            raise ValueError(f"Region '{region}' not defined")
        if (region, fuel) not in self._defined_fuels:
            raise ValueError(
                f"Fuel '{fuel}' not defined for region '{region}'. "
                "Call add_annual_demand() first."
            )

        # Determine years
        if year is None:
            years = self.years
        elif isinstance(year, int):
            if year not in self.years:
                raise ValueError(f"Year {year} not in model years")
            years = [year]
        else:
            years = year

        # Build assignments
        for y in years:
            if timeslice_weights is not None:
                weights = self._apply_timeslice_weights(timeslice_weights, y)
            elif any(w is not None for w in [season_weights, daytype_weights, bracket_weights]):
                weights = self._apply_hierarchical_weights(
                    season_weights or {},
                    daytype_weights or {},
                    bracket_weights or {},
                    y
                )
            else:
                # Flat profile (use YearSplit)
                self._profile_assignments[(region, fuel, y)] = {"type": "flat"}
                continue

            # Normalize
            total = sum(weights.values())
            if total > 0:
                norm_weights = {k: v / total for k, v in weights.items()}
                self._profile_assignments[(region, fuel, y)] = {
                    "type": "custom",
                    "weights": norm_weights
                }
            else:
                self._profile_assignments[(region, fuel, y)] = {"type": "flat"}

    # =========================================================================
    # Processing
    # =========================================================================

    def process(self) -> None:
        """
        Generate demand profiles from assignments.

        Creates SpecifiedDemandProfile entries for all defined (region, fuel)
        combinations. Profiles are normalized to sum to 1.0 per
        (region, fuel, year).

        Call this after setting up annual demands and profiles.
        """
        # Ensure all (region, fuel, year) have assignments
        for region, fuel in self._defined_fuels:
            for year in self.years:
                if (region, fuel, year) not in self._profile_assignments:
                    self._profile_assignments[(region, fuel, year)] = {"type": "flat"}

        # Generate profile rows
        all_rows = []
        for (region, fuel, year), assignment in self._profile_assignments.items():
            rows = self._generate_profile_rows(region, fuel, year, assignment)
            all_rows.extend(rows)

        # Normalize and update DataFrame
        normalized = self._normalize_profiles(all_rows)
        self.profile_demand_df = pd.DataFrame(normalized)

    # =========================================================================
    # Validation
    # =========================================================================

    def validate(self) -> None:
        """
        Validate demand component state.

        Raises
        ------
        ValueError
            If profiles don't sum to 1.0, or fuels referenced without
            annual demand.
        """
        if self.profile_demand_df.empty:
            return

        # Check profile sums
        grouped = self.profile_demand_df.groupby(
            ['REGION', 'FUEL', 'YEAR']
        )['VALUE'].sum()

        for (region, fuel, year), total in grouped.items():
            if not math.isclose(total, 1.0, abs_tol=1e-6):
                raise ValueError(
                    f"Profile for ({region}, {fuel}, {year}) sums to "
                    f"{total:.6f}, expected 1.0"
                )

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _load_time_axis(self) -> pd.DataFrame:
        """Load time axis data from TimeComponent."""
        time_data = TimeComponent.load_time_axis(self)
        df = time_data['yearsplit'].copy()
        slice_map = time_data['slice_map']

        df['Season'] = df['TIMESLICE'].map(lambda x: slice_map[x]['Season'])
        df['DayType'] = df['TIMESLICE'].map(lambda x: slice_map[x]['DayType'])
        df['DailyTimeBracket'] = df['TIMESLICE'].map(
            lambda x: slice_map[x]['DailyTimeBracket']
        )
        return df

    def _interpolate_trajectory(
        self,
        region: str,
        fuel: str,
        trajectory: Dict[int, float],
        method: str
    ) -> List[Dict]:
        """Interpolate trajectory to cover all model years."""
        records = []
        sorted_years = sorted(trajectory.keys())
        first_yr, last_yr = sorted_years[0], sorted_years[-1]

        # Preceding years (extrapolate backward)
        for y in [yr for yr in self.years if yr < first_yr]:
            records.append({
                "REGION": region, "FUEL": fuel, "YEAR": y,
                "VALUE": trajectory[first_yr]
            })

        # Interpolate between points
        for i in range(len(sorted_years) - 1):
            y_start, y_end = sorted_years[i], sorted_years[i + 1]
            v_start, v_end = trajectory[y_start], trajectory[y_end]

            years_to_fill = [yr for yr in self.years if y_start <= yr < y_end]

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
            else:
                values = [v_start] * len(years_to_fill)

            for yr, val in zip(years_to_fill, values):
                records.append({
                    "REGION": region, "FUEL": fuel, "YEAR": yr, "VALUE": val
                })

        # Final point
        if last_yr in self.years:
            records.append({
                "REGION": region, "FUEL": fuel, "YEAR": last_yr,
                "VALUE": trajectory[last_yr]
            })

        # Extrapolate forward using the same interpolation method
        remaining = [yr for yr in self.years if yr > last_yr]
        if remaining:
            last_val = trajectory[last_yr]
            if method == 'step' or len(sorted_years) < 2:
                extrap_values = [last_val] * len(remaining)
            else:
                prev_yr = sorted_years[-2]
                prev_val = trajectory[prev_yr]
                y_diff = last_yr - prev_yr
                if method == 'cagr' and prev_val > 0:
                    rate = (last_val / prev_val) ** (1 / y_diff) - 1
                    extrap_values = [
                        last_val * ((1 + rate) ** (yr - last_yr))
                        for yr in remaining
                    ]
                else:  # linear (or cagr with zero prev_val)
                    slope = (last_val - prev_val) / y_diff
                    extrap_values = [
                        last_val + slope * (yr - last_yr)
                        for yr in remaining
                    ]
            for yr, val in zip(remaining, extrap_values):
                records.append({
                    "REGION": region, "FUEL": fuel, "YEAR": yr,
                    "VALUE": max(0, val)
                })

        return records

    def _apply_timeslice_weights(
        self,
        weights: Dict[str, float],
        year: int
    ) -> Dict[str, float]:
        """Apply timeslice-level weights to YearSplit base."""
        result = {}
        year_data = self._time_axis[self._time_axis["YEAR"] == year]

        for _, row in year_data.iterrows():
            ts = row["TIMESLICE"]
            base_val = row["VALUE"]
            factor = weights.get(ts, 1.0)
            result[ts] = base_val * factor

        return result

    def _apply_hierarchical_weights(
        self,
        season_w: Dict[str, float],
        daytype_w: Dict[str, float],
        bracket_w: Dict[str, float],
        year: int
    ) -> Dict[str, float]:
        """Apply hierarchical weights (season × daytype × bracket)."""
        year_data = self._time_axis[self._time_axis["YEAR"] == year]
        result = {}

        for _, row in year_data.iterrows():
            ts = row["TIMESLICE"]
            s, d, b = row["Season"], row["DayType"], row["DailyTimeBracket"]
            base_val = row["VALUE"]

            factor = (
                season_w.get(s, 1.0) *
                daytype_w.get(d, 1.0) *
                bracket_w.get(b, 1.0)
            )
            result[ts] = base_val * factor

        return result

    def _generate_profile_rows(
        self,
        region: str,
        fuel: str,
        year: int,
        assignment: Dict
    ) -> List[Dict]:
        """Generate profile rows for a single (region, fuel, year)."""
        p_type = assignment.get("type", "flat")

        if p_type == "custom":
            weights = assignment["weights"]
            return [
                {"REGION": region, "FUEL": fuel, "TIMESLICE": ts,
                 "YEAR": year, "VALUE": weights[ts]}
                for ts in weights
            ]
        else:
            # Flat: use YearSplit directly
            year_data = self._time_axis[self._time_axis["YEAR"] == year]
            return [
                {"REGION": region, "FUEL": fuel, "TIMESLICE": row["TIMESLICE"],
                 "YEAR": year, "VALUE": row["VALUE"]}
                for _, row in year_data.iterrows()
            ]

    def _normalize_profiles(self, rows: List[Dict]) -> List[Dict]:
        """Normalize profile rows so each (region, fuel, year) sums to 1.0."""
        if not rows:
            return []

        df = pd.DataFrame(rows)
        group_cols = ["REGION", "FUEL", "YEAR"]
        sums = df.groupby(group_cols)['VALUE'].sum()

        for idx, total in sums.items():
            if not np.isclose(total, 1.0, atol=1e-9):
                residual = 1.0 - total
                mask = (
                    (df[group_cols[0]] == idx[0]) &
                    (df[group_cols[1]] == idx[1]) &
                    (df[group_cols[2]] == idx[2])
                )
                # Adjust largest value to fix residual
                idx_to_fix = df.loc[mask, 'VALUE'].idxmax()
                df.at[idx_to_fix, 'VALUE'] += residual
                df.loc[mask, 'VALUE'] = df.loc[mask, 'VALUE'].round(9)

        return df.to_dict('records')

    # =========================================================================
    # Representation
    # =========================================================================

    def __repr__(self) -> str:
        return (
            f"DemandComponent(scenario_dir='{self.scenario_dir}', "
            f"fuels={len(self._defined_fuels)})"
        )
