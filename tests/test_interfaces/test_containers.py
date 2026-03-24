# tests/test_interfaces/test_containers.py

"""
Tests for ScenarioData._PARAM_MAP consolidation (Phase C1) and
SupplyParameters duplicate OperationalLife validation (Phase D3).

Also covers missing edge cases for:
- to_dict() / get_parameter() consistency
- ScenarioData round-trip export → reload
- Year-varying cost warnings (Phase B1)
- MODE1 preference in _add_generators (Phase B2)
- require_single_region default is False (Phase D2)
- _compute_efficiency uses pre-indexed iar_idx (Phase A3)
"""

import logging
import tempfile
import pytest
import pandas as pd

from tests.test_simple.conftest import build_scenario
from pyoscomp.interfaces import ScenarioData
from pyoscomp.interfaces.harmonization import HarmonizationTolerances
from pyoscomp.interfaces.parameters import SupplyParameters
from pyoscomp.interfaces.sets import OSeMOSYSSets
from pyoscomp.translation.pypsa_translator import PyPSAInputTranslator


# ---------------------------------------------------------------------------
# C1: _PARAM_MAP consolidation
# ---------------------------------------------------------------------------

class TestParamMapConsistency:
    """to_dict() and get_parameter() must return the same keys/values."""

    def setup_method(self):
        self.sd = build_scenario(
            years=[2025],
            seasons={"S1": 365},
            daytypes={"D1": 1},
            brackets={"H1": 24},
        )

    def test_param_map_is_populated(self):
        assert len(ScenarioData._PARAM_MAP) > 30, (
            "Expected at least 30 entries in _PARAM_MAP"
        )

    def test_to_dict_and_get_parameter_same_keys(self):
        d = self.sd.to_dict()
        map_keys = set(ScenarioData._PARAM_MAP.keys())
        assert set(d.keys()) == map_keys

    def test_get_parameter_returns_same_data_as_to_dict(self):
        d = self.sd.to_dict()
        for name in ScenarioData._PARAM_MAP:
            from_dict = d[name]
            from_get = self.sd.get_parameter(name)
            assert from_get is not None, f"get_parameter('{name}') returned None"
            pd.testing.assert_frame_equal(
                from_dict.reset_index(drop=True),
                from_get.reset_index(drop=True),
                check_like=True,
            )

    def test_to_dict_returns_copies_not_references(self):
        """Mutating the dict should not affect the ScenarioData."""
        d = self.sd.to_dict()
        original_len = len(d["CapitalCost"])
        d["CapitalCost"].loc[9999, "VALUE"] = 0.0
        # Re-fetch from ScenarioData — should be unchanged
        assert len(self.sd.get_parameter("CapitalCost")) == original_len

    def test_contains_operator_works(self):
        assert "CapitalCost" in self.sd
        assert "YearSplit" in self.sd
        assert "REGION" in self.sd
        assert "NotARealParam" not in self.sd

    def test_getitem_operator_raises_on_unknown(self):
        with pytest.raises(KeyError, match="Unknown parameter"):
            _ = self.sd["NotARealParam"]

    def test_adding_new_param_to_map_shows_in_to_dict(self):
        """Regression: _PARAM_MAP is the single source of truth."""
        # All keys in _PARAM_MAP must appear in to_dict()
        result_keys = set(self.sd.to_dict().keys())
        for name in ScenarioData._PARAM_MAP:
            assert name in result_keys, f"'{name}' in _PARAM_MAP but not in to_dict()"


class TestRoundTrip:
    """Export to directory then reload should produce identical ScenarioData."""

    def test_round_trip_preserves_capital_cost(self):
        sd = build_scenario(
            years=[2025],
            seasons={"S1": 365},
            daytypes={"D1": 1},
            brackets={"H1": 24},
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            sd.export_to_directory(tmpdir)
            sd2 = ScenarioData.from_directory(tmpdir, validate=False)
        pd.testing.assert_frame_equal(
            sd.economics.capital_cost.reset_index(drop=True),
            sd2.economics.capital_cost.reset_index(drop=True),
            check_like=True,
        )

    def test_round_trip_preserves_year_split(self):
        sd = build_scenario(
            years=[2025],
            seasons={"S1": 182, "S2": 183},
            daytypes={"D1": 1},
            brackets={"H1": 24},
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            sd.export_to_directory(tmpdir)
            sd2 = ScenarioData.from_directory(tmpdir, validate=False)
        pd.testing.assert_frame_equal(
            sd.time.year_split.sort_values(["TIMESLICE", "YEAR"]).reset_index(drop=True),
            sd2.time.year_split.sort_values(["TIMESLICE", "YEAR"]).reset_index(drop=True),
            check_like=True,
        )

    def test_round_trip_preserves_regions(self):
        sd = build_scenario(
            years=[2025],
            seasons={"S1": 365},
            daytypes={"D1": 1},
            brackets={"H1": 24},
            region="NORTH",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            sd.export_to_directory(tmpdir)
            sd2 = ScenarioData.from_directory(tmpdir, validate=False)
        assert sd2.sets.regions == sd.sets.regions


# ---------------------------------------------------------------------------
# D2: require_single_region default is False
# ---------------------------------------------------------------------------

class TestRequireSingleRegionDefault:
    def test_default_is_false(self):
        tol = HarmonizationTolerances()
        assert tol.require_single_region is False, (
            "require_single_region must default to False to allow multi-region scenarios"
        )

    def test_explicit_true_still_enforces_single_region(self):
        tol = HarmonizationTolerances(require_single_region=True)
        assert tol.require_single_region is True


# ---------------------------------------------------------------------------
# D3: Duplicate OperationalLife validation
# ---------------------------------------------------------------------------

class TestDuplicateOperationalLife:

    def _make_sets(self):
        return OSeMOSYSSets(
            regions=frozenset(["R1"]),
            years=frozenset([2025]),
            technologies=frozenset(["WIND"]),
            fuels=frozenset(["ELEC"]),
            emissions=frozenset(),
            modes=frozenset(["MODE1"]),
            timeslices=frozenset(["S1D1H1"]),
            seasons=frozenset(["S1"]),
            daytypes=frozenset(["D1"]),
            dailytimebrackets=frozenset(["H1"]),
            storages=frozenset(),
        )

    def test_duplicate_raises_value_error(self):
        params = SupplyParameters(
            operational_life=pd.DataFrame({
                "REGION": ["R1", "R1"],
                "TECHNOLOGY": ["WIND", "WIND"],
                "VALUE": [25.0, 30.0],
            }),
            residual_capacity=pd.DataFrame(),
        )
        sets = self._make_sets()
        with pytest.raises(ValueError, match="Duplicate OperationalLife"):
            params.validate(sets)

    def test_unique_entries_pass(self):
        params = SupplyParameters(
            operational_life=pd.DataFrame({
                "REGION": ["R1"],
                "TECHNOLOGY": ["WIND"],
                "VALUE": [25.0],
            }),
            residual_capacity=pd.DataFrame(),
        )
        sets = self._make_sets()
        params.validate(sets)  # should not raise

    def test_different_regions_same_tech_ok(self):
        params = SupplyParameters(
            operational_life=pd.DataFrame({
                "REGION": ["R1", "R2"],
                "TECHNOLOGY": ["WIND", "WIND"],
                "VALUE": [25.0, 20.0],
            }),
            residual_capacity=pd.DataFrame(),
        )
        sets = OSeMOSYSSets(
            regions=frozenset(["R1", "R2"]),
            years=frozenset([2025]),
            technologies=frozenset(["WIND"]),
            fuels=frozenset(["ELEC"]),
            emissions=frozenset(),
            modes=frozenset(["MODE1"]),
            timeslices=frozenset(["S1D1H1"]),
            seasons=frozenset(["S1"]),
            daytypes=frozenset(["D1"]),
            dailytimebrackets=frozenset(["H1"]),
            storages=frozenset(),
        )
        params.validate(sets)  # different regions, same tech — OK

    def test_empty_operational_life_skips_check(self):
        params = SupplyParameters(
            operational_life=pd.DataFrame(),
            residual_capacity=pd.DataFrame(),
        )
        sets = self._make_sets()
        params.validate(sets)  # no error expected


# ---------------------------------------------------------------------------
# B1: Year-varying cost warnings
# ---------------------------------------------------------------------------

class TestYearVaryingCostWarnings:
    """_warn_if_year_varying must emit logger.warning when costs change by year."""

    def _build_year_varying_sd(self):
        """Build a multi-year scenario where capital costs differ by year."""
        import os
        from pyoscomp.scenario.components import (
            TopologyComponent, TimeComponent, DemandComponent,
            SupplyComponent, PerformanceComponent, EconomicsComponent,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            topology = TopologyComponent(tmpdir)
            topology.add_nodes(["R1"])
            topology.save()

            time = TimeComponent(tmpdir)
            time.add_time_structure(
                years=[2025, 2030],
                seasons={"S1": 365},
                daytypes={"D1": 1},
                brackets={"H1": 24},
            )
            time.save()

            demand = DemandComponent(tmpdir)
            demand.add_annual_demand("R1", "ELEC", {2025: 100.0, 2030: 120.0})
            demand.process()
            demand.save()

            supply = SupplyComponent(tmpdir)
            (
                supply.add_technology("R1", "WIND")
                .with_operational_life(25)
                .with_residual_capacity(0)
                .as_conversion(input_fuel="WIND_RES", output_fuel="ELEC")
            )
            supply.save()

            performance = PerformanceComponent(tmpdir)
            performance.set_efficiency("R1", "WIND", 1.0)
            performance.set_capacity_factor("R1", "WIND", 0.4)
            performance.set_availability_factor("R1", "WIND", 1.0)
            performance.set_capacity_to_activity_unit("R1", "WIND", 8760)
            performance.set_capacity_limits(
                "R1", "WIND",
                max_capacity={2025: 1000 / 8760, 2030: 1000 / 8760},
                min_capacity=0,
            )
            performance.process()
            performance.save()

            economics = EconomicsComponent(tmpdir)
            economics.set_discount_rate("R1", 0.05)
            # Different capital costs per year — should trigger warning
            economics.set_capital_cost("R1", "WIND", {2025: 1200, 2030: 900})
            economics.set_variable_cost("R1", "WIND", "MODE1", 0.0)
            economics.set_fixed_cost("R1", "WIND", 0)
            economics.save()

            return ScenarioData.from_components(
                topology, time, demand, supply, performance, economics,
                validate=False,
            )

    def test_warning_emitted_for_year_varying_capital_cost(self, caplog):
        sd = self._build_year_varying_sd()
        with caplog.at_level(logging.WARNING, logger="pyoscomp.translation.pypsa_translator"):
            PyPSAInputTranslator(sd).translate()
        assert any("CapitalCost" in msg for msg in caplog.messages), (
            "Expected a warning about year-varying CapitalCost"
        )

    def test_no_warning_when_costs_constant(self, caplog):
        """Constant costs (all years identical) must not emit warnings."""
        sd = build_scenario(
            years=[2025, 2030],
            seasons={"S1": 365},
            daytypes={"D1": 1},
            brackets={"H1": 24},
        )
        with caplog.at_level(logging.WARNING, logger="pyoscomp.translation.pypsa_translator"):
            PyPSAInputTranslator(sd).translate()
        cost_warnings = [
            m for m in caplog.messages
            if any(p in m for p in ("CapitalCost", "FixedCost", "VariableCost"))
        ]
        assert len(cost_warnings) == 0, (
            f"Unexpected cost warnings for constant-cost scenario: {cost_warnings}"
        )


# ---------------------------------------------------------------------------
# B2: MODE1 preference in mode selection
# ---------------------------------------------------------------------------

class TestModeSelection:
    """Variable cost mode selection must prefer MODE1 over alphabetically-first."""

    def test_mode1_preferred_over_alphabetically_earlier_mode(self):
        """When modes include 'AAA' and 'MODE1', 'MODE1' must win (not 'AAA')."""
        from pyoscomp.translation.pypsa_translator import PyPSAInputTranslator
        import dataclasses

        # Build a minimal ScenarioData and inject a VariableCost table
        # containing both 'AAA' (alphabetically before MODE1) and 'MODE1'.
        sd_base = build_scenario(
            years=[2025],
            seasons={"S1": 365},
            daytypes={"D1": 1},
            brackets={"H1": 24},
            technologies=["GAS_CCGT"],
        )

        # Add a second mode 'AAA' with a high variable cost so we can detect
        # if the wrong mode is picked.
        extra_vc = pd.DataFrame({
            "REGION": ["R1"],
            "TECHNOLOGY": ["GAS_CCGT"],
            "MODE_OF_OPERATION": ["AAA"],
            "YEAR": [2025],
            "VALUE": [999.0],  # very high — if picked, marginal_cost ≈ 999
        })
        orig_vc = sd_base.economics.variable_cost
        combined_vc = pd.concat([orig_vc, extra_vc], ignore_index=True)

        from pyoscomp.interfaces.parameters import EconomicsParameters
        new_econ = EconomicsParameters(
            discount_rate=sd_base.economics.discount_rate,
            discount_rate_idv=sd_base.economics.discount_rate_idv,
            capital_cost=sd_base.economics.capital_cost,
            variable_cost=combined_vc,
            fixed_cost=sd_base.economics.fixed_cost,
        )
        # Update modes set to include 'AAA'
        from pyoscomp.interfaces.sets import OSeMOSYSSets
        new_sets = OSeMOSYSSets(
            regions=sd_base.sets.regions,
            years=sd_base.sets.years,
            technologies=sd_base.sets.technologies,
            fuels=sd_base.sets.fuels,
            emissions=sd_base.sets.emissions,
            modes=sd_base.sets.modes | frozenset(["AAA"]),
            timeslices=sd_base.sets.timeslices,
            seasons=sd_base.sets.seasons,
            daytypes=sd_base.sets.daytypes,
            dailytimebrackets=sd_base.sets.dailytimebrackets,
            storages=sd_base.sets.storages,
        )
        sd = dataclasses.replace(sd_base, sets=new_sets, economics=new_econ,
                                  _skip_validation=True)

        net = PyPSAInputTranslator(sd).translate()
        # build_scenario sets variable_cost=2 for CCGT via MODE1
        mc = net.generators.loc["GAS_CCGT", "marginal_cost"]
        assert mc < 100, (
            f"Expected MODE1 marginal cost (~2), got {mc}. "
            "Looks like alphabetically-first mode 'AAA'=999 was picked."
        )


# ---------------------------------------------------------------------------
# A3: _compute_efficiency uses pre-indexed iar_idx
# ---------------------------------------------------------------------------

class TestComputeEfficiency:
    """_compute_efficiency must use the pre-indexed Series, not re-query the DataFrame."""

    def test_efficiency_equals_1_over_iar(self):
        """IAR = 2.0 → efficiency should be 0.5."""
        sd = build_scenario(
            years=[2025],
            seasons={"S1": 365},
            daytypes={"D1": 1},
            brackets={"H1": 24},
            technologies=["GAS_CCGT"],
        )
        net = PyPSAInputTranslator(sd).translate()
        # build_scenario sets efficiency=0.5 → IAR=2.0 for GAS_CCGT
        eff = net.generators.loc["GAS_CCGT", "efficiency"]
        assert abs(eff - 0.5) < 1e-6, (
            f"Expected efficiency 0.5 (1/IAR=2.0), got {eff}"
        )

    def test_missing_iar_returns_efficiency_1(self):
        """Technology with no IAR defined should default to efficiency=1.0."""
        from pyoscomp.translation.pypsa_translator import PyPSAInputTranslator
        translator_cls = PyPSAInputTranslator
        # Call _compute_efficiency directly with iar_idx=None
        # (instance method — we need a dummy instance)
        sd = build_scenario(
            years=[2025],
            seasons={"S1": 365},
            daytypes={"D1": 1},
            brackets={"H1": 24},
        )
        translator = translator_cls(sd)
        translator.translate()  # sets up network
        result = translator._compute_efficiency(None, "R1", "GAS_CCGT", "MODE1", 2025)
        assert result == 1.0


# ---------------------------------------------------------------------------
# C2: OSeMOSYSInputTranslator.export_to_csv delegates to ScenarioDataExporter
# ---------------------------------------------------------------------------

class TestExportToCsvDelegation:

    def test_export_creates_capital_cost_csv(self):
        from pyoscomp.translation.osemosys_translator import OSeMOSYSInputTranslator
        sd = build_scenario(
            years=[2025],
            seasons={"S1": 365},
            daytypes={"D1": 1},
            brackets={"H1": 24},
        )
        translator = OSeMOSYSInputTranslator(sd)
        with tempfile.TemporaryDirectory() as tmpdir:
            translator.export_to_csv(tmpdir)
            import os
            files = os.listdir(tmpdir)
        assert "CapitalCost.csv" in files
        assert "REGION.csv" in files
        assert "YearSplit.csv" in files

    def test_export_overwrite_false_raises_on_existing(self):
        from pyoscomp.translation.osemosys_translator import OSeMOSYSInputTranslator
        sd = build_scenario(
            years=[2025],
            seasons={"S1": 365},
            daytypes={"D1": 1},
            brackets={"H1": 24},
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            # First export creates CSVs
            translator = OSeMOSYSInputTranslator(sd)
            translator.export_to_csv(tmpdir)
            # Second export with overwrite=False must fail
            with pytest.raises(FileExistsError):
                translator.export_to_csv(tmpdir, overwrite=False)

    def test_export_overwrite_true_succeeds_on_existing(self):
        from pyoscomp.translation.osemosys_translator import OSeMOSYSInputTranslator
        sd = build_scenario(
            years=[2025],
            seasons={"S1": 365},
            daytypes={"D1": 1},
            brackets={"H1": 24},
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            translator = OSeMOSYSInputTranslator(sd)
            translator.export_to_csv(tmpdir)
            translator.export_to_csv(tmpdir, overwrite=True)  # must not raise


# ---------------------------------------------------------------------------
# YearSplit edge cases
# ---------------------------------------------------------------------------

class TestYearSplitValidation:
    """TimeParameters.validate() must enforce YearSplit sums to 1.0."""

    def test_year_split_not_summing_to_1_raises(self):
        from pyoscomp.interfaces.parameters import TimeParameters
        from pyoscomp.interfaces.sets import OSeMOSYSSets

        year_split = pd.DataFrame({
            "TIMESLICE": ["S1D1H1", "S1D1H2"],
            "YEAR": [2025, 2025],
            "VALUE": [0.4, 0.4],  # sums to 0.8, not 1.0
        })
        params = TimeParameters(year_split=year_split)
        sets = OSeMOSYSSets(
            regions=frozenset(["R1"]),
            years=frozenset([2025]),
            technologies=frozenset(["WIND"]),
            fuels=frozenset(["ELEC"]),
            emissions=frozenset(),
            modes=frozenset(["MODE1"]),
            timeslices=frozenset(["S1D1H1", "S1D1H2"]),
            seasons=frozenset(["S1"]),
            daytypes=frozenset(["D1"]),
            dailytimebrackets=frozenset(["H1", "H2"]),
            storages=frozenset(),
        )
        with pytest.raises(ValueError, match="YearSplit"):
            params.validate(sets)

    def test_empty_year_split_skips_check(self):
        from pyoscomp.interfaces.parameters import TimeParameters
        from pyoscomp.interfaces.sets import OSeMOSYSSets

        params = TimeParameters()  # all empty
        sets = OSeMOSYSSets(
            regions=frozenset(["R1"]),
            years=frozenset([2025]),
            technologies=frozenset(["WIND"]),
            fuels=frozenset(["ELEC"]),
            emissions=frozenset(),
            modes=frozenset(["MODE1"]),
            timeslices=frozenset(["S1D1H1"]),
            seasons=frozenset(["S1"]),
            daytypes=frozenset(["D1"]),
            dailytimebrackets=frozenset(["H1"]),
            storages=frozenset(),
        )
        params.validate(sets)  # should not raise
