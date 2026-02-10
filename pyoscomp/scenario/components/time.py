# pyoscomp/scenario/components/time.py

"""
Time component for scenario building in PyPSA-OSeMOSYS Comparison Framework.

This component handles temporal resolution definitions:
- YEAR set (model years / investment periods)
- TIMESLICE set (temporal divisions within a year)
- SEASON, DAYTYPE, DAILYTIMEBRACKET sets (timeslice hierarchy)
- Conversion tables (timeslice → season/daytype/bracket mappings)
- YearSplit, DaySplit, DaysInDayType parameters

OSeMOSYS uses a hierarchical timeslice structure:
    Year → Season → DayType → DailyTimeBracket → Timeslice

PyPSA uses sequential snapshots (timestamps).

The translation/time module handles conversion between these paradigms.
"""

import math
import os
import pandas as pd
from decimal import Decimal, getcontext
from typing import Dict, List, Optional, Tuple, Union

from .base import ScenarioComponent
from ...constants import TOL, HOURS_PER_DAY, hours_in_year, days_in_year

# Set decimal precision for exact arithmetic
getcontext().prec = 28


class TimeComponent(ScenarioComponent):
    """
    Time component for temporal structure definitions.

    Handles OSeMOSYS time parameters: years, timeslices, seasons, daytypes,
    daily time brackets, and all conversion/weighting tables.

    Attributes
    ----------
    years_df : pd.DataFrame
        YEAR set (VALUE column).
    timeslices_df : pd.DataFrame
        TIMESLICE set (VALUE column).
    seasons_df : pd.DataFrame
        SEASON set (VALUE column).
    daytypes_df : pd.DataFrame
        DAYTYPE set (VALUE column).
    brackets_df : pd.DataFrame
        DAILYTIMEBRACKET set (VALUE column).
    yearsplit_df : pd.DataFrame
        YearSplit parameter (TIMESLICE, YEAR, VALUE).
    daysplit_df : pd.DataFrame
        DaySplit parameter (DAILYTIMEBRACKET, YEAR, VALUE).
    conversionls_df : pd.DataFrame
        Conversionls (TIMESLICE, SEASON, VALUE) - binary mapping.
    conversionld_df : pd.DataFrame
        Conversionld (TIMESLICE, DAYTYPE, VALUE) - binary mapping.
    conversionlh_df : pd.DataFrame
        Conversionlh (TIMESLICE, DAILYTIMEBRACKET, VALUE) - binary mapping.
    daysindaytype_df : pd.DataFrame
        DaysInDayType (SEASON, DAYTYPE, YEAR, VALUE).

    Owned Files
    -----------
    Sets: YEAR.csv, TIMESLICE.csv, SEASON.csv, DAYTYPE.csv, DAILYTIMEBRACKET.csv
    Params: YearSplit.csv, DaySplit.csv, Conversionls.csv, Conversionld.csv,
            Conversionlh.csv, DaysInDayType.csv

    Example
    -------
    Create time structure::

        time = TimeComponent(scenario_dir)

        # Define structure
        years = [2025, 2030, 2035]
        seasons = {"Winter": 90, "Summer": 90, "Shoulder": 185}  # days
        daytypes = {"Weekday": 5, "Weekend": 2}  # relative weights
        brackets = {"Day": 16, "Night": 8}  # hours

        time.add_time_structure(years, seasons, daytypes, brackets)
        time.save()

        # Or load existing
        time.load()
        print(time.years)  # [2025, 2030, 2035]

    See Also
    --------
    translation.time : Module for PyPSA <-> OSeMOSYS time translation
    component_mapping.md : Full documentation of time ownership
    """

    owned_files = [
        'YEAR.csv', 'TIMESLICE.csv', 'SEASON.csv', 'DAYTYPE.csv',
        'DAILYTIMEBRACKET.csv', 'YearSplit.csv', 'DaySplit.csv',
        'Conversionls.csv', 'Conversionld.csv', 'Conversionlh.csv',
        'DaysInDayType.csv'
    ]

    def __init__(self, scenario_dir: str):
        """
        Initialize time component.

        Parameters
        ----------
        scenario_dir : str
            Path to the scenario directory.
        """
        super().__init__(scenario_dir)

        # Sets
        self.years_df = self.init_dataframe("YEAR")
        self.timeslices_df = self.init_dataframe("TIMESLICE")
        self.seasons_df = self.init_dataframe("SEASON")
        self.daytypes_df = self.init_dataframe("DAYTYPE")
        self.brackets_df = self.init_dataframe("DAILYTIMEBRACKET")

        # Parameters
        self.yearsplit_df = self.init_dataframe("YearSplit")
        self.daysplit_df = self.init_dataframe("DaySplit")
        self.conversionls_df = self.init_dataframe("Conversionls")
        self.conversionld_df = self.init_dataframe("Conversionld")
        self.conversionlh_df = self.init_dataframe("Conversionlh")
        self.daysindaytype_df = self.init_dataframe("DaysInDayType")

        # Internal tracking
        self._timeslice_map: Dict[str, Tuple[str, str, str]] = {}

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def years(self) -> List[int]:
        """Get sorted list of model years."""
        if self.years_df.empty:
            return []
        return sorted(self.years_df['VALUE'].astype(int).tolist())

    @property
    def timeslices(self) -> List[str]:
        """Get list of timeslice identifiers."""
        if self.timeslices_df.empty:
            return []
        return self.timeslices_df['VALUE'].tolist()

    @property
    def seasons(self) -> List[str]:
        """Get list of season identifiers."""
        if self.seasons_df.empty:
            return []
        return self.seasons_df['VALUE'].tolist()

    @property
    def daytypes(self) -> List[str]:
        """Get list of daytype identifiers."""
        if self.daytypes_df.empty:
            return []
        return self.daytypes_df['VALUE'].tolist()

    @property
    def dailytimebrackets(self) -> List[str]:
        """Get list of daily time bracket identifiers."""
        if self.brackets_df.empty:
            return []
        return self.brackets_df['VALUE'].tolist()

    @property
    def num_timeslices(self) -> int:
        """Get number of timeslices."""
        return len(self.timeslices_df)

    # =========================================================================
    # Load and Save
    # =========================================================================

    def load(self) -> None:
        """
        Load all time parameter CSV files.

        Raises
        ------
        FileNotFoundError
            If any required file is missing.
        ValueError
            If any file fails schema validation.
        """
        # Sets
        self.years_df = self.read_csv("YEAR.csv")
        self.timeslices_df = self.read_csv("TIMESLICE.csv")
        self.seasons_df = self.read_csv("SEASON.csv")
        self.daytypes_df = self.read_csv("DAYTYPE.csv")
        self.brackets_df = self.read_csv("DAILYTIMEBRACKET.csv")

        # Parameters
        self.yearsplit_df = self.read_csv("YearSplit.csv")
        self.daysplit_df = self.read_csv("DaySplit.csv")
        self.conversionls_df = self.read_csv("Conversionls.csv")
        self.conversionld_df = self.read_csv("Conversionld.csv")
        self.conversionlh_df = self.read_csv("Conversionlh.csv")
        self.daysindaytype_df = self.read_csv("DaysInDayType.csv")

        # Rebuild internal map
        self._build_timeslice_map()

    def save(self) -> None:
        """
        Save all time parameter DataFrames to CSV.

        Raises
        ------
        ValueError
            If any DataFrame fails schema validation.
        """
        # Sets
        self.write_dataframe("YEAR.csv", self.years_df)
        self.write_dataframe("TIMESLICE.csv", self.timeslices_df)
        self.write_dataframe("SEASON.csv", self.seasons_df)
        self.write_dataframe("DAYTYPE.csv", self.daytypes_df)
        self.write_dataframe("DAILYTIMEBRACKET.csv", self.brackets_df)

        # Parameters
        self.write_dataframe("YearSplit.csv", self.yearsplit_df)
        self.write_dataframe("DaySplit.csv", self.daysplit_df)
        self.write_dataframe("Conversionls.csv", self.conversionls_df)
        self.write_dataframe("Conversionld.csv", self.conversionld_df)
        self.write_dataframe("Conversionlh.csv", self.conversionlh_df)
        self.write_dataframe("DaysInDayType.csv", self.daysindaytype_df)

    # =========================================================================
    # User Input Methods
    # =========================================================================

    def add_time_structure(
        self,
        years: Union[List[int], Tuple[int, int, int]],
        seasons: Dict[str, float],
        daytypes: Dict[str, float],
        brackets: Dict[str, float]
    ) -> None:
        """
        Define the complete time structure for the scenario.

        Creates all time-related sets and parameters. Values are normalized
        to sum to 1.0 for consistent calculations.

        Parameters
        ----------
        years : list of int or tuple (start, end, step)
            Model years. Either explicit list [2025, 2030, 2035] or
            tuple for range (2025, 2050, 5).
        seasons : dict
            Season definitions {name: days}. Values represent relative
            duration (e.g., {"Winter": 90, "Summer": 90, "Shoulder": 185}).
            Should sum to ~365 for calendar alignment.
        daytypes : dict
            Day type definitions {name: weight}. Values represent relative
            frequency (e.g., {"Weekday": 5, "Weekend": 2}).
        brackets : dict
            Daily time bracket definitions {name: hours}.
            Should sum to 24 for hour alignment.

        Raises
        ------
        ValueError
            If inputs are empty or contain only zeros.

        Notes
        -----
        All values are normalized internally. If seasons don't sum to 365 or
        brackets don't sum to 24, a warning is printed but calculation proceeds.
        The relative proportions are always preserved.

        Example
        -------
        >>> time.add_time_structure(
        ...     years=[2025, 2030, 2035],
        ...     seasons={"Winter": 90, "Summer": 90, "Shoulder": 185},
        ...     daytypes={"Weekday": 5, "Weekend": 2},
        ...     brackets={"Day": 16, "Night": 8}
        ... )
        """
        # Process years
        processed_years = self._process_years(years)
        self.years_df = pd.DataFrame({"VALUE": processed_years})

        # Process time structure (creates all other DataFrames)
        self._process_time_structure(processed_years, seasons, daytypes, brackets)

    def set_years(self, years: Union[List[int], Tuple[int, int, int]]) -> List[int]:
        """
        Set model years without full time structure.

        Parameters
        ----------
        years : list of int or tuple (start, end, step)
            Model years.

        Returns
        -------
        list of int
            Processed year list.

        Notes
        -----
        Use add_time_structure() for complete setup including timeslices.
        This method only sets YEAR.csv.
        """
        processed = self._process_years(years)
        self.years_df = pd.DataFrame({"VALUE": processed})
        return processed

    # =========================================================================
    # Time Axis Access (for other components)
    # =========================================================================

    def get_timeslice_map(self) -> Dict[str, Dict[str, str]]:
        """
        Get mapping of timeslices to their components.

        Returns
        -------
        dict
            {timeslice: {'Season': s, 'DayType': d, 'DailyTimeBracket': b}}
        """
        if not self._timeslice_map:
            self._build_timeslice_map()

        result = {}
        for ts, (season, daytype, bracket) in self._timeslice_map.items():
            result[ts] = {
                'Season': season,
                'DayType': daytype,
                'DailyTimeBracket': bracket
            }
        return result

    def get_yearsplit(self, timeslice: str, year: int) -> Optional[float]:
        """
        Get YearSplit value for a specific timeslice and year.

        Parameters
        ----------
        timeslice : str
            Timeslice identifier.
        year : int
            Model year.

        Returns
        -------
        float or None
            YearSplit fraction, or None if not found.
        """
        mask = (
            (self.yearsplit_df['TIMESLICE'] == timeslice) &
            (self.yearsplit_df['YEAR'] == year)
        )
        matches = self.yearsplit_df.loc[mask, 'VALUE']
        if matches.empty:
            return None
        return float(matches.iloc[0])

    @staticmethod
    def load_time_axis(component: ScenarioComponent) -> Dict:
        """
        Static method to load time axis data for use in other components.

        Parameters
        ----------
        component : ScenarioComponent
            Any component with access to scenario_dir.

        Returns
        -------
        dict
            {'yearsplit': DataFrame, 'slice_map': dict}
        """
        scenario_dir = component.scenario_dir

        yearsplit = pd.read_csv(os.path.join(scenario_dir, "YearSplit.csv"))
        conversionls = pd.read_csv(os.path.join(scenario_dir, "Conversionls.csv"))
        conversionld = pd.read_csv(os.path.join(scenario_dir, "Conversionld.csv"))
        conversionlh = pd.read_csv(os.path.join(scenario_dir, "Conversionlh.csv"))

        # Build slice_map
        slice_map = {}
        for _, row in conversionls.iterrows():
            slice_map.setdefault(row['TIMESLICE'], {})['Season'] = row['SEASON']
        for _, row in conversionld.iterrows():
            slice_map.setdefault(row['TIMESLICE'], {})['DayType'] = row['DAYTYPE']
        for _, row in conversionlh.iterrows():
            slice_map.setdefault(row['TIMESLICE'], {})['DailyTimeBracket'] = row['DAILYTIMEBRACKET']

        return {'yearsplit': yearsplit, 'slice_map': slice_map}

    # =========================================================================
    # Validation
    # =========================================================================

    def validate(self) -> None:
        """
        Validate time component state.

        Raises
        ------
        ValueError
            If years empty, YearSplit doesn't sum to 1.0 per year,
            or timeslice mappings are incomplete.
        """
        if self.years_df.empty:
            raise ValueError("No years defined")

        if self.timeslices_df.empty:
            raise ValueError("No timeslices defined")

        # Validate YearSplit sums to 1.0 per year
        for year in self.years:
            year_mask = self.yearsplit_df['YEAR'] == year
            year_sum = self.yearsplit_df.loc[year_mask, 'VALUE'].sum()
            if not math.isclose(year_sum, 1.0, abs_tol=TOL):
                raise ValueError(
                    f"YearSplit for year {year} sums to {year_sum:.6f}, expected 1.0"
                )

        # Validate DaySplit sums to 1.0 per year
        for year in self.years:
            year_mask = self.daysplit_df['YEAR'] == year
            day_sum = self.daysplit_df.loc[year_mask, 'VALUE'].sum()
            if not math.isclose(day_sum, 1.0, abs_tol=TOL):
                raise ValueError(
                    f"DaySplit for year {year} sums to {day_sum:.6f}, expected 1.0"
                )

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _process_years(
        self,
        years_input: Union[List[int], Tuple[int, int, int]]
    ) -> List[int]:
        """Convert years input to sorted list."""
        if isinstance(years_input, (list, set)):
            return sorted(list(years_input))
        elif isinstance(years_input, tuple) and len(years_input) == 3:
            start, end, step = years_input
            return list(range(start, end + 1, step))
        else:
            raise ValueError(
                "years must be list of ints or tuple (start, end, step)"
            )

    def _process_time_structure(
        self,
        years: List[int],
        seasons: Dict[str, float],
        daytypes: Dict[str, float],
        brackets: Dict[str, float]
    ) -> None:
        """Generate all time structure DataFrames."""
        # Validate inputs
        if not seasons or not daytypes or not brackets:
            raise ValueError("Seasons, daytypes, and brackets must be non-empty")
        if sum(seasons.values()) == 0:
            raise ValueError("Season values must sum to non-zero")
        if sum(daytypes.values()) == 0:
            raise ValueError("Daytype values must sum to non-zero")
        if sum(brackets.values()) == 0:
            raise ValueError("Bracket values must sum to non-zero")

        # Warn if values don't match expected totals
        ref_year = years[0]
        if abs(sum(seasons.values()) - days_in_year(ref_year)) > 1:
            print(
                f"WARNING: Season days sum to {sum(seasons.values())}, "
                f"expected {days_in_year(ref_year)}. Values will be normalized."
            )
        if abs(sum(brackets.values()) - HOURS_PER_DAY) > 0.001:
            print(
                f"WARNING: Bracket hours sum to {sum(brackets.values())}, "
                f"expected {HOURS_PER_DAY}. Values will be normalized."
            )

        # Normalize to fractions
        s_fracs = self._normalize(seasons)
        d_fracs = self._normalize(daytypes)
        b_fracs = self._normalize(brackets)

        # Update set DataFrames
        self.seasons_df = pd.DataFrame({"VALUE": list(seasons.keys())})
        self.daytypes_df = pd.DataFrame({"VALUE": list(daytypes.keys())})
        self.brackets_df = pd.DataFrame({"VALUE": list(brackets.keys())})

        # Generate timeslices (Cartesian product: Season × DayType × Bracket)
        timeslice_data = []
        map_ls = []
        map_ld = []
        map_lh = []
        year_split_rows = []
        day_split_rows = []

        for s, s_val in s_fracs.items():
            for d, d_val in d_fracs.items():
                for b, b_val in b_fracs.items():
                    ts_name = f"{self._sanitize(s)}_{self._sanitize(d)}_{self._sanitize(b)}"
                    self._timeslice_map[ts_name] = (s, d, b)
                    timeslice_data.append(ts_name)

                    # Conversion tables (binary mappings)
                    map_ls.append({"TIMESLICE": ts_name, "SEASON": s, "VALUE": 1.0})
                    map_ld.append({"TIMESLICE": ts_name, "DAYTYPE": d, "VALUE": 1.0})
                    map_lh.append({"TIMESLICE": ts_name, "DAILYTIMEBRACKET": b, "VALUE": 1.0})

                    # YearSplit calculation per year
                    for y in years:
                        total_hours = Decimal(str(hours_in_year(y)))
                        season_hours = Decimal(str(s_val)) * total_hours
                        daytype_hours = Decimal(str(d_val)) * season_hours
                        slice_hours = Decimal(str(b_val)) * daytype_hours
                        year_split_frac = slice_hours / total_hours

                        year_split_rows.append({
                            "TIMESLICE": ts_name,
                            "YEAR": y,
                            "VALUE": float(year_split_frac)
                        })

                        # DaySplit (bracket fraction, same for all years)
                        day_split_rows.append({
                            "DAILYTIMEBRACKET": b,
                            "YEAR": y,
                            "VALUE": float(Decimal(str(b_val)))
                        })

        # Update DataFrames
        self.timeslices_df = pd.DataFrame({"VALUE": timeslice_data})
        self.conversionls_df = pd.DataFrame(map_ls)
        self.conversionld_df = pd.DataFrame(map_ld)
        self.conversionlh_df = pd.DataFrame(map_lh)
        self.yearsplit_df = pd.DataFrame(year_split_rows)
        self.daysplit_df = pd.DataFrame(day_split_rows).drop_duplicates()

        # DaysInDayType: days_in_year * season_frac * daytype_frac
        didt_rows = []
        for y in years:
            for s, s_val in s_fracs.items():
                for d, d_val in d_fracs.items():
                    didt_rows.append({
                        "SEASON": s,
                        "DAYTYPE": d,
                        "YEAR": y,
                        "VALUE": days_in_year(y) * s_val * d_val
                    })
        self.daysindaytype_df = pd.DataFrame(didt_rows)

    def _normalize(self, data: Dict[str, float]) -> Dict[str, float]:
        """Normalize values to sum to 1.0 using Decimal for precision."""
        decimal_data = {k: Decimal(str(v)) for k, v in data.items()}
        total = sum(decimal_data.values())
        if total == 0:
            return {k: 0.0 for k in data}
        return {k: float(v / total) for k, v in decimal_data.items()}

    def _sanitize(self, name: str) -> str:
        """Replace underscores to avoid naming ambiguity."""
        return name.replace("_", "__")

    def _unsanitize(self, name: str) -> str:
        """Revert sanitized names."""
        return name.replace("__", "_")

    def _build_timeslice_map(self) -> None:
        """Build internal timeslice → components mapping from conversion tables."""
        self._timeslice_map = {}

        # Index by timeslice
        ls_map = dict(
            zip(self.conversionls_df['TIMESLICE'], self.conversionls_df['SEASON'])
        )
        ld_map = dict(
            zip(self.conversionld_df['TIMESLICE'], self.conversionld_df['DAYTYPE'])
        )
        lh_map = dict(
            zip(self.conversionlh_df['TIMESLICE'], self.conversionlh_df['DAILYTIMEBRACKET'])
        )

        for ts in self.timeslices:
            self._timeslice_map[ts] = (
                ls_map.get(ts, ''),
                ld_map.get(ts, ''),
                lh_map.get(ts, '')
            )

    # =========================================================================
    # Representation
    # =========================================================================

    def __repr__(self) -> str:
        return (
            f"TimeComponent(scenario_dir='{self.scenario_dir}', "
            f"years={len(self.years)}, timeslices={self.num_timeslices})"
        )