# pyoscomp/interfaces/utilities.py

"""
Utility classes for loading and exporting ScenarioData.

This module provides the I/O layer for the interfaces package:
- ScenarioDataLoader: Load ScenarioData from CSV directories or components
- ScenarioDataExporter: Export ScenarioData to CSV directories

Design notes:
- These utilities are separate from ScenarioData to avoid circular imports
- Helper functions handle CSV reading/writing with error handling
- All CSV operations follow OSeMOSYS conventions (VALUE column for sets)
"""

import pandas as pd
from pathlib import Path
from typing import Union, FrozenSet, Any

from .sets import OSeMOSYSSets
from .parameters import (
    TimeParameters,
    DemandParameters,
    SupplyParameters,
    EconomicsParameters,
    PerformanceParameters,
)
from .containers import ScenarioData


# =============================================================================
# Helper Functions for CSV I/O
# =============================================================================

def load_set_csv(
    path: Union[str, Path],
    dtype: type = str,
    required: bool = False
) -> FrozenSet[Any]:
    """
    Load an OSeMOSYS set CSV file into a frozenset.

    Parameters
    ----------
    path : str or Path
        Path to the CSV file.
    dtype : type, optional
        Type to cast values to (default: str).
    required : bool, optional
        If True, raise error when file missing (default: False).

    Returns
    -------
    frozenset
        Set values from the VALUE column.

    Raises
    ------
    FileNotFoundError
        If required=True and file doesn't exist.
    ValueError
        If file exists but has no VALUE column.

    Notes
    -----
    OSeMOSYS convention: all set CSVs have a single column named 'VALUE'.
    """
    path = Path(path)

    if not path.exists():
        if required:
            raise FileNotFoundError(f"Required set file not found: {path}")
        return frozenset()

    df = pd.read_csv(path)

    if 'VALUE' not in df.columns:
        raise ValueError(f"Set CSV {path.name} must have 'VALUE' column")

    if dtype == int:
        return frozenset(df['VALUE'].astype(int).tolist())
    return frozenset(df['VALUE'].astype(str).tolist())


def load_param_csv(
    path: Union[str, Path],
    required: bool = False
) -> pd.DataFrame:
    """
    Load an OSeMOSYS parameter CSV file into a DataFrame.

    Parameters
    ----------
    path : str or Path
        Path to the CSV file.
    required : bool, optional
        If True, raise error when file missing (default: False).

    Returns
    -------
    pd.DataFrame
        Parameter data with original columns.

    Raises
    ------
    FileNotFoundError
        If required=True and file doesn't exist.
    """
    path = Path(path)

    if not path.exists():
        if required:
            raise FileNotFoundError(f"Required parameter file not found: {path}")
        return pd.DataFrame()

    return pd.read_csv(path)


def save_set_csv(
    values: Union[FrozenSet[Any], list],
    path: Union[str, Path]
) -> None:
    """
    Save a set to an OSeMOSYS-format CSV file.

    Parameters
    ----------
    values : frozenset or list
        Set values to save.
    path : str or Path
        Output file path.

    Notes
    -----
    Creates parent directories if they don't exist.
    Skips saving if set is empty.
    """
    if not values:
        return

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame({'VALUE': sorted(values)})
    df.to_csv(path, index=False)


def save_param_csv(
    df: pd.DataFrame,
    path: Union[str, Path]
) -> None:
    """
    Save a parameter DataFrame to CSV.

    Parameters
    ----------
    df : pd.DataFrame
        Parameter data to save.
    path : str or Path
        Output file path.

    Notes
    -----
    - Creates parent directories if they don't exist
    - Skips saving if DataFrame is empty
    """
    if df.empty:
        return

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


# =============================================================================
# ScenarioDataLoader
# =============================================================================

class ScenarioDataLoader:
    """
    Utility class for loading ScenarioData from various sources.

    Provides static methods to create ScenarioData instances from:
    - CSV directory (standard OSeMOSYS format)
    - Scenario component objects (in-memory, no CSV)

    Examples
    --------
    Load from directory:

    >>> from pyoscomp.interfaces import ScenarioDataLoader
    >>> data = ScenarioDataLoader.from_directory('/path/to/scenario')

    Load from components:

    >>> data = ScenarioDataLoader.from_components(
    ...     topology, time, demand, supply, economics
    ... )
    """

    @staticmethod
    def from_directory(scenario_dir: str, validate: bool = True) -> 'ScenarioData':
        """
        Load ScenarioData from a directory containing CSV files.

        Parameters
        ----------
        scenario_dir : str
            Path to directory with OSeMOSYS CSV files.
        validate : bool, optional
            If True, run validation after loading (default: True).

        Returns
        -------
        ScenarioData
            Loaded scenario data.

        Raises
        ------
        FileNotFoundError
            If required CSV files are missing.
        ValueError
            If validation fails.

        Notes
        -----
        Required files: REGION.csv, YEAR.csv, TECHNOLOGY.csv, TIMESLICE.csv
        Optional files: All others (empty DataFrames used if missing)
        """
        # Import here to avoid circular dependency
        from .containers import ScenarioData

        path = Path(scenario_dir)

        if not path.exists():
            raise FileNotFoundError(f"Scenario directory not found: {scenario_dir}")

        # Load sets
        sets = OSeMOSYSSets(
            regions=load_set_csv(path / 'REGION.csv', str, required=True),
            years=load_set_csv(path / 'YEAR.csv', int, required=True),
            technologies=load_set_csv(path / 'TECHNOLOGY.csv', str, required=True),
            fuels=load_set_csv(path / 'FUEL.csv', str, required=False),
            emissions=load_set_csv(path / 'EMISSION.csv', str, required=False),
            modes=load_set_csv(path / 'MODE_OF_OPERATION.csv', str, required=False),
            timeslices=load_set_csv(path / 'TIMESLICE.csv', str, required=True),
            seasons=load_set_csv(path / 'SEASON.csv', str, required=False),
            daytypes=load_set_csv(path / 'DAYTYPE.csv', str, required=False),
            dailytimebrackets=load_set_csv(path / 'DAILYTIMEBRACKET.csv', str, required=False),
            storages=load_set_csv(path / 'STORAGE.csv', str, required=False),
        )

        # Load time parameters
        time_params = TimeParameters(
            year_split=load_param_csv(path / 'YearSplit.csv', required=False),
            day_split=load_param_csv(path / 'DaySplit.csv', required=False),
            conversion_ls=load_param_csv(path / 'Conversionls.csv', required=False),
            conversion_ld=load_param_csv(path / 'Conversionld.csv', required=False),
            conversion_lh=load_param_csv(path / 'Conversionlh.csv', required=False),
            days_in_daytype=load_param_csv(path / 'DaysInDayType.csv', required=False),
        )

        # Load demand parameters
        demand_params = DemandParameters(
            specified_annual_demand=load_param_csv(path / 'SpecifiedAnnualDemand.csv'),
            specified_demand_profile=load_param_csv(path / 'SpecifiedDemandProfile.csv'),
            accumulated_annual_demand=load_param_csv(path / 'AccumulatedAnnualDemand.csv'),
        )

        # Load supply parameters
        supply_params = SupplyParameters(
            residual_capacity=load_param_csv(path / 'ResidualCapacity.csv'),
        )

        # Load economics parameters
        economics_params = EconomicsParameters(
            discount_rate=load_param_csv(path / 'DiscountRate.csv'),
            discount_rate_idv=load_param_csv(path / 'DiscountRateIdv.csv'),
            capital_cost=load_param_csv(path / 'CapitalCost.csv'),
            variable_cost=load_param_csv(path / 'VariableCost.csv'),
            fixed_cost=load_param_csv(path / 'FixedCost.csv'),
        )

        # Load performance parameters
        performance_params = PerformanceParameters(
            operational_life=load_param_csv(path / 'OperationalLife.csv'),
            capacity_to_activity_unit=load_param_csv(path / 'CapacityToActivityUnit.csv'),
            input_activity_ratio=load_param_csv(path / 'InputActivityRatio.csv'),
            output_activity_ratio=load_param_csv(path / 'OutputActivityRatio.csv'),
            capacity_factor=load_param_csv(path / 'CapacityFactor.csv'),
            availability_factor=load_param_csv(path / 'AvailabilityFactor.csv'),
        )

        # Create ScenarioData (validation runs in __post_init__ if validate=True)
        return ScenarioData(
            sets=sets,
            time=time_params,
            demand=demand_params,
            supply=supply_params,
            economics=economics_params,
            performance=performance_params,
            metadata={'source_dir': scenario_dir},
            _skip_validation=not validate,
        )

    @staticmethod
    def from_components(
        topology_component,
        time_component,
        demand_component,
        supply_component,
        economics_component,
        validate: bool = True
    ) -> 'ScenarioData':
        """
        Construct ScenarioData from scenario component objects.

        This allows direct translation without intermediate CSV files,
        extracting DataFrames directly from component internal state.

        Parameters
        ----------
        topology_component : TopologyComponent
            Component with region definitions.
        time_component : TimeComponent
            Component with temporal structure.
        demand_component : DemandComponent
            Component with demand data.
        supply_component : SupplyComponent
            Component with technology data.
        economics_component : EconomicsComponent
            Component with cost data.
        validate : bool, optional
            If True, run validation after construction (default: True).

        Returns
        -------
        ScenarioData
            Scenario data extracted from components.
        """
        # Extract sets from component DataFrames
        sets = OSeMOSYSSets(
            regions=frozenset(topology_component.regions_df['VALUE'].tolist()),
            years=frozenset(int(y) for y in time_component.years_df['VALUE'].tolist()),
            technologies=frozenset(
                supply_component.operational_life['TECHNOLOGY'].unique().tolist()
                if not supply_component.operational_life.empty else []
            ),
            fuels=frozenset(supply_component.defined_fuels),
            emissions=frozenset(),  # Future: EmissionsComponent
            modes=frozenset(
                supply_component.input_activity_ratio['MODE_OF_OPERATION'].unique().tolist()
                if not supply_component.input_activity_ratio.empty else []
            ),
            timeslices=frozenset(time_component.timeslices_df['VALUE'].tolist()),
            seasons=frozenset(time_component.seasons_df['VALUE'].tolist()),
            daytypes=frozenset(time_component.daytypes_df['VALUE'].tolist()),
            dailytimebrackets=frozenset(time_component.brackets_df['VALUE'].tolist()),
            storages=frozenset(),  # Future: StorageComponent
        )

        # Extract time parameters
        time_params = TimeParameters(
            year_split=time_component.yearsplit_df.copy(),
            day_split=time_component.daysplit_df.copy(),
            conversion_ls=time_component.conversionls_df.copy(),
            conversion_ld=time_component.conversionld_df.copy(),
            conversion_lh=time_component.conversionlh_df.copy(),
            days_in_daytype=time_component.daysindaytype_df.copy(),
        )

        # Extract demand parameters
        demand_params = DemandParameters(
            specified_annual_demand=demand_component.annual_demand_df.copy(),
            specified_demand_profile=demand_component.profile_demand_df.copy(),
            accumulated_annual_demand=demand_component.accumulated_demand_df.copy(),
        )

        # Extract supply parameters
        supply_params = SupplyParameters(
            residual_capacity=supply_component.residual_capacity.copy(),
        )

        # Extract economics parameters
        economics_params = EconomicsParameters(
            discount_rate=economics_component.discount_rate_df.copy(),
            discount_rate_idv=pd.DataFrame(),  # Not commonly used
            capital_cost=economics_component.capital_cost_df.copy(),
            variable_cost=economics_component.variable_cost_df.copy(),
            fixed_cost=economics_component.fixed_cost_df.copy(),
        )

        # Extract performance parameters
        performance_params = PerformanceParameters(
            operational_life=supply_component.operational_life.copy(),
            capacity_to_activity_unit=supply_component.capacity_to_activity_unit.copy(),
            input_activity_ratio=supply_component.input_activity_ratio.copy(),
            output_activity_ratio=supply_component.output_activity_ratio.copy(),
            capacity_factor=supply_component.capacity_factor.copy(),
            availability_factor=supply_component.availability_factor.copy(),
        )

        return ScenarioData(
            sets=sets,
            time=time_params,
            demand=demand_params,
            supply=supply_params,
            economics=economics_params,
            performance=performance_params,
            metadata={'source': 'components'},
            _skip_validation=not validate,
        )


# =============================================================================
# ScenarioDataExporter
# =============================================================================

class ScenarioDataExporter:
    """
    Utility class for exporting ScenarioData to various formats.

    Provides static methods to export ScenarioData to:
    - CSV directory (standard OSeMOSYS format)

    Examples
    --------
    Export to directory:

    >>> from pyoscomp.interfaces import ScenarioDataExporter
    >>> ScenarioDataExporter.to_directory(data, '/path/to/output')
    """

    @staticmethod
    def to_directory(data: 'ScenarioData', scenario_dir: str) -> None:
        """
        Export ScenarioData to CSV files in specified directory.

        Parameters
        ----------
        data : ScenarioData
            Scenario data to export.
        scenario_dir : str
            Target directory for CSV files (created if doesn't exist).

        Notes
        -----
        - Creates directory structure if needed
        - Only writes non-empty DataFrames/sets
        - Follows OSeMOSYS CSV conventions
        """
        path = Path(scenario_dir)
        path.mkdir(parents=True, exist_ok=True)

        # Export sets
        save_set_csv(data.sets.regions, path / 'REGION.csv')
        save_set_csv(data.sets.years, path / 'YEAR.csv')
        save_set_csv(data.sets.technologies, path / 'TECHNOLOGY.csv')
        save_set_csv(data.sets.fuels, path / 'FUEL.csv')
        save_set_csv(data.sets.emissions, path / 'EMISSION.csv')
        save_set_csv(data.sets.modes, path / 'MODE_OF_OPERATION.csv')
        save_set_csv(data.sets.timeslices, path / 'TIMESLICE.csv')
        save_set_csv(data.sets.seasons, path / 'SEASON.csv')
        save_set_csv(data.sets.daytypes, path / 'DAYTYPE.csv')
        save_set_csv(data.sets.dailytimebrackets, path / 'DAILYTIMEBRACKET.csv')
        save_set_csv(data.sets.storages, path / 'STORAGE.csv')

        # Export time parameters
        save_param_csv(data.time.year_split, path / 'YearSplit.csv')
        save_param_csv(data.time.day_split, path / 'DaySplit.csv')
        save_param_csv(data.time.conversion_ls, path / 'Conversionls.csv')
        save_param_csv(data.time.conversion_ld, path / 'Conversionld.csv')
        save_param_csv(data.time.conversion_lh, path / 'Conversionlh.csv')
        save_param_csv(data.time.days_in_daytype, path / 'DaysInDayType.csv')

        # Export demand parameters
        save_param_csv(data.demand.specified_annual_demand, path / 'SpecifiedAnnualDemand.csv')
        save_param_csv(data.demand.specified_demand_profile, path / 'SpecifiedDemandProfile.csv')
        save_param_csv(data.demand.accumulated_annual_demand, path / 'AccumulatedAnnualDemand.csv')

        # Export supply parameters
        save_param_csv(data.supply.residual_capacity, path / 'ResidualCapacity.csv')

        # Export economics parameters
        save_param_csv(data.economics.discount_rate, path / 'DiscountRate.csv')
        save_param_csv(data.economics.discount_rate_idv, path / 'DiscountRateIdv.csv')
        save_param_csv(data.economics.capital_cost, path / 'CapitalCost.csv')
        save_param_csv(data.economics.variable_cost, path / 'VariableCost.csv')
        save_param_csv(data.economics.fixed_cost, path / 'FixedCost.csv')

        # Export performance parameters
        save_param_csv(data.performance.operational_life, path / 'OperationalLife.csv')
        save_param_csv(data.performance.capacity_to_activity_unit, path / 'CapacityToActivityUnit.csv')
        save_param_csv(data.performance.input_activity_ratio, path / 'InputActivityRatio.csv')
        save_param_csv(data.performance.output_activity_ratio, path / 'OutputActivityRatio.csv')
        save_param_csv(data.performance.capacity_factor, path / 'CapacityFactor.csv')
        save_param_csv(data.performance.availability_factor, path / 'AvailabilityFactor.csv')
