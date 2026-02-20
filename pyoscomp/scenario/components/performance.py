# pyoscomp/scenario/components/performance.py

"""
Performance component for technology operational characteristics.

This component owns all parameters defining HOW technologies operate:
- CapacityToActivityUnit (capacity-to-activity conversion factor)
- InputActivityRatio (input fuel requirements / efficiency)
- OutputActivityRatio (output production per unit activity)
- CapacityFactor (sub-annual capacity availability per timeslice)
- AvailabilityFactor (annual availability accounting for maintenance)
- TotalAnnualMaxCapacity (upper bound on installed capacity)
- TotalAnnualMinCapacity (lower bound on installed capacity)

These parameters complement the SupplyComponent which defines WHAT
technologies exist and their fuel/mode relationships.

Prerequisites:
- TimeComponent (years, timeslices must be defined)
- TopologyComponent (regions must be defined)
- SupplyComponent (technologies, fuels, modes must be saved to disk)

See Also
--------
SupplyComponent : Technology registry (WHAT exists).
"""

import json
import os
import pandas as pd
from typing import Dict, List, Optional, Set, Tuple, Union

from .base import ScenarioComponent
from .time import TimeComponent


class PerformanceComponent(ScenarioComponent):
    """
    Performance component for technology operational parameters.

    Owns all DataFrames defining how technologies convert energy,
    their capacity utilization profiles, and capacity limits.

    Attributes
    ----------
    years : list of int
        Model years (from prerequisites).
    regions : list of str
        Region identifiers (from prerequisites).
    timeslices : list of str
        Timeslice identifiers (from prerequisites).

    Owned Files
    -----------
    CapacityToActivityUnit.csv, InputActivityRatio.csv,
    OutputActivityRatio.csv, CapacityFactor.csv,
    AvailabilityFactor.csv, TotalAnnualMaxCapacity.csv,
    TotalAnnualMinCapacity.csv

    Example
    -------
    Standalone usage after SupplyComponent has saved to disk::

        performance = PerformanceComponent(scenario_dir)

        performance.set_efficiency('REGION1', 'GAS_CCGT', 0.5)
        performance.set_capacity_factor('REGION1', 'GAS_CCGT', 0.9)
        performance.set_availability_factor('REGION1', 'GAS_CCGT', 1.0)
        performance.set_capacity_to_activity_unit(
            'REGION1', 'GAS_CCGT', 8760)
        performance.set_capacity_limits(
            'REGION1', 'GAS_CCGT',
            max_capacity={2026: 1000 / 8760})

        performance.process()
        performance.save()

    See Also
    --------
    SupplyComponent : Technology registry defining WHAT exists.
    """

    owned_files = [
        'CapacityToActivityUnit.csv',
        'InputActivityRatio.csv',
        'OutputActivityRatio.csv',
        'CapacityFactor.csv',
        'AvailabilityFactor.csv',
        'TotalAnnualMaxCapacity.csv',
        'TotalAnnualMinCapacity.csv',
    ]

    def __init__(self, scenario_dir: str):
        """
        Initialize performance component with empty DataFrames.

        Reads technology, fuel, and mode sets from disk (written by
        SupplyComponent) to enable validation and fuel-aware methods.

        Parameters
        ----------
        scenario_dir : str
            Path to the scenario directory.

        Raises
        ------
        ValueError
            If prerequisites (years, regions, timeslices) not met.
        """
        super().__init__(scenario_dir)

        # Check prerequisites
        prereqs = self.check_prerequisites(
            require_years=True,
            require_regions=True,
            require_timeslices=True,
        )
        self.years = prereqs['years']
        self.regions = prereqs['regions']
        self.timeslices = prereqs['timeslices']

        # Load supply registry from disk
        self._technologies = self._load_set("TECHNOLOGY.csv")
        self._fuels = self._load_set("FUEL.csv")
        self._modes = self._load_set("MODE_OF_OPERATION.csv")
        self._fuel_map = self._load_fuel_map()

        # Load time axis for hierarchical capacity factor support
        self._time_axis = self._load_time_axis()

        # Performance DataFrames
        self.capacity_to_activity_unit = self.init_dataframe(
            "CapacityToActivityUnit"
        )
        self.input_activity_ratio = self.init_dataframe(
            "InputActivityRatio"
        )
        self.output_activity_ratio = self.init_dataframe(
            "OutputActivityRatio"
        )
        self.capacity_factor = self.init_dataframe("CapacityFactor")
        self.availability_factor = self.init_dataframe(
            "AvailabilityFactor"
        )
        self.total_annual_max_capacity = self.init_dataframe(
            "TotalAnnualMaxCapacity"
        )
        self.total_annual_min_capacity = self.init_dataframe(
            "TotalAnnualMinCapacity"
        )

        # Tracking for deferred processing
        self._capacity_factor_assignments: Dict[Tuple, Dict] = {}
        self._defined_tech: Set[Tuple[str, str]] = set()

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def technologies(self) -> List[str]:
        """
        Get list of technologies from the supply registry.

        Returns
        -------
        list of str
            Technology identifiers loaded from TECHNOLOGY.csv.
        """
        return list(self._technologies)

    @property
    def defined_fuels(self) -> Set[str]:
        """
        Get set of fuels from the supply registry.

        Returns
        -------
        set of str
            Fuel identifiers loaded from FUEL.csv.
        """
        return set(self._fuels)

    @property
    def modes(self) -> Set[str]:
        """
        Get set of modes from the supply registry.

        Returns
        -------
        set of str
            Mode identifiers. Defaults to {'MODE1'} if none loaded.
        """
        return set(self._modes) if self._modes else {'MODE1'}

    # =========================================================================
    # Load and Save
    # =========================================================================

    def load(self) -> None:
        """
        Load all performance parameter CSV files from scenario directory.

        Raises
        ------
        FileNotFoundError
            If any required file is missing.
        ValueError
            If any file fails schema validation.
        """
        self.capacity_to_activity_unit = self.read_csv(
            "CapacityToActivityUnit.csv"
        )
        self.input_activity_ratio = self.read_csv(
            "InputActivityRatio.csv"
        )
        self.output_activity_ratio = self.read_csv(
            "OutputActivityRatio.csv"
        )
        self.capacity_factor = self.read_csv("CapacityFactor.csv")
        self.availability_factor = self.read_csv(
            "AvailabilityFactor.csv"
        )
        self.total_annual_max_capacity = self.read_csv(
            "TotalAnnualMaxCapacity.csv"
        )
        self.total_annual_min_capacity = self.read_csv(
            "TotalAnnualMinCapacity.csv"
        )

    def save(self) -> None:
        """
        Save all performance parameter DataFrames to CSV files.

        Raises
        ------
        ValueError
            If any DataFrame fails schema validation.
        """
        self._save_sorted(
            "CapacityToActivityUnit.csv",
            self.capacity_to_activity_unit,
            ["REGION", "TECHNOLOGY", "VALUE"],
            ["REGION", "TECHNOLOGY"],
        )
        self._save_sorted(
            "InputActivityRatio.csv",
            self.input_activity_ratio,
            ["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION",
             "YEAR", "VALUE"],
            ["REGION", "TECHNOLOGY", "FUEL",
             "MODE_OF_OPERATION", "YEAR"],
        )
        self._save_sorted(
            "OutputActivityRatio.csv",
            self.output_activity_ratio,
            ["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION",
             "YEAR", "VALUE"],
            ["REGION", "TECHNOLOGY", "FUEL",
             "MODE_OF_OPERATION", "YEAR"],
        )
        self._save_sorted(
            "CapacityFactor.csv",
            self.capacity_factor,
            ["REGION", "TECHNOLOGY", "TIMESLICE", "YEAR", "VALUE"],
            ["REGION", "TECHNOLOGY", "TIMESLICE", "YEAR"],
        )
        self._save_sorted(
            "AvailabilityFactor.csv",
            self.availability_factor,
            ["REGION", "TECHNOLOGY", "YEAR", "VALUE"],
            ["REGION", "TECHNOLOGY", "YEAR"],
        )
        self._save_sorted(
            "TotalAnnualMaxCapacity.csv",
            self.total_annual_max_capacity,
            ["REGION", "TECHNOLOGY", "YEAR", "VALUE"],
            ["REGION", "TECHNOLOGY", "YEAR"],
        )
        self._save_sorted(
            "TotalAnnualMinCapacity.csv",
            self.total_annual_min_capacity,
            ["REGION", "TECHNOLOGY", "YEAR", "VALUE"],
            ["REGION", "TECHNOLOGY", "YEAR"],
        )

    # =========================================================================
    # User Input: Efficiency / Activity Ratios
    # =========================================================================

    def set_efficiency(
        self,
        region: str,
        technology: str,
        efficiency: Union[float, Dict[int, float]],
        mode: str = 'MODE1',
        years: Optional[List[int]] = None
    ) -> None:
        """
        Set conversion efficiency for a technology.

        Generates InputActivityRatio and OutputActivityRatio rows.
        Fuel assignments are auto-discovered from the supply registry.

        Parameters
        ----------
        region : str
            Region identifier.
        technology : str
            Technology identifier (must be registered in supply).
        efficiency : float or dict
            Conversion efficiency in (0, 1]. If dict, {year: eff}.
        mode : str, default 'MODE1'
            Mode of operation.
        years : list of int, optional
            Years to apply. If None, applies to all model years.

        Raises
        ------
        ValueError
            If technology not in supply registry, efficiency invalid,
            or no fuel assignment found.

        Example
        -------
        >>> performance.set_efficiency('REGION1', 'GAS_CCGT', 0.5)
        """
        self._validate_technology(region, technology)

        # Look up fuel assignments from supply registry
        fuel_info = self._fuel_map.get((region, technology, mode))
        if fuel_info is None:
            raise ValueError(
                f"No fuel assignment found for ({region}, "
                f"{technology}, {mode}). Ensure supply component "
                "defined this technology with as_conversion()."
            )

        input_fuel = fuel_info.get('input')
        output_fuel = fuel_info.get('output')
        if input_fuel is None:
            raise ValueError(
                f"Technology ({region}, {technology}) is a resource "
                "type with no input fuel. Use set_resource_output() "
                "instead."
            )

        # Build year -> efficiency mapping
        eff_map = self._build_efficiency_map(efficiency)
        target_years = years if years else self.years

        # Generate activity ratio records
        input_records, output_records = [], []
        for y in target_years:
            eff = eff_map.get(y, list(eff_map.values())[0])
            inp_ratio = 1.0 / eff
            out_ratio = 1.0

            input_records.append({
                "REGION": region, "TECHNOLOGY": technology,
                "FUEL": input_fuel, "MODE_OF_OPERATION": mode,
                "YEAR": y, "VALUE": inp_ratio,
            })
            output_records.append({
                "REGION": region, "TECHNOLOGY": technology,
                "FUEL": output_fuel, "MODE_OF_OPERATION": mode,
                "YEAR": y, "VALUE": out_ratio,
            })

        key_cols = [
            "REGION", "TECHNOLOGY", "FUEL",
            "MODE_OF_OPERATION", "YEAR",
        ]
        self.input_activity_ratio = self.add_to_dataframe(
            self.input_activity_ratio, input_records,
            key_columns=key_cols,
        )
        self.output_activity_ratio = self.add_to_dataframe(
            self.output_activity_ratio, output_records,
            key_columns=key_cols,
        )
        self._defined_tech.add((region, technology))

    def set_resource_output(
        self,
        region: str,
        technology: str,
        mode: str = 'MODE1',
        years: Optional[List[int]] = None
    ) -> None:
        """
        Set output activity ratio for a resource technology (no input).

        Used for renewables, primary extraction, etc. Sets
        OutputActivityRatio = 1.0 for the registered output fuel.

        Parameters
        ----------
        region : str
            Region identifier.
        technology : str
            Technology identifier.
        mode : str, default 'MODE1'
            Mode of operation.
        years : list of int, optional
            Years to apply. If None, applies to all model years.

        Raises
        ------
        ValueError
            If technology not in supply registry or no fuel found.
        """
        self._validate_technology(region, technology)

        fuel_info = self._fuel_map.get((region, technology, mode))
        if fuel_info is None:
            raise ValueError(
                f"No fuel assignment found for ({region}, "
                f"{technology}, {mode})."
            )
        output_fuel = fuel_info.get('output')
        target_years = years if years else self.years

        output_records = [{
            "REGION": region, "TECHNOLOGY": technology,
            "FUEL": output_fuel, "MODE_OF_OPERATION": mode,
            "YEAR": y, "VALUE": 1.0,
        } for y in target_years]

        key_cols = [
            "REGION", "TECHNOLOGY", "FUEL",
            "MODE_OF_OPERATION", "YEAR",
        ]
        self.output_activity_ratio = self.add_to_dataframe(
            self.output_activity_ratio, output_records,
            key_columns=key_cols,
        )
        self._defined_tech.add((region, technology))

    def set_multimode_ratios(
        self,
        region: str,
        technology: str,
        modes_config: Dict[str, Dict],
        years: Optional[List[int]] = None
    ) -> None:
        """
        Set activity ratios for a multi-mode technology.

        Parameters
        ----------
        region : str
            Region identifier.
        technology : str
            Technology identifier.
        modes_config : dict
            Configuration per mode::

                {mode_name: {
                    'inputs': {fuel: ratio, ...},
                    'outputs': {fuel: ratio, ...},
                }}

        years : list of int, optional
            Years to apply. If None, applies to all model years.

        Raises
        ------
        ValueError
            If technology not in supply registry or ratios invalid.

        Example
        -------
        >>> performance.set_multimode_ratios('R1', 'CHP', {
        ...     'ELEC_ONLY': {
        ...         'inputs': {'GAS': 1.82},
        ...         'outputs': {'ELEC': 1.0}},
        ...     'CHP_MODE': {
        ...         'inputs': {'GAS': 1.25},
        ...         'outputs': {'ELEC': 0.5, 'HEAT': 0.3}},
        ... })
        """
        self._validate_technology(region, technology)
        target_years = years if years else self.years

        input_records, output_records = [], []

        for mode, config in modes_config.items():
            inputs = config.get('inputs', {})
            outputs = config.get('outputs', {})
            if not outputs:
                raise ValueError(
                    f"Mode '{mode}' must specify at least one output"
                )

            for y in target_years:
                for fuel, ratio in inputs.items():
                    if ratio <= 0:
                        raise ValueError(
                            f"Input ratio for '{fuel}' must be "
                            f"positive, got {ratio}"
                        )
                    input_records.append({
                        "REGION": region,
                        "TECHNOLOGY": technology,
                        "FUEL": fuel,
                        "MODE_OF_OPERATION": mode,
                        "YEAR": y, "VALUE": ratio,
                    })

                for fuel, ratio in outputs.items():
                    if ratio <= 0:
                        raise ValueError(
                            f"Output ratio for '{fuel}' must be "
                            f"positive, got {ratio}"
                        )
                    output_records.append({
                        "REGION": region,
                        "TECHNOLOGY": technology,
                        "FUEL": fuel,
                        "MODE_OF_OPERATION": mode,
                        "YEAR": y, "VALUE": ratio,
                    })

        key_cols = [
            "REGION", "TECHNOLOGY", "FUEL",
            "MODE_OF_OPERATION", "YEAR",
        ]
        self.input_activity_ratio = self.add_to_dataframe(
            self.input_activity_ratio, input_records,
            key_columns=key_cols,
        )
        self.output_activity_ratio = self.add_to_dataframe(
            self.output_activity_ratio, output_records,
            key_columns=key_cols,
        )
        self._defined_tech.add((region, technology))

    # =========================================================================
    # User Input: Capacity and Availability Factors
    # =========================================================================

    def set_capacity_factor(
        self,
        region: str,
        technology: str,
        factor: Union[float, Dict[int, float]],
        years: Optional[Union[int, List[int]]] = None,
        timeslice_weights: Optional[Dict[str, float]] = None,
        season_weights: Optional[Dict[str, float]] = None,
        daytype_weights: Optional[Dict[str, float]] = None,
        bracket_weights: Optional[Dict[str, float]] = None
    ) -> None:
        """
        Set capacity factor profile across timeslices.

        The simplest usage provides a single float applied uniformly
        to all timeslices and years. For sub-annual variation, use
        the weight arguments.

        Parameters
        ----------
        region : str
            Region identifier.
        technology : str
            Technology identifier.
        factor : float or dict
            Base capacity factor in [0, 1]. If dict, {year: factor}.
        years : int, list of int, or None
            Years to apply. None applies to all model years.
        timeslice_weights : dict, optional
            Direct {timeslice: weight} mapping. Overrides hierarchical.
        season_weights : dict, optional
            {season: weight} for seasonal variation.
        daytype_weights : dict, optional
            {daytype: weight} for day-pattern variation.
        bracket_weights : dict, optional
            {bracket: weight} for time-of-day variation.

        Notes
        -----
        When weights are provided, the final capacity factor for each
        timeslice is ``factor × weight``, clamped to [0, 1].
        Unspecified weights default to 1.0.

        Example
        -------
        Uniform capacity factor::

            >>> performance.set_capacity_factor(
            ...     'REGION1', 'GAS_CCGT', 0.9)

        With seasonal variation::

            >>> performance.set_capacity_factor(
            ...     'REGION1', 'SOLAR_PV', 0.25,
            ...     season_weights={'Summer': 1.2, 'Winter': 0.6})
        """
        self._validate_technology(region, technology)
        target_years = self._resolve_years(years)

        # Build base factor mapping
        if isinstance(factor, dict):
            factor_map = self._step_interpolate_dict(factor)
        else:
            if not 0 <= factor <= 1:
                raise ValueError(
                    f"Capacity factor must be in [0, 1], "
                    f"got {factor}"
                )
            factor_map = {y: factor for y in self.years}

        # Build weight dictionary per timeslice
        if timeslice_weights is not None:
            weight_dict = self._apply_timeslice_weights(
                timeslice_weights, default=1.0
            )
        elif any(w is not None for w in [
            season_weights, daytype_weights, bracket_weights
        ]):
            weight_dict = self._apply_hierarchical_weights(
                season_weights or {},
                daytype_weights or {},
                bracket_weights or {},
                default=1.0,
            )
        else:
            weight_dict = {ts: 1.0 for ts in self.timeslices}

        # Store assignments for processing
        for y in target_years:
            base = factor_map.get(y, factor_map[self.years[0]])
            weighted = {}
            for ts, w in weight_dict.items():
                weighted[ts] = max(0.0, min(1.0, base * w))
            self._capacity_factor_assignments[
                (region, technology, y)
            ] = weighted

        self._defined_tech.add((region, technology))

    def set_availability_factor(
        self,
        region: str,
        technology: str,
        availability: Union[float, Dict[int, float]]
    ) -> None:
        """
        Set annual availability factor (maintenance, outages).

        Parameters
        ----------
        region : str
            Region identifier.
        technology : str
            Technology identifier.
        availability : float or dict
            Annual availability in [0, 1]. If dict, {year: value}.

        Raises
        ------
        ValueError
            If availability out of bounds.

        Example
        -------
        >>> performance.set_availability_factor(
        ...     'REGION1', 'NUCLEAR', 0.90)
        """
        self._validate_technology(region, technology)

        if isinstance(availability, dict):
            avail_map = self._step_interpolate_dict(availability)
        else:
            if not 0 <= availability <= 1:
                raise ValueError(
                    f"Availability must be in [0, 1], "
                    f"got {availability}"
                )
            avail_map = {y: availability for y in self.years}

        records = [
            {"REGION": region, "TECHNOLOGY": technology,
             "YEAR": y, "VALUE": avail_map[y]}
            for y in self.years
        ]

        self.availability_factor = self.add_to_dataframe(
            self.availability_factor, records,
            key_columns=["REGION", "TECHNOLOGY", "YEAR"],
        )
        self._defined_tech.add((region, technology))

    # =========================================================================
    # User Input: Capacity-to-Activity and Capacity Limits
    # =========================================================================

    def set_capacity_to_activity_unit(
        self,
        region: str,
        technology: str,
        value: float = 8760
    ) -> None:
        """
        Set conversion factor from capacity to activity units.

        Parameters
        ----------
        region : str
            Region identifier.
        technology : str
            Technology identifier.
        value : float, default 8760
            Conversion factor. Default 8760 means 1 capacity unit =
            1 MW, 1 activity unit = 1 MWh (hours per year).

        Raises
        ------
        ValueError
            If value <= 0.

        Example
        -------
        >>> performance.set_capacity_to_activity_unit(
        ...     'REGION1', 'GAS_CCGT', 8760)
        """
        self._validate_technology(region, technology)
        if value <= 0:
            raise ValueError(
                f"CapacityToActivityUnit must be positive, "
                f"got {value}"
            )

        record = [{
            "REGION": region, "TECHNOLOGY": technology,
            "VALUE": value,
        }]
        self.capacity_to_activity_unit = self.add_to_dataframe(
            self.capacity_to_activity_unit, record,
            key_columns=["REGION", "TECHNOLOGY"],
        )
        self._defined_tech.add((region, technology))

    def set_capacity_limits(
        self,
        region: str,
        technology: str,
        max_capacity: Optional[
            Union[float, Dict[int, float]]
        ] = None,
        min_capacity: Optional[
            Union[float, Dict[int, float]]
        ] = None,
        interpolation: str = 'step'
    ) -> None:
        """
        Set annual capacity bounds for a technology.

        Parameters
        ----------
        region : str
            Region identifier.
        technology : str
            Technology identifier.
        max_capacity : float, dict, or None
            Upper bound on total installed capacity (MW).
            If float, applies to all years. If dict, {year: MW}.
            None leaves unlimited (OSeMOSYS default = -1).
        min_capacity : float, dict, or None
            Lower bound on total installed capacity (MW).
            If float, applies to all years. If dict, {year: MW}.
            None means no minimum (OSeMOSYS default = 0).
        interpolation : {'step', 'linear'}, default 'step'
            Interpolation method between trajectory points.

        Example
        -------
        >>> performance.set_capacity_limits(
        ...     'REGION1', 'GAS_CCGT',
        ...     max_capacity={2026: 1000 / 8760},
        ...     min_capacity=0)
        """
        self._validate_technology(region, technology)

        if max_capacity is not None:
            records = self._build_trajectory(
                region, technology, max_capacity, interpolation,
            )
            self.total_annual_max_capacity = self.add_to_dataframe(
                self.total_annual_max_capacity, records,
                key_columns=["REGION", "TECHNOLOGY", "YEAR"],
            )

        if min_capacity is not None:
            records = self._build_trajectory(
                region, technology, min_capacity, interpolation,
            )
            self.total_annual_min_capacity = self.add_to_dataframe(
                self.total_annual_min_capacity, records,
                key_columns=["REGION", "TECHNOLOGY", "YEAR"],
            )

        self._defined_tech.add((region, technology))

    # =========================================================================
    # Processing
    # =========================================================================

    def process(self) -> None:
        """
        Generate complete parameter DataFrames from assignments.

        Processes capacity factor assignments into full timeslice
        profiles and fills defaults for technologies that have
        activity ratios but no explicit factor or CAU values.

        Call after all set_* methods and before save().
        """
        # 1. Generate capacity factor rows from assignments
        cf_rows = []
        for (region, tech, year), weights in (
            self._capacity_factor_assignments.items()
        ):
            for ts, value in weights.items():
                cf_rows.append({
                    "REGION": region, "TECHNOLOGY": tech,
                    "TIMESLICE": ts, "YEAR": year,
                    "VALUE": value,
                })

        # 2. Fill default CF = 1.0 for technologies without assignment
        for region, tech in self._defined_tech:
            for year in self.years:
                key = (region, tech, year)
                if key not in self._capacity_factor_assignments:
                    for ts in self.timeslices:
                        cf_rows.append({
                            "REGION": region, "TECHNOLOGY": tech,
                            "TIMESLICE": ts, "YEAR": year,
                            "VALUE": 1.0,
                        })

        if cf_rows:
            self.capacity_factor = self.add_to_dataframe(
                self.capacity_factor, cf_rows,
                key_columns=[
                    "REGION", "TECHNOLOGY", "TIMESLICE", "YEAR",
                ],
            )

        # 3. Fill default AF = 1.0 for missing technologies
        af_rows = []
        for region, tech in self._defined_tech:
            for year in self.years:
                if self.availability_factor.empty:
                    exists = False
                else:
                    exists = (
                        (self.availability_factor["REGION"] == region)
                        & (self.availability_factor["TECHNOLOGY"]
                           == tech)
                        & (self.availability_factor["YEAR"] == year)
                    ).any()
                if not exists:
                    af_rows.append({
                        "REGION": region, "TECHNOLOGY": tech,
                        "YEAR": year, "VALUE": 1.0,
                    })

        if af_rows:
            self.availability_factor = self.add_to_dataframe(
                self.availability_factor, af_rows,
                key_columns=["REGION", "TECHNOLOGY", "YEAR"],
            )

        # 4. Fill default CAU = 8760 for missing technologies
        cau_rows = []
        for region, tech in self._defined_tech:
            if self.capacity_to_activity_unit.empty:
                exists = False
            else:
                exists = (
                    (self.capacity_to_activity_unit["REGION"]
                     == region)
                    & (self.capacity_to_activity_unit["TECHNOLOGY"]
                       == tech)
                ).any()
            if not exists:
                cau_rows.append({
                    "REGION": region, "TECHNOLOGY": tech,
                    "VALUE": 8760,
                })

        if cau_rows:
            self.capacity_to_activity_unit = self.add_to_dataframe(
                self.capacity_to_activity_unit, cau_rows,
                key_columns=["REGION", "TECHNOLOGY"],
            )

    # =========================================================================
    # Validation
    # =========================================================================

    def validate(self) -> None:
        """
        Validate performance parameter consistency.

        Checks:
        - Activity ratios are positive.
        - CapacityFactor and AvailabilityFactor in [0, 1].
        - Capacity limits are non-negative where specified.

        Raises
        ------
        ValueError
            If validation fails.
        """
        self._validate_activity_ratios()
        self._validate_factor_bounds()
        self._validate_capacity_limits()

    def _validate_activity_ratios(self) -> None:
        """Validate activity ratio consistency."""
        errors = []

        # Check for non-positive ratios
        for df_name, df in [
            ('InputActivityRatio', self.input_activity_ratio),
            ('OutputActivityRatio', self.output_activity_ratio),
        ]:
            if not df.empty and (df['VALUE'] <= 0).any():
                bad = df[df['VALUE'] <= 0]
                for _, row in bad.iterrows():
                    errors.append(
                        f"Non-positive {df_name}: "
                        f"{row['TECHNOLOGY']} year {row['YEAR']}"
                    )

        if errors:
            raise ValueError(
                "Activity ratio validation failed:\n"
                + "\n".join(f"  - {e}" for e in errors)
            )

    def _validate_factor_bounds(self) -> None:
        """Validate capacity and availability factors in [0, 1]."""
        if not self.capacity_factor.empty:
            vals = self.capacity_factor['VALUE']
            if (vals < 0).any() or (vals > 1).any():
                raise ValueError(
                    "CapacityFactor must be in range [0, 1]"
                )

        if not self.availability_factor.empty:
            vals = self.availability_factor['VALUE']
            if (vals < 0).any() or (vals > 1).any():
                raise ValueError(
                    "AvailabilityFactor must be in range [0, 1]"
                )

    def _validate_capacity_limits(self) -> None:
        """Validate capacity limit consistency."""
        if (not self.total_annual_min_capacity.empty
                and not self.total_annual_max_capacity.empty):
            # Check min <= max where both are specified
            merged = pd.merge(
                self.total_annual_min_capacity,
                self.total_annual_max_capacity,
                on=["REGION", "TECHNOLOGY", "YEAR"],
                suffixes=("_min", "_max"),
                how="inner",
            )
            if not merged.empty:
                # Only check where max is not -1 (unlimited)
                check = merged[merged['VALUE_max'] >= 0]
                bad = check[check['VALUE_min'] > check['VALUE_max']]
                if not bad.empty:
                    raise ValueError(
                        "TotalAnnualMinCapacity exceeds "
                        "TotalAnnualMaxCapacity for:\n"
                        + bad.to_string()
                    )

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _load_set(self, filename: str) -> List[str]:
        """Load a set CSV file, returning list of values."""
        path = os.path.join(self.scenario_dir, filename)
        if os.path.exists(path):
            df = pd.read_csv(path)
            if not df.empty and 'VALUE' in df.columns:
                return df['VALUE'].astype(str).tolist()
        return []

    def _load_fuel_map(self) -> Dict[Tuple, Dict]:
        """
        Load fuel assignments from supply's metadata JSON, falling
        back to InputActivityRatio / OutputActivityRatio CSVs.

        Returns
        -------
        dict
            Mapping of (region, technology, mode) -> fuel info.
        """
        fuel_map = {}

        # 1. Try supply's serialized fuel-assignment metadata
        fa_path = os.path.join(
            self.scenario_dir, "_fuel_assignments.json"
        )
        if os.path.exists(fa_path):
            try:
                with open(fa_path, 'r') as f:
                    raw = json.load(f)
                for composite_key, info in raw.items():
                    parts = composite_key.split('|')
                    key = tuple(parts)  # (region, tech, mode)
                    fuel_map[key] = info
                if fuel_map:
                    return fuel_map
            except Exception:
                pass

        # 2. Fallback: read from existing activity ratio CSVs
        iar_path = os.path.join(
            self.scenario_dir, "InputActivityRatio.csv"
        )
        oar_path = os.path.join(
            self.scenario_dir, "OutputActivityRatio.csv"
        )

        if os.path.exists(iar_path) and os.path.exists(oar_path):
            try:
                iar = pd.read_csv(iar_path)
                oar = pd.read_csv(oar_path)

                for _, row in oar.drop_duplicates(
                    subset=["REGION", "TECHNOLOGY",
                            "MODE_OF_OPERATION"]
                ).iterrows():
                    key = (
                        row['REGION'],
                        row['TECHNOLOGY'],
                        row['MODE_OF_OPERATION'],
                    )
                    fuel_map[key] = {
                        'output': row['FUEL'],
                    }

                for _, row in iar.drop_duplicates(
                    subset=["REGION", "TECHNOLOGY",
                            "MODE_OF_OPERATION"]
                ).iterrows():
                    key = (
                        row['REGION'],
                        row['TECHNOLOGY'],
                        row['MODE_OF_OPERATION'],
                    )
                    if key not in fuel_map:
                        fuel_map[key] = {}
                    fuel_map[key]['input'] = row['FUEL']

                return fuel_map
            except Exception:
                pass

        return fuel_map

    def _load_time_axis(self) -> Optional[pd.DataFrame]:
        """Load time axis data for hierarchical weight support."""
        try:
            time_data = TimeComponent.load_time_axis(self)
            df = time_data['yearsplit'].copy()
            slice_map = time_data['slice_map']

            df['Season'] = df['TIMESLICE'].map(
                lambda x: slice_map.get(x, {}).get('Season', '')
            )
            df['DayType'] = df['TIMESLICE'].map(
                lambda x: slice_map.get(x, {}).get('DayType', '')
            )
            df['DailyTimeBracket'] = df['TIMESLICE'].map(
                lambda x: slice_map.get(x, {}).get(
                    'DailyTimeBracket', ''
                )
            )
            return df
        except Exception:
            return None

    def _validate_technology(
        self, region: str, technology: str
    ) -> None:
        """Validate technology exists in the supply registry."""
        if region not in self.regions:
            raise ValueError(f"Region '{region}' not defined")
        if (technology not in self._technologies
                and technology not in {
                    t for _, t in self._defined_tech
                }):
            raise ValueError(
                f"Technology '{technology}' not found in supply "
                "registry. Ensure SupplyComponent has saved to disk."
            )

    def _build_efficiency_map(
        self, efficiency: Union[float, Dict[int, float]]
    ) -> Dict[int, float]:
        """Build year -> efficiency mapping with validation."""
        if isinstance(efficiency, (int, float)):
            if not 0 < efficiency <= 1:
                raise ValueError(
                    f"Efficiency must be in (0, 1], "
                    f"got {efficiency}"
                )
            return {y: efficiency for y in self.years}

        for y, val in efficiency.items():
            if not 0 < val <= 1:
                raise ValueError(
                    f"Efficiency for year {y} must be in (0, 1]"
                )
        return self._step_interpolate_dict(efficiency)

    def _step_interpolate_dict(
        self, data: Dict[int, float]
    ) -> Dict[int, float]:
        """Step-interpolate {year: value} to all model years."""
        sorted_years = sorted(data.keys())
        result = {}
        for y in self.years:
            prev = [ey for ey in sorted_years if ey <= y]
            if prev:
                result[y] = data[max(prev)]
            else:
                result[y] = data[min(sorted_years)]
        return result

    def _resolve_years(
        self, years: Optional[Union[int, List[int]]]
    ) -> List[int]:
        """Resolve years argument to list."""
        if years is None:
            return self.years
        elif isinstance(years, int):
            return [years]
        return years

    def _build_trajectory(
        self,
        region: str,
        technology: str,
        trajectory: Union[float, Dict[int, float]],
        interpolation: str
    ) -> List[Dict]:
        """Build records from a scalar or trajectory dict."""
        if isinstance(trajectory, (int, float)):
            trajectory = {self.years[0]: float(trajectory)}

        sorted_years = sorted(trajectory.keys())
        records = []

        for y in self.years:
            val = self._interpolate_value(
                y, trajectory, sorted_years, interpolation
            )
            records.append({
                "REGION": region, "TECHNOLOGY": technology,
                "YEAR": y, "VALUE": val,
            })
        return records

    def _interpolate_value(
        self,
        year: int,
        trajectory: Dict[int, float],
        sorted_years: List[int],
        method: str
    ) -> float:
        """Interpolate value for a single year."""
        first_yr = sorted_years[0]
        last_yr = sorted_years[-1]

        if year < first_yr:
            return trajectory[first_yr]
        if year > last_yr:
            return trajectory[last_yr]
        if year in trajectory:
            return trajectory[year]

        for i in range(len(sorted_years) - 1):
            y_start = sorted_years[i]
            y_end = sorted_years[i + 1]
            if y_start <= year < y_end:
                v_start = trajectory[y_start]
                v_end = trajectory[y_end]
                if method == 'linear':
                    ratio = (year - y_start) / (y_end - y_start)
                    return v_start + ratio * (v_end - v_start)
                else:
                    return v_start

        return trajectory[last_yr]

    def _apply_timeslice_weights(
        self,
        weights: Dict[str, float],
        default: float = 1.0
    ) -> Dict[str, float]:
        """Apply timeslice-level weights."""
        return {
            ts: weights.get(ts, default)
            for ts in self.timeslices
        }

    def _apply_hierarchical_weights(
        self,
        season_w: Dict[str, float],
        daytype_w: Dict[str, float],
        bracket_w: Dict[str, float],
        default: float = 1.0
    ) -> Dict[str, float]:
        """Apply hierarchical weights (season x daytype x bracket)."""
        if self._time_axis is None:
            # Fallback: all weights = default
            return {ts: default for ts in self.timeslices}

        s_adj = {
            s: season_w.get(s, default)
            for s in self._time_axis["Season"].unique()
        }
        d_adj = {
            d: daytype_w.get(d, default)
            for d in self._time_axis["DayType"].unique()
        }
        t_adj = {
            t: bracket_w.get(t, default)
            for t in self._time_axis["DailyTimeBracket"].unique()
        }

        result = {}
        unique_ts = self._time_axis.drop_duplicates(
            subset=['TIMESLICE']
        )
        for _, row in unique_ts.iterrows():
            ts = row["TIMESLICE"]
            val = (
                s_adj.get(row["Season"], default)
                * d_adj.get(row["DayType"], default)
                * t_adj.get(row["DailyTimeBracket"], default)
            )
            result[ts] = val

        return result

    def register_technology(
        self, region: str, technology: str
    ) -> None:
        """
        Manually register a (region, technology) pair for processing.

        Useful when the technology was not loaded from TECHNOLOGY.csv
        but needs default values generated during process().

        Parameters
        ----------
        region : str
            Region identifier.
        technology : str
            Technology identifier.
        """
        self._defined_tech.add((region, technology))
        if technology not in self._technologies:
            self._technologies.append(technology)

    # =========================================================================
    # Representation
    # =========================================================================

    def __repr__(self) -> str:
        n_tech = len(self._defined_tech)
        return (
            f"PerformanceComponent("
            f"scenario_dir='{self.scenario_dir}', "
            f"technologies={n_tech})"
        )
