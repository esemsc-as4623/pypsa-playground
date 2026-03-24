# tests/test_translation/test_naming_convention.py

"""
Tests for A2: generator and storage naming convention fix.

Multi-region generators must be named "{TECHNOLOGY}_{REGION}" so that the
output translator can strip the region suffix and recover the technology name.
Single-region generators keep the bare technology name.
"""

import pytest
import tempfile

from tests.test_simple.conftest import build_scenario
from pyoscomp.translation.pypsa_translator import PyPSAInputTranslator, PyPSAOutputTranslator


class TestSingleRegionNaming:
    """Single-region: generator name = technology name (no region suffix)."""

    def test_generator_names_no_region_suffix(self):
        sd = build_scenario(
            years=[2025],
            seasons={"S1": 365},
            daytypes={"D1": 1},
            brackets={"H1": 24},
        )
        net = PyPSAInputTranslator(sd).translate()
        for gen_name in net.generators.index:
            assert "_R1" not in gen_name, (
                f"Single-region generator '{gen_name}' must not have '_R1' suffix"
            )

    def test_supply_result_recovers_technology(self):
        sd = build_scenario(
            years=[2025],
            seasons={"S1": 365},
            daytypes={"D1": 1},
            brackets={"H1": 24},
        )
        net = PyPSAInputTranslator(sd).translate()
        # Fake optimization: set p_nom_opt = p_nom
        net.generators["p_nom_opt"] = net.generators["p_nom"]
        supply = PyPSAOutputTranslator._extract_supply(net)
        techs = set(supply.installed_capacity["TECHNOLOGY"])
        assert "GAS_CCGT" in techs, f"Expected 'GAS_CCGT' in {techs}"
        assert "GAS_PEAKER" in techs, f"Expected 'GAS_PEAKER' in {techs}"


class TestMultiRegionNaming:
    """Multi-region: generator name = "{tech}_{region}", not "{region}_{tech}"."""

    def _build_two_region_scenario(self):
        import tempfile
        import os
        from pyoscomp.scenario.components import (
            TopologyComponent, TimeComponent, DemandComponent,
            SupplyComponent, PerformanceComponent, EconomicsComponent,
        )
        from pyoscomp.interfaces import ScenarioData

        with tempfile.TemporaryDirectory() as tmpdir:
            topology = TopologyComponent(tmpdir)
            topology.add_nodes(["HUB", "SHORE"])
            topology.save()

            time = TimeComponent(tmpdir)
            time.add_time_structure(
                years=[2025],
                seasons={"S1": 365},
                daytypes={"D1": 1},
                brackets={"H1": 24},
            )
            time.save()

            demand = DemandComponent(tmpdir)
            for region in ["HUB", "SHORE"]:
                demand.add_annual_demand(region, "ELEC", {2025: 100.0})
            demand.process()
            demand.save()

            supply = SupplyComponent(tmpdir)
            for region in ["HUB", "SHORE"]:
                (
                    supply.add_technology(region, "WIND")
                    .with_operational_life(25)
                    .with_residual_capacity(0)
                    .as_conversion(input_fuel="WIND_RES", output_fuel="ELEC")
                )
            supply.save()

            performance = PerformanceComponent(tmpdir)
            for region in ["HUB", "SHORE"]:
                performance.set_efficiency(region, "WIND", 1.0)
                performance.set_capacity_factor(region, "WIND", 0.4)
                performance.set_availability_factor(region, "WIND", 1.0)
                performance.set_capacity_to_activity_unit(region, "WIND", 8760)
                performance.set_capacity_limits(
                    region, "WIND",
                    max_capacity={2025: 1000 / 8760},
                    min_capacity=0,
                )
            performance.process()
            performance.save()

            economics = EconomicsComponent(tmpdir)
            for region in ["HUB", "SHORE"]:
                economics.set_discount_rate(region, 0.05)
                economics.set_capital_cost(region, "WIND", 1200)
                economics.set_variable_cost(region, "WIND", "MODE1", 0.0)
                economics.set_fixed_cost(region, "WIND", 30)
            economics.save()

            return ScenarioData.from_components(
                topology, time, demand, supply, performance, economics,
                validate=False,
            )

    def test_generator_names_tech_first(self):
        sd = self._build_two_region_scenario()
        net = PyPSAInputTranslator(sd).translate()
        gen_names = list(net.generators.index)
        # Should be "WIND_HUB" and "WIND_SHORE", not "HUB_WIND" / "SHORE_WIND"
        assert "WIND_HUB" in gen_names, f"Expected 'WIND_HUB' in {gen_names}"
        assert "WIND_SHORE" in gen_names, f"Expected 'WIND_SHORE' in {gen_names}"
        assert "HUB_WIND" not in gen_names, f"'HUB_WIND' must not appear (old naming)"

    def test_supply_result_recovers_technology_multi_region(self):
        sd = self._build_two_region_scenario()
        net = PyPSAInputTranslator(sd).translate()
        net.generators["p_nom_opt"] = net.generators["p_nom"]
        supply = PyPSAOutputTranslator._extract_supply(net)
        techs = set(supply.installed_capacity["TECHNOLOGY"])
        regions = set(supply.installed_capacity["REGION"])
        assert "WIND" in techs, f"Expected 'WIND' in {techs}"
        assert {"HUB", "SHORE"} == regions, f"Expected both regions, got {regions}"


class TestHarmonizationInferRegionTech:
    """_infer_region_tech must use suffix matching ({tech}_{region})."""

    def test_single_region_returns_full_name_as_tech(self):
        from pyoscomp.interfaces.harmonization import _infer_region_tech
        region, tech = _infer_region_tech("GAS_CCGT", ["R1"], single_region=True)
        assert region == "R1"
        assert tech == "GAS_CCGT"

    def test_multi_region_strips_region_suffix(self):
        from pyoscomp.interfaces.harmonization import _infer_region_tech
        region, tech = _infer_region_tech("WIND_HUB", ["HUB", "SHORE"], single_region=False)
        assert region == "HUB"
        assert tech == "WIND"

    def test_multi_region_no_match_falls_back(self):
        from pyoscomp.interfaces.harmonization import _infer_region_tech
        region, tech = _infer_region_tech("UNKNOWN", ["HUB", "SHORE"], single_region=False)
        assert region == "HUB"  # fallback to first region
        assert tech == "UNKNOWN"

    def test_old_prefix_format_not_matched(self):
        """Old format "HUB_WIND" must NOT be mistakenly parsed as region=HUB, tech=WIND."""
        from pyoscomp.interfaces.harmonization import _infer_region_tech
        # "HUB_WIND" ends with "_WIND", not "_HUB" or "_SHORE"
        region, tech = _infer_region_tech("HUB_WIND", ["HUB", "SHORE"], single_region=False)
        # Falls back: full name is preserved as tech
        assert tech == "HUB_WIND"
