"""
pyoscomp/output/writer.py

Handles writing standardized output data to CSV files and managing output directories.
"""
import os
import pandas as pd
from typing import Dict

class OutputWriter:
    """
    Writes output data (as DataFrames) to standardized CSV files in the output directory.
    """
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def write_csv(self, name: str, df: pd.DataFrame) -> str:
        """Writes a DataFrame to a CSV file in the output directory."""
        path = os.path.join(self.output_dir, f"{name}.csv")
        df.to_csv(path, index=False)
        return path

    def write_multiple(self, data: Dict[str, pd.DataFrame]) -> Dict[str, str]:
        """Writes multiple DataFrames to CSV files. Returns dict of file paths."""
        paths = {}
        for name, df in data.items():
            paths[name] = self.write_csv(name, df)
        return paths
