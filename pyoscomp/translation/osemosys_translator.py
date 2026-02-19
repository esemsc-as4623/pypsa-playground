"""
pyoscomp/translation/osemosys_translator.py

Translates ScenarioData to OSeMOSYS-compatible CSV format (otoole-ready).

This module handles:
- Exporting ScenarioData to CSV files in OSeMOSYS format
- Converting ScenarioData to dictionary format for direct otoole usage
- Translating OSeMOSYS results back to standardized format
"""

from .base import InputTranslator, OutputTranslator
from typing import Dict, Optional
from pathlib import Path
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class OSeMOSYSInputTranslator(InputTranslator):
    """
    Translates ScenarioData to OSeMOSYS-compatible format.
    
    This can either export to CSV files (for otoole/glpsol) or return
    a dictionary representation for direct programmatic access.
    
    Attributes
    ----------
    scenario_data : ScenarioData
        The source scenario data (from base class).
    output_dir : Optional[str]
        Directory to write CSVs (set via export_to_csv method).
    
    Example
    -------
    >>> from pyoscomp.interfaces import ScenarioData
    >>> data = ScenarioData.from_directory('/path/to/scenario')
    >>> translator = OSeMOSYSInputTranslator(data)
    
    # Option 1: Get dict for programmatic use
    >>> data_dict = translator.translate()
    
    # Option 2: Export to CSV files
    >>> translator.export_to_csv('/path/to/output')
    """
    
    def __init__(self, scenario_data):
        """
        Initialize the translator with scenario data.
        
        Parameters
        ----------
        scenario_data : ScenarioData
            The scenario data to translate.
        """
        super().__init__(scenario_data)
        self.output_dir = None

    def translate(self) -> Dict[str, pd.DataFrame]:
        """
        Convert ScenarioData to OSeMOSYS dictionary format.
        
        Returns a dictionary mapping OSeMOSYS parameter names (without .csv)
        to pandas DataFrames. This is compatible with otoole's expected format.
        
        Returns
        -------
        Dict[str, pd.DataFrame]
            Dictionary of DataFrames keyed by OSeMOSYS parameter name.
        
        Notes
        -----
        Uses ScenarioData.to_dict() which handles all the conversion logic.
        """
        return self.scenario_data.to_dict()
    
    def export_to_csv(self, output_dir: str, overwrite: bool = True) -> str:
        """
        Export scenario data to OSeMOSYS CSV files.
        
        Creates CSV files in the standard OSeMOSYS format that can be
        used directly with otoole for conversion to datafile format.
        
        Parameters
        ----------
        output_dir : str
            Directory to write CSV files.
        overwrite : bool, optional
            If True, overwrite existing files (default: True).
            If False, raise error if directory exists with files.
        
        Returns
        -------
        str
            Path to the output directory.
        
        Raises
        ------
        FileExistsError
            If overwrite=False and output_dir contains CSV files.
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Check for existing files if not overwriting
        if not overwrite:
            existing_csvs = list(output_path.glob("*.csv"))
            if existing_csvs:
                raise FileExistsError(
                    f"Directory {output_dir} contains {len(existing_csvs)} CSV files. "
                    "Use overwrite=True to replace them."
                )
        
        # Get data dictionary
        data_dict = self.translate()
        
        # Write each DataFrame to CSV
        for name, df in data_dict.items():
            if df is not None and not df.empty:
                csv_path = output_path / f"{name}.csv"
                df.to_csv(csv_path, index=False)
                logger.debug(f"Wrote {csv_path}")
            else:
                # Write empty file with headers for required files
                csv_path = output_path / f"{name}.csv"
                # Use empty DataFrame with expected columns
                pd.DataFrame().to_csv(csv_path, index=False)
                logger.debug(f"Wrote empty {csv_path}")
        
        self.output_dir = str(output_path)
        logger.info(f"Exported {len(data_dict)} files to {output_dir}")
        
        return self.output_dir
    
    def get_required_files(self) -> Dict[str, bool]:
        """
        Check which required OSeMOSYS files exist in the scenario data.
        
        Returns
        -------
        Dict[str, bool]
            Dictionary mapping filename to existence status.
        """
        required_sets = ['REGION', 'YEAR', 'TECHNOLOGY', 'FUEL', 'TIMESLICE', 
                         'MODE_OF_OPERATION', 'SEASON', 'DAYTYPE', 'DAILYTIMEBRACKET']
        required_params = ['YearSplit', 'SpecifiedAnnualDemand', 'SpecifiedDemandProfile']
        
        data_dict = self.translate()
        
        result = {}
        for name in required_sets + required_params:
            df = data_dict.get(name, pd.DataFrame())
            result[name] = df is not None and not df.empty
        
        return result


class OSeMOSYSOutputTranslator(OutputTranslator):
    """
    Translates OSeMOSYS results to standardized output DataFrames.
    
    Reads otoole-generated result CSVs and converts to standard format.
    
    Attributes
    ----------
    model_output : Any
        Either a directory path (str) containing result CSVs,
        or a dictionary of DataFrames.
    """
    
    def __init__(self, model_output):
        """
        Initialize with OSeMOSYS results.
        
        Parameters
        ----------
        model_output : str or Dict[str, pd.DataFrame]
            Either path to results directory or dict of result DataFrames.
        """
        super().__init__(model_output)
        self._results_dict = None
    
    @property
    def results_dict(self) -> Dict[str, pd.DataFrame]:
        """Load results from directory if needed."""
        if self._results_dict is None:
            if isinstance(self.model_output, str):
                self._results_dict = self._load_results_from_directory(self.model_output)
            elif isinstance(self.model_output, dict):
                self._results_dict = self.model_output
            else:
                raise TypeError(f"model_output must be str or dict, got {type(self.model_output)}")
        return self._results_dict
    
    def _load_results_from_directory(self, results_dir: str) -> Dict[str, pd.DataFrame]:
        """Load all CSV files from results directory."""
        results_path = Path(results_dir)
        if not results_path.exists():
            raise FileNotFoundError(f"Results directory not found: {results_dir}")
        
        results = {}
        for csv_file in results_path.glob("*.csv"):
            name = csv_file.stem
            try:
                df = pd.read_csv(csv_file)
                results[name] = df
            except Exception as e:
                logger.warning(f"Failed to read {csv_file}: {e}")
        
        return results
    
    def translate(self) -> Dict[str, pd.DataFrame]:
        """
        Convert OSeMOSYS results to standardized output DataFrames.
        
        Returns
        -------
        Dict[str, pd.DataFrame]
            Dictionary of result DataFrames with standardized keys.
        """
        results = {}
        
        # Map OSeMOSYS result names to standard names
        standard_mapping = {
            'TotalCapacityAnnual': 'OptimalCapacity',
            'ProductionByTechnologyAnnual': 'Production',
            'TotalDiscountedCost': 'Objective',
            'NewCapacity': 'NewCapacity',
            'CapitalInvestment': 'CapitalInvestment',
            'RateOfActivity': 'Dispatch',
        }
        
        for osemosys_name, standard_name in standard_mapping.items():
            if osemosys_name in self.results_dict:
                results[standard_name] = self.results_dict[osemosys_name].copy()
        
        # Include all original results under their original names too
        for name, df in self.results_dict.items():
            if name not in results:
                results[name] = df.copy()
        
        return results
    
    def get_objective(self) -> float:
        """
        Get the total discounted cost (objective value).
        
        Returns
        -------
        float
            Total discounted cost.
        """
        obj_df = self.results_dict.get('TotalDiscountedCost')
        if obj_df is not None and not obj_df.empty:
            return obj_df['VALUE'].sum()
        return 0.0
    
    def get_optimal_capacity(self, technology: Optional[str] = None) -> pd.DataFrame:
        """
        Get optimal capacity by technology.
        
        Parameters
        ----------
        technology : str, optional
            Filter to specific technology.
        
        Returns
        -------
        pd.DataFrame
            Capacity values.
        """
        cap_df = self.results_dict.get('TotalCapacityAnnual', pd.DataFrame())
        if technology and not cap_df.empty:
            cap_df = cap_df[cap_df['TECHNOLOGY'] == technology]
        return cap_df
