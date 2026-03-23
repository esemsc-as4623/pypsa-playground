# tests/test_simple/test_5_harmonization.py

"""
Harmonization protocol checks on simple scenario fixtures.

These tests validate the newly added harmonization utilities for:
- input-layer consistency checks
- translation-layer parity checks against PyPSA network objects
"""

import pytest

from pyoscomp.interfaces import (
    HarmonizationTolerances,
    validate_input_harmonization,
    validate_pypsa_translation_harmonization,
)

from .conftest import build_scenario


@pytest.fixture
def harmonization_data():
    return build_scenario(
        years=[2025],
        seasons={"SUMMER": 182, "WINTER": 183},
        daytypes={"ALLDAYS": 1},
        brackets={"ALLTIMES": 24},
    )


@pytest.fixture
def harmonization_network(harmonization_data):
    from pyoscomp.translation.pypsa_translator import PyPSAInputTranslator

    return PyPSAInputTranslator(harmonization_data).translate()


class TestHarmonizationInput:
    def test_input_report_passes_on_simple_case(self, harmonization_data):
        report = validate_input_harmonization(harmonization_data)
        assert report.passed

    def test_input_metrics_exist(self, harmonization_data):
        report = validate_input_harmonization(harmonization_data)
        expected_names = {
            "discount_rate_uniform",
            "operational_life_coverage",
            "topology_single_region",
            "demand_annual_integral",
            "wind_cf_bounds",
        }
        names = {m.name for m in report.metrics}
        assert expected_names.issubset(names)

    def test_strict_protocol_validate_passes(self, harmonization_data):
        harmonization_data.validate(strict_protocol=True)

    def test_strict_protocol_validate_fails_on_missing_discount_rate(
        self,
        harmonization_data,
    ):
        harmonization_data.economics.discount_rate.drop(
            harmonization_data.economics.discount_rate.index,
            inplace=True,
        )
        with pytest.raises(ValueError, match="Strict harmonization protocol failed"):
            harmonization_data.validate(strict_protocol=True)


class TestHarmonizationTranslation:
    def test_translation_report_passes_on_simple_case(
        self,
        harmonization_data,
        harmonization_network,
    ):
        report = validate_pypsa_translation_harmonization(
            harmonization_data,
            harmonization_network,
        )
        assert report.passed

    def test_demand_correlation_exceeds_protocol_threshold(
        self,
        harmonization_data,
        harmonization_network,
    ):
        tolerances = HarmonizationTolerances(demand_corr_min=0.99)
        report = validate_pypsa_translation_harmonization(
            harmonization_data,
            harmonization_network,
            tolerances=tolerances,
        )
        metric = report.get("demand_shape_correlation")
        assert metric is not None
        assert metric.observed >= 0.99
