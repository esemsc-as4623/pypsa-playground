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
