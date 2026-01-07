# pyoscomp/scenario/components/base.py

"""
Base class for scenario components in PyPSA-OSeMOSYS Comparison Framework.
"""
import os
import shutil
import pandas as pd
from abc import ABC

class ScenarioComponent(ABC):
    def __init__(self, scenario_dir: str):
        self.scenario_dir = scenario_dir

    def write_dataframe(self, filename: str, df: pd.DataFrame):
        """
        Writes a pandas DataFrame to a CSV in the scenario directory.
        Used for Parameters (e.g. Conversionls, YearSplit from OSeMOSYS).
        """
        file_path = os.path.join(self.scenario_dir, filename)
        df.to_csv(file_path, index=False)

    def read_csv(self, filename, expected_columns=[]):
        """
        Helper to read a CSV file and validate columns.
        Returns DataFrame. Raises informative error if file missing or columns mismatch.
        """
        path = os.path.join(self.scenario_dir, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Required parameter file '{filename}' not found in scenario directory.")
        df = pd.read_csv(path)
        if len(expected_columns) > 0:
            missing = [col for col in expected_columns if col not in df.columns]
            if missing:
                raise ValueError(f"File '{filename}' is missing columns: {missing}. Found columns: {list(df.columns)}")
        return df
    
    @staticmethod
    def copy(source_scenario, target_scenario, overwrite=False):
        """
        Copy the entire source scenario configuration to a target scenario directory.
        :param src_dir: Source scenario directory
        :param dest_dir: Destination scenario directory
        :param overwrite: If True, overwrite destination if it exists
        """
        if os.path.exists(target_scenario):
            if overwrite:
                shutil.rmtree(target_scenario)
                shutil.copytree(source_scenario, target_scenario)
                return
            # Only copy files/directories that do not exist in target
            for file in os.listdir(source_scenario):
                s = os.path.join(source_scenario, file)
                d = os.path.join(target_scenario, file)
                if os.path.isdir(s):
                    if not os.path.exists(d):
                        shutil.copytree(s, d)
                else:
                    if not os.path.exists(d):
                        shutil.copy2(s, d)
        else:
            shutil.copytree(source_scenario, target_scenario)