# pyoscomp/scenario/components/performance.py

"""
Performance component for technology operational characteristics.

This component owns all technology performance parameters:
- OperationalLife (asset lifetime)
- CapacityToActivityUnit (capacity-to-activity conversion factor)
- InputActivityRatio (input fuel requirements / efficiency)
- OutputActivityRatio (output production per unit activity)
- CapacityFactor (sub-annual capacity availability per timeslice)
- AvailabilityFactor (annual availability accounting for maintenance)

These parameters define HOW technologies operate, complementing the
SupplyComponent which defines WHAT technologies exist and their fuel
relationships.

Prerequisites:
- TimeComponent (years, timeslices must be defined)
- TopologyComponent (regions must be defined)

See Also
--------
SupplyComponent : Technology registry; writes to PerformanceComponent DataFrames
    via back-reference when defining technology types.
component_mapping.md : Section 6 - Performance Parameters ownership
"""

import pandas as pd
from typing import List, Set

from .base import ScenarioComponent


class PerformanceComponent(ScenarioComponent):
    """
    Performance component for technology operational parameters.

    Owns the DataFrames for all six performance-related OSeMOSYS parameters.
    SupplyComponent methods (add_technology, set_conversion_technology, etc.)
    write to these DataFrames via a back-reference established in Scenario.

    Attributes
    ----------
    operational_life : pd.DataFrame
        OperationalLife[r,t] - Asset lifetime in years.
        Columns: REGION, TECHNOLOGY, VALUE
    capacity_to_activity_unit : pd.DataFrame
        CapacityToActivityUnit[r,t] - Conversion factor (default 31.536).
        Columns: REGION, TECHNOLOGY, VALUE
    input_activity_ratio : pd.DataFrame
        InputActivityRatio[r,t,f,m,y] - Input fuel per unit output.
        Columns: REGION, TECHNOLOGY, FUEL, MODE_OF_OPERATION, YEAR, VALUE
    output_activity_ratio : pd.DataFrame
        OutputActivityRatio[r,t,f,m,y] - Output per unit activity.
        Columns: REGION, TECHNOLOGY, FUEL, MODE_OF_OPERATION, YEAR, VALUE
    capacity_factor : pd.DataFrame
        CapacityFactor[r,t,l,y] - Max utilization per timeslice [0,1].
        Columns: REGION, TECHNOLOGY, TIMESLICE, YEAR, VALUE
    availability_factor : pd.DataFrame
        AvailabilityFactor[r,t,y] - Annual availability [0,1].
        Columns: REGION, TECHNOLOGY, YEAR, VALUE

    Owned Files
    -----------
    OperationalLife.csv, CapacityToActivityUnit.csv,
    InputActivityRatio.csv, OutputActivityRatio.csv,
    CapacityFactor.csv, AvailabilityFactor.csv

    Example
    -------
    Typically used through Scenario, which wires SupplyComponent::

        scenario = Scenario(scenario_dir)
        # SupplyComponent writes to PerformanceComponent internally:
        scenario.supply.add_technology('REGION1', 'GAS_CCGT',
                                       operational_life=30)
        scenario.supply.set_conversion_technology(
            'REGION1', 'GAS_CCGT',
            input_fuel='GAS', output_fuel='ELEC', efficiency=0.55
        )

        # Direct access to performance data:
        print(scenario.performance.operational_life)
        print(scenario.performance.capacity_factor)
    """

    owned_files = [
        'OperationalLife.csv', 'CapacityToActivityUnit.csv',
        'InputActivityRatio.csv', 'OutputActivityRatio.csv',
        'CapacityFactor.csv', 'AvailabilityFactor.csv',
    ]

    def __init__(self, scenario_dir: str):
        """
        Initialize performance component with empty DataFrames.

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
            require_timeslices=True,
        )
        self.years = prereqs['years']
        self.regions = prereqs['regions']
        self.timeslices = prereqs['timeslices']

        # Performance DataFrames
        self.operational_life = self.init_dataframe("OperationalLife")
        self.capacity_to_activity_unit = self.init_dataframe(
            "CapacityToActivityUnit"
        )
        self.input_activity_ratio = self.init_dataframe("InputActivityRatio")
        self.output_activity_ratio = self.init_dataframe("OutputActivityRatio")
        self.capacity_factor = self.init_dataframe("CapacityFactor")
        self.availability_factor = self.init_dataframe("AvailabilityFactor")

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def technologies(self) -> List[str]:
        """
        Get list of technologies that have operational life defined.

        Returns
        -------
        list of str
            Unique technology identifiers from OperationalLife.
        """
        if self.operational_life.empty:
            return []
        return self.operational_life['TECHNOLOGY'].unique().tolist()

    @property
    def defined_fuels(self) -> Set[str]:
        """
        Get set of fuels referenced in activity ratios.

        Returns
        -------
        set of str
            Fuel identifiers from InputActivityRatio and OutputActivityRatio.
        """
        fuels = set()
        if not self.input_activity_ratio.empty:
            fuels.update(self.input_activity_ratio['FUEL'].unique())
        if not self.output_activity_ratio.empty:
            fuels.update(self.output_activity_ratio['FUEL'].unique())
        return fuels

    @property
    def modes(self) -> Set[str]:
        """
        Get set of all modes referenced in activity ratios.

        Returns
        -------
        set of str
            Mode identifiers. Defaults to {'MODE1'} if none defined.
        """
        all_modes = set()
        for df in [self.input_activity_ratio, self.output_activity_ratio]:
            if not df.empty:
                all_modes.update(df['MODE_OF_OPERATION'].unique())
        return all_modes if all_modes else {'MODE1'}

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
        self.operational_life = self.read_csv("OperationalLife.csv")
        self.capacity_to_activity_unit = self.read_csv(
            "CapacityToActivityUnit.csv"
        )
        self.input_activity_ratio = self.read_csv("InputActivityRatio.csv")
        self.output_activity_ratio = self.read_csv("OutputActivityRatio.csv")
        self.capacity_factor = self.read_csv("CapacityFactor.csv")
        self.availability_factor = self.read_csv("AvailabilityFactor.csv")

    def save(self) -> None:
        """
        Save all performance parameter DataFrames to CSV files.

        Raises
        ------
        ValueError
            If any DataFrame fails schema validation.
        """
        self._save_sorted(
            "OperationalLife.csv", self.operational_life,
            ["REGION", "TECHNOLOGY", "VALUE"],
            ["REGION", "TECHNOLOGY"],
        )
        self._save_sorted(
            "CapacityToActivityUnit.csv", self.capacity_to_activity_unit,
            ["REGION", "TECHNOLOGY", "VALUE"],
            ["REGION", "TECHNOLOGY"],
        )
        self._save_sorted(
            "InputActivityRatio.csv", self.input_activity_ratio,
            ["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION",
             "YEAR", "VALUE"],
            ["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR"],
        )
        self._save_sorted(
            "OutputActivityRatio.csv", self.output_activity_ratio,
            ["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION",
             "YEAR", "VALUE"],
            ["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR"],
        )
        self._save_sorted(
            "CapacityFactor.csv", self.capacity_factor,
            ["REGION", "TECHNOLOGY", "TIMESLICE", "YEAR", "VALUE"],
            ["REGION", "TECHNOLOGY", "TIMESLICE", "YEAR"],
        )
        self._save_sorted(
            "AvailabilityFactor.csv", self.availability_factor,
            ["REGION", "TECHNOLOGY", "YEAR", "VALUE"],
            ["REGION", "TECHNOLOGY", "YEAR"],
        )

    def _save_sorted(
        self,
        filename: str,
        df: pd.DataFrame,
        cols: List[str],
        sort_cols: List[str],
    ) -> None:
        """Helper to save DataFrame with column selection and sorting."""
        if df.empty:
            self.write_dataframe(filename, df)
        else:
            sorted_df = df[cols].sort_values(by=sort_cols)
            self.write_dataframe(filename, sorted_df)

    # =========================================================================
    # Validation
    # =========================================================================

    def validate(self) -> None:
        """
        Validate performance parameter consistency.

        Checks:
        - Every technology with OperationalLife has at least one output
        - Activity ratios are positive
        - CapacityFactor and AvailabilityFactor in [0, 1]

        Raises
        ------
        ValueError
            If validation fails.
        """
        self._validate_activity_ratios()
        self._validate_factor_bounds()

    def _validate_activity_ratios(self) -> None:
        """Validate activity ratio consistency."""
        errors = []

        # Every technology with operational_life needs at least one output
        if not self.operational_life.empty:
            defined_tech = set(
                zip(
                    self.operational_life['REGION'],
                    self.operational_life['TECHNOLOGY'],
                )
            )
            if self.output_activity_ratio.empty:
                if defined_tech:
                    errors.append(
                        "No output activity ratios defined for any technology"
                    )
            else:
                techs_with_outputs = set(
                    zip(
                        self.output_activity_ratio['REGION'],
                        self.output_activity_ratio['TECHNOLOGY'],
                    )
                )
                for region, tech in defined_tech:
                    if (region, tech) not in techs_with_outputs:
                        errors.append(
                            f"Technology '{tech}' in '{region}' has no outputs"
                        )

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
        """Validate that capacity and availability factors are in [0, 1]."""
        if not self.capacity_factor.empty:
            vals = self.capacity_factor['VALUE']
            if (vals < 0).any() or (vals > 1).any():
                raise ValueError("CapacityFactor must be in range [0, 1]")

        if not self.availability_factor.empty:
            vals = self.availability_factor['VALUE']
            if (vals < 0).any() or (vals > 1).any():
                raise ValueError("AvailabilityFactor must be in range [0, 1]")

    # =========================================================================
    # Representation
    # =========================================================================

    def __repr__(self) -> str:
        n_tech = len(self.technologies)
        n_fuels = len(self.defined_fuels)
        return (
            f"PerformanceComponent(scenario_dir='{self.scenario_dir}', "
            f"technologies={n_tech}, fuels={n_fuels})"
        )
