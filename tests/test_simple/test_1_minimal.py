# tests/test_simple/test_1_minimal.py

"""
Minimal scenario: 1 region, 1 year, 1 timeslice (1 season × 1 daytype × 1 bracket).

Verifies:
- ScenarioData builds and validates without errors
- YearSplit sums to 1.0 per year
- PyPSA network is built: correct buses, generators, loads
- Snapshot weightings sum to 8760 per year
- Optimization runs and produces non-negative capacities (if solver available)
"""

import pytest
import numpy as np

from .conftest import build_scenario


@pytest.fixture
def minimal_data():
    return build_scenario(
        years=[2025],
        seasons={"ALLSEASONS": 365},
        daytypes={"ALLDAYS": 1},
        brackets={"ALLTIMES": 24},
    )


class TestMinimalScenarioData:
    def test_builds_without_error(self, minimal_data):
        assert minimal_data is not None

    def test_sets_populated(self, minimal_data):
        assert "R1" in minimal_data.sets.regions
        assert 2025 in minimal_data.sets.years
        assert len(minimal_data.sets.technologies) == 2
        assert len(minimal_data.sets.timeslices) == 1

    def test_year_split_sums_to_one(self, minimal_data):
        ys = minimal_data.time.year_split
        total = ys[ys["YEAR"] == 2025]["VALUE"].sum()
        assert abs(total - 1.0) < 1e-9, f"YearSplit for 2025 sums to {total}, expected 1.0"

    def test_demand_non_negative(self, minimal_data):
        sad = minimal_data.demand.specified_annual_demand
        assert (sad["VALUE"] >= 0).all()

    def test_capital_cost_positive(self, minimal_data):
        cc = minimal_data.economics.capital_cost
        assert (cc["VALUE"] > 0).all()


class TestMinimalPyPSANetwork:
    @pytest.fixture
    def network(self, minimal_data):
        from pyoscomp.translation.pypsa_translator import PyPSAInputTranslator
        return PyPSAInputTranslator(minimal_data).translate()

    def test_network_has_bus(self, network):
        assert "R1" in network.buses.index

    def test_network_has_two_generators(self, network):
        assert len(network.generators) == 2

    def test_network_has_load(self, network):
        assert len(network.loads) >= 1

    def test_snapshot_weightings_sum_to_8760(self, network):
        total = network.snapshot_weightings["generators"].sum()
        assert abs(total - 8760.0) < 1.0, (
            f"Snapshot weightings sum to {total}, expected ~8760"
        )

    def test_generators_capital_cost_positive(self, network):
        assert (network.generators["capital_cost"] > 0).all()

    def test_generators_p_nom_extendable(self, network):
        assert network.generators["p_nom_extendable"].all()

    def test_single_snapshot(self, network):
        # 1 timeslice → 1 snapshot (single period, single timestep)
        assert len(network.snapshots) == 1


class TestMinimalOptimization:
    @pytest.fixture
    def network(self, minimal_data):
        from pyoscomp.translation.pypsa_translator import PyPSAInputTranslator
        return PyPSAInputTranslator(minimal_data).translate()

    def test_optimization_runs(self, network):
        pytest.importorskip("highspy", reason="HiGHS solver not available")
        network.optimize(solver_name="highs", multi_investment_periods=False)
        assert network.generators["p_nom_opt"].notna().all()
        assert (network.generators["p_nom_opt"] >= 0).all()

    def test_total_installed_capacity_covers_demand(self, network):
        pytest.importorskip("highspy", reason="HiGHS solver not available")
        network.optimize(solver_name="highs", multi_investment_periods=False)
        # Annual demand 100 MWh, 1 timeslice with weight 8760 h → load = 100/8760 MW
        # At least one generator must be built
        total_cap = network.generators["p_nom_opt"].sum()
        assert total_cap > 0
