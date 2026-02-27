# pyoscomp/translation/time/results.py

import pandas as pd
from typing import Union, List, Set, Dict
from dataclasses import dataclass

from ...constants import TOL, hours_in_year
from .structures import Season, DayType, DailyTimeBracket, Timeslice


@dataclass
class TimesliceResult:
    """
    Convert PyPSA sequential snapshots to OSeMOSYS hierarchical timeslice structure.
    
    Transforms PyPSA's datetime-based sequential representation into OSeMOSYS's
    categorical hierarchical structure (seasons/daytypes/dailytimebrackets/timeslices).
    The conversion preserves temporal coverage and duration weightings.
    
    Parameters
    ----------
    snapshots : pd.DatetimeIndex or pd.Index
        PyPSA snapshot timestamps. Must contain datetime-like values that can be
        converted to pd.DatetimeIndex. The function extracts unique dates and times
        to construct the OSeMOSYS time structure.
    
    Returns
    -------
    TimesliceResult
        Container with hierarchical timeslice structure and mapping from snapshots
        to timeslices. Includes methods for validation and CSV export.
    
    Raises
    ------
    ValueError
        If snapshots is empty.
    ValueError
        If timeslice structure does not cover the entire year (validation fails).
    
    Notes
    -----
    The conversion algorithm:
    
    1. Extracts unique years from snapshot timestamps
    2. Creates Season objets from unique months or month-of-year ranges
    3. Creates DayType objects from unique dates (day-of-month ranges)
    4. Creates DailyTimeBracket objects from unique times (time-of-day ranges)
    5. Forms Timeslice objects as cartesian product of Season x DayTypes × DailyTimeBrackets
    6. Validates that timeslices partition the year completely
    
    Examples
    --------
    From hourly snapshots:
    
    >>> snapshots = pd.date_range('2025-01-01', periods=8760, freq='H')
    >>> result = to_timeslices(snapshots)
    >>> print(len(result.timeslices))
    8760  # One timeslice per hour
    >>> result.validate_coverage()
    True
    
    From custom snapshots:
    
    >>> snapshots = pd.DatetimeIndex([
    ...     '2025-01-01 00:00', '2025-01-01 12:00',
    ...     '2025-07-01 00:00', '2025-07-01 12:00'
    ... ])
    >>> result = to_timeslices(snapshots)
    >>> print(len(result.daytypes))
    # Seasons: 01 to 01, 02 to 06, 07 to 07, 08 to 12
    # DayTypes: 01 to 01, 02 to 31
    # DailyTimeBrackets: 00:00 to 12:00, 12:00 to 24:00
    16  # 4*2*2 = 16 timeslices
    >>> print(len(result.dailytimebrackets))
    2  # 00:00 to 12:00 and 12:00 to 24:00
    
    Export to CSV:
    
    >>> result = to_timeslices(snapshots)
    >>> csv_dict = result.export()
    >>> for filename, df in csv_dict.items():
    ...     df.to_csv(f'osemosys_scenario/{filename}.csv', index=False)
    
    See Also
    --------
    to_snapshots : Convert OSeMOSYS timeslices to PyPSA snapshots (inverse operation)
    TimesliceResult : Container class for conversion results
    Season : Month-of-year range structure
    DayType : Day-of-month range structure
    DailyTimeBracket : Time-of-day range structure
    Timeslice : Combined temporal slice structure
    """
    years: List[int]
    seasons: Set[Season]
    daytypes: Set[DayType]
    dailytimebrackets: Set[DailyTimeBracket]
    timeslices: List[Timeslice]

    def validate_coverage(self) -> bool:
        """Validate that timeslices partition the year completely."""
        for year in self.years:
            total_hours = sum(
                ts.duration_hours(year) 
                for ts in self.timeslices
            )
            expected_hours = hours_in_year(year)
            if abs(total_hours - expected_hours) > TOL:
                return False
        return True
    
    def export(self) -> Dict[str, pd.DataFrame]:
        """
        Generate OSeMOSYS-compatible CSV DataFrames.
        
        Creates DataFrames for all required OSeMOSYS time parameters that can be
        written directly to CSV files for use in OSeMOSYS models.

        Returns
        -------
        Dict[str, pd.DataFrame]
            Dictionary mapping CSV filenames (without .csv extension) to DataFrames:
            
            - 'YEAR': DataFrame with columns ['VALUE']
            - 'SEASON': DataFrame with columns ['VALUE']
            - 'DAYTYPE': DataFrame with columns ['VALUE']
            - 'DAILYTIMEBRACKET': DataFrame with columns ['VALUE']
            - 'TIMESLICE': DataFrame with columns ['VALUE']
            - 'YearSplit': DataFrame with columns ['TIMESLICE', 'YEAR', 'VALUE']
            - 'DaySplit': DataFrame with columns ['TIMESLICE', 'YEAR', 'VALUE']
            - 'DaysInDayType': DataFrame with columns ['SEASON', 'DAYTYPE', 'YEAR', 'VALUE']
            - 'Conversionls': DataFrame with columns ['TIMESLICE', 'SEASON', 'VALUE']
            - 'Conversionld': DataFrame with columns ['TIMESLICE', 'DAYTYPE', 'VALUE']
            - 'Conversionlh': DataFrame with columns ['TIMESLICE', 'DAILYTIMEBRACKET', 'VALUE']
        
        Examples
        --------
        >>> result = to_timeslices(snapshots)
        >>> csv_dict = result.export()
        >>> for name, df in csv_dict.items():
        ...     df.to_csv(f'scenario/{name}.csv', index=False)
        """
        result = {}
        
        # YEAR.csv
        result['YEAR'] = pd.DataFrame({'VALUE': self.years})
        
        # SEASON.csv
        season_names = sorted(set(s.name for s in self.seasons))
        result['SEASON'] = pd.DataFrame({'VALUE': season_names})
        
        # DAYTYPE.csv
        daytype_names = sorted(set(dt.name for dt in self.daytypes))
        result['DAYTYPE'] = pd.DataFrame({'VALUE': daytype_names})
        
        # DAILYTIMEBRACKET.csv
        bracket_names = sorted(set(dtb.name for dtb in self.dailytimebrackets))
        result['DAILYTIMEBRACKET'] = pd.DataFrame({'VALUE': bracket_names})

        # TIMESLICE.csv - unique timeslice names
        timeslice_names = sorted(set(ts.name for ts in self.timeslices))
        result['TIMESLICE'] = pd.DataFrame({'VALUE': timeslice_names})
        
        # YearSplit - fraction of year for each timeslice per year
        year_split_rows = []
        for year in self.years:
            for ts in self.timeslices:
                year_split_rows.append({
                    'TIMESLICE': ts.name,
                    'YEAR': year,
                    'VALUE': ts.year_fraction(year)
                })
        result[f'YearSplit'] = pd.DataFrame(year_split_rows)

        # DaySplit - length of one timebracket in one specific day as a fraction of the year
        day_split_rows = []
        for year in self.years:
            for dtb in self.dailytimebrackets:
                day_split_rows.append({
                    'DAILYTIMEBRACKET': dtb.name,
                    'YEAR': year,
                    'VALUE': dtb.duration_hours() / hours_in_year(year)
                })
        result[f'DaySplit'] = pd.DataFrame(day_split_rows)
        
        # DaysInDayType - number of days for each daytype within one week
        # (equivalent to the number of days in that daytype for that season and year as DayType construction enforces max 7 days per daytype)
        didt_rows = []
        for year in self.years:
            for season in self.seasons:
                for daytype in self.daytypes:
                    # Calculate number of days in this daytype for this season and year
                    days_in_season_year = 0
                    for m in range(season.month_start, season.month_end + 1):
                        days_in_season_year += daytype.duration_days(year, m)
                    didt_rows.append({
                        'SEASON': season.name,
                        'DAYTYPE': daytype.name,
                        'YEAR': year,
                        'VALUE': days_in_season_year
                    })
        result[f'DaysInDayType'] = pd.DataFrame(didt_rows)

        # Conversionls, Conversionld, Conversionlh - mapping timeslices to their components
        conversion_ls_rows = []
        conversion_ld_rows = []
        conversion_lh_rows = []
        for ts in self.timeslices:
            conversion_ls_rows.append({
                'TIMESLICE': ts.name,
                'SEASON': ts.season.name,
                'VALUE': 1
            })
            conversion_ld_rows.append({
                'TIMESLICE': ts.name,
                'DAYTYPE': ts.daytype.name,
                'VALUE': 1
            })
            conversion_lh_rows.append({
                'TIMESLICE': ts.name,
                'DAILYTIMEBRACKET': ts.dailytimebracket.name,
                'VALUE': 1
            })

        result[f'Conversionls'] = pd.DataFrame(conversion_ls_rows)
        result[f'Conversionld'] = pd.DataFrame(conversion_ld_rows)
        result[f'Conversionlh'] = pd.DataFrame(conversion_lh_rows)

        return result
    
    def to_csv(self, output_dir: str) -> None:
        """
        Export all DataFrames to CSV files in output directory.
        
        Parameters
        ----------
        output_dir : str
            Directory to write CSV files.
        
        Examples
        --------
        >>> result.to_csv('output/scenario1/')
        # Creates: output/scenario1/YEAR.csv, output/scenario1/TIMESLICE.csv, etc.
        """
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        for name, df in self.export().items():
            filepath = os.path.join(output_dir, f"{name}.csv")
            df.to_csv(filepath, index=False)


@dataclass
class SnapshotResult:
    """
    Container for PyPSA snapshot conversion results.
    
    Encapsulates the output of OSeMOSYS-to-PyPSA time structure conversion,
    providing snapshots (time indices) and their durations (weightings) in a
    format ready for PyPSA Network configuration.
    
    Attributes
    ----------
    years : List[int]
        List of model years (investment periods).
    snapshots : pd.MultiIndex
        PyPSA snapshot labels.
        This is a MultiIndex with levels ('period', 'timestep') for capacity expansion.
    weightings : pd.Series
        Duration in hours for each snapshot. Index is aligned with snapshots.
    timeslice_names : List[str]
        List of unique timeslice names (timestep labels).
    
    Examples
    --------
    >>> result = to_snapshots('scenario_dir/')
    >>> result.validate_coverage()
    True
    >>> result.apply_to_network(network)
    """
    years: List[int]
    snapshots: Union[pd.MultiIndex, pd.Index, pd.DatetimeIndex, pd.Timestamp]
    weightings: pd.Series # Index aligned with snapshots
    timeslice_names: List[str]

    def validate_coverage(self) -> bool:
        """
        Validate that weightings sum to correct hours per year.
        
        Returns
        -------
        bool
            True if total hours match expected hours per year within tolerance.
        """
        for year in self.years:
            year_mask = self.snapshots.get_level_values('period') == year
            total_hours = self.weightings[year_mask].sum()
            expected_hours = hours_in_year(year)
            if abs(total_hours - expected_hours) > TOL:
                return False
        return True
    
    def apply_to_network(self, network) -> None:
        """
        Apply snapshots and weightings to a PyPSA Network.
        
        Configures the network's temporal structure by setting snapshots and
        their duration weightings for optimization.
        
        Parameters
        ----------
        network : pypsa.Network
            The PyPSA Network object to configure.
        
        Notes
        -----
        This method modifies the network in-place by:
        - Setting network.snapshots
        - Setting network.snapshot_weightings['objective']
        - Setting network.snapshot_weightings['generators']
        - Setting network.snapshot_weightings['stores']
        """
        network.set_snapshots(self.snapshots)
        network.snapshot_weightings = pd.DataFrame(
            {
                "objective": self.weightings,
                "stores": self.weightings,
                "generators": self.weightings
            },
            index=self.snapshots
        )