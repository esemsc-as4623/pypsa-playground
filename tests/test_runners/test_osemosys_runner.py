"""Tests for OSeMOSYS result-table handling and NPV parity diagnostics."""

from pathlib import Path
import importlib

import pandas as pd
import pytest

from pyoscomp.interfaces.harmonization import compare_npv_to_osemosys
from pyoscomp.run import run, run_pypsa
from tests.test_simple.conftest import build_scenario

run_module = importlib.import_module("pyoscomp.run")


@pytest.fixture
def simple_data():
    return build_scenario(
        years=[2025],
        seasons={"ALLSEASONS": 365},
        daytypes={"ALLDAYS": 1},
        brackets={"ALLTIMES": 24},
    )


def test_compare_npv_to_osemosys_uses_results_table(simple_data):
    pytest.importorskip("highspy", reason="HiGHS solver not available")
    fixture_path = Path("notebooks/results/TotalDiscountedCost.csv")
    table = pd.read_csv(fixture_path)

    # Align table value with reconstructed PyPSA NPV to test parity pass.
    pypsa_result = run_pypsa(
        simple_data,
        solver_name="highs",
        multi_investment_periods=False,
    )
    table = table.copy()
    table["VALUE"] = pypsa_result.harmonization["npv_reconstructed"]
    metric = compare_npv_to_osemosys(
        simple_data,
        pypsa_result.model_object,
        {"TotalDiscountedCost": table},
    )

    assert metric.name == "npv_parity"
    assert metric.passed


def test_run_both_attaches_npv_parity_when_osemosys_results_injected(
	simple_data,
	monkeypatch,
):
	pytest.importorskip("highspy", reason="HiGHS solver not available")

	fixture_path = Path("notebooks/results/TotalDiscountedCost.csv")
	table = pd.read_csv(fixture_path)

	def fake_run_osemosys(scenario_data, **kwargs):
		pypsa_result = run_pypsa(
			scenario_data,
			solver_name="highs",
			multi_investment_periods=False,
		)

		class _FakeResult:
			model_name = "osemosys"
			objective = float(table["VALUE"].sum())
			optimal_capacities = pd.DataFrame()
			dispatch = pd.DataFrame()
			costs = pd.DataFrame()
			raw_results = {
				"TotalDiscountedCost": pd.DataFrame(
					{
						"REGION": ["REGION1"],
						"YEAR": [2025],
						"VALUE": [
							pypsa_result.harmonization["npv_reconstructed"]
						],
					}
				)
			}
			status = "optimal"
			solve_time = 0.0
			model_object = None
			harmonization = {
				"input": {
					"scope": "input",
					"passed": True,
					"metrics": [],
				}
			}

		return _FakeResult()

	monkeypatch.setattr(run_module, "run_osemosys", fake_run_osemosys)

	comparison = run(
		simple_data,
		model="both",
		pypsa_options={
			"solver_name": "highs",
			"multi_investment_periods": False,
		},
	)

	assert "npv_parity" in comparison.harmonization
	assert comparison.harmonization["npv_parity"]["passed"]

