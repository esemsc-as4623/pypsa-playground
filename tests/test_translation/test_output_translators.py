# tests/test_translation/test_output_translators.py

"""Tests for harmonized output translators."""

import pandas as pd

from pyoscomp.translation.osemosys_translator import OSeMOSYSOutputTranslator
from pyoscomp.translation.pypsa_translator import (
    PyPSAInputTranslator,
    PyPSAOutputTranslator,
)
from tests.test_simple.conftest import build_scenario


def test_osemosys_output_translator_maps_extended_domains() -> None:
    results_dict = {
        "TotalCapacityAnnual": pd.DataFrame(
            {
                "REGION": ["R1"],
                "TECHNOLOGY": ["WIND"],
                "YEAR": [2030],
                "VALUE": [10.0],
            }
        ),
        "NewCapacity": pd.DataFrame(
            {
                "REGION": ["R1"],
                "TECHNOLOGY": ["WIND"],
                "YEAR": [2030],
                "VALUE": [2.0],
            }
        ),
        "ProductionByTechnology": pd.DataFrame(
            {
                "REGION": ["R1"],
                "TIMESLICE": ["TS1"],
                "TECHNOLOGY": ["WIND"],
                "FUEL": ["ELC"],
                "YEAR": [2030],
                "VALUE": [3.0],
            }
        ),
        "UseByTechnology": pd.DataFrame(
            {
                "REGION": ["R1"],
                "TIMESLICE": ["TS1"],
                "TECHNOLOGY": ["WIND"],
                "FUEL": ["WIND_RESOURCE"],
                "YEAR": [2030],
                "VALUE": [3.1],
            }
        ),
        "CapitalInvestment": pd.DataFrame(
            {
                "REGION": ["R1"],
                "TECHNOLOGY": ["WIND"],
                "YEAR": [2030],
                "VALUE": [100.0],
            }
        ),
        "AnnualFixedOperatingCost": pd.DataFrame(
            {
                "REGION": ["R1"],
                "TECHNOLOGY": ["WIND"],
                "YEAR": [2030],
                "VALUE": [1.0],
            }
        ),
        "AnnualVariableOperatingCost": pd.DataFrame(
            {
                "REGION": ["R1"],
                "TECHNOLOGY": ["WIND"],
                "YEAR": [2030],
                "VALUE": [2.0],
            }
        ),
        "DiscountedSalvageValue": pd.DataFrame(
            {
                "REGION": ["R1"],
                "TECHNOLOGY": ["WIND"],
                "YEAR": [2030],
                "VALUE": [5.0],
            }
        ),
        "TotalDiscountedCost": pd.DataFrame(
            {
                "REGION": ["R1"],
                "YEAR": [2030],
                "VALUE": [120.0],
            }
        ),
        "Trade": pd.DataFrame(
            {
                "REGION": ["R1"],
                "REGION.1": ["R2"],
                "TIMESLICE": ["TS1"],
                "FUEL": ["ELC"],
                "YEAR": [2030],
                "VALUE": [4.0],
            }
        ),
    }

    translator = OSeMOSYSOutputTranslator(results_dict)
    model_results = translator.translate()

    assert not model_results.dispatch.production.empty
    assert not model_results.economics.total_system_cost.empty
    assert not model_results.trade.flows.empty
    assert model_results.objective == 120.0


def test_pypsa_output_translator_returns_extended_model_results() -> None:
    data = build_scenario(
        years=[2025],
        seasons={"ALLSEASONS": 365},
        daytypes={"ALLDAYS": 1},
        brackets={"ALLTIMES": 24},
    )
    network = PyPSAInputTranslator(data).translate()

    translator = PyPSAOutputTranslator(network)
    model_results = translator.translate()

    model_results.validate()
    assert model_results.model_name == "PyPSA"
    assert model_results.dispatch.production.empty
    assert not model_results.economics.total_system_cost.empty
