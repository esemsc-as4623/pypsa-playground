# tests/test_translation/test_investment_periods.py

"""
Tests for A1: investment period duration fix.

Verifies that the first investment period gets a non-zero duration so it
carries correct weight in the PyPSA multi-period objective.
"""

import pytest
from tests.test_simple.conftest import build_scenario
from pyoscomp.translation.pypsa_translator import PyPSAInputTranslator


class TestInvestmentPeriodDuration:
    """Investment period weightings must have positive duration for every period."""

    def test_single_year_duration_is_one(self):
        sd = build_scenario(
            years=[2025],
            seasons={"S1": 365},
            daytypes={"D1": 1},
            brackets={"H1": 24},
        )
        net = PyPSAInputTranslator(sd).translate()
        ipw = net.investment_period_weightings
        assert len(ipw) == 1
        assert ipw["years"].iloc[0] == 1, (
            "Single-year model should have duration 1, not 0"
        )

    def test_multi_year_first_period_positive(self):
        sd = build_scenario(
            years=[2025, 2030, 2035],
            seasons={"S1": 365},
            daytypes={"D1": 1},
            brackets={"H1": 24},
        )
        net = PyPSAInputTranslator(sd).translate()
        ipw = net.investment_period_weightings
        assert len(ipw) == 3
        # First period must not be 0
        first_duration = ipw["years"].iloc[0]
        assert first_duration > 0, (
            f"First investment period duration is {first_duration}, expected > 0"
        )

    def test_multi_year_durations_match_gaps(self):
        sd = build_scenario(
            years=[2025, 2030, 2035],
            seasons={"S1": 365},
            daytypes={"D1": 1},
            brackets={"H1": 24},
        )
        net = PyPSAInputTranslator(sd).translate()
        ipw = net.investment_period_weightings
        # Gaps: 2025→2030 = 5, 2030→2035 = 5, last replicated = 5
        assert list(ipw["years"]) == [5, 5, 5], (
            f"Expected [5, 5, 5], got {list(ipw['years'])}"
        )

    def test_uneven_gaps_replicate_last(self):
        sd = build_scenario(
            years=[2025, 2030, 2040],
            seasons={"S1": 365},
            daytypes={"D1": 1},
            brackets={"H1": 24},
        )
        net = PyPSAInputTranslator(sd).translate()
        ipw = net.investment_period_weightings
        # Gaps: 5, 10, replicate last → 10
        assert list(ipw["years"]) == [5, 10, 10], (
            f"Expected [5, 10, 10], got {list(ipw['years'])}"
        )
