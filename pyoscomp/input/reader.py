# pyoscomp/input/reader.py

"""
Reads scenario input data from a specified folder containing CSV and config files.
"""
import os
import glob
import pandas as pd
import yaml
from typing import Dict, Any

class ScenarioInputReader:
    """
    Reads scenario input data from a specified folder containing CSV and config files.
    """
    def __init__(self, input_dir: str):
        self.input_dir = input_dir
        self.csv_data: Dict[str, pd.DataFrame] = {}
        self.config: Dict[str, Any] = {}

    def read_all_csvs(self) -> None:
        """Reads all CSV files in the input directory into pandas DataFrames."""
        csv_files = glob.glob(os.path.join(self.input_dir, '*.csv'))
        for csv_file in csv_files:
            key = os.path.splitext(os.path.basename(csv_file))[0]
            self.csv_data[key] = pd.read_csv(csv_file)

    def read_config(self, config_name: str = 'config.yaml') -> None:
        """Reads a YAML config file from the input directory."""
        config_path = os.path.join(self.input_dir, config_name)
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
        else:
            self.config = {}

    def get_csv(self, name: str) -> pd.DataFrame:
        """Returns a DataFrame for a given CSV name (without .csv)."""
        return self.csv_data.get(name)

    def get_config(self) -> Dict[str, Any]:
        """Returns the loaded config dictionary."""
        return self.config
