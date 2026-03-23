# tests/test_interfaces/test_results.py

"""Tests for harmonized output result interfaces."""

import pandas as pd
import pytest

from pyoscomp.interfaces import (
    DispatchResult,
    EconomicsResult,
    ModelResults,
    StorageResult,
    SupplyResult,
    TopologyResult,
    TradeResult,
    compare,
)


def _base_topology() -> TopologyResult:
    return TopologyResult(nodes=pd.DataFrame({"NAME": ["R1"]}))


def _base_supply(value: float = 1.0) -> SupplyResult:
    return SupplyResult(
        installed_capacity=pd.DataFrame(
            {
                "REGION": ["R1"],
                "TECHNOLOGY": ["WIND"],
                "YEAR": [2030],
                "VALUE": [value],
            }
        )
    )


def test_dispatch_validate_missing_column_raises() -> None:
    dispatch = DispatchResult(
        production=pd.DataFrame(
            {
                "REGION": ["R1"],
                "TIMESLICE": ["TS1"],
                "TECHNOLOGY": ["WIND"],
                # missing FUEL
                "YEAR": [2030],
                "VALUE": [10.0],
            }
        )
    )

    with pytest.raises(ValueError, match="missing columns"):
        dispatch.validate()


def test_storage_validate_non_negative_raises() -> None:
    storage = StorageResult(
        charge=pd.DataFrame(
            {
                "REGION": ["R1"],
                "TIMESLICE": ["TS1"],
                "STORAGE_TECHNOLOGY": ["BATTERY"],
                "YEAR": [2030],
                "VALUE": [-0.1],
            }
        )
    )

    with pytest.raises(ValueError, match="negative"):
        storage.validate()


def test_model_results_validate_passes_with_optional_domains_empty() -> None:
    results = ModelResults(
        model_name="PyPSA",
        topology=_base_topology(),
        supply=_base_supply(),
    )

    results.validate()


def test_compare_includes_new_domain_tables() -> None:
    dispatch = DispatchResult(
        production=pd.DataFrame(
            {
                "REGION": ["R1"],
                "TIMESLICE": ["TS1"],
                "TECHNOLOGY": ["WIND"],
                "FUEL": ["ELC"],
                "YEAR": [2030],
                "VALUE": [3.0],
            }
        )
    )
    storage = StorageResult(
        throughput=pd.DataFrame(
            {
                "REGION": ["R1"],
                "STORAGE_TECHNOLOGY": ["BATTERY"],
                "YEAR": [2030],
                "VALUE": [5.0],
            }
        )
    )
    economics = EconomicsResult(
        total_system_cost=pd.DataFrame(
            {
                "REGION": ["R1"],
                "YEAR": [2030],
                "VALUE": [100.0],
            }
        )
    )
    trade = TradeResult(
        flows=pd.DataFrame(
            {
                "REGION": ["R1"],
                "TO_REGION": ["R2"],
                "TIMESLICE": ["TS1"],
                "FUEL": ["ELC"],
                "YEAR": [2030],
                "VALUE": [2.0],
            }
        )
    )

    a = ModelResults(
        model_name="PyPSA",
        topology=_base_topology(),
        supply=_base_supply(1.0),
        dispatch=dispatch,
        storage=storage,
        economics=economics,
        trade=trade,
        objective=100.0,
    )
    b = ModelResults(
        model_name="OSeMOSYS",
        topology=_base_topology(),
        supply=_base_supply(1.2),
        dispatch=dispatch,
        storage=storage,
        economics=economics,
        trade=trade,
        objective=101.0,
    )

    tables = compare(a, b)

    assert "dispatch_production" in tables
    assert "storage_throughput" in tables
    assert "economics_total_system_cost" in tables
    assert "trade_flows" in tables
    assert not tables["dispatch_production"].empty
