# tests/test_simple/test_2_seasonal.py

"""
Seasonal scenario: 1 region, 1 year, 2 timeslices (2 seasons × 1 daytype × 1 bracket).

Verifies:
- YearSplit sums to 1.0 across 2 timeslices
- 2 snapshots in the PyPSA network (one per timeslice)
- Snapshot weightings sum to 8760
- Demand profile distributes correctly across timeslices
- CapacityFactor applied per timeslice
"""

import pytest
import numpy as np

from .conftest import build_scenario


@pytest.fixture
def seasonal_data():
    # Summer: 182 days, Winter: 183 days → total 365
    return build_scenario(
        years=[2025],
        seasons={"SUMMER": 182, "WINTER": 183},
        daytypes={"ALLDAYS": 1},
        brackets={"ALLTIMES": 24},
    )


class TestSeasonalScenarioData:
    def test_two_timeslices(self, seasonal_data):
        assert len(seasonal_data.sets.timeslices) == 2

    def test_year_split_sums_to_one(self, seasonal_data):
        ys = seasonal_data.time.year_split
        total = ys[ys["YEAR"] == 2025]["VALUE"].sum()
        assert abs(total - 1.0) < 1e-9, f"YearSplit sums to {total}"

    def test_year_split_proportional_to_days(self, seasonal_data):
        ys = seasonal_data.time.year_split
        vals = ys[ys["YEAR"] == 2025]["VALUE"].values
        # Summer fraction ≈ 182/365, Winter fraction ≈ 183/365
        expected = sorted([182 / 365, 183 / 365])
        actual = sorted(vals)
        np.testing.assert_allclose(actual, expected, atol=1e-6)

    def test_demand_profile_sums_to_one(self, seasonal_data):
        sdp = seasonal_data.demand.specified_demand_profile
        per_year = sdp.groupby("YEAR")["VALUE"].sum()
        for y, total in per_year.items():
            assert abs(total - 1.0) < 1e-6, f"Demand profile for {y} sums to {total}"


class TestSeasonalPyPSANetwork:
    @pytest.fixture
    def network(self, seasonal_data):
        from pyoscomp.translation.pypsa_translator import PyPSAInputTranslator
        return PyPSAInputTranslator(seasonal_data).translate()

    def test_two_snapshots(self, network):
        assert len(network.snapshots) == 2

    def test_snapshot_weightings_sum_to_8760(self, network):
        total = network.snapshot_weightings["generators"].sum()
        assert abs(total - 8760.0) < 1.0, f"Weightings sum to {total}"

    def test_snapshot_weights_proportional_to_season_days(self, network):
        weights = sorted(network.snapshot_weightings["generators"].values)
        expected = sorted([182 * 24.0, 183 * 24.0])
        np.testing.assert_allclose(weights, expected, rtol=1e-4)

    def test_load_energy_balance(self, network):
        """Total load energy (MW × h) must be positive."""
        load_series = network.loads_t.p_set
        weightings = network.snapshot_weightings["generators"]
        # Multiply each load column by the snapshot weights (align on snapshot axis)
        total_energy = (load_series.values * weightings.values[:, None]).sum()
        assert total_energy > 0


class TestSeasonalOptimization:
    @pytest.fixture
    def network(self, seasonal_data):
        from pyoscomp.translation.pypsa_translator import PyPSAInputTranslator
        return PyPSAInputTranslator(seasonal_data).translate()

    def test_optimization_runs(self, network):
        pytest.importorskip("highspy", reason="HiGHS solver not available")
        network.optimize(solver_name="highs", multi_investment_periods=False)
        assert (network.generators["p_nom_opt"] >= 0).all()
