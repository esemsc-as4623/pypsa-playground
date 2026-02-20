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
    Translate OSeMOSYS otoole-CSV results to a harmonized ``ModelResults``.

    The translator reads result CSVs produced by ``otoole`` (or accepts
    them as a pre-loaded dictionary) and maps them to the model-agnostic
    ``ModelResults`` interface.

    Extraction mapping:

    * **Topology** — ``REGION`` column from ``TotalCapacityAnnual``
      (or any result CSV) → nodes.  Trade results → edges (when
      present).
    * **Supply** — ``TotalCapacityAnnual`` → installed_capacity;
      ``NewCapacity`` → new_capacity.
    * **Objective** — ``TotalDiscountedCost`` ``VALUE`` sum.

    Parameters
    ----------
    model_output : str or Dict[str, pd.DataFrame]
        Either a path to the results directory containing otoole CSVs,
        or a dictionary mapping CSV stem names to DataFrames.

    Examples
    --------
    >>> translator = OSeMOSYSOutputTranslator('path/to/results')
    >>> results = translator.translate()
    >>> results.supply.installed_capacity
       REGION  TECHNOLOGY  YEAR     VALUE
    0  REGION1    GAS_CCGT  2026  0.012684
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
        self._results_dict: Optional[Dict[str, pd.DataFrame]] = None

    # ------------------------------------------------------------------ #
    # lazy loader
    # ------------------------------------------------------------------ #

    @property
    def results_dict(self) -> Dict[str, pd.DataFrame]:
        """
        Load result CSVs lazily on first access.

        Returns
        -------
        Dict[str, pd.DataFrame]
            Mapping of CSV stem → DataFrame.

        Raises
        ------
        TypeError
            If ``model_output`` is neither str nor dict.
        """
        if self._results_dict is None:
            if isinstance(self.model_output, str):
                self._results_dict = self._load_results_from_directory(
                    self.model_output
                )
            elif isinstance(self.model_output, dict):
                self._results_dict = self.model_output
            else:
                raise TypeError(
                    f"model_output must be str or dict, "
                    f"got {type(self.model_output)}"
                )
        return self._results_dict

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #

    def translate(self) -> "ModelResults":
        """
        Convert OSeMOSYS results to a ``ModelResults`` container.

        Returns
        -------
        ModelResults
            Harmonized, frozen result object.
        """
        from ..interfaces.results import (
            ModelResults,
            TopologyResult,
            SupplyResult,
        )

        rd = self.results_dict

        # 1. Build TopologyResult
        topology = self._extract_topology(rd)

        # 2. Build SupplyResult
        supply = self._extract_supply(rd)

        # 3. Objective
        objective = self._compute_objective(rd)

        # 4. Metadata
        metadata: Dict[str, object] = {
            "result_files": list(rd.keys()),
        }

        result = ModelResults(
            model_name="OSeMOSYS",
            topology=topology,
            supply=supply,
            objective=objective,
            metadata=metadata,
        )
        result.validate()
        return result

    # ------------------------------------------------------------------ #
    # convenience accessors (kept for backward compatibility)
    # ------------------------------------------------------------------ #

    def get_objective(self) -> float:
        """
        Get the total discounted cost (objective value).

        Returns
        -------
        float
            Sum of ``TotalDiscountedCost.VALUE``.
        """
        return self._compute_objective(self.results_dict)

    def get_optimal_capacity(
        self, technology: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get optimal capacity, optionally filtered by technology.

        Parameters
        ----------
        technology : str, optional
            Filter to a specific technology name.

        Returns
        -------
        pd.DataFrame
            ``TotalCapacityAnnual`` rows (or empty DataFrame).
        """
        cap_df = self.results_dict.get(
            "TotalCapacityAnnual", pd.DataFrame()
        )
        if technology and not cap_df.empty:
            cap_df = cap_df[cap_df["TECHNOLOGY"] == technology]
        return cap_df

    # ------------------------------------------------------------------ #
    # private helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _load_results_from_directory(
        results_dir: str,
    ) -> Dict[str, pd.DataFrame]:
        """
        Load all CSV files from a results directory.

        Parameters
        ----------
        results_dir : str
            Path to directory containing otoole result CSVs.

        Returns
        -------
        Dict[str, pd.DataFrame]
            Mapping of CSV stem name → DataFrame.

        Raises
        ------
        FileNotFoundError
            If ``results_dir`` does not exist.
        """
        results_path = Path(results_dir)
        if not results_path.exists():
            raise FileNotFoundError(
                f"Results directory not found: {results_dir}"
            )

        results: Dict[str, pd.DataFrame] = {}
        for csv_file in results_path.glob("*.csv"):
            name = csv_file.stem
            try:
                df = pd.read_csv(csv_file)
                results[name] = df
            except Exception as e:
                logger.warning(f"Failed to read {csv_file}: {e}")

        return results

    @staticmethod
    def _extract_topology(
        rd: Dict[str, pd.DataFrame],
    ) -> "TopologyResult":
        """
        Infer topology from OSeMOSYS result CSVs.

        Regions are deduced from the ``REGION`` column of any result
        table.  If ``Trade`` results are present, they become edges.

        Parameters
        ----------
        rd : Dict[str, pd.DataFrame]
            Loaded result CSVs.

        Returns
        -------
        TopologyResult
        """
        from ..interfaces.results import TopologyResult

        # Collect unique region names from all result DataFrames
        regions: set = set()
        for df in rd.values():
            if "REGION" in df.columns:
                regions.update(df["REGION"].unique())
        if not regions:
            # Fallback: single unnamed region
            regions = {"REGION1"}

        nodes = pd.DataFrame({"NAME": sorted(regions)})

        # Edges from Trade results (if present)
        trade_df = rd.get("Trade")
        edges: pd.DataFrame
        if trade_df is not None and not trade_df.empty:
            # Trade CSV typically has REGION, rr, YEAR, TIMESLICE, VALUE
            from_col = "REGION" if "REGION" in trade_df.columns else None
            to_col = "rr" if "rr" in trade_df.columns else None
            if from_col and to_col:
                agg = (
                    trade_df.groupby([from_col, to_col], as_index=False)
                    .agg({"VALUE": "sum"})
                )
                edges = pd.DataFrame(
                    {
                        "FROM": agg[from_col].values,
                        "TO": agg[to_col].values,
                        "CAPACITY": agg["VALUE"].abs().values,
                    }
                )
            else:
                edges = pd.DataFrame(
                    columns=["FROM", "TO", "CAPACITY"]
                )
        else:
            edges = pd.DataFrame(
                columns=["FROM", "TO", "CAPACITY"]
            )

        return TopologyResult(nodes=nodes, edges=edges)

    @staticmethod
    def _extract_supply(
        rd: Dict[str, pd.DataFrame],
    ) -> "SupplyResult":
        """
        Build a ``SupplyResult`` from OSeMOSYS capacity CSVs.

        Parameters
        ----------
        rd : Dict[str, pd.DataFrame]
            Loaded result CSVs.

        Returns
        -------
        SupplyResult
        """
        from ..interfaces.results import SupplyResult

        required = ["REGION", "TECHNOLOGY", "YEAR", "VALUE"]

        # -- Installed capacity --
        cap_df = rd.get("TotalCapacityAnnual", pd.DataFrame())
        if not cap_df.empty:
            cap_df = cap_df[required].copy()
        else:
            cap_df = pd.DataFrame(columns=required)

        # -- New capacity --
        new_df = rd.get("NewCapacity", pd.DataFrame())
        if not new_df.empty:
            new_df = new_df[required].copy()
        else:
            new_df = pd.DataFrame(columns=required)

        return SupplyResult(
            installed_capacity=cap_df,
            new_capacity=new_df,
        )

    @staticmethod
    def _compute_objective(
        rd: Dict[str, pd.DataFrame],
    ) -> float:
        """
        Sum ``TotalDiscountedCost.VALUE`` to obtain the scalar objective.

        Parameters
        ----------
        rd : Dict[str, pd.DataFrame]
            Loaded result CSVs.

        Returns
        -------
        float
            Total discounted system cost, or 0.0 if absent.
        """
        obj_df = rd.get("TotalDiscountedCost")
        if obj_df is not None and not obj_df.empty:
            return float(obj_df["VALUE"].sum())
        return 0.0
