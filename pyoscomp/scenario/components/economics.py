# pyoscomp/scenario/components/economics.py

"""
Economics component for scenario building in PyPSA-OSeMOSYS Comparison Framework.

This component handles all cost and economic parameters:
- DiscountRate (regional discount rates)
- CapitalCost (CAPEX per technology)
- FixedCost (Fixed O&M per technology)
- VariableCost (Variable O&M per technology/mode)

Prerequisites:
- TimeComponent (years must be defined)
- TopologyComponent (regions must be defined)
- SupplyComponent (technologies must be defined for cost assignment)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Union

from .base import ScenarioComponent


class EconomicsComponent(ScenarioComponent):
    """
    Economics component for cost parameters.

    Handles discount rates and technology cost trajectories including
    capital costs (CAPEX), fixed O&M, and variable O&M.

    Attributes
    ----------
    years : list of int
        Model years (from prerequisites).
    regions : list of str
        Region identifiers (from prerequisites).

    Owned Files
    -----------
    DiscountRate.csv, CapitalCost.csv, FixedCost.csv, VariableCost.csv

    Example
    -------
    Set economic parameters::

        econ = EconomicsComponent(scenario_dir)

        # Regional discount rate
        econ.set_discount_rate('REGION1', 0.05)

        # Technology costs
        econ.set_capital_cost('REGION1', 'GAS_CCGT', {2025: 500, 2030: 450})
        econ.set_fixed_cost('REGION1', 'GAS_CCGT', 10)
        econ.set_variable_cost('REGION1', 'GAS_CCGT', 'MODE1', 2.5)

        econ.save()

    See Also
    --------
    component_mapping.md : Full documentation of economics ownership
    """

    owned_files = [
        'DiscountRate.csv', 'CapitalCost.csv', 'FixedCost.csv', 'VariableCost.csv'
    ]

    def __init__(self, scenario_dir: str):
        """
        Initialize economics component.

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
            require_regions=True
        )
        self.years = prereqs['years']
        self.regions = prereqs['regions']

        # Initialize DataFrames
        self.discount_rate = self.init_dataframe("DiscountRate")
        self.capital_cost = self.init_dataframe("CapitalCost")
        self.fixed_cost = self.init_dataframe("FixedCost")
        self.variable_cost = self.init_dataframe("VariableCost")

    # =========================================================================
    # Load and Save
    # =========================================================================

    def load(self) -> None:
        """
        Load all economics parameter CSV files.

        Raises
        ------
        FileNotFoundError
            If any required file is missing.
        ValueError
            If any file fails schema validation.
        """
        self.discount_rate = self.read_csv("DiscountRate.csv")
        self.capital_cost = self.read_csv("CapitalCost.csv")
        self.fixed_cost = self.read_csv("FixedCost.csv")
        self.variable_cost = self.read_csv("VariableCost.csv")

    def save(self) -> None:
        """
        Save all economics parameter DataFrames to CSV.

        Raises
        ------
        ValueError
            If any DataFrame fails schema validation.
        """
        self._save_sorted("DiscountRate.csv", self.discount_rate,
                          ["REGION", "VALUE"], ["REGION"])
        self._save_sorted("CapitalCost.csv", self.capital_cost,
                          ["REGION", "TECHNOLOGY", "YEAR", "VALUE"],
                          ["REGION", "TECHNOLOGY", "YEAR"])
        self._save_sorted("FixedCost.csv", self.fixed_cost,
                          ["REGION", "TECHNOLOGY", "YEAR", "VALUE"],
                          ["REGION", "TECHNOLOGY", "YEAR"])
        self._save_sorted("VariableCost.csv", self.variable_cost,
                          ["REGION", "TECHNOLOGY", "MODE_OF_OPERATION", "YEAR", "VALUE"],
                          ["REGION", "TECHNOLOGY", "MODE_OF_OPERATION", "YEAR"])

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
    # User Input Methods
    # =========================================================================

    def set_discount_rate(self, region: str, rate: float) -> None:
        """
        Set discount rate for a region.

        Parameters
        ----------
        region : str
            Region identifier.
        rate : float
            Discount rate in [0, 1] (e.g., 0.05 for 5%).

        Raises
        ------
        ValueError
            If region not defined or rate out of bounds.

        Example
        -------
        >>> econ.set_discount_rate('REGION1', 0.05)
        """
        if region not in self.regions:
            raise ValueError(f"Region '{region}' not defined in scenario")
        if not 0 <= rate <= 1:
            raise ValueError(f"Discount rate must be in [0, 1], got {rate}")

        record = [{"REGION": region, "VALUE": rate}]
        self.discount_rate = self.add_to_dataframe(
            self.discount_rate, record, key_columns=["REGION"]
        )

    def set_capital_cost(
        self,
        region: str,
        technology: str,
        cost_trajectory: Union[float, Dict[int, float]],
        interpolation: str = 'step'
    ) -> None:
        """
        Set capital cost (CAPEX) for a technology.

        Parameters
        ----------
        region : str
            Region identifier.
        technology : str
            Technology identifier.
        cost_trajectory : float or dict
            Cost in monetary units per capacity unit.
            If float, applies to all years.
            If dict, {year: cost} with interpolation.
        interpolation : {'step', 'linear'}, default 'step'
            Interpolation method between trajectory points.

        Raises
        ------
        ValueError
            If region not defined or negative costs.

        Example
        -------
        >>> econ.set_capital_cost('REGION1', 'GAS_CCGT', {2025: 500, 2030: 450})
        >>> econ.set_capital_cost('REGION1', 'SOLAR_PV', 300)  # All years
        """
        self._validate_region(region)
        records = self._build_cost_trajectory(
            region, technology, cost_trajectory, interpolation, 'Capital'
        )
        self.capital_cost = self.add_to_dataframe(
            self.capital_cost, records,
            key_columns=["REGION", "TECHNOLOGY", "YEAR"]
        )

    def set_fixed_cost(
        self,
        region: str,
        technology: str,
        cost_trajectory: Union[float, Dict[int, float]],
        interpolation: str = 'step'
    ) -> None:
        """
        Set fixed annual O&M cost for a technology.

        Parameters
        ----------
        region : str
            Region identifier.
        technology : str
            Technology identifier.
        cost_trajectory : float or dict
            Fixed cost in monetary units per capacity unit per year.
        interpolation : {'step', 'linear'}, default 'step'
            Interpolation method.

        Example
        -------
        >>> econ.set_fixed_cost('REGION1', 'GAS_CCGT', 10)
        """
        self._validate_region(region)
        records = self._build_cost_trajectory(
            region, technology, cost_trajectory, interpolation, 'Fixed'
        )
        self.fixed_cost = self.add_to_dataframe(
            self.fixed_cost, records,
            key_columns=["REGION", "TECHNOLOGY", "YEAR"]
        )

    def set_variable_cost(
        self,
        region: str,
        technology: str,
        mode: str,
        cost_trajectory: Union[float, Dict[int, float]],
        interpolation: str = 'step'
    ) -> None:
        """
        Set variable O&M cost for a technology and mode.

        Parameters
        ----------
        region : str
            Region identifier.
        technology : str
            Technology identifier.
        mode : str
            Mode of operation (e.g., 'MODE1').
        cost_trajectory : float or dict
            Variable cost in monetary units per activity unit.
        interpolation : {'step', 'linear'}, default 'step'
            Interpolation method.

        Example
        -------
        >>> econ.set_variable_cost('REGION1', 'GAS_CCGT', 'MODE1', 2.5)
        """
        self._validate_region(region)
        mode = str(mode)  # Ensure string

        records = self._build_cost_trajectory(
            region, technology, cost_trajectory, interpolation, 'Variable',
            mode=mode
        )
        self.variable_cost = self.add_to_dataframe(
            self.variable_cost, records,
            key_columns=["REGION", "TECHNOLOGY", "MODE_OF_OPERATION", "YEAR"]
        )

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _validate_region(self, region: str) -> None:
        """Validate region exists."""
        if region not in self.regions:
            raise ValueError(f"Region '{region}' not defined in scenario")

    def _build_cost_trajectory(
        self,
        region: str,
        technology: str,
        trajectory: Union[float, Dict[int, float]],
        interpolation: str,
        cost_type: str,
        mode: Optional[str] = None
    ) -> List[Dict]:
        """
        Build cost records with interpolation.

        Parameters
        ----------
        region : str
            Region identifier.
        technology : str
            Technology identifier.
        trajectory : float or dict
            Cost trajectory.
        interpolation : str
            Interpolation method.
        cost_type : str
            Cost type for error messages.
        mode : str, optional
            Mode of operation (for variable costs).

        Returns
        -------
        list of dict
            Records ready for DataFrame.
        """
        # Convert single value to dict
        if isinstance(trajectory, (int, float)):
            trajectory = {self.years[0]: trajectory}

        # Validate non-negative
        for y, cost in trajectory.items():
            if cost < 0:
                raise ValueError(
                    f"{cost_type} cost cannot be negative: {cost} for "
                    f"{technology} in year {y}"
                )

        # Interpolate to all years
        sorted_years = sorted(trajectory.keys())
        records = []

        for y in self.years:
            cost = self._interpolate_value(y, trajectory, sorted_years, interpolation)
            record = {
                "REGION": region,
                "TECHNOLOGY": technology,
                "YEAR": y,
                "VALUE": cost
            }
            if mode is not None:
                record["MODE_OF_OPERATION"] = mode
            records.append(record)

        return records

    def _interpolate_value(
        self,
        year: int,
        trajectory: Dict[int, float],
        sorted_years: List[int],
        method: str
    ) -> float:
        """Interpolate value for a single year."""
        first_yr, last_yr = sorted_years[0], sorted_years[-1]

        # Before first point
        if year < first_yr:
            return trajectory[first_yr]

        # After last point
        if year > last_yr:
            return trajectory[last_yr]

        # Exact match
        if year in trajectory:
            return trajectory[year]

        # Between points
        for i in range(len(sorted_years) - 1):
            y_start, y_end = sorted_years[i], sorted_years[i + 1]
            if y_start <= year < y_end:
                v_start, v_end = trajectory[y_start], trajectory[y_end]
                if method == 'linear':
                    ratio = (year - y_start) / (y_end - y_start)
                    return v_start + ratio * (v_end - v_start)
                else:
                    return v_start

        return trajectory[last_yr]

    # =========================================================================
    # Representation
    # =========================================================================

    def __repr__(self) -> str:
        n_tech = len(self.capital_cost['TECHNOLOGY'].unique()) if not self.capital_cost.empty else 0
        return f"EconomicsComponent(scenario_dir='{self.scenario_dir}', technologies_costed={n_tech})"
