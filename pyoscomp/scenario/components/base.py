# pyoscomp/scenario/components/base.py

"""
Base class for scenario components in PyPSA-OSeMOSYS Comparison Framework.
"""
import os
import shutil
import importlib.resources
import pandas as pd
from abc import ABC, abstractmethod

from tests.test_scenario.test_validation.test_schema import schema

from ..validation.schemas import SchemaRegistry, validate_csv

class ScenarioComponent(ABC):
    def __init__(self, scenario_dir: str):
        self.scenario_dir = scenario_dir
        # Load the schema from the package
        schema_path = importlib.resources.files("pyoscomp").joinpath("osemosys_config.yaml")
        self.schema = SchemaRegistry(str(schema_path))

    def _get_schema_name(self, filename: str) -> str:
        """
        Infer OSeMOSYS parameter/set/result name from filename (e.g., 'YEAR.csv' -> 'YEAR').
        """
        return os.path.splitext(os.path.basename(filename))[0]
    
    def init_dataframe(self, schema_name: str) -> pd.DataFrame:
        """
        Initialize an empty DataFrame with columns based on the schema for the given parameter/set/result.
        :param schema_name: Name of the schema to use for columns
        :return: Empty DataFrame with schema columns
        """
        cols = self.schema.get_csv_columns(schema_name)
        dtype = self.schema.get_dtype(schema_name)
        # Build dtype mapping
        dtype_map = {}
        for col in cols:
            if col == 'VALUE':
                if dtype == 'int':
                    dtype_map[col] = 'int'
                elif dtype == 'float':
                    dtype_map[col] = 'float'
                elif dtype == 'str':
                    dtype_map[col] = 'str'
                else:
                    dtype_map[col] = 'object'
            else:
                # Index columns: default to str
                dtype_map[col] = 'str'
        # Create empty DataFrame with correct dtypes
        df = pd.DataFrame({col: pd.Series(dtype=dtype_map[col]) for col in cols})
        return df
    
    def write_dataframe(self, filename: str, df: pd.DataFrame):
        """
        Writes a pandas DataFrame to a CSV in the scenario directory, with schema validation.
        :param filename: Name of the CSV file
        :param df: DataFrame to write
        """
        schema_name = self._get_schema_name(filename)
        validate_csv(schema_name, df, self.schema)
        file_path = os.path.join(self.scenario_dir, filename)
        df.to_csv(file_path, index=False)

    def read_csv(self, filename: str) -> pd.DataFrame:
        """
        Helper to read a CSV file and validate against the OSeMOSYS schema.
        Returns DataFrame. Raises informative error if file missing or schema mismatch.
        :param filename: Name of the CSV file
        :return: DataFrame with CSV contents
        """
        path = os.path.join(self.scenario_dir, filename)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Required parameter file '{filename}' not found in scenario directory.")
        df = pd.read_csv(path)
        schema_name = self._get_schema_name(filename)
        validate_csv(schema_name, df, self.schema)
        return df
    
    def add_to_dataframe(self, existing_df: pd.DataFrame, new_records: list,
                         key_columns: list, keep='last') -> pd.DataFrame:
        """
        Append new records to an existing DataFrame.
        :param existing_df: Existing DataFrame
        :param new_records: List of dicts representing new records
        :param key_columns: Columns to identify duplicates
        :param keep: Which duplicate to keep ('first' or 'last')
        :return: Merged DataFrame
        """
        for col in key_columns:
            if col not in existing_df.columns and not existing_df.empty:
                raise ValueError(f"Key column '{col}' not found in existing DataFrame.")
        if keep not in ['first', 'last']:
            raise ValueError("Parameter 'keep' must be either 'first' or 'last'.")
        
        df_new = pd.DataFrame(new_records)
        if existing_df.empty:
            return df_new
        else:
            combined = pd.concat([existing_df, df_new], ignore_index=True)
            # Drop duplicates based on all key columns, keep last (newest)
            merged_df = combined.drop_duplicates(subset=key_columns, keep=keep).reset_index(drop=True)
            return merged_df
    
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

    # === Load and Save Methods ===
    @abstractmethod
    def load(self):
        pass

    @abstractmethod
    def save(self):
        pass