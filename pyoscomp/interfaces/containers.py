# pyoscomp/interfaces/containers.py

"""
ScenarioData aggregate container for the interfaces package.

This module defines the main ScenarioData class that aggregates all OSeMOSYS
sets and parameters into a single, validated, immutable container. It serves
as the bridge between scenario building (components) and translation.

Design principles:
- Immutable after construction (frozen dataclass)
- Validation runs automatically in __post_init__
- Provides both structured access (attributes) and dict-based access (to_dict)
- No direct imports from scenario.components to avoid circular dependencies
"""

import pandas as pd
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

from .sets import OSeMOSYSSets
from .parameters import (
    TimeParameters,
    DemandParameters,
    SupplyParameters,
    PerformanceParameters,
    EconomicsParameters,
)


@dataclass
class ScenarioData:
    """
    Complete structured representation of an OSeMOSYS scenario.

    This interface bridges scenario building and translation by providing
    a typed, validated container for all model data. Translators consume
    ScenarioData instead of raw CSV dictionaries.

    Attributes
    ----------
    sets : OSeMOSYSSets
        All OSeMOSYS set definitions (REGION, YEAR, TECHNOLOGY, etc.)
    time : TimeParameters
        Time structure parameters (YearSplit, DaySplit, conversions)
    demand : DemandParameters
        Demand parameters (SpecifiedAnnualDemand, profiles)
    supply : SupplyParameters
        Supply parameters (ResidualCapacity)
    economics : EconomicsParameters
        Cost and discount parameters
    performance : PerformanceParameters
        Technology performance parameters (efficiency, capacity factors)
    metadata : dict
        Optional metadata (scenario name, source directory, etc.)

    Examples
    --------
    Load from scenario directory:

    >>> data = ScenarioData.from_directory('/path/to/scenario')
    >>> data.validate()  # Already called in construction
    >>> data.export_to_directory('/path/to/new/scenario')

    Use with translators:

    >>> translator = PyPSAInputTranslator(scenario_data=data)
    >>> network = translator.translate()

    Access parameters by OSeMOSYS name:

    >>> capital_cost = data.get_parameter('CapitalCost')
    >>> year_split = data['YearSplit']  # Dict-style access

    Notes
    -----
    - Immutable design - create new ScenarioData for modifications
    - Validation runs automatically unless _skip_validation=True
    - Use to_dict() for backward compatibility with legacy code
    """
    sets: OSeMOSYSSets
    time: TimeParameters
    demand: DemandParameters
    supply: SupplyParameters
    performance: PerformanceParameters
    economics: EconomicsParameters
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Internal flag to skip validation (used by loaders during construction)
    _skip_validation: bool = field(default=False, repr=False, compare=False)

    def __post_init__(self):
        """Validate structure immediately after construction unless skipped."""
        if not self._skip_validation:
            self.validate()

    def validate(self) -> None:
        """
        Validate all cross-component references and parameter consistency.

        Checks:
        - Required sets are non-empty (regions, years, technologies, timeslices)
        - Each parameter group's internal validation
        - Cross-references between parameters and sets

        Raises
        ------
        ValueError
            If validation fails (missing references, sum constraints, etc.)
        """
        # Validate required sets are non-empty
        self.sets.validate_non_empty()

        # Validate each parameter group against sets
        self.time.validate(self.sets)
        self.demand.validate(self.sets)
        self.supply.validate(self.sets)
        self.performance.validate(self.sets)
        self.economics.validate(self.sets)

    @classmethod
    def from_directory(cls, scenario_dir: str, validate: bool = True) -> 'ScenarioData':
        """
        Load ScenarioData from a scenario directory containing CSV files.

        Parameters
        ----------
        scenario_dir : str
            Path to directory with OSeMOSYS CSV files.
        validate : bool, optional
            If True, run validation after loading (default: True).

        Returns
        -------
        ScenarioData
            Validated scenario data.

        Raises
        ------
        FileNotFoundError
            If required CSV files are missing.
        ValueError
            If validation fails.
        """
        from .utilities import ScenarioDataLoader
        return ScenarioDataLoader.from_directory(scenario_dir, validate=validate)

    @classmethod
    def from_components(
        cls,
        topology_component,
        time_component,
        demand_component,
        supply_component,
        performance_component,
        economics_component,
        validate: bool = True
    ) -> 'ScenarioData':
        """
        Construct ScenarioData from scenario component objects.

        This allows direct translation without intermediate CSV files.

        Parameters
        ----------
        topology_component : TopologyComponent
            Component with region definitions.
        time_component : TimeComponent
            Component with temporal structure.
        demand_component : DemandComponent
            Component with demand data.
        supply_component : SupplyComponent
            Component with technology registry and fuel/mode tracking.
        performance_component : PerformanceComponent
            Component with performance data (activity ratios, factors).
        economics_component : EconomicsComponent
            Component with cost data.
        validate : bool, optional
            If True, run validation after construction (default: True).

        Returns
        -------
        ScenarioData
            Validated scenario data.
        """
        from .utilities import ScenarioDataLoader
        return ScenarioDataLoader.from_components(
            topology_component,
            time_component,
            demand_component,
            supply_component,
            performance_component,
            economics_component,
            validate=validate
        )

    def export_to_directory(self, scenario_dir: str) -> None:
        """
        Export ScenarioData to CSV files in specified directory.

        Parameters
        ----------
        scenario_dir : str
            Target directory for CSV files (created if doesn't exist).
        """
        from .utilities import ScenarioDataExporter
        ScenarioDataExporter.to_directory(self, scenario_dir)

    def to_dict(self) -> Dict[str, pd.DataFrame]:
        """
        Convert to dictionary format for backward compatibility.

        Returns
        -------
        Dict[str, pd.DataFrame]
            Dictionary mapping CSV names (without .csv) to DataFrames.

        Notes
        -----
        This method supports legacy code that expects Dict[str, pd.DataFrame].
        New code should use ScenarioData attributes directly.

        Examples
        --------
        >>> data_dict = scenario_data.to_dict()
        >>> regions = data_dict['REGION']
        >>> capital_cost = data_dict['CapitalCost']
        """
        result = {}

        # Sets (as single-column DataFrames with VALUE)
        result['REGION'] = pd.DataFrame({'VALUE': sorted(self.sets.regions)})
        result['YEAR'] = pd.DataFrame({'VALUE': sorted(self.sets.years)})
        result['TECHNOLOGY'] = pd.DataFrame({'VALUE': sorted(self.sets.technologies)})
        result['FUEL'] = pd.DataFrame({'VALUE': sorted(self.sets.fuels)})
        result['EMISSION'] = pd.DataFrame({'VALUE': sorted(self.sets.emissions)})
        result['MODE_OF_OPERATION'] = pd.DataFrame({'VALUE': sorted(self.sets.modes)})
        result['TIMESLICE'] = pd.DataFrame({'VALUE': sorted(self.sets.timeslices)})
        result['SEASON'] = pd.DataFrame({'VALUE': sorted(self.sets.seasons)})
        result['DAYTYPE'] = pd.DataFrame({'VALUE': sorted(self.sets.daytypes)})
        result['DAILYTIMEBRACKET'] = pd.DataFrame({'VALUE': sorted(self.sets.dailytimebrackets)})
        result['STORAGE'] = pd.DataFrame({'VALUE': sorted(self.sets.storages)})

        # Time parameters
        result['YearSplit'] = self.time.year_split.copy()
        result['DaySplit'] = self.time.day_split.copy()
        result['Conversionls'] = self.time.conversion_ls.copy()
        result['Conversionld'] = self.time.conversion_ld.copy()
        result['Conversionlh'] = self.time.conversion_lh.copy()
        result['DaysInDayType'] = self.time.days_in_daytype.copy()

        # Demand parameters
        result['SpecifiedAnnualDemand'] = self.demand.specified_annual_demand.copy()
        result['SpecifiedDemandProfile'] = self.demand.specified_demand_profile.copy()
        result['AccumulatedAnnualDemand'] = self.demand.accumulated_annual_demand.copy()

        # Supply parameters
        result['ResidualCapacity'] = self.supply.residual_capacity.copy()

        # Performance parameters
        result['OperationalLife'] = self.performance.operational_life.copy()
        result['CapacityToActivityUnit'] = self.performance.capacity_to_activity_unit.copy()
        result['InputActivityRatio'] = self.performance.input_activity_ratio.copy()
        result['OutputActivityRatio'] = self.performance.output_activity_ratio.copy()
        result['CapacityFactor'] = self.performance.capacity_factor.copy()
        result['AvailabilityFactor'] = self.performance.availability_factor.copy()

        # Economics parameters
        result['DiscountRate'] = self.economics.discount_rate.copy()
        result['DiscountRateIdv'] = self.economics.discount_rate_idv.copy()
        result['CapitalCost'] = self.economics.capital_cost.copy()
        result['VariableCost'] = self.economics.variable_cost.copy()
        result['FixedCost'] = self.economics.fixed_cost.copy()

        return result

    def get_parameter(self, name: str) -> Optional[pd.DataFrame]:
        """
        Get parameter DataFrame by OSeMOSYS parameter name.

        Parameters
        ----------
        name : str
            OSeMOSYS parameter or set name (e.g., 'CapitalCost', 'YearSplit', 'REGION')

        Returns
        -------
        pd.DataFrame or None
            Parameter/set DataFrame if exists, None otherwise.

        Examples
        --------
        >>> capital_cost = data.get_parameter('CapitalCost')
        >>> regions = data.get_parameter('REGION')
        """
        # Parameter name to attribute mapping
        param_map = {
            # Sets
            'REGION': pd.DataFrame({'VALUE': sorted(self.sets.regions)}),
            'YEAR': pd.DataFrame({'VALUE': sorted(self.sets.years)}),
            'TECHNOLOGY': pd.DataFrame({'VALUE': sorted(self.sets.technologies)}),
            'FUEL': pd.DataFrame({'VALUE': sorted(self.sets.fuels)}),
            'EMISSION': pd.DataFrame({'VALUE': sorted(self.sets.emissions)}),
            'MODE_OF_OPERATION': pd.DataFrame({'VALUE': sorted(self.sets.modes)}),
            'TIMESLICE': pd.DataFrame({'VALUE': sorted(self.sets.timeslices)}),
            'SEASON': pd.DataFrame({'VALUE': sorted(self.sets.seasons)}),
            'DAYTYPE': pd.DataFrame({'VALUE': sorted(self.sets.daytypes)}),
            'DAILYTIMEBRACKET': pd.DataFrame({'VALUE': sorted(self.sets.dailytimebrackets)}),
            'STORAGE': pd.DataFrame({'VALUE': sorted(self.sets.storages)}),
            # Time parameters
            'YearSplit': self.time.year_split,
            'DaySplit': self.time.day_split,
            'Conversionls': self.time.conversion_ls,
            'Conversionld': self.time.conversion_ld,
            'Conversionlh': self.time.conversion_lh,
            'DaysInDayType': self.time.days_in_daytype,
            # Demand parameters
            'SpecifiedAnnualDemand': self.demand.specified_annual_demand,
            'SpecifiedDemandProfile': self.demand.specified_demand_profile,
            'AccumulatedAnnualDemand': self.demand.accumulated_annual_demand,
            # Supply parameters
            'ResidualCapacity': self.supply.residual_capacity,
            # Performance parameters
            'OperationalLife': self.performance.operational_life,
            'CapacityToActivityUnit': self.performance.capacity_to_activity_unit,
            'InputActivityRatio': self.performance.input_activity_ratio,
            'OutputActivityRatio': self.performance.output_activity_ratio,
            'CapacityFactor': self.performance.capacity_factor,
            'AvailabilityFactor': self.performance.availability_factor,
            # Economics parameters
            'DiscountRate': self.economics.discount_rate,
            'DiscountRateIdv': self.economics.discount_rate_idv,
            'CapitalCost': self.economics.capital_cost,
            'VariableCost': self.economics.variable_cost,
            'FixedCost': self.economics.fixed_cost,
        }
        return param_map.get(name)

    def __getitem__(self, name: str) -> pd.DataFrame:
        """
        Dict-style access to parameters.

        Parameters
        ----------
        name : str
            OSeMOSYS parameter or set name.

        Returns
        -------
        pd.DataFrame
            Parameter/set DataFrame.

        Raises
        ------
        KeyError
            If parameter name not found.

        Examples
        --------
        >>> capital_cost = data['CapitalCost']
        >>> regions = data['REGION']
        """
        result = self.get_parameter(name)
        if result is None:
            raise KeyError(f"Unknown parameter: {name}")
        return result

    def __contains__(self, name: str) -> bool:
        """Check if parameter name exists."""
        return self.get_parameter(name) is not None

    @property
    def years_list(self) -> list:
        """Return years as sorted list for convenience."""
        return self.sets.get_sorted_years()

    @property
    def timeslices_list(self) -> list:
        """Return timeslices as sorted list for convenience."""
        return self.sets.get_sorted_timeslices()

    @property
    def regions_list(self) -> list:
        """Return regions as sorted list for convenience."""
        return sorted(self.sets.regions)

    @property
    def technologies_list(self) -> list:
        """Return technologies as sorted list for convenience."""
        return sorted(self.sets.technologies)

    def summary(self) -> str:
        """
        Return a summary string of the scenario data.

        Returns
        -------
        str
            Human-readable summary of scenario contents.
        """
        lines = [
            "ScenarioData Summary",
            "=" * 40,
            f"Regions: {len(self.sets.regions)}",
            f"Years: {len(self.sets.years)} ({min(self.sets.years)}-{max(self.sets.years)})",
            f"Technologies: {len(self.sets.technologies)}",
            f"Fuels: {len(self.sets.fuels)}",
            f"Timeslices: {len(self.sets.timeslices)}",
            f"Modes: {len(self.sets.modes)}",
            "",
            "Parameter Counts:",
            f"  YearSplit: {len(self.time.year_split)} rows",
            f"  SpecifiedAnnualDemand: {len(self.demand.specified_annual_demand)} rows",
            f"  CapitalCost: {len(self.economics.capital_cost)} rows",
            f"  InputActivityRatio: {len(self.performance.input_activity_ratio)} rows",
            f"  OutputActivityRatio: {len(self.performance.output_activity_ratio)} rows",
        ]
        return "\n".join(lines)

    def __repr__(self) -> str:
        """Short representation."""
        return (
            f"ScenarioData(regions={len(self.sets.regions)}, "
            f"years={len(self.sets.years)}, "
            f"technologies={len(self.sets.technologies)})"
        )
