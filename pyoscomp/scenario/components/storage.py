# pyoscomp/scenario/components/storage.py

"""
Storage component for scenario building in PyPSA-OSeMOSYS Comparison Framework.

This component handles storage facility definitions:
- STORAGE set (storage identifiers)
- TechnologyToStorage / TechnologyFromStorage (charge and discharge technology links)
- CapitalCostStorage, OperationalLifeStorage, ResidualStorageCapacity, MinStorageCharge
- StorageEnergyRatio (non-standard: max_hours for PyPSA, ignored by otoole)

OSeMOSYS models storage as a triplet:
    charge_technology → storage_facility → discharge_technology

PyPSA models storage as a single StorageUnit. The translation combines
costs into one component (total NPV preserved, cost attribution collapsed).

Prerequisites:
- TimeComponent (years must be defined)
- TopologyComponent (regions must be defined)
- SupplyComponent (charge/discharge technologies must be registered there)

See Also
--------
SupplyComponent : Owns charge and discharge technologies (CAPEX, efficiency, lifetime)
"""

from __future__ import annotations

import pandas as pd
from typing import Dict, List, Optional, Set, Tuple, Union

from .base import ScenarioComponent


class StorageBuilder:
    """
    Fluent builder for defining a storage facility.

    Returned by ``StorageComponent.add_storage()`` to enable method
    chaining for common storage attributes.

    Parameters
    ----------
    storage : StorageComponent
        Parent storage component.
    region : str
        Region identifier.
    storage_name : str
        Storage facility identifier (e.g. 'BATT_STOR').

    Example
    -------
    ::

        storage.add_storage('OFFSHORE_HUB', 'BATT_STOR') \\
            .with_operational_life(20) \\
            .with_energy_ratio(4.0) \\
            .with_capital_cost_storage({2025: 150_000}) \\
            .with_min_charge(0.1) \\
            .with_charge_technology('BATT_CHARGE', mode='MODE1') \\
            .with_discharge_technology('BATT_DISCHARGE', mode='MODE1') \\
            .with_residual_capacity({2025: 0.0})
    """

    def __init__(self, storage: 'StorageComponent', region: str, storage_name: str):
        self._storage = storage
        self._region = region
        self._name = storage_name

    def with_operational_life(self, years: int) -> 'StorageBuilder':
        """
        Set the operational lifetime of the storage facility.

        Parameters
        ----------
        years : int
            Operational lifetime in years (must be positive).

        Returns
        -------
        StorageBuilder
        """
        if years <= 0:
            raise ValueError(f"Operational life must be positive, got {years}")
        record = [{"REGION": self._region, "STORAGE": self._name, "VALUE": years}]
        self._storage.operational_life_storage = self._storage.add_to_dataframe(
            self._storage.operational_life_storage, record,
            key_columns=["REGION", "STORAGE"],
        )
        return self

    def with_energy_ratio(self, max_hours: float) -> 'StorageBuilder':
        """
        Set the energy-to-power ratio (max_hours = MWh per MW of discharge capacity).

        This is stored in the non-standard StorageEnergyRatio.csv, which otoole
        ignores but the PyPSA translator reads to configure ``StorageUnit.max_hours``.

        Parameters
        ----------
        max_hours : float
            Energy capacity in hours of discharge at full power (must be positive).

        Returns
        -------
        StorageBuilder
        """
        if max_hours <= 0:
            raise ValueError(f"energy_ratio (max_hours) must be positive, got {max_hours}")
        record = [{"REGION": self._region, "STORAGE": self._name, "VALUE": max_hours}]
        self._storage.energy_ratio = self._storage.add_to_dataframe(
            self._storage.energy_ratio, record,
            key_columns=["REGION", "STORAGE"],
        )
        return self

    def with_capital_cost_storage(
        self,
        trajectory: Union[float, Dict[int, float]],
        interpolation: str = 'step',
    ) -> 'StorageBuilder':
        """
        Set the capital cost of storage energy capacity (cost per MWh).

        Parameters
        ----------
        trajectory : float or dict
            If float, applies as constant across all model years.
            If dict, {year: cost_per_MWh} with interpolation between points.
        interpolation : {'step', 'linear'}, default 'step'

        Returns
        -------
        StorageBuilder
        """
        if isinstance(trajectory, (int, float)):
            trajectory = {self._storage.years[0]: float(trajectory)}

        for y, val in trajectory.items():
            if val < 0:
                raise ValueError(f"CapitalCostStorage cannot be negative, got {val} in year {y}")

        records = _interpolate_storage_trajectory(
            self._region, self._name, trajectory, self._storage.years, interpolation
        )
        self._storage.capital_cost_storage = self._storage.add_to_dataframe(
            self._storage.capital_cost_storage, records,
            key_columns=["REGION", "STORAGE", "YEAR"],
        )
        return self

    def with_min_charge(
        self,
        trajectory: Union[float, Dict[int, float]],
        interpolation: str = 'step',
    ) -> 'StorageBuilder':
        """
        Set the minimum state of charge (fraction of total capacity).

        Parameters
        ----------
        trajectory : float or dict
            Minimum charge fraction in [0, 1].
        interpolation : {'step', 'linear'}, default 'step'

        Returns
        -------
        StorageBuilder
        """
        if isinstance(trajectory, (int, float)):
            trajectory = {self._storage.years[0]: float(trajectory)}

        for y, val in trajectory.items():
            if not (0.0 <= val <= 1.0):
                raise ValueError(
                    f"MinStorageCharge must be in [0, 1], got {val} in year {y}"
                )

        records = _interpolate_storage_trajectory(
            self._region, self._name, trajectory, self._storage.years, interpolation
        )
        self._storage.min_storage_charge = self._storage.add_to_dataframe(
            self._storage.min_storage_charge, records,
            key_columns=["REGION", "STORAGE", "YEAR"],
        )
        return self

    def with_residual_capacity(
        self,
        trajectory: Union[float, Dict[int, float]],
        interpolation: str = 'step',
    ) -> 'StorageBuilder':
        """
        Set pre-installed storage energy capacity (MWh).

        Parameters
        ----------
        trajectory : float or dict
            Existing energy capacity in MWh.
        interpolation : {'step', 'linear'}, default 'step'

        Returns
        -------
        StorageBuilder
        """
        if isinstance(trajectory, (int, float)):
            trajectory = {self._storage.years[0]: float(trajectory)}

        for y, val in trajectory.items():
            if val < 0:
                raise ValueError(f"ResidualStorageCapacity cannot be negative, got {val} in year {y}")

        records = _interpolate_storage_trajectory(
            self._region, self._name, trajectory, self._storage.years, interpolation
        )
        self._storage.residual_storage_capacity = self._storage.add_to_dataframe(
            self._storage.residual_storage_capacity, records,
            key_columns=["REGION", "STORAGE", "YEAR"],
        )
        return self

    def with_charge_technology(
        self, technology: str, mode: str = 'MODE1'
    ) -> 'StorageBuilder':
        """
        Link a charge technology to this storage (TechnologyToStorage).

        Parameters
        ----------
        technology : str
            Technology identifier that charges the storage.
        mode : str, default 'MODE1'
            Mode of operation.

        Returns
        -------
        StorageBuilder
        """
        record = [{
            "REGION": self._region,
            "TECHNOLOGY": technology,
            "STORAGE": self._name,
            "MODE_OF_OPERATION": mode,
            "VALUE": 1,
        }]
        self._storage.technology_to_storage = self._storage.add_to_dataframe(
            self._storage.technology_to_storage, record,
            key_columns=["REGION", "TECHNOLOGY", "STORAGE", "MODE_OF_OPERATION"],
        )
        self._storage._charge_techs.add((self._region, technology))
        return self

    def with_discharge_technology(
        self, technology: str, mode: str = 'MODE1'
    ) -> 'StorageBuilder':
        """
        Link a discharge technology to this storage (TechnologyFromStorage).

        Parameters
        ----------
        technology : str
            Technology identifier that discharges the storage.
        mode : str, default 'MODE1'
            Mode of operation.

        Returns
        -------
        StorageBuilder
        """
        record = [{
            "REGION": self._region,
            "TECHNOLOGY": technology,
            "STORAGE": self._name,
            "MODE_OF_OPERATION": mode,
            "VALUE": 1,
        }]
        self._storage.technology_from_storage = self._storage.add_to_dataframe(
            self._storage.technology_from_storage, record,
            key_columns=["REGION", "TECHNOLOGY", "STORAGE", "MODE_OF_OPERATION"],
        )
        self._storage._discharge_techs.add((self._region, technology))
        return self


def _interpolate_storage_trajectory(
    region: str,
    storage: str,
    trajectory: Dict[int, float],
    years: List[int],
    method: str = 'step',
) -> List[dict]:
    """Interpolate a storage cost/capacity trajectory across model years."""
    sorted_points = sorted(trajectory.items())
    records = []
    for year in sorted(years):
        if year in trajectory:
            val = trajectory[year]
        elif method == 'linear' and len(sorted_points) >= 2:
            # Linear interpolation/extrapolation
            xs = [p[0] for p in sorted_points]
            ys = [p[1] for p in sorted_points]
            if year < xs[0]:
                val = ys[0]
            elif year > xs[-1]:
                val = ys[-1]
            else:
                for i in range(len(xs) - 1):
                    if xs[i] <= year <= xs[i + 1]:
                        t = (year - xs[i]) / (xs[i + 1] - xs[i])
                        val = ys[i] + t * (ys[i + 1] - ys[i])
                        break
        else:
            # Step: use last value at or before year
            val = sorted_points[0][1]
            for point_year, point_val in sorted_points:
                if point_year <= year:
                    val = point_val
        records.append({"REGION": region, "STORAGE": storage, "YEAR": year, "VALUE": val})
    return records


class StorageComponent(ScenarioComponent):
    """
    Storage component for storage facility definitions.

    Handles the OSeMOSYS storage triplet (charge tech → storage → discharge tech)
    and the non-standard StorageEnergyRatio parameter used by the PyPSA translator.

    Attributes
    ----------
    years : list of int
        Model years (from prerequisites).
    regions : list of str
        Region identifiers (from prerequisites).

    Owned Files
    -----------
    STORAGE.csv, TechnologyToStorage.csv, TechnologyFromStorage.csv,
    CapitalCostStorage.csv, OperationalLifeStorage.csv,
    ResidualStorageCapacity.csv, MinStorageCharge.csv,
    StorageEnergyRatio.csv

    Example
    -------
    ::

        storage = StorageComponent(scenario_dir)

        storage.add_storage('OFFSHORE_HUB', 'BATT_STOR') \\
            .with_operational_life(20) \\
            .with_energy_ratio(4.0) \\
            .with_capital_cost_storage({2025: 150_000}) \\
            .with_min_charge(0.1) \\
            .with_charge_technology('BATT_CHARGE', mode='MODE1') \\
            .with_discharge_technology('BATT_DISCHARGE', mode='MODE1') \\
            .with_residual_capacity({2025: 0.0})

        storage.save()

    Notes
    -----
    StorageEnergyRatio.csv is non-standard (not in OSeMOSYS_config.yaml).
    otoole will ignore it; the PyPSA translator reads it directly.
    """

    owned_files = [
        'STORAGE.csv',
        'TechnologyToStorage.csv',
        'TechnologyFromStorage.csv',
        'CapitalCostStorage.csv',
        'OperationalLifeStorage.csv',
        'ResidualStorageCapacity.csv',
        'MinStorageCharge.csv',
        'StorageEnergyRatio.csv',
    ]

    def __init__(self, scenario_dir: str):
        super().__init__(scenario_dir)

        prereqs = self.check_prerequisites(
            require_years=True,
            require_regions=True,
        )
        self.years = prereqs['years']
        self.regions = prereqs['regions']

        # Storage-owned DataFrames (OSeMOSYS-standard ones use schema)
        self.storage_df = self.init_dataframe("STORAGE")
        self.technology_to_storage = self.init_dataframe("TechnologyToStorage")
        self.technology_from_storage = self.init_dataframe("TechnologyFromStorage")
        self.capital_cost_storage = self.init_dataframe("CapitalCostStorage")
        self.operational_life_storage = self.init_dataframe("OperationalLifeStorage")
        self.residual_storage_capacity = self.init_dataframe("ResidualStorageCapacity")
        self.min_storage_charge = self.init_dataframe("MinStorageCharge")
        # Non-standard: not in OSeMOSYS schema; used by PyPSA translator for max_hours
        self.energy_ratio = pd.DataFrame(columns=["REGION", "STORAGE", "VALUE"])

        # Tracking
        self.defined_storages: Set[Tuple[str, str]] = set()  # (region, storage_name)
        self._charge_techs: Set[Tuple[str, str]] = set()
        self._discharge_techs: Set[Tuple[str, str]] = set()

    @property
    def storages(self) -> List[str]:
        """Sorted list of unique storage identifiers."""
        return sorted({s for _, s in self.defined_storages})

    def add_storage(self, region: str, storage_name: str) -> StorageBuilder:
        """
        Register a new storage facility and return a builder for configuration.

        Parameters
        ----------
        region : str
            Region identifier (must exist in topology).
        storage_name : str
            Storage facility identifier (e.g. 'BATT_STOR').

        Returns
        -------
        StorageBuilder
            Fluent builder for configuring this storage.

        Raises
        ------
        ValueError
            If region not in model regions.
        """
        if region not in self.regions:
            raise ValueError(
                f"Region '{region}' not in model regions: {self.regions}"
            )
        self.defined_storages.add((region, storage_name))
        record = [{"VALUE": storage_name}]
        self.storage_df = self.add_to_dataframe(
            self.storage_df, record, key_columns=["VALUE"]
        )
        return StorageBuilder(self, region, storage_name)

    def validate(self) -> None:
        """
        Validate storage definitions for internal consistency.

        Checks:
        - Each storage has at most one charge and one discharge technology
        - energy_ratio is positive where defined
        - min_storage_charge is in [0, 1]

        Raises
        ------
        ValueError
            If validation fails.
        """
        if not self.technology_to_storage.empty:
            # Check each storage has at most one charge tech per region/mode
            grouped = self.technology_to_storage.groupby(
                ["REGION", "STORAGE", "MODE_OF_OPERATION"]
            )["TECHNOLOGY"].nunique()
            multi = grouped[grouped > 1]
            if not multi.empty:
                raise ValueError(
                    f"Each storage can have at most one charge technology per "
                    f"region/mode. Multiple found: {multi.to_dict()}"
                )

        if not self.energy_ratio.empty:
            if (self.energy_ratio["VALUE"] <= 0).any():
                raise ValueError("StorageEnergyRatio must be positive")

        if not self.min_storage_charge.empty:
            vals = self.min_storage_charge["VALUE"]
            if (vals < 0).any() or (vals > 1).any():
                raise ValueError("MinStorageCharge must be in [0, 1]")

    def save(self) -> None:
        """Write all storage CSVs to the scenario directory."""
        self.validate()
        path = self.scenario_dir

        self._save_csv(self.storage_df, "STORAGE")
        self._save_csv(self.technology_to_storage, "TechnologyToStorage")
        self._save_csv(self.technology_from_storage, "TechnologyFromStorage")
        self._save_csv(self.capital_cost_storage, "CapitalCostStorage")
        self._save_csv(self.operational_life_storage, "OperationalLifeStorage")
        self._save_csv(self.residual_storage_capacity, "ResidualStorageCapacity")
        self._save_csv(self.min_storage_charge, "MinStorageCharge")
        self._save_csv(self.energy_ratio, "StorageEnergyRatio")

    def load(self) -> None:
        """Load all storage CSVs from the scenario directory."""
        self.storage_df = self._load_csv_or_empty("STORAGE")
        self.technology_to_storage = self._load_csv_or_empty("TechnologyToStorage")
        self.technology_from_storage = self._load_csv_or_empty("TechnologyFromStorage")
        self.capital_cost_storage = self._load_csv_or_empty("CapitalCostStorage")
        self.operational_life_storage = self._load_csv_or_empty("OperationalLifeStorage")
        self.residual_storage_capacity = self._load_csv_or_empty("ResidualStorageCapacity")
        self.min_storage_charge = self._load_csv_or_empty("MinStorageCharge")
        self.energy_ratio = self._load_csv_or_empty("StorageEnergyRatio")

        # Rebuild tracking sets from loaded data
        if not self.storage_df.empty and "VALUE" in self.storage_df.columns:
            # Storage is region-agnostic in STORAGE.csv, so we can't recover region
            # tracking — only storage names
            for s in self.storage_df["VALUE"].tolist():
                for r in self.regions:
                    self.defined_storages.add((r, s))

        if not self.technology_to_storage.empty:
            for _, row in self.technology_to_storage.iterrows():
                self._charge_techs.add((row["REGION"], row["TECHNOLOGY"]))

        if not self.technology_from_storage.empty:
            for _, row in self.technology_from_storage.iterrows():
                self._discharge_techs.add((row["REGION"], row["TECHNOLOGY"]))

    def _save_csv(self, df: pd.DataFrame, name: str) -> None:
        """Save a DataFrame to CSV if non-empty."""
        import os
        if df is not None and not df.empty:
            filepath = os.path.join(self.scenario_dir, f"{name}.csv")
            df.to_csv(filepath, index=False)

    def _load_csv_or_empty(self, name: str) -> pd.DataFrame:
        """Load a CSV if it exists, otherwise return empty DataFrame."""
        import os
        filepath = os.path.join(self.scenario_dir, f"{name}.csv")
        if os.path.exists(filepath):
            return pd.read_csv(filepath)
        return pd.DataFrame()
