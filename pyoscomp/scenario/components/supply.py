# pyoscomp/scenario/components/supply.py

"""
Supply component for scenario building in PyPSA-OSeMOSYS Comparison Framework.

This component handles technology/generator definitions and supply-side parameters:
- TECHNOLOGY set (technology registry)
- FUEL set (auto-generated from activity ratios)
- MODE_OF_OPERATION set (auto-generated from technology modes)
- Activity ratios (InputActivityRatio, OutputActivityRatio)
- Capacity parameters (ResidualCapacity, CapacityFactor, AvailabilityFactor)
- Operational parameters (OperationalLife, CapacityToActivityUnit)

OSeMOSYS Terminology: TECHNOLOGY, InputActivityRatio, OutputActivityRatio
PyPSA Terminology: Generator (with efficiency, p_nom, etc.)

Prerequisites:
- TimeComponent (years, timeslices must be defined)
- TopologyComponent (regions must be defined)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Set, Tuple, Union

from .base import ScenarioComponent
from .time import TimeComponent


class SupplyComponent(ScenarioComponent):
    """
    Supply component for technology/generator definitions.

    Handles the technology registry and all supply-side parameters including
    conversion efficiencies, capacity factors, and residual capacities.

    Attributes
    ----------
    years : list of int
        Model years (from prerequisites).
    regions : list of str
        Region identifiers (from prerequisites).
    defined_tech : set
        Set of (region, technology) pairs.
    defined_fuels : set
        Set of fuel identifiers referenced in activity ratios.

    Owned Files
    -----------
    Sets: TECHNOLOGY.csv, FUEL.csv, MODE_OF_OPERATION.csv
    Params: CapacityToActivityUnit.csv, OperationalLife.csv,
            InputActivityRatio.csv, OutputActivityRatio.csv,
            CapacityFactor.csv, AvailabilityFactor.csv, ResidualCapacity.csv

    Example
    -------
    Define technologies::

        supply = SupplyComponent(scenario_dir)

        # Register technology
        supply.add_technology('REGION1', 'GAS_CCGT', operational_life=30)

        # Set conversion (input -> output)
        supply.set_conversion_technology(
            'REGION1', 'GAS_CCGT',
            input_fuel='GAS', output_fuel='ELECTRICITY',
            efficiency=0.55
        )

        # Set capacity factors
        supply.set_capacity_factor(
            'REGION1', 'GAS_CCGT',
            season_weights={'Winter': 0.9, 'Summer': 1.0}
        )

        supply.process()
        supply.save()

    See Also
    --------
    component_mapping.md : Full documentation of supply ownership
    """

    owned_files = [
        'TECHNOLOGY.csv', 'FUEL.csv', 'MODE_OF_OPERATION.csv',
        'ResidualCapacity.csv',
    ]

    def __init__(self, scenario_dir: str, performance=None):
        """
        Initialize supply component.

        Parameters
        ----------
        scenario_dir : str
            Path to the scenario directory.
        performance : PerformanceComponent, optional
            Performance component instance for storing performance data.
            Must be provided before calling technology definition methods.

        Raises
        ------
        AttributeError
            If TimeComponent or TopologyComponent not initialized.
        """
        super().__init__(scenario_dir)

        # Performance component back-reference
        self._perf = performance

        # Check prerequisites
        prereqs = self.check_prerequisites(
            require_years=True,
            require_regions=True,
            require_timeslices=True
        )
        self.years = prereqs['years']
        self.regions = prereqs['regions']
        self.timeslices = prereqs['timeslices']

        # Load time axis for capacity factor calculations
        self._time_axis = self._load_time_axis()

        # Supply-owned DataFrames only
        self.residual_capacity = self.init_dataframe("ResidualCapacity")

        # Tracking
        self.defined_tech: Set[Tuple[str, str]] = set()
        self.defined_fuels: Set[str] = set()
        self._mode_definitions: Dict[Tuple[str, str], List[str]] = {}
        self._capacity_factor_assignments: Dict[Tuple, Dict] = {}

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def technologies(self) -> List[str]:
        """Get list of unique technology identifiers."""
        return list({tech for _, tech in self.defined_tech})

    @property
    def fuels(self) -> List[str]:
        """Get list of defined fuel identifiers."""
        return list(self.defined_fuels)

    @property
    def modes(self) -> Set[str]:
        """Get set of all modes across all technologies."""
        all_modes = set()
        for modes in self._mode_definitions.values():
            all_modes.update(modes)
        return all_modes if all_modes else {'MODE1'}

    # =========================================================================
    # Load and Save
    # =========================================================================

    def load(self) -> None:
        """
        Load supply-owned parameter CSV files.

        Performance parameters (OperationalLife, activity ratios, etc.)
        are loaded by PerformanceComponent.

        Raises
        ------
        FileNotFoundError
            If any required file is missing.
        ValueError
            If any file fails schema validation.
        """
        self.residual_capacity = self.read_csv("ResidualCapacity.csv")

        # Rebuild tracking from performance data
        if self._perf is not None:
            self.defined_tech = set(
                zip(
                    self._perf.capacity_to_activity_unit['REGION'],
                    self._perf.capacity_to_activity_unit['TECHNOLOGY']
                )
            ) if not self._perf.capacity_to_activity_unit.empty else set()
            self._rebuild_fuels_and_modes()

    def save(self) -> None:
        """
        Save supply-owned DataFrames to CSV.

        Generates TECHNOLOGY.csv, FUEL.csv, MODE_OF_OPERATION.csv sets
        based on defined technologies and activity ratios.
        Performance parameters are saved by PerformanceComponent.

        Raises
        ------
        ValueError
            If any DataFrame fails schema validation.
        """
        # Generate set CSVs
        tech_df = pd.DataFrame({"VALUE": list(self.technologies)})
        fuel_df = pd.DataFrame({"VALUE": list(self.defined_fuels)})
        mode_df = pd.DataFrame({"VALUE": list(self.modes)})

        self.write_dataframe("TECHNOLOGY.csv", tech_df)
        self.write_dataframe("FUEL.csv", fuel_df)
        self.write_dataframe("MODE_OF_OPERATION.csv", mode_df)

        # Save supply-owned parameter CSVs
        self._save_sorted("ResidualCapacity.csv", self.residual_capacity,
                          ["REGION", "TECHNOLOGY", "YEAR", "VALUE"],
                          ["REGION", "TECHNOLOGY", "YEAR"])

    def _save_sorted(
        self,
        filename: str,
        df: pd.DataFrame,
        cols: List[str],
        sort_cols: List[str]
    ) -> None:
        """Helper to save DataFrame with column selection and sorting."""
        if df.empty:
            self.write_dataframe(filename, df)
        else:
            sorted_df = df[cols].sort_values(by=sort_cols)
            self.write_dataframe(filename, sorted_df)

    # =========================================================================
    # User Input: Technology Registration
    # =========================================================================

    def add_technology(
        self,
        region: str,
        technology: str,
        operational_life: int,
        capacity_to_activity_unit: float = 31.536
    ) -> None:
        """
        Register a new technology with basic metadata.

        This is the entry point for defining any supply technology.
        Call this before setting conversion, capacity factors, etc.

        Parameters
        ----------
        region : str
            Region identifier.
        technology : str
            Technology identifier (e.g., 'GAS_CCGT', 'SOLAR_PV').
        operational_life : int
            Operational lifetime in years (must be positive).
        capacity_to_activity_unit : float, default 31.536
            Conversion factor from capacity to activity.
            Default converts GW to PJ/year (GW × 8760h × 3.6 MJ/kWh / 1000).

        Raises
        ------
        ValueError
            If region not defined or operational_life <= 0.

        Example
        -------
        >>> supply.add_technology('REGION1', 'GAS_CCGT', operational_life=30)
        """
        if region not in self.regions:
            raise ValueError(f"Region '{region}' not defined. Initialize topology first.")
        if operational_life <= 0:
            raise ValueError(f"Operational life must be positive, got {operational_life}")

        self.defined_tech.add((region, technology))

        # OperationalLife → PerformanceComponent
        ol_record = [{"REGION": region, "TECHNOLOGY": technology, "VALUE": operational_life}]
        self._perf.operational_life = self.add_to_dataframe(
            self._perf.operational_life, ol_record, key_columns=["REGION", "TECHNOLOGY"]
        )

        # CapacityToActivityUnit → PerformanceComponent
        cau_record = [{"REGION": region, "TECHNOLOGY": technology, "VALUE": capacity_to_activity_unit}]
        self._perf.capacity_to_activity_unit = self.add_to_dataframe(
            self._perf.capacity_to_activity_unit, cau_record, key_columns=["REGION", "TECHNOLOGY"]
        )

    # =========================================================================
    # User Input: Technology Types
    # =========================================================================

    def set_conversion_technology(
        self,
        region: str,
        technology: str,
        input_fuel: str,
        output_fuel: str,
        efficiency: Union[float, Dict[int, float]],
        mode: str = 'MODE1',
        years: Optional[List[int]] = None
    ) -> None:
        """
        Define a conversion technology (input fuel → output fuel).

        Parameters
        ----------
        region : str
            Region identifier.
        technology : str
            Technology identifier (must be registered via add_technology).
        input_fuel : str
            Input fuel consumed.
        output_fuel : str
            Output fuel produced.
        efficiency : float or dict
            Conversion efficiency (0, 1]. If dict, {year: efficiency}.
        mode : str, default 'MODE1'
            Mode of operation identifier.
        years : list of int, optional
            Years to apply. If None, applies to all model years.

        Raises
        ------
        ValueError
            If technology not registered, efficiency invalid, or fuels same.

        Example
        -------
        >>> supply.set_conversion_technology(
        ...     'REGION1', 'GAS_CCGT',
        ...     input_fuel='NATURAL_GAS', output_fuel='ELECTRICITY',
        ...     efficiency=0.55
        ... )
        """
        self._validate_technology(region, technology)

        if input_fuel == output_fuel:
            raise ValueError("Input and output fuels must be different")

        # Validate and map efficiency
        eff_map = self._build_efficiency_map(efficiency)
        target_years = years if years else self.years

        # Generate activity ratios
        input_records, output_records = [], []
        for y in target_years:
            eff = eff_map.get(y, list(eff_map.values())[0])
            inp_ratio, out_ratio = self._efficiency_to_ratios(eff)

            input_records.append({
                "REGION": region, "TECHNOLOGY": technology, "FUEL": input_fuel,
                "MODE_OF_OPERATION": mode, "YEAR": y, "VALUE": inp_ratio
            })
            output_records.append({
                "REGION": region, "TECHNOLOGY": technology, "FUEL": output_fuel,
                "MODE_OF_OPERATION": mode, "YEAR": y, "VALUE": out_ratio
            })

        self._perf.input_activity_ratio = self.add_to_dataframe(
            self._perf.input_activity_ratio, input_records,
            key_columns=["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR"]
        )
        self._perf.output_activity_ratio = self.add_to_dataframe(
            self._perf.output_activity_ratio, output_records,
            key_columns=["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR"]
        )

        self.defined_fuels.update([input_fuel, output_fuel])
        self._register_mode(region, technology, mode)

    def set_resource_technology(
        self,
        region: str,
        technology: str,
        output_fuel: str
    ) -> None:
        """
        Define a resource/extraction technology (no input, produces output).

        Used for renewables (wind, solar), primary extraction (mining), etc.

        Parameters
        ----------
        region : str
            Region identifier.
        technology : str
            Technology identifier.
        output_fuel : str
            Fuel produced.

        Example
        -------
        >>> supply.set_resource_technology('REGION1', 'SOLAR_PV', 'ELECTRICITY')
        """
        self._validate_technology(region, technology)

        output_records = []
        for y in self.years:
            output_records.append({
                "REGION": region, "TECHNOLOGY": technology, "FUEL": output_fuel,
                "MODE_OF_OPERATION": "MODE1", "YEAR": y, "VALUE": 1.0
            })

        self._perf.output_activity_ratio = self.add_to_dataframe(
            self._perf.output_activity_ratio, output_records,
            key_columns=["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR"]
        )

        self.defined_fuels.add(output_fuel)
        self._register_mode(region, technology, "MODE1")

    def set_multimode_technology(
        self,
        region: str,
        technology: str,
        modes_config: Dict[str, Dict]
    ) -> None:
        """
        Define a technology with multiple operating modes.

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
                    'years': list or None  # Optional
                }}

        Example
        -------
        >>> supply.set_multimode_technology('REGION1', 'CHP_PLANT', {
        ...     'ELEC_ONLY': {'inputs': {'GAS': 1.82}, 'outputs': {'ELEC': 1.0}},
        ...     'CHP_MODE': {'inputs': {'GAS': 1.25}, 'outputs': {'ELEC': 0.5, 'HEAT': 0.3}}
        ... })
        """
        self._validate_technology(region, technology)
        self._validate_modes_config(modes_config)

        input_records, output_records = [], []

        for mode, config in modes_config.items():
            inputs = config.get('inputs', {})
            outputs = config.get('outputs', {})
            mode_years = config.get('years', self.years)

            for y in mode_years:
                for fuel, ratio in inputs.items():
                    input_records.append({
                        "REGION": region, "TECHNOLOGY": technology, "FUEL": fuel,
                        "MODE_OF_OPERATION": mode, "YEAR": y, "VALUE": ratio
                    })
                    self.defined_fuels.add(fuel)

                for fuel, ratio in outputs.items():
                    output_records.append({
                        "REGION": region, "TECHNOLOGY": technology, "FUEL": fuel,
                        "MODE_OF_OPERATION": mode, "YEAR": y, "VALUE": ratio
                    })
                    self.defined_fuels.add(fuel)

            self._register_mode(region, technology, mode)

        self._perf.input_activity_ratio = self.add_to_dataframe(
            self._perf.input_activity_ratio, input_records,
            key_columns=["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR"]
        )
        self._perf.output_activity_ratio = self.add_to_dataframe(
            self._perf.output_activity_ratio, output_records,
            key_columns=["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR"]
        )

    # =========================================================================
    # User Input: Capacity and Availability
    # =========================================================================

    def set_residual_capacity(
        self,
        region: str,
        technology: str,
        trajectory: Dict[int, float],
        interpolation: str = 'step'
    ) -> None:
        """
        Define existing/legacy capacity over model years.

        Parameters
        ----------
        region : str
            Region identifier.
        technology : str
            Technology identifier.
        trajectory : dict
            Known capacity points {year: capacity}.
        interpolation : {'step', 'linear'}
            Method for years between trajectory points.

        Example
        -------
        >>> supply.set_residual_capacity(
        ...     'REGION1', 'OLD_COAL',
        ...     trajectory={2025: 10, 2035: 5, 2045: 0},
        ...     interpolation='linear'
        ... )
        """
        self._validate_technology(region, technology)

        if not trajectory:
            raise ValueError(f"Empty trajectory for {region}/{technology}")
        for y, val in trajectory.items():
            if val < 0:
                raise ValueError(f"Negative capacity {val} in year {y}")

        records = self._interpolate_trajectory(
            {"REGION": region, "TECHNOLOGY": technology},
            trajectory, interpolation
        )

        self.residual_capacity = self.add_to_dataframe(
            self.residual_capacity, records,
            key_columns=["REGION", "TECHNOLOGY", "YEAR"]
        )

    def set_capacity_factor(
        self,
        region: str,
        technology: str,
        years: Optional[Union[int, List[int]]] = None,
        timeslice_weights: Optional[Dict[str, float]] = None,
        season_weights: Optional[Dict[str, float]] = None,
        daytype_weights: Optional[Dict[str, float]] = None,
        bracket_weights: Optional[Dict[str, float]] = None
    ) -> None:
        """
        Set capacity factor profile across timeslices.

        Parameters
        ----------
        region : str
            Region identifier.
        technology : str
            Technology identifier.
        years : int, list, or None
            Years to apply. None applies to all years.
        timeslice_weights : dict, optional
            Direct {timeslice: factor} mapping.
        season_weights : dict, optional
            {season: factor} for seasonal variation.
        daytype_weights : dict, optional
            {daytype: factor} for day pattern variation.
        bracket_weights : dict, optional
            {bracket: factor} for time-of-day variation.

        Notes
        -----
        Weights default to 1.0 for unspecified entries.
        Values are clamped to [0, 1].

        Example
        -------
        >>> supply.set_capacity_factor(
        ...     'REGION1', 'SOLAR_PV',
        ...     bracket_weights={'Day': 0.8, 'Night': 0.0}
        ... )
        """
        self._validate_technology(region, technology)

        target_years = self._resolve_years(years)

        # Build capacity factor dictionary
        if timeslice_weights is not None:
            cf_dict = self._apply_timeslice_weights(timeslice_weights, default=1.0)
        elif any(w is not None for w in [season_weights, daytype_weights, bracket_weights]):
            cf_dict = self._apply_hierarchical_weights(
                season_weights or {},
                daytype_weights or {},
                bracket_weights or {},
                default=1.0
            )
        else:
            cf_dict = {ts: 1.0 for ts in self.timeslices}

        for y in target_years:
            self._capacity_factor_assignments[(region, technology, y)] = {
                "type": "custom", "weights": cf_dict
            }

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
            Annual availability [0, 1]. If dict, {year: availability}.

        Example
        -------
        >>> supply.set_availability_factor('REGION1', 'NUCLEAR', 0.90)
        """
        self._validate_technology(region, technology)

        # Build availability map
        if isinstance(availability, dict):
            avail_map = self._step_interpolate_dict(availability)
        else:
            if not 0 <= availability <= 1:
                raise ValueError(f"Availability must be in [0, 1], got {availability}")
            avail_map = {y: availability for y in self.years}

        records = [
            {"REGION": region, "TECHNOLOGY": technology, "YEAR": y, "VALUE": avail_map[y]}
            for y in self.years
        ]

        self._perf.availability_factor = self.add_to_dataframe(
            self._perf.availability_factor, records,
            key_columns=["REGION", "TECHNOLOGY", "YEAR"]
        )

    # =========================================================================
    # Processing
    # =========================================================================

    def process(self) -> None:
        """
        Generate complete parameter DataFrames from assignments.

        Processes capacity factor assignments into full timeslice profiles,
        ensures defaults for missing data, and validates consistency.

        Call after all user input methods and before save().
        """
        if self._perf is not None:
            self._perf.validate()

        # Generate capacity factor rows
        cf_rows = []
        for (region, tech, year), assignment in self._capacity_factor_assignments.items():
            for ts, value in assignment["weights"].items():
                cf_rows.append({
                    "REGION": region, "TECHNOLOGY": tech,
                    "TIMESLICE": ts, "YEAR": year, "VALUE": value
                })

        # Default capacity factors (1.0) for missing assignments
        for region, tech in self.defined_tech:
            for year in self.years:
                if (region, tech, year) not in self._capacity_factor_assignments:
                    for ts in self.timeslices:
                        cf_rows.append({
                            "REGION": region, "TECHNOLOGY": tech,
                            "TIMESLICE": ts, "YEAR": year, "VALUE": 1.0
                        })

        self._perf.capacity_factor = self.add_to_dataframe(
            self._perf.capacity_factor, cf_rows,
            key_columns=["REGION", "TECHNOLOGY", "TIMESLICE", "YEAR"]
        )

        # Default availability factors (1.0) for missing
        af_rows = []
        for region, tech in self.defined_tech:
            for year in self.years:
                exists = (
                    (self._perf.availability_factor["REGION"] == region) &
                    (self._perf.availability_factor["TECHNOLOGY"] == tech) &
                    (self._perf.availability_factor["YEAR"] == year)
                ).any()
                if not exists:
                    af_rows.append({
                        "REGION": region, "TECHNOLOGY": tech, "YEAR": year, "VALUE": 1.0
                    })

        self._perf.availability_factor = self.add_to_dataframe(
            self._perf.availability_factor, af_rows,
            key_columns=["REGION", "TECHNOLOGY", "YEAR"]
        )

    # =========================================================================
    # Validation
    # =========================================================================

    def validate(self) -> None:
        """
        Validate supply component state.

        Delegates activity ratio validation to PerformanceComponent.

        Raises
        ------
        ValueError
            If technologies have no outputs, modes inconsistent, or
            activity ratios non-positive.
        """
        if self._perf is not None:
            self._perf.validate()

    def _validate_technology(self, region: str, technology: str) -> None:
        """Validate technology is registered."""
        if region not in self.regions:
            raise ValueError(f"Region '{region}' not defined")
        if (region, technology) not in self.defined_tech:
            raise ValueError(
                f"Technology '{technology}' not registered in '{region}'. "
                "Call add_technology() first."
            )

    def _validate_modes_config(self, modes_config: Dict) -> None:
        """Validate multi-mode configuration structure."""
        if not isinstance(modes_config, dict):
            raise ValueError("modes_config must be a dictionary")

        for mode, config in modes_config.items():
            if 'outputs' not in config or not config['outputs']:
                raise ValueError(f"Mode '{mode}' must specify at least one output")

            for fuel, ratio in list(config.get('inputs', {}).items()) + list(config.get('outputs', {}).items()):
                if not isinstance(ratio, (int, float)) or ratio <= 0:
                    raise ValueError(f"Ratio for '{fuel}' in mode '{mode}' must be positive")

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _load_time_axis(self) -> pd.DataFrame:
        """Load time axis data from TimeComponent."""
        time_data = TimeComponent.load_time_axis(self)
        df = time_data['yearsplit'].copy()
        slice_map = time_data['slice_map']

        df['Season'] = df['TIMESLICE'].map(lambda x: slice_map[x]['Season'])
        df['DayType'] = df['TIMESLICE'].map(lambda x: slice_map[x]['DayType'])
        df['DailyTimeBracket'] = df['TIMESLICE'].map(lambda x: slice_map[x]['DailyTimeBracket'])
        return df

    def _rebuild_fuels_and_modes(self) -> None:
        """Rebuild tracking sets from PerformanceComponent DataFrames."""
        self.defined_fuels = set()
        if not self._perf.input_activity_ratio.empty:
            self.defined_fuels.update(self._perf.input_activity_ratio['FUEL'].unique())
        if not self._perf.output_activity_ratio.empty:
            self.defined_fuels.update(self._perf.output_activity_ratio['FUEL'].unique())

        self._mode_definitions = {}
        for df in [self._perf.input_activity_ratio, self._perf.output_activity_ratio]:
            if not df.empty:
                for _, row in df.iterrows():
                    key = (row['REGION'], row['TECHNOLOGY'])
                    if key not in self._mode_definitions:
                        self._mode_definitions[key] = []
                    mode = row['MODE_OF_OPERATION']
                    if mode not in self._mode_definitions[key]:
                        self._mode_definitions[key].append(mode)

    def _register_mode(self, region: str, technology: str, mode: str) -> None:
        """Register a mode for a technology."""
        key = (region, technology)
        if key not in self._mode_definitions:
            self._mode_definitions[key] = []
        if mode not in self._mode_definitions[key]:
            self._mode_definitions[key].append(mode)

    def _resolve_years(self, years: Optional[Union[int, List[int]]]) -> List[int]:
        """Resolve years argument to list."""
        if years is None:
            return self.years
        elif isinstance(years, int):
            return [years]
        return years

    def _efficiency_to_ratios(self, efficiency: float) -> Tuple[float, float]:
        """Convert efficiency to (input_ratio, output_ratio)."""
        if not 0 < efficiency <= 1:
            raise ValueError(f"Efficiency must be in (0, 1], got {efficiency}")
        return 1.0 / efficiency, 1.0

    def _build_efficiency_map(self, efficiency: Union[float, Dict[int, float]]) -> Dict[int, float]:
        """Build year -> efficiency mapping with step interpolation."""
        if isinstance(efficiency, (int, float)):
            if not 0 < efficiency <= 1:
                raise ValueError(f"Efficiency must be in (0, 1], got {efficiency}")
            return {y: efficiency for y in self.years}

        for y, val in efficiency.items():
            if not 0 < val <= 1:
                raise ValueError(f"Efficiency for year {y} must be in (0, 1]")

        return self._step_interpolate_dict(efficiency)

    def _step_interpolate_dict(self, data: Dict[int, float]) -> Dict[int, float]:
        """Step-interpolate a {year: value} dict to cover all model years."""
        sorted_years = sorted(data.keys())
        result = {}

        for y in self.years:
            prev_years = [ey for ey in sorted_years if ey <= y]
            if prev_years:
                result[y] = data[max(prev_years)]
            else:
                result[y] = data[min(sorted_years)]

        return result

    def _interpolate_trajectory(
        self,
        base_record: Dict,
        trajectory: Dict[int, float],
        method: str
    ) -> List[Dict]:
        """Interpolate trajectory to all model years."""
        records = []
        sorted_years = sorted(trajectory.keys())
        first_yr, last_yr = sorted_years[0], sorted_years[-1]

        # Before first point
        for y in [yr for yr in self.years if yr < first_yr]:
            records.append({**base_record, "YEAR": y, "VALUE": trajectory[first_yr]})

        # Between points
        for i in range(len(sorted_years) - 1):
            y_start, y_end = sorted_years[i], sorted_years[i + 1]
            v_start, v_end = trajectory[y_start], trajectory[y_end]
            years_to_fill = [yr for yr in self.years if y_start <= yr < y_end]

            if method == 'linear':
                values = np.linspace(v_start, v_end, len(years_to_fill) + 1)[:-1]
            else:
                values = [v_start] * len(years_to_fill)

            for yr, val in zip(years_to_fill, values):
                records.append({**base_record, "YEAR": yr, "VALUE": val})

        # Last point
        if last_yr in self.years:
            records.append({**base_record, "YEAR": last_yr, "VALUE": trajectory[last_yr]})

        # After last point
        for y in [yr for yr in self.years if yr > last_yr]:
            records.append({**base_record, "YEAR": y, "VALUE": max(0, trajectory[last_yr])})

        return records

    def _apply_timeslice_weights(
        self,
        weights: Dict[str, float],
        default: float = 1.0
    ) -> Dict[str, float]:
        """Apply timeslice-level weights, clamping to [0, 1]."""
        result = {}
        for ts in self.timeslices:
            val = weights.get(ts, default)
            result[ts] = max(0.0, min(1.0, val))
        return result

    def _apply_hierarchical_weights(
        self,
        season_w: Dict[str, float],
        daytype_w: Dict[str, float],
        bracket_w: Dict[str, float],
        default: float = 1.0
    ) -> Dict[str, float]:
        """Apply hierarchical weights (season × daytype × bracket)."""
        # Build lookup dicts with defaults
        s_adj = {s: season_w.get(s, default) for s in self._time_axis["Season"].unique()}
        d_adj = {d: daytype_w.get(d, default) for d in self._time_axis["DayType"].unique()}
        t_adj = {t: bracket_w.get(t, default) for t in self._time_axis["DailyTimeBracket"].unique()}

        result = {}
        for _, row in self._time_axis.drop_duplicates(subset=['TIMESLICE']).iterrows():
            ts = row["TIMESLICE"]
            val = s_adj[row["Season"]] * d_adj[row["DayType"]] * t_adj[row["DailyTimeBracket"]]
            result[ts] = max(0.0, min(1.0, val))

        return result

    # =========================================================================
    # Representation
    # =========================================================================

    def __repr__(self) -> str:
        return (
            f"SupplyComponent(scenario_dir='{self.scenario_dir}', "
            f"technologies={len(self.defined_tech)}, fuels={len(self.defined_fuels)})"
        )
