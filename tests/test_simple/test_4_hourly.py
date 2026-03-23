# tests/test_simple/test_4_hourly.py

"""
Hourly-equivalent scenario: 1 region, 1 year, 24 timeslices
(1 season × 1 daytype × 24 brackets of 1h each).

Verifies:
- 24 snapshots, each with weight 365 h
- Total weightings = 24 × 365 = 8760 h
- Multi-year extension: 2 years, verifies per-year weights
- Edge case: non-365-day year (leap year 2024, 8784 h)
"""

import pytest
import numpy as np

from .conftest import build_scenario


@pytest.fixture
def hourly_data():
    return build_scenario(
        years=[2025],
        seasons={"ALLSEASONS": 365},
        daytypes={"ALLDAYS": 1},
        brackets={f"H{h:02d}": 1 for h in range(24)},
    )


@pytest.fixture
def hourly_data_leap():
    """2024 is a leap year: 366 days = 8784 hours."""
    return build_scenario(
        years=[2024],
        seasons={"ALLSEASONS": 366},
        daytypes={"ALLDAYS": 1},
        brackets={f"H{h:02d}": 1 for h in range(24)},
    )


@pytest.fixture
def hourly_data_multiyear():
    return build_scenario(
        years=[2025, 2030],
        seasons={"ALLSEASONS": 365},
        daytypes={"ALLDAYS": 1},
        brackets={f"H{h:02d}": 1 for h in range(24)},
    )


class TestHourlyScenarioData:
    def test_24_timeslices(self, hourly_data):
        assert len(hourly_data.sets.timeslices) == 24

    def test_year_split_sums_to_one(self, hourly_data):
        ys = hourly_data.time.year_split
        total = ys[ys["YEAR"] == 2025]["VALUE"].sum()
        assert abs(total - 1.0) < 1e-9

    def test_year_split_equal_24ths(self, hourly_data):
        ys = hourly_data.time.year_split
        vals = ys[ys["YEAR"] == 2025]["VALUE"].values
        expected = 365 / 8760
        np.testing.assert_allclose(vals, expected, rtol=1e-6)

    def test_demand_profile_sums_to_one(self, hourly_data):
        sdp = hourly_data.demand.specified_demand_profile
        total = sdp[sdp["YEAR"] == 2025]["VALUE"].sum()
        assert abs(total - 1.0) < 1e-6

    def test_24_brackets(self, hourly_data):
        assert len(hourly_data.sets.dailytimebrackets) == 24


class TestHourlyPyPSANetwork:
    @pytest.fixture
    def network(self, hourly_data):
        from pyoscomp.translation.pypsa_translator import PyPSAInputTranslator
        return PyPSAInputTranslator(hourly_data).translate()

    def test_24_snapshots(self, network):
        assert len(network.snapshots) == 24

    def test_snapshot_weightings_sum_to_8760(self, network):
        total = network.snapshot_weightings["generators"].sum()
        assert abs(total - 8760.0) < 1.0

    def test_each_snapshot_weight_is_365(self, network):
        """Each 1h bracket repeated over 365 days has weight 365."""
        weights = network.snapshot_weightings["generators"].values
        np.testing.assert_allclose(weights, 365.0, rtol=1e-4)

    def test_generators_exist(self, network):
        assert len(network.generators) == 2

    def test_loads_exist(self, network):
        assert len(network.loads) >= 1


class TestLeapYearNetwork:
    @pytest.fixture
    def network(self, hourly_data_leap):
        from pyoscomp.translation.pypsa_translator import PyPSAInputTranslator
        return PyPSAInputTranslator(hourly_data_leap).translate()

    def test_24_snapshots(self, network):
        assert len(network.snapshots) == 24

    def test_snapshot_weightings_sum_to_8784(self, network):
        total = network.snapshot_weightings["generators"].sum()
        assert abs(total - 8784.0) < 1.0, f"Weightings sum to {total}, expected 8784"

    def test_each_snapshot_weight_is_366(self, network):
        weights = network.snapshot_weightings["generators"].values
        np.testing.assert_allclose(weights, 366.0, rtol=1e-4)


class TestMultiYearNetwork:
    @pytest.fixture
    def network(self, hourly_data_multiyear):
        from pyoscomp.translation.pypsa_translator import PyPSAInputTranslator
        return PyPSAInputTranslator(hourly_data_multiyear).translate()

    def test_48_snapshots(self, network):
        """2 years × 24 timeslices = 48 snapshots."""
        assert len(network.snapshots) == 48

    def test_snapshot_weightings_sum_to_2_times_8760(self, network):
        total = network.snapshot_weightings["generators"].sum()
        assert abs(total - 2 * 8760.0) < 2.0

    def test_investment_periods(self, network):
        assert set(network.investment_periods) == {2025, 2030}

    def test_per_year_weights_sum_to_8760(self, network):
        """Each year's snapshots must independently sum to 8760."""
        for period in network.investment_periods:
            mask = network.snapshots.get_level_values("period") == period
            year_total = network.snapshot_weightings["generators"][mask].sum()
            assert abs(year_total - 8760.0) < 1.0, (
                f"Year {period} weightings sum to {year_total}"
            )


class TestHourlyOptimization:
    @pytest.fixture
    def network(self, hourly_data):
        from pyoscomp.translation.pypsa_translator import PyPSAInputTranslator
        return PyPSAInputTranslator(hourly_data).translate()

    def test_optimization_runs(self, network):
        pytest.importorskip("highspy", reason="HiGHS solver not available")
        network.optimize(solver_name="highs", multi_investment_periods=False)
        assert (network.generators["p_nom_opt"] >= 0).all()

    def test_demand_balance(self, network):
        """After optimization, generation should approximately equal demand."""
        pytest.importorskip("highspy", reason="HiGHS solver not available")
        network.optimize(solver_name="highs", multi_investment_periods=False)
        gen_energy = (
            network.generators_t.p.sum(axis=1) * network.snapshot_weightings["generators"]
        ).sum()
        load_energy = (
            network.loads_t.p_set.sum(axis=1) * network.snapshot_weightings["generators"]
        ).sum()
        # Allow 0.1% tolerance for numerical rounding
        np.testing.assert_allclose(gen_energy, load_energy, rtol=1e-3)
