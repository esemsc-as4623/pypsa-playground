# pyoscomp/scenario/components/supply.py

"""
Supply Component for scenario building in PyPSA-OSeMOSYS Comparison Framework.
Note: this component handles technology / generator definitions and supply-side parameters.
Supply is provided by a TECHNOLOGY in OSeMOSYS terminology, and by a Generator in PyPSA terminology.
"""
import pandas as pd
import numpy as np
import os

from .base import ScenarioComponent

class SupplyComponent(ScenarioComponent):
    """
    Supply component for technology/generator definitions and supply-side parameters.
    Handles OSeMOSYS supply parameters: technology metadata, capacity, activity ratios, and operational parameters.

    Prerequisites:
        - Time component must be initialized in the scenario (defines years and timeslices).
        - Topology component (regions, nodes) must be initialized.

    Raises descriptive errors if prerequisites are missing.
    
    Example usage::
        supply = SupplyComponent(scenario_dir)
        supply.check_prerequisites(scenario)
        supply.load()  # Loads all supply parameter CSVs
        # ... modify DataFrames as needed ...
        supply.save()  # Saves all supply parameter DataFrames to CSV
    
    CSV Format Expectations:
        - All CSVs must have columns as specified in each method's docstring.
        - See OSeMOSYS.md for parameter definitions.
    """
    
    def __init__(self, scenario_dir):
        super().__init__(scenario_dir)

        # Technology metadata: DataFrame indexed by REGION, TECHNOLOGY
        self.technology_metadata = pd.DataFrame(columns=["REGION", "TECHNOLOGY", "OPERATIONAL_LIFE"])

        # Capacity parameters
        self.capacity_to_activity_unit = pd.DataFrame(columns=["REGION", "TECHNOLOGY", "VALUE"])
        self.residual_capacity = pd.DataFrame(columns=["REGION", "TECHNOLOGY", "YEAR", "VALUE"])

        # Activity ratios
        self.input_activity_ratio = pd.DataFrame(columns=["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR", "VALUE"])
        self.output_activity_ratio = pd.DataFrame(columns=["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR", "VALUE"])

        # Operational parameters
        self.capacity_factor = pd.DataFrame(columns=["REGION", "TECHNOLOGY", "TIMESLICE", "YEAR", "VALUE"])
        self.availability_factor = pd.DataFrame(columns=["REGION", "TECHNOLOGY", "YEAR", "VALUE"])
        self.operational_life = pd.DataFrame(columns=["REGION", "TECHNOLOGY", "VALUE"])

        # Tracking
        # TODO: create placeholder data structures for tracking of supply component parameters (akin to demand.py)

    # === Prerequisite Check ===
    def check_prerequisites(self, scenario):
        """
        Check that required scenario components are initialized.
        Raises descriptive errors if prerequisites are missing.
        :param scenario: Scenario object containing components.
        :raises RuntimeError: if time or topology/network component is missing.
        """
        # Check for time component
        if not hasattr(scenario, "time") or scenario.time is None:
            raise RuntimeError("Supply component requires time structure. Initialize Time component first.")
        # Check for topology component
        if not hasattr(scenario, "topology") or scenario.topology is None:
            raise RuntimeError("Supply component requires topology structure. Initialize Topology component first.")

    # === Load and Save Methods ===
    def load(self):
        """
        Load all supply parameter CSV files into DataFrames.
        Uses read_csv from base class.
        :raises FileNotFoundError: if any required file is missing.
        :raises ValueError: if any file has missing or incorrect columns.
        """
        self._load_capacity_to_activity_unit()
        self._load_capacity_factor()
        self._load_availability_factor()
        self._load_operational_life()
        self._load_residual_capacity()
        self._load_input_activity_ratio()
        self._load_output_activity_ratio()

    def save(self):
        """
        Save all supply parameter DataFrames to CSV files in the scenario directory.
        Uses write_dataframe from base class.
        """
        self._save_capacity_to_activity_unit()
        self._save_capacity_factor()
        self._save_availability_factor()
        self._save_operational_life()
        self._save_residual_capacity()
        self._save_input_activity_ratio()
        self._save_output_activity_ratio()

    # === User Input Methods ===
    def add_technology(self, region, technology, operational_life):
        """
        Add a new technology to the technology metadata DataFrame.
        :param region: Region where the technology is located.
        :param technology: Name of the technology.
        :param operational_life: Operational life of the technology (years).
        """
        new_entry = {"REGION": region, "TECHNOLOGY": technology, "OPERATIONAL_LIFE": operational_life}
        self.technology_metadata = pd.concat([self.technology_metadata, pd.DataFrame([new_entry])], ignore_index=True)

    # TODO: initilize methods for setting capacity, activity ratios, and operational parameters (akin to demand.py)
    # def set_operational_parameters()
    # def set_capacity()
    # def set_activity()

    # === Processing ===
    def process(self, **kwargs):
        """
        Orchestrator: Loads Dependencies -> Calculates Logic -> Writes Output.
        """
        # 1. Load Dependency
        
        # 2. Calculation Logic

        # 3. Write Output
        pass

    # === Internal Logic Helpers ===
    
    # === Internal Load/Save Helpers ===
    def _load_capacity_to_activity_unit(self):
        """
        Load CapacityToActivityUnit.csv.
        Expected columns: REGION, TECHNOLOGY, VALUE.
        """
        self.capacity_to_activity_unit = self.read_csv("CapacityToActivityUnit.csv", ["REGION", "TECHNOLOGY", "VALUE"])

    def _load_capacity_factor(self):
        """
        Load CapacityFactor.csv.
        Expected columns: REGION, TECHNOLOGY, TIMESLICE, YEAR, VALUE.
        """
        self.capacity_factor = self.read_csv("CapacityFactor.csv", ["REGION", "TECHNOLOGY", "TIMESLICE", "YEAR", "VALUE"])

    def _load_availability_factor(self):
        """
        Load AvailabilityFactor.csv.
        Expected columns: REGION, TECHNOLOGY, YEAR, VALUE.
        """
        self.availability_factor = self.read_csv("AvailabilityFactor.csv", ["REGION", "TECHNOLOGY", "YEAR", "VALUE"])

    def _load_operational_life(self):
        """
        Load OperationalLife.csv.
        Expected columns: REGION, TECHNOLOGY, VALUE.
        """
        self.operational_life = self.read_csv("OperationalLife.csv", ["REGION", "TECHNOLOGY", "VALUE"])

    def _load_residual_capacity(self):
        """
        Load ResidualCapacity.csv.
        Expected columns: REGION, TECHNOLOGY, YEAR, VALUE.
        """
        self.residual_capacity = self.read_csv("ResidualCapacity.csv", ["REGION", "TECHNOLOGY", "YEAR", "VALUE"])

    def _load_input_activity_ratio(self):
        """
        Load InputActivityRatio.csv.
        Expected columns: REGION, TECHNOLOGY, FUEL, MODE_OF_OPERATION, YEAR, VALUE.
        """
        self.input_activity_ratio = self.read_csv("InputActivityRatio.csv", ["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR", "VALUE"])

    def _load_output_activity_ratio(self):
        """
        Load OutputActivityRatio.csv.
        Expected columns: REGION, TECHNOLOGY, FUEL, MODE_OF_OPERATION, YEAR, VALUE.
        """
        self.output_activity_ratio = self.read_csv("OutputActivityRatio.csv", ["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR", "VALUE"])

    def _save_capacity_to_activity_unit(self):
        """
        Save CapacityToActivityUnit.csv.
        Columns: REGION, TECHNOLOGY, VALUE.
        """
        self.write_dataframe("CapacityToActivityUnit.csv", self.capacity_to_activity_unit)

    def _save_capacity_factor(self):
        """
        Save CapacityFactor.csv.
        Columns: REGION, TECHNOLOGY, TIMESLICE, YEAR, VALUE.
        """
        self.write_dataframe("CapacityFactor.csv", self.capacity_factor)

    def _save_availability_factor(self):
        """
        Save AvailabilityFactor.csv.
        Columns: REGION, TECHNOLOGY, YEAR, VALUE.
        """
        self.write_dataframe("AvailabilityFactor.csv", self.availability_factor)

    def _save_operational_life(self):
        """
        Save OperationalLife.csv.
        Columns: REGION, TECHNOLOGY, VALUE.
        """
        self.write_dataframe("OperationalLife.csv", self.operational_life)

    def _save_residual_capacity(self):
        """
        Save ResidualCapacity.csv.
        Columns: REGION, TECHNOLOGY, YEAR, VALUE.
        """
        self.write_dataframe("ResidualCapacity.csv", self.residual_capacity)

    def _save_input_activity_ratio(self):
        """
        Save InputActivityRatio.csv.
        Columns: REGION, TECHNOLOGY, FUEL, MODE_OF_OPERATION, YEAR, VALUE.
        """
        self.write_dataframe("InputActivityRatio.csv", self.input_activity_ratio)

    def _save_output_activity_ratio(self):
        """
        Save OutputActivityRatio.csv.
        Columns: REGION, TECHNOLOGY, FUEL, MODE_OF_OPERATION, YEAR, VALUE.
        """
        self.write_dataframe("OutputActivityRatio.csv", self.output_activity_ratio)

    # === Visualization ===
    def visualize(self):
        """
        Creates a visualization of the supply composition by timeslice for a given region.
        """
        import matplotlib.pyplot as plt

        # --- Styles ---
        CB_PALETTE = ['#56B4E9', '#D55E00', '#009E73', '#F0E442', '#0072B2', '#CC79A7', '#E69F00']
        HATCHES = ['', '//', '..', 'xx', '++', '**', 'OO']
        plt.rcParams.update({
            'font.size': 14, 
            'text.color': 'black',
            'axes.labelcolor': 'black',
            'xtick.color': 'black',
            'ytick.color': 'black',
            'font.family': 'sans-serif'
        })

        # --- Load Data ---

        # --- Process Data ---

        # --- Plotting ---

        # --- Formatting ---

        # plt.grid(axis='y', linestyle='--', alpha=0.3)
        # plt.tight_layout()
        # plt.show()
        pass

    def visualize_all(self):
        """
        Creates visualizations for all regions defined in the topology component.
        """
        import matplotlib.pyplot as plt

        # plt.tight_layout()
        # plt.show()
        pass