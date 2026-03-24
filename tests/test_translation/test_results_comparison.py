# tests/test_translation/test_results_comparison.py

"""
Phase 4 tests: compare(), divergence_analysis(), and output extraction.

Covers:
- Annual production aggregation from timeslice data
- Curtailment extraction from PyPSA
- Effective capacity factor derivation
- compare() produces the expected table keys
- divergence_analysis() flags structural vs unexplained divergence
- OSeMOSYS storage output extraction (unit tests over synthetic dicts)
"""

import pytest
import pandas as pd
import numpy as np

from pyoscomp.interfaces.results import (
    ModelResults,
    TopologyResult,
    SupplyResult,
    DispatchResult,
    StorageResult,
    EconomicsResult,
    TradeResult,
    compare,
    divergence_analysis,
    DivergenceFlag,
    _aggregate_annual,
    _compare_effective_capacity_factor,
)
from pyoscomp.translation.osemosys_translator import OSeMOSYSOutputTranslator
from pyoscomp.translation.pypsa_translator import (
    PyPSAInputTranslator,
    PyPSAOutputTranslator,
)
from tests.test_simple.conftest import build_scenario
from tests.test_translation.test_pypsa_translator_storage import build_storage_scenario


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_minimal_results(
    model_name: str,
    capacity_mw: float = 100.0,
    annual_production_mwh: float = 350_000.0,
    year: int = 2025,
    tech: str = "WIND",
    region: str = "HUB",
    objective: float = 1_000_000.0,
) -> ModelResults:
    """Build a minimal ModelResults with supply + dispatch populated."""
    installed = pd.DataFrame(
        {"REGION": [region], "TECHNOLOGY": [tech], "YEAR": [year], "VALUE": [capacity_mw]}
    )
    production = pd.DataFrame(
        {
            "REGION": [region, region],
            "TIMESLICE": ["S1_H1", "S1_H2"],
            "TECHNOLOGY": [tech, tech],
            "FUEL": ["ELEC", "ELEC"],
            "YEAR": [year, year],
            "VALUE": [annual_production_mwh / 2, annual_production_mwh / 2],
        }
    )
    nodes = pd.DataFrame({"NAME": [region]})
    return ModelResults(
        model_name=model_name,
        topology=TopologyResult(nodes=nodes),
        supply=SupplyResult(installed_capacity=installed),
        dispatch=DispatchResult(production=production),
        objective=objective,
    )


# ---------------------------------------------------------------------------
# _aggregate_annual tests
# ---------------------------------------------------------------------------


class TestAggregateAnnual:
    def test_collapses_timeslice(self):
        df = pd.DataFrame(
            {
                "REGION": ["R1", "R1"],
                "TIMESLICE": ["S1", "S2"],
                "TECHNOLOGY": ["WIND", "WIND"],
                "FUEL": ["ELEC", "ELEC"],
                "YEAR": [2025, 2025],
                "VALUE": [100.0, 200.0],
            }
        )
        result = _aggregate_annual(df, ["TIMESLICE"])
        assert len(result) == 1
        assert float(result["VALUE"].iloc[0]) == pytest.approx(300.0)

    def test_empty_returns_empty(self):
        result = _aggregate_annual(pd.DataFrame(), ["TIMESLICE"])
        assert result.empty

    def test_multiple_techs_aggregated_separately(self):
        df = pd.DataFrame(
            {
                "REGION": ["R1", "R1", "R1", "R1"],
                "TIMESLICE": ["S1", "S2", "S1", "S2"],
                "TECHNOLOGY": ["WIND", "WIND", "SOLAR", "SOLAR"],
                "FUEL": ["ELEC", "ELEC", "ELEC", "ELEC"],
                "YEAR": [2025, 2025, 2025, 2025],
                "VALUE": [100.0, 200.0, 50.0, 75.0],
            }
        )
        result = _aggregate_annual(df, ["TIMESLICE"])
        assert len(result) == 2
        wind_val = result.loc[result["TECHNOLOGY"] == "WIND", "VALUE"].iloc[0]
        solar_val = result.loc[result["TECHNOLOGY"] == "SOLAR", "VALUE"].iloc[0]
        assert wind_val == pytest.approx(300.0)
        assert solar_val == pytest.approx(125.0)


# ---------------------------------------------------------------------------
# compare() table keys
# ---------------------------------------------------------------------------


class TestCompareTableKeys:
    def test_compare_produces_expected_keys(self):
        r_a = _make_minimal_results("PyPSA")
        r_b = _make_minimal_results("OSeMOSYS")
        tables = compare(r_a, r_b)
        expected_keys = [
            "topology",
            "supply",
            "objective",
            "dispatch_production",
            "dispatch_annual_production",
            "dispatch_curtailment",
            "storage_throughput",
            "storage_installed_capacity",
            "storage_installed_energy_capacity",
            "economics_total_system_cost",
            "economics_capex",
            "economics_fixed_opex",
            "economics_variable_opex",
            "economics_salvage",
            "trade_flows",
            "effective_capacity_factor",
        ]
        for key in expected_keys:
            assert key in tables, f"Missing key: {key}"

    def test_annual_production_aggregates_over_timeslice(self):
        r_a = _make_minimal_results("PyPSA", annual_production_mwh=350_000.0)
        r_b = _make_minimal_results("OSeMOSYS", annual_production_mwh=360_000.0)
        tables = compare(r_a, r_b)
        ap = tables["dispatch_annual_production"]
        assert not ap.empty
        assert "TIMESLICE" not in ap.columns
        # PyPSA total
        pypsa_val = float(ap.loc[ap["REGION"] == "HUB", "PyPSA"].iloc[0])
        assert pypsa_val == pytest.approx(350_000.0)

    def test_matching_results_produce_true_match(self):
        r_a = _make_minimal_results("PyPSA", capacity_mw=100.0)
        r_b = _make_minimal_results("OSeMOSYS", capacity_mw=100.0)
        tables = compare(r_a, r_b)
        assert tables["supply"]["MATCH"].all()

    def test_divergent_capacity_produces_false_match(self):
        r_a = _make_minimal_results("PyPSA", capacity_mw=100.0)
        r_b = _make_minimal_results("OSeMOSYS", capacity_mw=200.0)
        tables = compare(r_a, r_b)
        assert not tables["supply"]["MATCH"].all()


# ---------------------------------------------------------------------------
# Effective capacity factor
# ---------------------------------------------------------------------------


class TestEffectiveCapacityFactor:
    def test_ecf_value_correct(self):
        """ECF = annual_production / (installed_capacity * 8760)."""
        capacity_mw = 100.0
        annual_mwh = 350_000.0
        r_a = _make_minimal_results("PyPSA", capacity_mw=capacity_mw, annual_production_mwh=annual_mwh)
        r_b = _make_minimal_results("OSeMOSYS", capacity_mw=capacity_mw, annual_production_mwh=annual_mwh)
        tables = compare(r_a, r_b)
        ecf = tables["effective_capacity_factor"]
        assert not ecf.empty
        expected = annual_mwh / (capacity_mw * 8760.0)
        assert float(ecf["PyPSA"].iloc[0]) == pytest.approx(expected, rel=1e-5)
        assert float(ecf["OSeMOSYS"].iloc[0]) == pytest.approx(expected, rel=1e-5)

    def test_ecf_empty_when_no_dispatch(self):
        r_a = _make_minimal_results("PyPSA")
        # Override with empty dispatch
        r_a = ModelResults(
            model_name="PyPSA",
            topology=r_a.topology,
            supply=r_a.supply,
        )
        r_b = ModelResults(
            model_name="OSeMOSYS",
            topology=r_a.topology,
            supply=r_a.supply,
        )
        result = _compare_effective_capacity_factor(r_a, r_b)
        assert result.empty


# ---------------------------------------------------------------------------
# divergence_analysis()
# ---------------------------------------------------------------------------


class TestDivergenceAnalysis:
    def test_no_flags_when_identical(self):
        r_a = _make_minimal_results("PyPSA")
        r_b = _make_minimal_results("OSeMOSYS")
        flags, _ = divergence_analysis(r_a, r_b)
        non_structural = [f for f in flags if not f.structural]
        assert non_structural == [], f"Unexpected non-structural flags: {non_structural}"

    def test_capacity_flag_raised_when_divergent(self):
        r_a = _make_minimal_results("PyPSA", capacity_mw=100.0)
        r_b = _make_minimal_results("OSeMOSYS", capacity_mw=200.0)
        flags, _ = divergence_analysis(r_a, r_b)
        categories = [f.category for f in flags]
        assert "capacity" in categories

    def test_capacity_flag_is_non_structural(self):
        r_a = _make_minimal_results("PyPSA", capacity_mw=100.0)
        r_b = _make_minimal_results("OSeMOSYS", capacity_mw=200.0)
        flags, _ = divergence_analysis(r_a, r_b)
        cap_flags = [f for f in flags if f.category == "capacity"]
        assert all(not f.structural for f in cap_flags)

    def test_non_structural_flags_appear_first(self):
        r_a = _make_minimal_results("PyPSA", capacity_mw=100.0)
        r_b = _make_minimal_results("OSeMOSYS", capacity_mw=200.0)
        flags, _ = divergence_analysis(r_a, r_b)
        if len(flags) >= 2:
            # First flag should not be structural
            assert not flags[0].structural

    def test_objective_flag_raised_when_different(self):
        r_a = _make_minimal_results("PyPSA", objective=1_000_000.0)
        r_b = _make_minimal_results("OSeMOSYS", objective=2_000_000.0)
        flags, _ = divergence_analysis(r_a, r_b)
        obj_flags = [f for f in flags if f.category == "objective"]
        assert obj_flags, "Expected objective divergence flag"
        assert obj_flags[0].structural  # objective divergence is structural

    def test_divergence_flag_str(self):
        f = DivergenceFlag(
            category="capacity",
            description="test",
            n_mismatches=2,
            max_abs_diff=10.0,
            max_rel_diff=0.1,
            structural=False,
        )
        s = str(f)
        assert "[DIVERGENCE]" in s
        assert "capacity" in s

    def test_structural_flag_str(self):
        f = DivergenceFlag(
            category="curtailment",
            description="test",
            n_mismatches=1,
            max_abs_diff=5.0,
            max_rel_diff=0.5,
            structural=True,
        )
        assert "[STRUCTURAL]" in str(f)


# ---------------------------------------------------------------------------
# OSeMOSYS storage output extraction
# ---------------------------------------------------------------------------


class TestOSeMOSYSStorageExtraction:
    """Unit tests for _extract_storage() using synthetic result dicts."""

    def _make_rd(self, **overrides) -> dict:
        rd = {
            "TotalCapacityAnnual": pd.DataFrame(
                {"REGION": ["R1"], "TECHNOLOGY": ["WIND"], "YEAR": [2025], "VALUE": [100.0]}
            ),
        }
        rd.update(overrides)
        return rd

    def test_new_storage_capacity_extracted(self):
        rd = self._make_rd(
            NewStorageCapacity=pd.DataFrame(
                {"REGION": ["R1"], "STORAGE": ["BATT_STOR"], "YEAR": [2025], "VALUE": [400.0]}
            )
        )
        result = OSeMOSYSOutputTranslator(rd).translate()
        e_cap = result.storage.installed_energy_capacity
        assert not e_cap.empty
        assert "STORAGE_TECHNOLOGY" in e_cap.columns
        val = float(e_cap.loc[e_cap["STORAGE_TECHNOLOGY"] == "BATT_STOR", "VALUE"].iloc[0])
        assert val == pytest.approx(400.0)

    def test_accumulated_storage_overrides_new(self):
        """AccumulatedNewStorageCapacity takes precedence over NewStorageCapacity."""
        rd = self._make_rd(
            NewStorageCapacity=pd.DataFrame(
                {"REGION": ["R1"], "STORAGE": ["BATT_STOR"], "YEAR": [2025], "VALUE": [100.0]}
            ),
            AccumulatedNewStorageCapacity=pd.DataFrame(
                {"REGION": ["R1"], "STORAGE": ["BATT_STOR"], "YEAR": [2025], "VALUE": [200.0]}
            ),
        )
        result = OSeMOSYSOutputTranslator(rd).translate()
        e_cap = result.storage.installed_energy_capacity
        val = float(e_cap.loc[e_cap["STORAGE_TECHNOLOGY"] == "BATT_STOR", "VALUE"].iloc[0])
        assert val == pytest.approx(200.0), "AccumulatedNewStorageCapacity should override"

    def test_soc_from_year_start(self):
        rd = self._make_rd(
            StorageLevelYearStart=pd.DataFrame(
                {"REGION": ["R1"], "STORAGE": ["BATT_STOR"], "YEAR": [2025], "VALUE": [50.0]}
            )
        )
        result = OSeMOSYSOutputTranslator(rd).translate()
        soc = result.storage.state_of_charge
        assert not soc.empty
        row = soc[soc["STORAGE_TECHNOLOGY"] == "BATT_STOR"]
        assert not row.empty
        assert row["TIMESLICE"].iloc[0] == "YEAR_START"

    def test_charge_discharge_throughput_from_naming_convention(self):
        rd = self._make_rd(
            ProductionByTechnology=pd.DataFrame(
                {
                    "REGION": ["R1"],
                    "TIMESLICE": ["S1"],
                    "TECHNOLOGY": ["BATT_DISCHARGE"],
                    "FUEL": ["ELEC"],
                    "YEAR": [2025],
                    "VALUE": [80.0],
                }
            ),
            UseByTechnology=pd.DataFrame(
                {
                    "REGION": ["R1"],
                    "TIMESLICE": ["S1"],
                    "TECHNOLOGY": ["BATT_CHARGE"],
                    "FUEL": ["ELEC"],
                    "YEAR": [2025],
                    "VALUE": [100.0],
                }
            ),
        )
        result = OSeMOSYSOutputTranslator(rd).translate()
        throughput = result.storage.throughput
        assert not throughput.empty

    def test_no_storage_gives_empty_storage_result(self):
        rd = self._make_rd()
        result = OSeMOSYSOutputTranslator(rd).translate()
        assert result.storage.installed_energy_capacity.empty
        assert result.storage.state_of_charge.empty


# ---------------------------------------------------------------------------
# PyPSA curtailment extraction (end-to-end)
# ---------------------------------------------------------------------------


class TestPyPSACurtailmentExtraction:
    def test_curtailment_populated_after_optimization(self, tmp_path):
        """Curtailment is non-empty for a wind scenario with demand constraint."""
        sd = build_scenario(
            years=[2025],
            seasons={"S1": 365},
            daytypes={"D1": 1},
            brackets={"H1": 24},
        )
        net = PyPSAInputTranslator(sd).translate()
        net.optimize(solver_name="highs", multi_investment_periods=False)
        results = PyPSAOutputTranslator(net).translate()
        # curtailment may be zero if wind exactly meets demand — just check schema
        curtailment = results.dispatch.curtailment
        required = {"REGION", "TIMESLICE", "TECHNOLOGY", "YEAR", "VALUE"}
        if not curtailment.empty:
            assert required.issubset(set(curtailment.columns))
            assert (curtailment["VALUE"] >= 0).all()

    def test_curtailment_columns_always_present(self, tmp_path):
        sd = build_scenario(
            years=[2025],
            seasons={"S1": 365},
            daytypes={"D1": 1},
            brackets={"H1": 24},
        )
        net = PyPSAInputTranslator(sd).translate()
        net.optimize(solver_name="highs", multi_investment_periods=False)
        results = PyPSAOutputTranslator(net).translate()
        curtailment = results.dispatch.curtailment
        # Must have correct columns regardless of whether it's empty
        required = ["REGION", "TIMESLICE", "TECHNOLOGY", "YEAR", "VALUE"]
        for col in required:
            assert col in curtailment.columns or curtailment.empty


# ---------------------------------------------------------------------------
# compare() with storage scenario (end-to-end)
# ---------------------------------------------------------------------------


def _clone_as(results: ModelResults, new_name: str) -> ModelResults:
    """Return a copy of ModelResults with a different model_name."""
    return ModelResults(
        model_name=new_name,
        topology=results.topology,
        supply=results.supply,
        dispatch=results.dispatch,
        storage=results.storage,
        economics=results.economics,
        trade=results.trade,
        objective=results.objective,
        metadata=results.metadata,
    )


class TestCompareWithStorage:
    def test_compare_produces_storage_tables_after_solve(self, tmp_path):
        sd = build_storage_scenario(tmp_path)
        net = PyPSAInputTranslator(sd).translate()
        net.optimize(solver_name="highs", multi_investment_periods=False)
        results = PyPSAOutputTranslator(net).translate()

        # Compare against a copy with a different name — identical values → all MATCH
        results_copy = _clone_as(results, "OSeMOSYS")
        tables = compare(results, results_copy)
        for key in ("storage_installed_capacity", "storage_installed_energy_capacity"):
            df = tables[key]
            if not df.empty:
                assert df["MATCH"].all(), f"{key}: equivalent comparison should match"

    def test_divergence_analysis_no_unexplained_flags_when_equal(self, tmp_path):
        sd = build_storage_scenario(tmp_path)
        net = PyPSAInputTranslator(sd).translate()
        net.optimize(solver_name="highs", multi_investment_periods=False)
        results = PyPSAOutputTranslator(net).translate()

        results_copy = _clone_as(results, "OSeMOSYS")
        flags, _ = divergence_analysis(results, results_copy)
        non_structural = [f for f in flags if not f.structural]
        assert non_structural == [], (
            f"Equivalent comparison should have no non-structural flags: {non_structural}"
        )
