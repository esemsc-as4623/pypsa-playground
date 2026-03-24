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
            DispatchResult,
            EconomicsResult,
            ModelResults,
            StorageResult,
            TopologyResult,
            SupplyResult,
            TradeResult,
        )

        rd = self.results_dict

        # 1. Build TopologyResult
        topology = self._extract_topology(rd)

        # 2. Build SupplyResult
        supply = self._extract_supply(rd)

        # 3. Objective
        objective = self._compute_objective(rd)

        # 4. Additional harmonized outputs
        dispatch = self._extract_dispatch(rd)
        storage = self._extract_storage(rd)
        economics = self._extract_economics(rd)
        trade = self._extract_trade(rd)

        # 5. Metadata
        metadata: Dict[str, object] = {
            "result_files": list(rd.keys()),
        }

        result = ModelResults(
            model_name="OSeMOSYS",
            topology=topology,
            supply=supply,
            dispatch=dispatch,
            storage=storage,
            economics=economics,
            trade=trade,
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

        # Add destination regions from Trade table when available.
        trade_df = rd.get("Trade")
        if trade_df is not None and not trade_df.empty:
            to_col = OSeMOSYSOutputTranslator._resolve_trade_to_column(trade_df)
            if to_col and to_col in trade_df.columns:
                regions.update(trade_df[to_col].dropna().unique())

        if not regions:
            # Fallback: single unnamed region
            regions = {"REGION1"}

        nodes = pd.DataFrame({"NAME": sorted(regions)})

        # Edges from Trade results (if present)
        edges: pd.DataFrame
        if trade_df is not None and not trade_df.empty:
            # Trade CSV destination column names vary across pipelines.
            from_col = "REGION" if "REGION" in trade_df.columns else None
            to_col = OSeMOSYSOutputTranslator._resolve_trade_to_column(
                trade_df
            )
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
    def _resolve_trade_to_column(trade_df: pd.DataFrame) -> Optional[str]:
        """Resolve destination-region column name in Trade outputs."""
        for candidate in ("TO_REGION", "rr", "_REGION", "REGION_2"):
            if candidate in trade_df.columns:
                return candidate

        # pandas may rename duplicate REGION columns as REGION.1
        if "REGION.1" in trade_df.columns:
            return "REGION.1"

        # Last resort: use any non-source column ending with REGION
        for col in trade_df.columns:
            if col != "REGION" and "REGION" in col.upper():
                return col

        return None

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

    @staticmethod
    def _extract_dispatch(rd: Dict[str, pd.DataFrame]) -> "DispatchResult":
        """
        Build DispatchResult from standard OSeMOSYS outputs.

        OSeMOSYS outputs used:
        - ``ProductionByTechnology[r,l,t,f,y]`` → production
        - ``UseByTechnology[r,l,t,f,y]``         → use (fuel consumed)
        - Curtailment is not a native OSeMOSYS variable; it is left empty
          unless ``TotalAnnualTechnologyActivityUpperLimit`` CSVs are provided
          alongside the results, which is uncommon.  Curtailment analysis
          should instead be performed externally using scenario inputs.
        """
        from ..interfaces.results import DispatchResult

        flow_cols = [
            "REGION",
            "TIMESLICE",
            "TECHNOLOGY",
            "FUEL",
            "YEAR",
            "VALUE",
        ]

        production = rd.get("ProductionByTechnology", pd.DataFrame())
        if not production.empty and all(c in production.columns for c in flow_cols):
            production = production[flow_cols].copy()
        else:
            production = pd.DataFrame(columns=flow_cols)

        use = rd.get("UseByTechnology", pd.DataFrame())
        if not use.empty and all(c in use.columns for c in flow_cols):
            use = use[flow_cols].copy()
        else:
            use = pd.DataFrame(columns=flow_cols)

        # Curtailment: not a native OSeMOSYS output; left empty.
        # (To compute curtailment, compare ProductionByTechnology against
        # CapacityFactor × TotalCapacityAnnual × YearSplit × CAU using
        # scenario input data alongside results.)
        curtailment = pd.DataFrame(
            columns=["REGION", "TIMESLICE", "TECHNOLOGY", "YEAR", "VALUE"]
        )
        unmet = pd.DataFrame(
            columns=["REGION", "TIMESLICE", "FUEL", "YEAR", "VALUE"]
        )

        return DispatchResult(
            production=production,
            use=use,
            curtailment=curtailment,
            unmet_demand=unmet,
        )

    @staticmethod
    def _extract_storage(rd: Dict[str, pd.DataFrame]) -> "StorageResult":
        """
        Build StorageResult from OSeMOSYS storage output variables.

        OSeMOSYS storage outputs used:

        - ``NewStorageCapacity[r,s,y]``          → installed_energy_capacity (MWh, new)
        - ``AccumulatedNewStorageCapacity[r,s,y]``→ cumulative new energy capacity
        - ``StorageLevelYearStart[r,s,y]``        → annual state_of_charge proxy
        - ``StorageLevelDayTypeFinish[r,s,ls,ld,y]`` → timeslice-level SOC (if available)

        Charge / discharge throughput are derived from ``UseByTechnology`` /
        ``ProductionByTechnology`` for technologies linked to storage via
        ``TechnologyToStorage`` / ``TechnologyFromStorage``.  Since output
        CSVs do not carry these linkages, we fall back to using the total
        activity of technologies whose names contain the ``_CHARGE`` /
        ``_DISCHARGE`` suffix convention.
        """
        from ..interfaces.results import StorageResult

        annual_cols = ["REGION", "STORAGE_TECHNOLOGY", "YEAR", "VALUE"]
        ts_cols = ["REGION", "TIMESLICE", "STORAGE_TECHNOLOGY", "YEAR", "VALUE"]

        def _rename_storage_col(df: pd.DataFrame, src: str) -> pd.DataFrame:
            """Rename STORAGE column to STORAGE_TECHNOLOGY."""
            if src in df.columns:
                return df.rename(columns={src: "STORAGE_TECHNOLOGY"})
            return df

        # --- Installed energy capacity (MWh): new additions per year ---
        new_stor = rd.get("NewStorageCapacity", pd.DataFrame())
        if not new_stor.empty and "STORAGE" in new_stor.columns:
            installed_energy = _rename_storage_col(
                new_stor[["REGION", "STORAGE", "YEAR", "VALUE"]].copy(), "STORAGE"
            )
        else:
            installed_energy = pd.DataFrame(columns=annual_cols)

        # Accumulated (cumulative) storage capacity if available
        acc_stor = rd.get("AccumulatedNewStorageCapacity", pd.DataFrame())
        if not acc_stor.empty and "STORAGE" in acc_stor.columns:
            # Use accumulated as the "installed" total when available
            installed_energy = _rename_storage_col(
                acc_stor[["REGION", "STORAGE", "YEAR", "VALUE"]].copy(), "STORAGE"
            )

        # --- State of charge: StorageLevelYearStart (annual resolution) ---
        soc_annual = rd.get("StorageLevelYearStart", pd.DataFrame())
        soc_ts = pd.DataFrame(columns=ts_cols)
        if not soc_annual.empty and "STORAGE" in soc_annual.columns:
            # Map to timeslice-level structure using a sentinel TIMESLICE="YEAR_START"
            soc_yr = _rename_storage_col(
                soc_annual[["REGION", "STORAGE", "YEAR", "VALUE"]].copy(), "STORAGE"
            )
            soc_yr.insert(1, "TIMESLICE", "YEAR_START")
            soc_ts = soc_yr[ts_cols]

        # Prefer per-daytype SOC if available (richer temporal resolution)
        soc_dtf = rd.get("StorageLevelDayTypeFinish", pd.DataFrame())
        if not soc_dtf.empty and "STORAGE" in soc_dtf.columns:
            # Columns: REGION, STORAGE, SEASON, DAYTYPE, YEAR, VALUE (otoole convention)
            # Collapse SEASON+DAYTYPE into a synthetic TIMESLICE label
            soc_dtf = soc_dtf.copy()
            soc_dtf = _rename_storage_col(soc_dtf, "STORAGE")
            season_col = next(
                (c for c in soc_dtf.columns if "SEASON" in c.upper()), None
            )
            daytype_col = next(
                (c for c in soc_dtf.columns if "DAYTYPE" in c.upper()), None
            )
            if season_col and daytype_col:
                soc_dtf["TIMESLICE"] = (
                    soc_dtf[season_col].astype(str)
                    + "_"
                    + soc_dtf[daytype_col].astype(str)
                )
                soc_ts = soc_dtf[ts_cols]

        # --- Charge / discharge throughput ---
        # Attempt to use ProductionByTechnology for technologies with DISCHARGE
        # and UseByTechnology for CHARGE techs (naming convention fallback).
        prod = rd.get("ProductionByTechnology", pd.DataFrame())
        use = rd.get("UseByTechnology", pd.DataFrame())

        discharge_rows = []
        charge_rows = []

        for df, store_list, is_charge in [
            (prod, discharge_rows, False),
            (use, charge_rows, True),
        ]:
            if df.empty or "TECHNOLOGY" not in df.columns:
                continue
            # Heuristic: techs with DISCHARGE or CHARGE in name
            pattern = "CHARGE" if is_charge else "DISCHARGE"
            mask = df["TECHNOLOGY"].astype(str).str.contains(pattern, case=False)
            sub = df[mask]
            if sub.empty:
                continue
            for _, row in sub.iterrows():
                tech = str(row["TECHNOLOGY"])
                # Derive storage name: strip _CHARGE / _DISCHARGE suffix
                stor_name = (
                    tech.replace("_CHARGE", "").replace("_DISCHARGE", "")
                       .replace("_CHG", "").replace("_DIS", "")
                )
                timeslice = str(row.get("TIMESLICE", "ANNUAL"))
                store_list.append(
                    {
                        "REGION": str(row["REGION"]),
                        "TIMESLICE": timeslice,
                        "STORAGE_TECHNOLOGY": stor_name,
                        "YEAR": int(row["YEAR"]),
                        "VALUE": float(row["VALUE"]),
                    }
                )

        charge = pd.DataFrame(charge_rows, columns=ts_cols)
        discharge = pd.DataFrame(discharge_rows, columns=ts_cols)

        if not charge.empty:
            charge = charge.groupby(ts_cols[:-1], as_index=False)["VALUE"].sum()
        if not discharge.empty:
            discharge = discharge.groupby(ts_cols[:-1], as_index=False)["VALUE"].sum()

        # Throughput = charge + discharge energy (total energy moved)
        throughput = pd.DataFrame(columns=annual_cols)
        if not charge.empty or not discharge.empty:
            both = pd.concat([charge, discharge], ignore_index=True)
            throughput = both.groupby(
                ["REGION", "STORAGE_TECHNOLOGY", "YEAR"], as_index=False
            )["VALUE"].sum()

        return StorageResult(
            charge=charge,
            discharge=discharge,
            state_of_charge=soc_ts,
            throughput=throughput,
            installed_energy_capacity=installed_energy,
        )

    @staticmethod
    def _extract_economics(rd: Dict[str, pd.DataFrame]) -> "EconomicsResult":
        """
        Build EconomicsResult from standard OSeMOSYS cost outputs.

        OSeMOSYS cost outputs used:

        - ``DiscountedCapitalInvestment[r,t,y]``   → capex
          (``CapitalInvestment`` is undiscounted; we use the discounted
           version so costs are comparable to PyPSA multi-period objective)
        - ``AnnualFixedOperatingCost[r,t,y]``      → fixed_opex (undiscounted)
        - ``AnnualVariableOperatingCost[r,t,y]``   → variable_opex (undiscounted)
        - ``DiscountedSalvageValue[r,t,y]``        → salvage
        - ``TotalDiscountedCost[r,y]``             → total_system_cost
        - ``TotalDiscountedStorageCost[r,s,y]``    → included in total but not
          disaggregated at technology level (OSeMOSYS tracks storage costs
          separately; they appear in TotalDiscountedCost)
        """
        from ..interfaces.results import EconomicsResult

        tech_cols = ["REGION", "TECHNOLOGY", "YEAR", "VALUE"]

        def _safe_get(name: str, cols) -> pd.DataFrame:
            df = rd.get(name, pd.DataFrame())
            if not df.empty and all(c in df.columns for c in cols):
                return df[cols].copy()
            return pd.DataFrame(columns=cols)

        # Use DiscountedCapitalInvestment for parity with PyPSA objective.
        # Fall back to undiscounted CapitalInvestment if not available.
        capex = _safe_get("DiscountedCapitalInvestment", tech_cols)
        if capex.empty:
            capex = _safe_get("CapitalInvestment", tech_cols)

        fixed = _safe_get("AnnualFixedOperatingCost", tech_cols)
        variable = _safe_get("AnnualVariableOperatingCost", tech_cols)
        salvage = _safe_get("DiscountedSalvageValue", tech_cols)

        total = _safe_get("TotalDiscountedCost", ["REGION", "YEAR", "VALUE"])

        return EconomicsResult(
            capex=capex,
            fixed_opex=fixed,
            variable_opex=variable,
            salvage=salvage,
            total_system_cost=total,
        )

    @staticmethod
    def _extract_trade(rd: Dict[str, pd.DataFrame]) -> "TradeResult":
        """Build TradeResult from Trade output, if available."""
        from ..interfaces.results import TradeResult

        trade_df = rd.get("Trade", pd.DataFrame())
        if trade_df.empty:
            return TradeResult()

        to_col = OSeMOSYSOutputTranslator._resolve_trade_to_column(trade_df)
        if to_col is None:
            return TradeResult()

        needed = ["REGION", to_col, "TIMESLICE", "FUEL", "YEAR", "VALUE"]
        missing = [c for c in needed if c not in trade_df.columns]
        if missing:
            return TradeResult()

        flows = trade_df[needed].rename(columns={to_col: "TO_REGION"})
        return TradeResult(flows=flows)
