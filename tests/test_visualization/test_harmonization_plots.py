"""Tests for harmonization and divergence visualization plots."""

import matplotlib.figure
import matplotlib.pyplot as plt
import pandas as pd
import pytest

from pyoscomp.interfaces.results import (
    DispatchResult,
    DivergenceFlag,
    ModelResults,
    SupplyResult,
    TopologyResult,
)
from pyoscomp.translation.pypsa_translator import PyPSAInputTranslator
from pyoscomp.visualization import HarmonizationViolation, HarmonizationVisualizer
from tests.test_simple.conftest import build_scenario


@pytest.fixture(autouse=True)
def _close_figures():
    """Prevent matplotlib figure accumulation across tests."""
    yield
    plt.close("all")


@pytest.fixture
def visualizer() -> HarmonizationVisualizer:
    """Shared HarmonizationVisualizer instance."""
    return HarmonizationVisualizer()


def _wind_scenario_and_network():
    """Create a single-technology wind scenario and translated network."""
    sd = build_scenario(
        years=[2025],
        seasons={"S1": 365},
        daytypes={"D1": 1},
        brackets={"H1": 24},
        technologies=["WIND"],
    )
    net = PyPSAInputTranslator(sd).translate()
    return sd, net


def _make_minimal_results(
    model_name: str,
    capacity_mw: float = 100.0,
    annual_production_mwh: float = 350_000.0,
    year: int = 2025,
    tech: str = "WIND",
    region: str = "HUB",
) -> ModelResults:
    """Build minimal ModelResults with supply and dispatch production."""
    installed = pd.DataFrame(
        {
            "REGION": [region],
            "TECHNOLOGY": [tech],
            "YEAR": [year],
            "VALUE": [capacity_mw],
        }
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
    )


def test_plot_time_structure_returns_figure(visualizer):
    sd, net = _wind_scenario_and_network()
    fig = visualizer.plot_time_structure(sd, net)
    assert isinstance(fig, matplotlib.figure.Figure)


def test_plot_time_structure_raises_on_bad_year_split(visualizer):
    sd, net = _wind_scenario_and_network()
    bad = sd.time.year_split.copy()
    bad.loc[:, "VALUE"] = bad["VALUE"] * 0.9
    bad_total = bad["VALUE"].sum()
    assert bad_total == pytest.approx(0.9, rel=1e-9)
    sd.time.year_split.loc[:, "VALUE"] = bad["VALUE"].values

    with pytest.raises(HarmonizationViolation):
        visualizer.plot_time_structure(sd, net)


def test_plot_capacity_factor_profile_returns_figure(visualizer):
    sd, net = _wind_scenario_and_network()
    fig = visualizer.plot_capacity_factor_profile(sd, net, technology="WIND")
    assert isinstance(fig, matplotlib.figure.Figure)


def test_plot_capital_cost_comparison_returns_figure(visualizer):
    sd, net = _wind_scenario_and_network()
    fig = visualizer.plot_capital_cost_comparison(sd, net)
    assert isinstance(fig, matplotlib.figure.Figure)


def test_plot_translation_report_returns_figure(visualizer):
    sd, net = _wind_scenario_and_network()
    fig = visualizer.plot_translation_report(sd, net)
    assert isinstance(fig, matplotlib.figure.Figure)
    assert len(fig.axes) == 4


def test_plot_capacity_comparison_returns_figure(visualizer):
    a = _make_minimal_results("PyPSA", capacity_mw=120.0)
    b = _make_minimal_results("OSeMOSYS", capacity_mw=100.0)
    fig = visualizer.plot_capacity_comparison(a, b)
    assert isinstance(fig, matplotlib.figure.Figure)


def test_plot_divergence_summary_empty(visualizer):
    fig = visualizer.plot_divergence_summary(flags=[])
    assert isinstance(fig, matplotlib.figure.Figure)


def test_plot_divergence_summary_with_flags(visualizer):
    flags = [
        DivergenceFlag(
            category="capacity",
            description="Installed generation capacity differs",
            n_mismatches=3,
            max_abs_diff=50.0,
            max_rel_diff=0.10,
            structural=False,
        ),
        DivergenceFlag(
            category="dispatch",
            description="Timeslice aggregation mismatch",
            n_mismatches=5,
            max_abs_diff=120.0,
            max_rel_diff=0.20,
            structural=True,
        ),
    ]
    fig = visualizer.plot_divergence_summary(flags=flags)
    assert isinstance(fig, matplotlib.figure.Figure)
