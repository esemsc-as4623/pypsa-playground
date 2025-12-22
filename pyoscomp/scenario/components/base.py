# pyoscomp/scenario/components/base.py

"""
Base class for scenario components in PyPSA-OSeMOSYS Comparison Framework.
"""
import os
import csv
import pandas as pd
from abc import ABC, abstractmethod

class ScenarioComponent(ABC):
    def __init__(self, scenario_dir: str):
        self.scenario_dir = scenario_dir

    @abstractmethod
    def process(self, **kwargs):
        """Execute the logic for this component."""
        pass

    def write_csv(self, filename: str, data: list):
        """
        Writes a list of data to a CSV in the scenario directory.
        Used for Sets (e.g. REGION, YEAR from OSeMOSYS).
        """
        file_path = os.path.join(self.scenario_dir, filename)
        
        with open(file_path, "w", newline="") as f:
            writer = csv.writer(f)
            # Sets usually expect a single column. 
            # Iterate and write rows to ensure correct CSV format.
            for item in data:
                writer.writerow([item])

    def write_dataframe(self, filename: str, df: pd.DataFrame):
        """
        Writes a pandas DataFrame to a CSV in the scenario directory.
        Used for Parameters (e.g. Conversionls, YearSplit from OSeMOSYS).
        """
        file_path = os.path.join(self.scenario_dir, filename)
        df.to_csv(file_path, index=False)