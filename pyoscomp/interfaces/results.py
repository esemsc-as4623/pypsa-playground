# pyoscomp/interfaces/results.py

"""
Harmonized model-result containers for cross-model comparison.

This module defines immutable dataclasses that hold optimisation results
in a model-agnostic format.  Both ``PyPSAOutputTranslator`` and
``OSeMOSYSOutputTranslator`` produce a single ``ModelResults`` object,
enabling direct, apples-to-apples comparison of topology, installed
capacity, and (in the future) dispatch, costs, and emissions.

Design mirrors the *input* pipeline:

    ScenarioData  (immutable input interface)
         ↕
    ModelResults  (immutable output interface)

Each result group (``TopologyResult``, ``SupplyResult``, ...) is a
frozen dataclass with:

* A canonical DataFrame schema (documented in Attributes)
* A ``validate()`` method for internal consistency checks
* ``__eq__`` / ``__hash__`` delegated to ``dataclass(frozen=True)``
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


def _empty_df() -> pd.DataFrame:
    """Factory for creating empty DataFrames (optional fields)."""
    return pd.DataFrame()


def _check_required_columns(
    df: pd.DataFrame,
    required: frozenset,
    table_name: str,
) -> None:
    """Validate that ``df`` contains all ``required`` columns."""
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"{table_name} is missing columns: {sorted(missing)}"
        )


def _check_non_negative(
    df: pd.DataFrame,
    table_name: str,
    tol: float = -1e-8,
) -> None:
    """Validate that ``VALUE`` column is non-negative if present."""
    if "VALUE" in df.columns and (df["VALUE"] < tol).any():
        raise ValueError(
            f"{table_name} contains negative values"
        )


# ------------------------------------------------------------------
# TopologyResult
# ------------------------------------------------------------------

@dataclass(frozen=True)
class TopologyResult:
    """
    Model-agnostic representation of network topology.

    Attributes
    ----------
    nodes : pd.DataFrame
        One row per spatial node / region.
        Required columns: ``NAME`` (str).
        Optional columns: ``CARRIER`` (str, default ``'AC'``).
    edges : pd.DataFrame
        One row per inter-regional connection.
        Required columns: ``FROM`` (str), ``TO`` (str).
        Optional columns: ``CAPACITY`` (float, MW),
        ``CARRIER`` (str).
        Empty DataFrame for single-region models.

    Examples
    --------
    >>> topo = TopologyResult(
    ...     nodes=pd.DataFrame({'NAME': ['R1', 'R2']}),
    ...     edges=pd.DataFrame({
    ...         'FROM': ['R1'], 'TO': ['R2'],
    ...         'CAPACITY': [500.0]
    ...     }),
    ... )
    >>> topo.validate()
    """

    nodes: pd.DataFrame
    edges: pd.DataFrame = field(default_factory=_empty_df)

    def validate(self) -> None:
        """
        Check internal consistency of topology data.

        Raises
        ------
        ValueError
            If required columns are missing or edge references
            are not present in nodes.
        """
        if self.nodes.empty:
            raise ValueError("TopologyResult.nodes must not be empty")
        if "NAME" not in self.nodes.columns:
            raise ValueError(
                "TopologyResult.nodes must contain a 'NAME' column"
            )

        if not self.edges.empty:
            for col in ("FROM", "TO"):
                if col not in self.edges.columns:
                    raise ValueError(
                        f"TopologyResult.edges must contain "
                        f"a '{col}' column"
                    )
            node_names = set(self.nodes["NAME"])
            edge_refs = set(self.edges["FROM"]) | set(
                self.edges["TO"]
            )
            unknown = edge_refs - node_names
            if unknown:
                raise ValueError(
                    f"Edges reference unknown nodes: {unknown}"
                )

    @property
    def region_names(self) -> List[str]:
        """Return sorted list of region / node names."""
        return sorted(self.nodes["NAME"].tolist())


# ------------------------------------------------------------------
# SupplyResult
# ------------------------------------------------------------------

@dataclass(frozen=True)
class SupplyResult:
    """
    Model-agnostic representation of technology capacity results.

    All capacity values are in the same power unit (MW by default).
    The ``installed_capacity`` table gives the *total* capacity
    available in each year (existing + newly built).

    Attributes
    ----------
    installed_capacity : pd.DataFrame
        Total installed capacity after optimisation.
        Columns: ``REGION`` (str), ``TECHNOLOGY`` (str),
        ``YEAR`` (int), ``VALUE`` (float, MW).
    new_capacity : pd.DataFrame
        Newly built capacity in each year.
        Same columns as ``installed_capacity``.
        May be empty if the model does not report it.

    Examples
    --------
    >>> cap = pd.DataFrame({
    ...     'REGION': ['R1', 'R1'],
    ...     'TECHNOLOGY': ['SOLAR', 'WIND'],
    ...     'YEAR': [2030, 2030],
    ...     'VALUE': [500.0, 300.0],
    ... })
    >>> supply = SupplyResult(installed_capacity=cap)
    >>> supply.validate()
    """

    installed_capacity: pd.DataFrame
    new_capacity: pd.DataFrame = field(default_factory=_empty_df)

    # Required columns for capacity DataFrames
    _REQUIRED_COLS = frozenset(
        {"REGION", "TECHNOLOGY", "YEAR", "VALUE"}
    )

    def validate(self) -> None:
        """
        Check column schema and value constraints.

        Raises
        ------
        ValueError
            If required columns are missing or capacity is negative.
        """
        for attr_name in ("installed_capacity", "new_capacity"):
            df = getattr(self, attr_name)
            if df.empty:
                continue
            missing = self._REQUIRED_COLS - set(df.columns)
            if missing:
                raise ValueError(
                    f"SupplyResult.{attr_name} is missing "
                    f"columns: {missing}"
                )
            if (df["VALUE"] < -1e-8).any():
                raise ValueError(
                    f"SupplyResult.{attr_name} contains "
                    f"negative capacity values"
                )

    def get_capacity(
        self,
        region: Optional[str] = None,
        technology: Optional[str] = None,
        year: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Filter installed capacity by region, technology, or year.

        Parameters
        ----------
        region : str, optional
            Filter to a specific region.
        technology : str, optional
            Filter to a specific technology.
        year : int, optional
            Filter to a specific year.

        Returns
        -------
        pd.DataFrame
            Filtered view of ``installed_capacity``.
        """
        df = self.installed_capacity
        if region is not None:
            df = df[df["REGION"] == region]
        if technology is not None:
            df = df[df["TECHNOLOGY"] == technology]
        if year is not None:
            df = df[df["YEAR"] == year]
        return df


# ------------------------------------------------------------------
# DispatchResult
# ------------------------------------------------------------------


@dataclass(frozen=True)
class DispatchResult:
    """
    Harmonized representation of operational energy flows.

    Attributes
    ----------
    production : pd.DataFrame
        Energy produced by technologies.
        Columns: ``REGION``, ``TIMESLICE``, ``TECHNOLOGY``,
        ``FUEL``, ``YEAR``, ``VALUE``.
    use : pd.DataFrame
        Energy consumed by technologies.
        Columns: ``REGION``, ``TIMESLICE``, ``TECHNOLOGY``,
        ``FUEL``, ``YEAR``, ``VALUE``.
    curtailment : pd.DataFrame
        Curtailed available energy.
        Columns: ``REGION``, ``TIMESLICE``, ``TECHNOLOGY``,
        ``YEAR``, ``VALUE``.
    unmet_demand : pd.DataFrame
        Unserved demand by fuel.
        Columns: ``REGION``, ``TIMESLICE``, ``FUEL``, ``YEAR``,
        ``VALUE``.
    """

    production: pd.DataFrame = field(default_factory=_empty_df)
    use: pd.DataFrame = field(default_factory=_empty_df)
    curtailment: pd.DataFrame = field(default_factory=_empty_df)
    unmet_demand: pd.DataFrame = field(default_factory=_empty_df)

    _FLOW_COLS = frozenset(
        {"REGION", "TIMESLICE", "TECHNOLOGY", "FUEL", "YEAR", "VALUE"}
    )
    _CURTAIL_COLS = frozenset(
        {"REGION", "TIMESLICE", "TECHNOLOGY", "YEAR", "VALUE"}
    )
    _UNMET_COLS = frozenset(
        {"REGION", "TIMESLICE", "FUEL", "YEAR", "VALUE"}
    )

    def validate(self) -> None:
        """Check dispatch table schemas and non-negativity."""
        if not self.production.empty:
            _check_required_columns(
                self.production,
                self._FLOW_COLS,
                "DispatchResult.production",
            )
            _check_non_negative(self.production, "DispatchResult.production")
        if not self.use.empty:
            _check_required_columns(
                self.use,
                self._FLOW_COLS,
                "DispatchResult.use",
            )
            _check_non_negative(self.use, "DispatchResult.use")
        if not self.curtailment.empty:
            _check_required_columns(
                self.curtailment,
                self._CURTAIL_COLS,
                "DispatchResult.curtailment",
            )
            _check_non_negative(self.curtailment, "DispatchResult.curtailment")
        if not self.unmet_demand.empty:
            _check_required_columns(
                self.unmet_demand,
                self._UNMET_COLS,
                "DispatchResult.unmet_demand",
            )
            _check_non_negative(
                self.unmet_demand,
                "DispatchResult.unmet_demand",
            )


# ------------------------------------------------------------------
# StorageResult
# ------------------------------------------------------------------


@dataclass(frozen=True)
class StorageResult:
    """
    Harmonized representation of storage-service variables.

    Attributes
    ----------
    charge : pd.DataFrame
        Charging power/energy by timeslice.
        Columns: ``REGION``, ``TIMESLICE``, ``STORAGE_TECHNOLOGY``,
        ``YEAR``, ``VALUE``.
    discharge : pd.DataFrame
        Discharging power/energy by timeslice.
        Same columns as ``charge``.
    state_of_charge : pd.DataFrame
        State of charge by timeslice.
        Same columns as ``charge``.
    standing_loss : pd.DataFrame
        Storage standing losses by timeslice.
        Same columns as ``charge``.
    throughput : pd.DataFrame
        Annual storage throughput.
        Columns: ``REGION``, ``STORAGE_TECHNOLOGY``, ``YEAR``,
        ``VALUE``.
    equivalent_cycles : pd.DataFrame
        Annual equivalent full cycles.
        Columns: ``REGION``, ``STORAGE_TECHNOLOGY``, ``YEAR``,
        ``VALUE``.
    """

    charge: pd.DataFrame = field(default_factory=_empty_df)
    discharge: pd.DataFrame = field(default_factory=_empty_df)
    state_of_charge: pd.DataFrame = field(default_factory=_empty_df)
    standing_loss: pd.DataFrame = field(default_factory=_empty_df)
    throughput: pd.DataFrame = field(default_factory=_empty_df)
    equivalent_cycles: pd.DataFrame = field(default_factory=_empty_df)

    _TIMESLICE_COLS = frozenset(
        {
            "REGION",
            "TIMESLICE",
            "STORAGE_TECHNOLOGY",
            "YEAR",
            "VALUE",
        }
    )
    _ANNUAL_COLS = frozenset(
        {"REGION", "STORAGE_TECHNOLOGY", "YEAR", "VALUE"}
    )

    def validate(self) -> None:
        """Check storage table schemas and value constraints."""
        for name in (
            "charge",
            "discharge",
            "state_of_charge",
            "standing_loss",
        ):
            df = getattr(self, name)
            if df.empty:
                continue
            _check_required_columns(
                df,
                self._TIMESLICE_COLS,
                f"StorageResult.{name}",
            )
            _check_non_negative(df, f"StorageResult.{name}")

        for name in ("throughput", "equivalent_cycles"):
            df = getattr(self, name)
            if df.empty:
                continue
            _check_required_columns(
                df,
                self._ANNUAL_COLS,
                f"StorageResult.{name}",
            )
            _check_non_negative(df, f"StorageResult.{name}")


# ------------------------------------------------------------------
# EconomicsResult
# ------------------------------------------------------------------


@dataclass(frozen=True)
class EconomicsResult:
    """
    Harmonized representation of cost and value decomposition.

    Attributes
    ----------
    capex : pd.DataFrame
        Capital expenditure by technology/year.
        Columns: ``REGION``, ``TECHNOLOGY``, ``YEAR``, ``VALUE``.
    fixed_opex : pd.DataFrame
        Fixed operational cost by technology/year.
        Same columns as ``capex``.
    variable_opex : pd.DataFrame
        Variable operational cost by technology/year.
        Same columns as ``capex``.
    salvage : pd.DataFrame
        Salvage value by technology/year.
        Same columns as ``capex``.
    total_system_cost : pd.DataFrame
        Total system cost by region/year.
        Columns: ``REGION``, ``YEAR``, ``VALUE``.
    """

    capex: pd.DataFrame = field(default_factory=_empty_df)
    fixed_opex: pd.DataFrame = field(default_factory=_empty_df)
    variable_opex: pd.DataFrame = field(default_factory=_empty_df)
    salvage: pd.DataFrame = field(default_factory=_empty_df)
    total_system_cost: pd.DataFrame = field(default_factory=_empty_df)

    _TECH_COST_COLS = frozenset(
        {"REGION", "TECHNOLOGY", "YEAR", "VALUE"}
    )
    _SYSTEM_COLS = frozenset({"REGION", "YEAR", "VALUE"})

    def validate(self) -> None:
        """Check economics table schemas and value constraints."""
        for name in ("capex", "fixed_opex", "variable_opex", "salvage"):
            df = getattr(self, name)
            if df.empty:
                continue
            _check_required_columns(
                df,
                self._TECH_COST_COLS,
                f"EconomicsResult.{name}",
            )

        if not self.total_system_cost.empty:
            _check_required_columns(
                self.total_system_cost,
                self._SYSTEM_COLS,
                "EconomicsResult.total_system_cost",
            )


# ------------------------------------------------------------------
# TradeResult
# ------------------------------------------------------------------


@dataclass(frozen=True)
class TradeResult:
    """
    Harmonized representation of inter-regional trade flows.

    Attributes
    ----------
    flows : pd.DataFrame
        Directed trade flows.
        Columns: ``REGION`` (source), ``TO_REGION`` (sink),
        ``TIMESLICE``, ``FUEL``, ``YEAR``, ``VALUE``.
    """

    flows: pd.DataFrame = field(default_factory=_empty_df)

    _FLOW_COLS = frozenset(
        {"REGION", "TO_REGION", "TIMESLICE", "FUEL", "YEAR", "VALUE"}
    )

    def validate(self) -> None:
        """Check trade-flow schema and value constraints."""
        if self.flows.empty:
            return
        _check_required_columns(
            self.flows,
            self._FLOW_COLS,
            "TradeResult.flows",
        )


# ------------------------------------------------------------------
# ModelResults — aggregate container
# ------------------------------------------------------------------

@dataclass(frozen=True)
class ModelResults:
    """
    Immutable container for all harmonized model-optimisation results.

    This is the output-side counterpart of ``ScenarioData``.  Both
    ``PyPSAOutputTranslator`` and ``OSeMOSYSOutputTranslator`` produce
    a ``ModelResults`` instance with identical schema, enabling direct
    comparison via :func:`compare`.

    Attributes
    ----------
    model_name : str
        Identifier for the solver that produced these results
        (e.g. ``'PyPSA'``, ``'OSeMOSYS'``).
    topology : TopologyResult
        Spatial structure of the optimised model.
    supply : SupplyResult
        Technology capacity results.
    objective : float
        Scalar objective-function value (total system cost).
    metadata : dict
        Arbitrary key-value pairs (solver status, runtime, etc.).

    Examples
    --------
    >>> results = translator.translate()
    >>> results.topology.region_names
    ['REGION1']
    >>> results.supply.installed_capacity
       REGION  TECHNOLOGY  YEAR     VALUE
    0  REGION1    GAS_CCGT  2026  0.012684
    """

    model_name: str
    topology: TopologyResult
    supply: SupplyResult
    dispatch: DispatchResult = field(default_factory=DispatchResult)
    storage: StorageResult = field(default_factory=StorageResult)
    economics: EconomicsResult = field(default_factory=EconomicsResult)
    trade: TradeResult = field(default_factory=TradeResult)
    objective: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        """
        Validate all sub-results.

        Raises
        ------
        ValueError
            If any sub-result validation fails.
        """
        self.topology.validate()
        self.supply.validate()
        self.dispatch.validate()
        self.storage.validate()
        self.economics.validate()
        self.trade.validate()

    def summary(self) -> str:
        """
        Return a human-readable summary of results.

        Returns
        -------
        str
            Multi-line summary string.
        """
        cap_df = self.supply.installed_capacity
        n_techs = (
            cap_df["TECHNOLOGY"].nunique()
            if not cap_df.empty
            else 0
        )
        lines = [
            f"ModelResults ({self.model_name})",
            "=" * 40,
            f"Regions: {self.topology.region_names}",
            f"Connections: {len(self.topology.edges)}",
            f"Technologies with capacity: {n_techs}",
            f"Dispatch rows: {len(self.dispatch.production)}",
            f"Storage rows: {len(self.storage.charge)}",
            f"Trade rows: {len(self.trade.flows)}",
            f"Objective: {self.objective:.4f}",
        ]
        return "\n".join(lines)

    def __repr__(self) -> str:
        return self.summary()


# ------------------------------------------------------------------
# compare() — cross-model comparison helper
# ------------------------------------------------------------------

def compare(
    a: ModelResults,
    b: ModelResults,
) -> Dict[str, pd.DataFrame]:
    """
    Compare two ``ModelResults`` and return harmonized diff tables.

    Parameters
    ----------
    a : ModelResults
        First set of results (e.g. PyPSA).
    b : ModelResults
        Second set of results (e.g. OSeMOSYS).

    Returns
    -------
    Dict[str, pd.DataFrame]
        Dictionary with comparison DataFrames:

        ``'topology'``
            Columns: ``NODE``, ``IN_<a>``, ``IN_<b>``,
            ``MATCH``.
        ``'supply'``
            Columns: ``REGION``, ``TECHNOLOGY``, ``YEAR``,
            ``<a.model_name>`` (float), ``<b.model_name>`` (float),
            ``DIFF`` (float), ``MATCH`` (bool).
        ``'objective'``
            Single-row DataFrame with both objectives and diff.

    Examples
    --------
    >>> tables = compare(pypsa_results, osemosys_results)
    >>> print(tables['supply'])
    """
    result: Dict[str, pd.DataFrame] = {}

    # --- topology comparison ---
    result["topology"] = _compare_topology(a, b)

    # --- supply comparison ---
    result["supply"] = _compare_supply(a, b)

    # --- objective comparison ---
    result["objective"] = pd.DataFrame(
        {
            "model": [a.model_name, b.model_name, "diff"],
            "objective": [
                a.objective,
                b.objective,
                a.objective - b.objective,
            ],
        }
    )

    # --- dispatch comparison (production only for now) ---
    result["dispatch_production"] = _compare_optional_value_table(
        a.dispatch.production,
        b.dispatch.production,
        a.model_name,
        b.model_name,
        join_cols=["REGION", "TIMESLICE", "TECHNOLOGY", "FUEL", "YEAR"],
    )

    # --- storage comparison (throughput only for now) ---
    result["storage_throughput"] = _compare_optional_value_table(
        a.storage.throughput,
        b.storage.throughput,
        a.model_name,
        b.model_name,
        join_cols=["REGION", "STORAGE_TECHNOLOGY", "YEAR"],
    )

    # --- economics comparison (total cost by year/region) ---
    result["economics_total_system_cost"] = _compare_optional_value_table(
        a.economics.total_system_cost,
        b.economics.total_system_cost,
        a.model_name,
        b.model_name,
        join_cols=["REGION", "YEAR"],
    )

    # --- trade comparison ---
    result["trade_flows"] = _compare_optional_value_table(
        a.trade.flows,
        b.trade.flows,
        a.model_name,
        b.model_name,
        join_cols=["REGION", "TO_REGION", "TIMESLICE", "FUEL", "YEAR"],
    )

    return result


def _compare_topology(
    a: ModelResults, b: ModelResults
) -> pd.DataFrame:
    """
    Compare region / node presence across two model results.

    Returns
    -------
    pd.DataFrame
        Columns: NODE, IN_<a.model_name>, IN_<b.model_name>, MATCH.
    """
    nodes_a = set(a.topology.region_names)
    nodes_b = set(b.topology.region_names)
    all_nodes = sorted(nodes_a | nodes_b)

    col_a = f"IN_{a.model_name}"
    col_b = f"IN_{b.model_name}"

    rows = []
    for node in all_nodes:
        in_a = node in nodes_a
        in_b = node in nodes_b
        rows.append(
            {
                "NODE": node,
                col_a: in_a,
                col_b: in_b,
                "MATCH": in_a == in_b,
            }
        )
    return pd.DataFrame(rows)


def _compare_supply(
    a: ModelResults, b: ModelResults
) -> pd.DataFrame:
    """
    Compare installed capacity across two model results.

    Performs a full outer join on (REGION, TECHNOLOGY, YEAR) and
    computes absolute difference.

    Returns
    -------
    pd.DataFrame
        Columns: REGION, TECHNOLOGY, YEAR, <a.model_name>,
        <b.model_name>, DIFF, MATCH.
    """
    join_cols = ["REGION", "TECHNOLOGY", "YEAR"]
    col_a = a.model_name
    col_b = b.model_name

    df_a = a.supply.installed_capacity.rename(
        columns={"VALUE": col_a}
    )
    df_b = b.supply.installed_capacity.rename(
        columns={"VALUE": col_b}
    )

    merged = pd.merge(
        df_a[join_cols + [col_a]],
        df_b[join_cols + [col_b]],
        on=join_cols,
        how="outer",
    )
    merged[col_a] = merged[col_a].fillna(0.0)
    merged[col_b] = merged[col_b].fillna(0.0)
    merged["DIFF"] = merged[col_a] - merged[col_b]
    merged["MATCH"] = np.abs(merged["DIFF"]) < 1e-4

    return merged.sort_values(join_cols).reset_index(drop=True)


def _compare_optional_value_table(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    model_a: str,
    model_b: str,
    join_cols: List[str],
) -> pd.DataFrame:
    """
    Compare VALUE tables if present in either model result.

    Returns an empty DataFrame when both inputs are empty.
    """
    if df_a.empty and df_b.empty:
        return pd.DataFrame()

    col_a = model_a
    col_b = model_b

    left = pd.DataFrame(columns=join_cols + [col_a])
    right = pd.DataFrame(columns=join_cols + [col_b])

    if not df_a.empty:
        left = df_a[join_cols + ["VALUE"]].rename(
            columns={"VALUE": col_a}
        )
    if not df_b.empty:
        right = df_b[join_cols + ["VALUE"]].rename(
            columns={"VALUE": col_b}
        )

    merged = pd.merge(
        left,
        right,
        on=join_cols,
        how="outer",
    )
    merged[col_a] = merged[col_a].fillna(0.0)
    merged[col_b] = merged[col_b].fillna(0.0)
    merged["DIFF"] = merged[col_a] - merged[col_b]
    merged["MATCH"] = np.abs(merged["DIFF"]) < 1e-4

    return merged.sort_values(join_cols).reset_index(drop=True)
