# pyoscomp/scenario/components/base.py

"""
Base class for scenario components in PyPSA-OSeMOSYS Comparison Framework.

This module defines the abstract base class that all scenario components inherit from.
It provides common functionality for:

- Schema-validated CSV I/O operations
- Prerequisite checking (years, regions, technologies)
- DataFrame initialization and manipulation
- Scenario directory management

All concrete components (TopologyComponent, TimeComponent, etc.) must inherit from
ScenarioComponent and implement the abstract load() and save() methods.
"""

import os
import shutil
import importlib.resources
import pandas as pd
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any, Union

from ..validation import SchemaRegistry, validate_csv


class ScenarioComponent(ABC):
    """
    Abstract base class for all scenario components.

    Provides common infrastructure for loading, saving, and validating
    OSeMOSYS-format CSV files. Each concrete component handles a specific
    domain (time, topology, demand, supply, economics, performance).

    Attributes
    ----------
    scenario_dir : str
        Absolute path to the scenario directory containing CSV files.
    schema : SchemaRegistry
        Schema registry for CSV validation.

    Notes
    -----
    Subclasses must implement:
    - load(): Load all component CSVs into DataFrames
    - save(): Write all component DataFrames to CSVs
    - owned_files: Class attribute listing CSV files owned by this component

    Example
    -------
    Subclass pattern::

        class TimeComponent(ScenarioComponent):
            owned_files = ['YEAR.csv', 'TIMESLICE.csv', 'YearSplit.csv', ...]

            def __init__(self, scenario_dir):
                super().__init__(scenario_dir)
                self.years_df = self.init_dataframe("YEAR")
                # ... other DataFrames

            def load(self):
                self.years_df = self.read_csv("YEAR.csv")
                # ... load other files

            def save(self):
                self.write_dataframe("YEAR.csv", self.years_df)
                # ... save other files
    """

    # Class attribute: list of CSV files owned by this component
    # Subclasses should override this
    owned_files: List[str] = []

    def __init__(self, scenario_dir: str):
        """
        Initialize the scenario component.

        Parameters
        ----------
        scenario_dir : str
            Path to the scenario directory. Will be created if it doesn't exist.

        Raises
        ------
        FileNotFoundError
            If schema configuration file cannot be found.
        """
        self.scenario_dir = str(scenario_dir)

        # Ensure directory exists
        os.makedirs(self.scenario_dir, exist_ok=True)

        # Load the schema from the package
        schema_path = importlib.resources.files("pyoscomp").joinpath(
            "osemosys_config.yaml"
        )
        self.schema = SchemaRegistry(str(schema_path))

    # =========================================================================
    # Abstract Methods - Must be implemented by subclasses
    # =========================================================================

    @abstractmethod
    def load(self) -> None:
        """
        Load all component CSV files into DataFrames.

        Must be implemented by each concrete component to load its owned files.

        Raises
        ------
        FileNotFoundError
            If any required file is missing.
        ValueError
            If any file fails schema validation.
        """
        pass

    @abstractmethod
    def save(self) -> None:
        """
        Save all component DataFrames to CSV files.

        Must be implemented by each concrete component to save its owned files.

        Raises
        ------
        ValueError
            If any DataFrame fails schema validation.
        """
        pass

    # =========================================================================
    # Optional Abstract Methods - Override if needed
    # =========================================================================

    def validate(self) -> None:
        """
        Validate component state and cross-references.

        Override in subclasses to add domain-specific validation logic.
        Default implementation does nothing.
        """
        pass

    # =========================================================================
    # Schema and DataFrame Utilities
    # =========================================================================

    def _get_schema_name(self, filename: str) -> str:
        """
        Extract OSeMOSYS parameter/set name from filename.

        Parameters
        ----------
        filename : str
            CSV filename (e.g., 'YEAR.csv', 'CapacityFactor.csv')

        Returns
        -------
        str
            Schema name without extension (e.g., 'YEAR', 'CapacityFactor')
        """
        return os.path.splitext(os.path.basename(filename))[0]

    def init_dataframe(self, schema_name: str) -> pd.DataFrame:
        """
        Initialize an empty DataFrame with schema-defined columns and dtypes.

        Parameters
        ----------
        schema_name : str
            OSeMOSYS parameter/set name (e.g., 'YEAR', 'YearSplit')

        Returns
        -------
        pd.DataFrame
            Empty DataFrame with correct columns and dtypes.

        Raises
        ------
        ValueError
            If schema_name not found in schema registry.
        """
        cols = self.schema.get_csv_columns(schema_name)
        dtype = self.schema.get_dtype(schema_name)

        # Build dtype mapping
        dtype_map = {}
        for col in cols:
            if col == 'VALUE':
                dtype_map[col] = {
                    'int': 'int64',
                    'float': 'float64',
                    'str': 'object',
                }.get(dtype, 'object')
            else:
                # Index columns default to object (string)
                dtype_map[col] = 'object'

        # Create empty DataFrame with correct dtypes
        df = pd.DataFrame({col: pd.Series(dtype=dtype_map[col]) for col in cols})
        return df

    def read_csv(self, filename: str, optional: bool = False) -> Optional[pd.DataFrame]:
        """
        Read and validate a CSV file from the scenario directory.

        Parameters
        ----------
        filename : str
            Name of the CSV file (e.g., 'YEAR.csv')
        optional : bool
            If True, return empty DataFrame if file does not exist. If False, raise FileNotFoundError.

        Returns
        -------
        Optional[pd.DataFrame]
            Validated DataFrame contents or None if optional and file missing.

        Raises
        ------
        FileNotFoundError
            If file does not exist.
        ValueError
            If file fails schema validation.
        """
        path = os.path.join(self.scenario_dir, filename)
        if not os.path.exists(path):
            if optional:
                return None
            raise FileNotFoundError(
                f"Required file '{filename}' not found in {self.scenario_dir}"
            )

        df = pd.read_csv(path)
        schema_name = self._get_schema_name(filename)
        validate_csv(schema_name, df, self.schema)
        return df

    def write_dataframe(self, filename: str, df: pd.DataFrame) -> None:
        """
        Validate and write a DataFrame to CSV.

        Parameters
        ----------
        filename : str
            Name of the CSV file to write.
        df : pd.DataFrame
            DataFrame to write.

        Raises
        ------
        ValueError
            If DataFrame fails schema validation.
        """
        schema_name = self._get_schema_name(filename)
        validate_csv(schema_name, df, self.schema)
        file_path = os.path.join(self.scenario_dir, filename)
        df.to_csv(file_path, index=False)

    def file_exists(self, filename: str) -> bool:
        """Check if a CSV file exists in the scenario directory."""
        return os.path.exists(os.path.join(self.scenario_dir, filename))

    # =========================================================================
    # DataFrame Manipulation
    # =========================================================================

    def add_to_dataframe(
        self,
        existing_df: pd.DataFrame,
        new_records: List[Dict[str, Any]],
        key_columns: List[str],
        keep: str = 'last'
    ) -> pd.DataFrame:
        """
        Add records to a DataFrame, handling duplicates by key columns.

        Parameters
        ----------
        existing_df : pd.DataFrame
            Existing DataFrame to add to.
        new_records : list of dict
            New records as list of dictionaries.
        key_columns : list of str
            Columns that define uniqueness.
        keep : {'first', 'last'}, default 'last'
            Which duplicate to keep.

        Returns
        -------
        pd.DataFrame
            Merged DataFrame with duplicates removed.

        Raises
        ------
        ValueError
            If key columns not in existing DataFrame or invalid keep value.
        """
        if keep not in ['first', 'last']:
            raise ValueError("Parameter 'keep' must be 'first' or 'last'")

        # Validate key columns exist (if DataFrame not empty)
        if not existing_df.empty:
            missing_cols = [c for c in key_columns if c not in existing_df.columns]
            if missing_cols:
                raise ValueError(f"Key columns {missing_cols} not in DataFrame")

        df_new = pd.DataFrame(new_records)

        if existing_df.empty:
            return df_new

        combined = pd.concat([existing_df, df_new], ignore_index=True)
        merged = combined.drop_duplicates(
            subset=key_columns, keep=keep
        ).reset_index(drop=True)

        return merged

    # =========================================================================
    # Prerequisite Loading - Common Methods for Dependent Components
    # =========================================================================

    def load_years(self) -> List[int]:
        """
        Load model years from YEAR.csv.

        Returns
        -------
        list of int
            Sorted list of model years.

        Raises
        ------
        FileNotFoundError
            If YEAR.csv does not exist.
        ValueError
            If no years defined.
        """
        df = self.read_csv("YEAR.csv")
        if df.empty:
            raise ValueError("No years defined in YEAR.csv")
        return sorted(df["VALUE"].astype(int).tolist())

    def load_regions(self) -> List[str]:
        """
        Load regions from REGION.csv.

        Returns
        -------
        list of str
            List of region identifiers.

        Raises
        ------
        FileNotFoundError
            If REGION.csv does not exist.
        ValueError
            If no regions defined.
        """
        df = self.read_csv("REGION.csv")
        if df.empty:
            raise ValueError("No regions defined in REGION.csv")
        return df["VALUE"].tolist()

    def load_timeslices(self) -> List[str]:
        """
        Load timeslices from TIMESLICE.csv.

        Returns
        -------
        list of str
            List of timeslice identifiers.

        Raises
        ------
        FileNotFoundError
            If TIMESLICE.csv does not exist.
        """
        df = self.read_csv("TIMESLICE.csv")
        return df["VALUE"].tolist()

    def load_technologies(self) -> Set[str]:
        """
        Load technologies from TECHNOLOGY.csv if it exists.

        Returns
        -------
        set of str
            Set of technology identifiers (empty if file doesn't exist).
        """
        df = self.read_csv("TECHNOLOGY.csv", optional=True)
        if df is None or df.empty:
            return set()
        return set(df["VALUE"].tolist())

    def load_fuels(self) -> Set[str]:
        """
        Load fuels from FUEL.csv if it exists.

        Returns
        -------
        set of str
            Set of fuel identifiers (empty if file doesn't exist).
        """
        df = self.read_csv("FUEL.csv", optional=True)
        if df is None or df.empty:
            return set()
        return set(df["VALUE"].tolist())

    def check_prerequisites(
        self,
        require_years: bool = False,
        require_regions: bool = False,
        require_timeslices: bool = False
    ) -> Dict[str, Any]:
        """
        Check that prerequisite components are initialized.

        Parameters
        ----------
        require_years : bool
            Require TimeComponent (YEAR.csv) to exist.
        require_regions : bool
            Require TopologyComponent (REGION.csv) to exist.
        require_timeslices : bool
            Require timeslices (TIMESLICE.csv) to exist.

        Returns
        -------
        dict
            Dictionary with 'years', 'regions', 'timeslices' keys
            containing loaded data (or None if not required/found).

        Raises
        ------
        AttributeError
            If required component is missing.
        """
        result = {'years': None, 'regions': None, 'timeslices': None}

        if require_years:
            if not self.file_exists("YEAR.csv"):
                raise AttributeError(
                    "Time component not initialized: YEAR.csv required"
                )
            result['years'] = self.load_years()

        if require_regions:
            if not self.file_exists("REGION.csv"):
                raise AttributeError(
                    "Topology component not initialized: REGION.csv required"
                )
            result['regions'] = self.load_regions()

        if require_timeslices:
            if not self.file_exists("TIMESLICE.csv"):
                raise AttributeError(
                    "Time component incomplete: TIMESLICE.csv required"
                )
            result['timeslices'] = self.load_timeslices()

        return result

    # =========================================================================
    # Scenario Directory Operations
    # =========================================================================

    @staticmethod
    def copy_scenario(
        source_dir: str,
        target_dir: str,
        overwrite: bool = False
    ) -> None:
        """
        Copy an entire scenario directory to a new location.

        Parameters
        ----------
        source_dir : str
            Source scenario directory path.
        target_dir : str
            Target scenario directory path.
        overwrite : bool, default False
            If True, overwrite target if it exists.

        Raises
        ------
        FileExistsError
            If target exists and overwrite=False.
        """
        if os.path.exists(target_dir):
            if overwrite:
                shutil.rmtree(target_dir)
            else:
                # Merge: copy only files that don't exist
                for item in os.listdir(source_dir):
                    src = os.path.join(source_dir, item)
                    dst = os.path.join(target_dir, item)
                    if not os.path.exists(dst):
                        if os.path.isdir(src):
                            shutil.copytree(src, dst)
                        else:
                            shutil.copy2(src, dst)
                return

        shutil.copytree(source_dir, target_dir)

    def get_file_path(self, filename: str) -> Path:
        """
        Get absolute path to a file in the scenario directory.

        Parameters
        ----------
        filename : str
            Name of the file.

        Returns
        -------
        Path
            Absolute path to the file.
        """
        return Path(self.scenario_dir) / filename

    # =========================================================================
    # Representation
    # =========================================================================

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(scenario_dir='{self.scenario_dir}')"
