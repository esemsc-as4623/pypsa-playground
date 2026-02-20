# pyoscomp/scenario/components/supply.py

"""
Supply component for scenario building in PyPSA-OSeMOSYS Comparison Framework.

This component handles the technology registry and supply-side definitions:
- TECHNOLOGY set (technology identifiers)
- FUEL set (auto-generated from technology fuel assignments)
- MODE_OF_OPERATION set (auto-generated from technology mode assignments)
- OperationalLife (asset lifetime per technology)
- ResidualCapacity (existing/legacy capacity trajectory)

OSeMOSYS Terminology: TECHNOLOGY, FUEL, MODE_OF_OPERATION, OperationalLife
PyPSA Terminology: Generator (carrier, lifetime, p_nom)

Prerequisites:
- TimeComponent (years must be defined)
- TopologyComponent (regions must be defined)

See Also
--------
PerformanceComponent : Owns HOW technologies operate (efficiency, factors,
    capacity limits). Should be initialized after SupplyComponent.
"""

from __future__ import annotations

import json
import os
import numpy as np
import pandas as pd
from typing import Dict, List, Set, Tuple, Union

from .base import ScenarioComponent


class TechnologyBuilder:
    """
    Fluent builder for defining a technology in the supply registry.

    Returned by ``SupplyComponent.add_technology()`` to enable method
    chaining for common technology attributes.

    Parameters
    ----------
    supply : SupplyComponent
        Parent supply component that owns this builder.
    region : str
        Region identifier for the technology.
    technology : str
        Technology identifier.

    Example
    -------
    Fluent definition of a conversion technology::

        supply.add_technology('REGION1', 'GAS_CCGT') \\
            .with_operational_life(30) \\
            .with_residual_capacity({2026: 0}) \\
            .as_conversion(input_fuel='GAS', output_fuel='ELEC')

    See Also
    --------
    SupplyComponent.add_technology : Entry point that creates a builder.
    """

    def __init__(
        self,
        supply: 'SupplyComponent',
        region: str,
        technology: str
    ):
        self._supply = supply
        self._region = region
        self._technology = technology

    def with_operational_life(self, years: int) -> 'TechnologyBuilder':
        """
        Set the operational lifetime of the technology.

        Parameters
        ----------
        years : int
            Operational lifetime in years (must be positive).

        Returns
        -------
        TechnologyBuilder
            Self for method chaining.

        Raises
        ------
        ValueError
            If years <= 0.
        """
        if years <= 0:
            raise ValueError(
                f"Operational life must be positive, got {years}"
            )
        record = [{
            "REGION": self._region,
            "TECHNOLOGY": self._technology,
            "VALUE": years,
        }]
        self._supply.operational_life = self._supply.add_to_dataframe(
            self._supply.operational_life, record,
            key_columns=["REGION", "TECHNOLOGY"],
        )
        return self

    def with_residual_capacity(
        self,
        trajectory: Union[float, Dict[int, float]],
        interpolation: str = 'step'
    ) -> 'TechnologyBuilder':
        """
        Set existing/legacy capacity over model years.

        Parameters
        ----------
        trajectory : float or dict
            If float, applies as constant across all model years.
            If dict, {year: capacity_MW} with interpolation between
            points.
        interpolation : {'step', 'linear'}, default 'step'
            Method for years between trajectory points.

        Returns
        -------
        TechnologyBuilder
            Self for method chaining.

        Raises
        ------
        ValueError
            If trajectory contains negative values.
        """
        if isinstance(trajectory, (int, float)):
            trajectory = {self._supply.years[0]: float(trajectory)}

        for y, val in trajectory.items():
            if val < 0:
                raise ValueError(
                    f"Negative capacity {val} in year {y}"
                )

        records = self._supply._interpolate_trajectory(
            {"REGION": self._region, "TECHNOLOGY": self._technology},
            trajectory, interpolation,
        )
        self._supply.residual_capacity = self._supply.add_to_dataframe(
            self._supply.residual_capacity, records,
            key_columns=["REGION", "TECHNOLOGY", "YEAR"],
        )
        return self

    def as_conversion(
        self,
        input_fuel: str,
        output_fuel: str,
        mode: str = 'MODE1'
    ) -> 'TechnologyBuilder':
        """
        Register technology as a conversion type (input -> output).

        Records the fuel and mode associations in the supply registry.
        Actual efficiency values are set via PerformanceComponent.

        Parameters
        ----------
        input_fuel : str
            Fuel consumed by the technology.
        output_fuel : str
            Fuel produced by the technology.
        mode : str, default 'MODE1'
            Mode of operation identifier.

        Returns
        -------
        TechnologyBuilder
            Self for method chaining.

        Raises
        ------
        ValueError
            If input_fuel and output_fuel are the same.
        """
        if input_fuel == output_fuel:
            raise ValueError(
                "Input and output fuels must be different"
            )
        self._supply.defined_fuels.update([input_fuel, output_fuel])
        self._supply._register_mode(
            self._region, self._technology, mode
        )
        key = (self._region, self._technology, mode)
        self._supply._fuel_assignments[key] = {
            'input': input_fuel,
            'output': output_fuel,
        }
        return self

    def as_resource(
        self,
        output_fuel: str,
        mode: str = 'MODE1'
    ) -> 'TechnologyBuilder':
        """
        Register technology as a resource/extraction type (no input).

        Used for renewables (wind, solar), primary extraction, etc.

        Parameters
        ----------
        output_fuel : str
            Fuel produced by the technology.
        mode : str, default 'MODE1'
            Mode of operation identifier.

        Returns
        -------
        TechnologyBuilder
            Self for method chaining.
        """
        self._supply.defined_fuels.add(output_fuel)
        self._supply._register_mode(
            self._region, self._technology, mode
        )
        key = (self._region, self._technology, mode)
        self._supply._fuel_assignments[key] = {
            'input': None,
            'output': output_fuel,
        }
        return self

    def as_multimode(
        self,
        modes_config: Dict[str, Dict]
    ) -> 'TechnologyBuilder':
        """
        Register technology with multiple operating modes.

        Parameters
        ----------
        modes_config : dict
            Configuration per mode::

                {mode_name: {
                    'inputs': {fuel: ...},
                    'outputs': {fuel: ...},
                }}

            Only fuel names are recorded here. Ratio values are set
            via ``PerformanceComponent.set_multimode_ratios()``.

        Returns
        -------
        TechnologyBuilder
            Self for method chaining.

        Raises
        ------
        ValueError
            If modes_config is not a dict or a mode lacks outputs.
        """
        if not isinstance(modes_config, dict):
            raise ValueError("modes_config must be a dictionary")

        for mode, config in modes_config.items():
            if 'outputs' not in config or not config['outputs']:
                raise ValueError(
                    f"Mode '{mode}' must specify at least one output"
                )
            inputs = config.get('inputs', {})
            outputs = config.get('outputs', {})

            self._supply.defined_fuels.update(inputs.keys())
            self._supply.defined_fuels.update(outputs.keys())
            self._supply._register_mode(
                self._region, self._technology, mode
            )

            key = (self._region, self._technology, mode)
            self._supply._fuel_assignments[key] = {
                'input_fuels': list(inputs.keys()),
                'output_fuels': list(outputs.keys()),
            }
        return self


class SupplyComponent(ScenarioComponent):
    """
    Supply component for the technology registry.

    Defines WHAT technologies exist, their fuel/mode associations,
    operational lifetimes, and residual capacities. Performance
    characteristics (efficiency, factors, limits) are owned by
    ``PerformanceComponent``.

    Attributes
    ----------
    years : list of int
        Model years (from prerequisites).
    regions : list of str
        Region identifiers (from prerequisites).
    defined_tech : set of tuple(str, str)
        Set of (region, technology) pairs.
    defined_fuels : set of str
        Set of fuel identifiers referenced in technology definitions.

    Owned Files
    -----------
    TECHNOLOGY.csv, FUEL.csv, MODE_OF_OPERATION.csv,
    OperationalLife.csv, ResidualCapacity.csv

    Example
    -------
    Define technologies with a fluent builder API::

        supply = SupplyComponent(scenario_dir)

        supply.add_technology('REGION1', 'GAS_CCGT') \\
            .with_operational_life(30) \\
            .with_residual_capacity({2026: 0}) \\
            .as_conversion(input_fuel='GAS', output_fuel='ELEC')

        supply.add_technology('REGION1', 'SOLAR_PV') \\
            .with_operational_life(25) \\
            .as_resource(output_fuel='ELEC')

        supply.save()

    See Also
    --------
    PerformanceComponent : Owns HOW technologies operate.
    TechnologyBuilder : Fluent builder returned by add_technology().
    """

    owned_files = [
        'TECHNOLOGY.csv', 'FUEL.csv', 'MODE_OF_OPERATION.csv',
        'OperationalLife.csv', 'ResidualCapacity.csv',
    ]

    def __init__(self, scenario_dir: str):
        """
        Initialize supply component.

        Parameters
        ----------
        scenario_dir : str
            Path to the scenario directory.

        Raises
        ------
        ValueError
            If TimeComponent or TopologyComponent prerequisites not met.
        """
        super().__init__(scenario_dir)

        # Check prerequisites
        prereqs = self.check_prerequisites(
            require_years=True,
            require_regions=True,
        )
        self.years = prereqs['years']
        self.regions = prereqs['regions']

        # Supply-owned DataFrames
        self.operational_life = self.init_dataframe("OperationalLife")
        self.residual_capacity = self.init_dataframe("ResidualCapacity")

        # Tracking
        self.defined_tech: Set[Tuple[str, str]] = set()
        self.defined_fuels: Set[str] = set()
        self._mode_definitions: Dict[Tuple[str, str], List[str]] = {}
        self._fuel_assignments: Dict[Tuple, Dict] = {}

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def technologies(self) -> List[str]:
        """Get sorted list of unique technology identifiers."""
        return sorted({tech for _, tech in self.defined_tech})

    @property
    def fuels(self) -> List[str]:
        """Get sorted list of defined fuel identifiers."""
        return sorted(self.defined_fuels)

    @property
    def modes(self) -> Set[str]:
        """
        Get set of all modes across all technologies.

        Returns
        -------
        set of str
            Mode identifiers. Defaults to {'MODE1'} if none defined.
        """
        all_modes = set()
        for modes in self._mode_definitions.values():
            all_modes.update(modes)
        return all_modes if all_modes else {'MODE1'}

    @property
    def fuel_assignments(self) -> Dict[Tuple, Dict]:
        """
        Get fuel assignments per (region, technology, mode).

        Returns
        -------
        dict
            Mapping of (region, technology, mode) to fuel info.
        """
        return dict(self._fuel_assignments)

    # =========================================================================
    # Load and Save
    # =========================================================================

    def load(self) -> None:
        """
        Load supply-owned parameter CSV files.

        Rebuilds tracking sets from saved data.

        Raises
        ------
        FileNotFoundError
            If any required file is missing.
        ValueError
            If any file fails schema validation.
        """
        self.operational_life = self.read_csv("OperationalLife.csv")
        self.residual_capacity = self.read_csv("ResidualCapacity.csv")

        # Rebuild tracking from loaded data
        self._rebuild_tracking()

    def save(self) -> None:
        """
        Save supply-owned DataFrames to CSV.

        Generates TECHNOLOGY.csv, FUEL.csv, MODE_OF_OPERATION.csv sets
        and saves OperationalLife.csv, ResidualCapacity.csv parameters.

        Raises
        ------
        ValueError
            If any DataFrame fails schema validation.
        """
        # 1. Generate set CSVs
        tech_df = pd.DataFrame({"VALUE": self.technologies})
        fuel_df = pd.DataFrame({"VALUE": self.fuels})
        mode_df = pd.DataFrame({"VALUE": sorted(self.modes)})

        self.write_dataframe("TECHNOLOGY.csv", tech_df)
        self.write_dataframe("FUEL.csv", fuel_df)
        self.write_dataframe("MODE_OF_OPERATION.csv", mode_df)

        # 2. Save parameter CSVs
        self._save_sorted(
            "OperationalLife.csv", self.operational_life,
            ["REGION", "TECHNOLOGY", "VALUE"],
            ["REGION", "TECHNOLOGY"],
        )
        self._save_sorted(
            "ResidualCapacity.csv", self.residual_capacity,
            ["REGION", "TECHNOLOGY", "YEAR", "VALUE"],
            ["REGION", "TECHNOLOGY", "YEAR"],
        )

        # 3. Serialize fuel assignments for PerformanceComponent
        fa_serializable = {
            f"{r}|{t}|{m}": info
            for (r, t, m), info in self._fuel_assignments.items()
        }
        fa_path = os.path.join(
            self.scenario_dir, "_fuel_assignments.json"
        )
        with open(fa_path, 'w') as f:
            json.dump(fa_serializable, f, indent=2)

    # =========================================================================
    # User Input: Technology Registration
    # =========================================================================

    def add_technology(
        self,
        region: str,
        technology: str
    ) -> TechnologyBuilder:
        """
        Register a new technology and return a builder for chaining.

        This is the entry point for defining any supply technology.
        Use the returned ``TechnologyBuilder`` to set operational life,
        residual capacity, and fuel/mode associations.

        Parameters
        ----------
        region : str
            Region identifier (must exist in topology).
        technology : str
            Technology identifier (e.g., 'GAS_CCGT', 'SOLAR_PV').

        Returns
        -------
        TechnologyBuilder
            Fluent builder for chaining configuration methods.

        Raises
        ------
        ValueError
            If region is not defined in the topology.

        Example
        -------
        >>> builder = supply.add_technology('REGION1', 'GAS_CCGT')
        >>> builder.with_operational_life(30).as_conversion(
        ...     input_fuel='GAS', output_fuel='ELEC')
        """
        if region not in self.regions:
            raise ValueError(
                f"Region '{region}' not defined. "
                "Initialize topology first."
            )
        self.defined_tech.add((region, technology))
        return TechnologyBuilder(self, region, technology)

    # =========================================================================
    # Validation
    # =========================================================================

    def validate(self) -> None:
        """
        Validate supply component state.

        Checks:
        - All registered technologies have an operational life.
        - No negative residual capacities.

        Raises
        ------
        ValueError
            If validation fails.
        """
        errors = []

        # Check operational life for all registered technologies
        for region, tech in self.defined_tech:
            if not self.operational_life.empty:
                match = (
                    (self.operational_life['REGION'] == region)
                    & (self.operational_life['TECHNOLOGY'] == tech)
                )
                if not match.any():
                    errors.append(
                        f"Technology '{tech}' in '{region}' "
                        "has no operational life defined"
                    )
            else:
                errors.append(
                    f"Technology '{tech}' in '{region}' "
                    "has no operational life defined"
                )

        # Check residual capacities non-negative
        if not self.residual_capacity.empty:
            neg = self.residual_capacity[
                self.residual_capacity['VALUE'] < 0
            ]
            for _, row in neg.iterrows():
                errors.append(
                    f"Negative residual capacity {row['VALUE']} for "
                    f"'{row['TECHNOLOGY']}' in '{row['REGION']}' "
                    f"year {row['YEAR']}"
                )

        if errors:
            raise ValueError(
                "Supply validation failed:\n"
                + "\n".join(f"  - {e}" for e in errors)
            )

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _register_mode(
        self, region: str, technology: str, mode: str
    ) -> None:
        """Register a mode for a technology."""
        key = (region, technology)
        if key not in self._mode_definitions:
            self._mode_definitions[key] = []
        if mode not in self._mode_definitions[key]:
            self._mode_definitions[key].append(mode)

    def _rebuild_tracking(self) -> None:
        """Rebuild tracking sets from loaded DataFrames."""
        # Rebuild defined_tech from operational_life
        if not self.operational_life.empty:
            self.defined_tech = set(
                zip(
                    self.operational_life['REGION'],
                    self.operational_life['TECHNOLOGY'],
                )
            )
        else:
            self.defined_tech = set()

        # Rebuild fuels from FUEL.csv if it exists
        fuel_df = self.read_csv("FUEL.csv", optional=True)
        if fuel_df is not None and not fuel_df.empty:
            self.defined_fuels = set(fuel_df['VALUE'].tolist())

        # Rebuild modes from MODE_OF_OPERATION.csv if it exists
        mode_df = self.read_csv(
            "MODE_OF_OPERATION.csv", optional=True
        )
        if mode_df is not None and not mode_df.empty:
            modes = mode_df['VALUE'].tolist()
            for region, tech in self.defined_tech:
                self._mode_definitions[(region, tech)] = modes

    def _interpolate_trajectory(
        self,
        base_record: Dict,
        trajectory: Dict[int, float],
        method: str
    ) -> List[Dict]:
        """
        Interpolate trajectory to all model years.

        Parameters
        ----------
        base_record : dict
            Base record fields (e.g., REGION, TECHNOLOGY).
        trajectory : dict
            Known points {year: value}.
        method : {'step', 'linear'}
            Interpolation method.

        Returns
        -------
        list of dict
            Records for all model years.
        """
        records = []
        sorted_years = sorted(trajectory.keys())
        first_yr, last_yr = sorted_years[0], sorted_years[-1]

        # Before first point
        for y in [yr for yr in self.years if yr < first_yr]:
            records.append(
                {**base_record, "YEAR": y,
                 "VALUE": trajectory[first_yr]}
            )

        # Between points
        for i in range(len(sorted_years) - 1):
            y_start = sorted_years[i]
            y_end = sorted_years[i + 1]
            v_start = trajectory[y_start]
            v_end = trajectory[y_end]
            years_to_fill = [
                yr for yr in self.years
                if y_start <= yr < y_end
            ]

            if method == 'linear':
                values = np.linspace(
                    v_start, v_end, len(years_to_fill) + 1
                )[:-1]
            else:
                values = [v_start] * len(years_to_fill)

            for yr, val in zip(years_to_fill, values):
                records.append(
                    {**base_record, "YEAR": yr, "VALUE": val}
                )

        # Last point
        if last_yr in self.years:
            records.append(
                {**base_record, "YEAR": last_yr,
                 "VALUE": trajectory[last_yr]}
            )

        # After last point
        for y in [yr for yr in self.years if yr > last_yr]:
            records.append(
                {**base_record, "YEAR": y,
                 "VALUE": max(0, trajectory[last_yr])}
            )

        return records

    # =========================================================================
    # Representation
    # =========================================================================

    def __repr__(self) -> str:
        return (
            f"SupplyComponent(scenario_dir='{self.scenario_dir}', "
            f"technologies={len(self.defined_tech)}, "
            f"fuels={len(self.defined_fuels)})"
        )
