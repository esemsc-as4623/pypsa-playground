"""Tests for run_pypsa harmonization diagnostics and NPV parity wiring."""

from pathlib import Path

import pandas as pd
import pytest

from pyoscomp.interfaces.harmonization import compare_npv_to_osemosys
from pyoscomp.run import run_pypsa
from tests.test_simple.conftest import build_scenario


@pytest.fixture
def simple_data():
	return build_scenario(
		years=[2025],
		seasons={"ALLSEASONS": 365},
		daytypes={"ALLDAYS": 1},
		brackets={"ALLTIMES": 24},
	)


def test_run_pypsa_returns_harmonization_diagnostics(simple_data):
	pytest.importorskip("highspy", reason="HiGHS solver not available")
	result = run_pypsa(
		simple_data,
		solver_name="highs",
		multi_investment_periods=False,
	)

	assert result.status != "error"
	assert "input" in result.harmonization
	assert "translation" in result.harmonization
	assert "npv_reconstructed" in result.harmonization


def test_npv_parity_metric_passes_with_osemosys_table_format(simple_data):
	pytest.importorskip("highspy", reason="HiGHS solver not available")
	result = run_pypsa(
		simple_data,
		solver_name="highs",
		multi_investment_periods=False,
	)

	fixture_path = Path("notebooks/results/TotalDiscountedCost.csv")
	table = pd.read_csv(fixture_path)
	table = table.copy()
	table["VALUE"] = result.harmonization["npv_reconstructed"]
	osemosys_results = {"TotalDiscountedCost": table}

	metric = compare_npv_to_osemosys(
		simple_data,
		result.model_object,
		osemosys_results,
	)
	assert metric.name == "npv_parity"
	assert metric.passed

