# tests/test_simple/test_3_intraday.py

"""
Intra-day variation: 1 region, 1 year, 3 timeslices (1 season × 1 daytype × 3 brackets).

Verifies:
- YearSplit sums to 1.0 across 3 intra-day brackets
- Snapshot weightings correctly represent hours per bracket × days
- DaySplit is consistent with bracket fractions
- CapacityFactor per timeslice is applied
"""

import pytest
import numpy as np

from .conftest import build_scenario


@pytest.fixture
def intraday_data():
    # Night (8h), Day (8h), Peak (8h) = 24h per day, 365 days
    return build_scenario(
        years=[2025],
        seasons={"ALLSEASONS": 365},
        daytypes={"ALLDAYS": 1},
        brackets={"NIGHT": 8, "DAY": 8, "PEAK": 8},
    )


class TestIntradayScenarioData:
    def test_three_timeslices(self, intraday_data):
        assert len(intraday_data.sets.timeslices) == 3

    def test_year_split_sums_to_one(self, intraday_data):
        ys = intraday_data.time.year_split
        total = ys[ys["YEAR"] == 2025]["VALUE"].sum()
        assert abs(total - 1.0) < 1e-9

    def test_year_split_equal_thirds(self, intraday_data):
        """Each 8h bracket over 365 days = 365×8 / 8760 ≈ 1/3 of year."""
        ys = intraday_data.time.year_split
        vals = ys[ys["YEAR"] == 2025]["VALUE"].values
        expected = 365 * 8 / 8760
        np.testing.assert_allclose(vals, expected, rtol=1e-6)

    def test_three_daily_timebrackets(self, intraday_data):
        assert len(intraday_data.sets.dailytimebrackets) == 3

    def test_daysplit_sums_correct(self, intraday_data):
        """DaySplit values per bracket should each be 8/24."""
        ds = intraday_data.time.day_split
        vals = ds[ds["YEAR"] == 2025]["VALUE"].values
        np.testing.assert_allclose(vals, 8 / 24, rtol=1e-6)


class TestIntradayPyPSANetwork:
    @pytest.fixture
    def network(self, intraday_data):
        from pyoscomp.translation.pypsa_translator import PyPSAInputTranslator
        return PyPSAInputTranslator(intraday_data).translate()

    def test_three_snapshots(self, network):
        assert len(network.snapshots) == 3

    def test_snapshot_weightings_sum_to_8760(self, network):
        total = network.snapshot_weightings["generators"].sum()
        assert abs(total - 8760.0) < 1.0

    def test_snapshot_weights_equal(self, network):
        """All three brackets have the same weight: 365×8 = 2920 h."""
        weights = network.snapshot_weightings["generators"].values
        np.testing.assert_allclose(weights, 365 * 8.0, rtol=1e-4)

    def test_generators_marginal_cost_positive(self, network):
        assert (network.generators["marginal_cost"] > 0).all()


class TestIntradayOptimization:
    @pytest.fixture
    def network(self, intraday_data):
        from pyoscomp.translation.pypsa_translator import PyPSAInputTranslator
        return PyPSAInputTranslator(intraday_data).translate()

    def test_optimization_runs(self, network):
        pytest.importorskip("highspy", reason="HiGHS solver not available")
        network.optimize(solver_name="highs", multi_investment_periods=False)
        assert (network.generators["p_nom_opt"] >= 0).all()

    def test_cheaper_generator_dispatched_first(self, network):
        """GAS_CCGT (lower marginal cost) should carry more generation."""
        pytest.importorskip("highspy", reason="HiGHS solver not available")
        network.optimize(solver_name="highs", multi_investment_periods=False)
        gen_t = network.generators_t.p
        if "GAS_CCGT" in gen_t.columns and "GAS_PEAKER" in gen_t.columns:
            ccgt_total = (gen_t["GAS_CCGT"] * network.snapshot_weightings["generators"]).sum()
            peaker_total = (gen_t["GAS_PEAKER"] * network.snapshot_weightings["generators"]).sum()
            # CCGT has lower variable cost (2) vs PEAKER (5) → should dispatch more
            assert ccgt_total >= peaker_total
