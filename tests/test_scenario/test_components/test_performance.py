# tests/test_scenario/test_components/test_performance.py

"""
Tests for PerformanceComponent.

Tests cover:
- Initialization and prerequisites
- owned_files class attribute
- Properties (technologies, defined_fuels, modes)
- DataFrame population via add_to_dataframe
- Validation (activity ratios, factor bounds)
- Load / save round-trip
- Edge cases (empty DataFrames, multiple technologies)
- Representation (__repr__)
"""

import math
import os
import pytest
import pandas as pd

from pyoscomp.scenario.components.performance import PerformanceComponent


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def perf(complete_scenario_dir):
    """Create PerformanceComponent with all prerequisites."""
    return PerformanceComponent(complete_scenario_dir)


@pytest.fixture
def perf_with_tech(complete_scenario_dir):
    """PerformanceComponent with one technology registered via DataFrames."""
    perf = PerformanceComponent(complete_scenario_dir)

    # Manually populate OperationalLife
    perf.operational_life = perf.add_to_dataframe(
        perf.operational_life,
        [{"REGION": "REGION1", "TECHNOLOGY": "GAS_CCGT", "VALUE": 30}],
        key_columns=["REGION", "TECHNOLOGY"],
    )

    # CapacityToActivityUnit
    perf.capacity_to_activity_unit = perf.add_to_dataframe(
        perf.capacity_to_activity_unit,
        [{"REGION": "REGION1", "TECHNOLOGY": "GAS_CCGT", "VALUE": 31.536}],
        key_columns=["REGION", "TECHNOLOGY"],
    )

    return perf


@pytest.fixture
def perf_with_ratios(perf_with_tech):
    """PerformanceComponent with activity ratios populated."""
    perf = perf_with_tech
    years = perf.years

    # InputActivityRatio: GAS → GAS_CCGT at 1/0.55 ≈ 1.818
    input_records = [
        {
            "REGION": "REGION1", "TECHNOLOGY": "GAS_CCGT",
            "FUEL": "GAS", "MODE_OF_OPERATION": "MODE1",
            "YEAR": y, "VALUE": 1.0 / 0.55,
        }
        for y in years
    ]
    perf.input_activity_ratio = perf.add_to_dataframe(
        perf.input_activity_ratio, input_records,
        key_columns=[
            "REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR"
        ],
    )

    # OutputActivityRatio: GAS_CCGT → ELEC at 1.0
    output_records = [
        {
            "REGION": "REGION1", "TECHNOLOGY": "GAS_CCGT",
            "FUEL": "ELEC", "MODE_OF_OPERATION": "MODE1",
            "YEAR": y, "VALUE": 1.0,
        }
        for y in years
    ]
    perf.output_activity_ratio = perf.add_to_dataframe(
        perf.output_activity_ratio, output_records,
        key_columns=[
            "REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR"
        ],
    )

    return perf


@pytest.fixture
def perf_full(perf_with_ratios):
    """PerformanceComponent with all six DataFrames populated."""
    perf = perf_with_ratios
    years = perf.years
    timeslices = perf.timeslices

    # CapacityFactor: 0.9 for all timeslices
    cf_records = [
        {
            "REGION": "REGION1", "TECHNOLOGY": "GAS_CCGT",
            "TIMESLICE": ts, "YEAR": y, "VALUE": 0.9,
        }
        for y in years
        for ts in timeslices
    ]
    perf.capacity_factor = perf.add_to_dataframe(
        perf.capacity_factor, cf_records,
        key_columns=["REGION", "TECHNOLOGY", "TIMESLICE", "YEAR"],
    )

    # AvailabilityFactor: 0.95 for all years
    af_records = [
        {
            "REGION": "REGION1", "TECHNOLOGY": "GAS_CCGT",
            "YEAR": y, "VALUE": 0.95,
        }
        for y in years
    ]
    perf.availability_factor = perf.add_to_dataframe(
        perf.availability_factor, af_records,
        key_columns=["REGION", "TECHNOLOGY", "YEAR"],
    )

    return perf


# =============================================================================
# Initialization Tests
# =============================================================================

class TestPerformanceInit:
    """Test PerformanceComponent initialization."""

    def test_init_loads_prerequisites(self, perf):
        """Initialization loads years, regions, timeslices."""
        assert perf.years is not None
        assert len(perf.years) == 6
        assert perf.regions is not None
        assert 'REGION1' in perf.regions
        assert perf.timeslices is not None
        assert len(perf.timeslices) > 0

    def test_init_missing_time_raises(self, topology_scenario_dir):
        """Missing time component raises AttributeError."""
        with pytest.raises(AttributeError):
            PerformanceComponent(topology_scenario_dir)

    def test_init_missing_topology_raises(self, empty_scenario_dir):
        """Missing topology raises error."""
        with pytest.raises((AttributeError, FileNotFoundError)):
            PerformanceComponent(empty_scenario_dir)

    def test_init_dataframes_empty(self, perf):
        """All six DataFrames are empty after init."""
        assert perf.operational_life.empty
        assert perf.capacity_to_activity_unit.empty
        assert perf.input_activity_ratio.empty
        assert perf.output_activity_ratio.empty
        assert perf.capacity_factor.empty
        assert perf.availability_factor.empty

    def test_init_dataframe_columns(self, perf):
        """DataFrames have correct columns from schema."""
        assert 'REGION' in perf.operational_life.columns
        assert 'TECHNOLOGY' in perf.operational_life.columns
        assert 'VALUE' in perf.operational_life.columns

        assert 'FUEL' in perf.input_activity_ratio.columns
        assert 'MODE_OF_OPERATION' in perf.input_activity_ratio.columns
        assert 'YEAR' in perf.input_activity_ratio.columns

        assert 'TIMESLICE' in perf.capacity_factor.columns


# =============================================================================
# owned_files Tests
# =============================================================================

class TestOwnedFiles:
    """Test owned_files class attribute."""

    def test_owned_files_contents(self):
        """owned_files contains all six performance CSV files."""
        expected = {
            'OperationalLife.csv',
            'CapacityToActivityUnit.csv',
            'InputActivityRatio.csv',
            'OutputActivityRatio.csv',
            'CapacityFactor.csv',
            'AvailabilityFactor.csv',
        }
        assert set(PerformanceComponent.owned_files) == expected

    def test_owned_files_count(self):
        """owned_files has exactly 6 entries."""
        assert len(PerformanceComponent.owned_files) == 6


# =============================================================================
# Properties Tests
# =============================================================================

class TestPerformanceProperties:
    """Test PerformanceComponent properties."""

    # --- technologies ---

    def test_technologies_empty(self, perf):
        """technologies empty when no OperationalLife data."""
        assert perf.technologies == []

    def test_technologies_populated(self, perf_with_tech):
        """technologies reflects OperationalLife entries."""
        assert 'GAS_CCGT' in perf_with_tech.technologies

    def test_technologies_unique(self, perf):
        """technologies returns unique values only."""
        perf.operational_life = perf.add_to_dataframe(
            perf.operational_life,
            [
                {"REGION": "REGION1", "TECHNOLOGY": "SOLAR", "VALUE": 25},
                {"REGION": "REGION1", "TECHNOLOGY": "SOLAR", "VALUE": 25},
            ],
            key_columns=["REGION", "TECHNOLOGY"],
        )
        assert perf.technologies.count('SOLAR') == 1

    def test_technologies_multiple(self, perf):
        """technologies lists multiple techs."""
        records = [
            {"REGION": "REGION1", "TECHNOLOGY": "SOLAR", "VALUE": 25},
            {"REGION": "REGION1", "TECHNOLOGY": "WIND", "VALUE": 25},
            {"REGION": "REGION1", "TECHNOLOGY": "GAS", "VALUE": 30},
        ]
        perf.operational_life = perf.add_to_dataframe(
            perf.operational_life, records,
            key_columns=["REGION", "TECHNOLOGY"],
        )
        techs = set(perf.technologies)
        assert techs == {'SOLAR', 'WIND', 'GAS'}

    # --- defined_fuels ---

    def test_defined_fuels_empty(self, perf):
        """defined_fuels empty when no activity ratios."""
        assert perf.defined_fuels == set()

    def test_defined_fuels_from_input(self, perf_with_ratios):
        """defined_fuels includes input fuels."""
        assert 'GAS' in perf_with_ratios.defined_fuels

    def test_defined_fuels_from_output(self, perf_with_ratios):
        """defined_fuels includes output fuels."""
        assert 'ELEC' in perf_with_ratios.defined_fuels

    def test_defined_fuels_union(self, perf_with_ratios):
        """defined_fuels is union of input and output fuels."""
        assert perf_with_ratios.defined_fuels == {'GAS', 'ELEC'}

    # --- modes ---

    def test_modes_default(self, perf):
        """modes returns {'MODE1'} when no data."""
        assert perf.modes == {'MODE1'}

    def test_modes_from_ratios(self, perf_with_ratios):
        """modes reflects activity ratio data."""
        assert 'MODE1' in perf_with_ratios.modes

    def test_modes_multiple(self, perf):
        """modes collects from both input and output ratios."""
        inp = [
            {
                "REGION": "REGION1", "TECHNOLOGY": "CHP",
                "FUEL": "GAS", "MODE_OF_OPERATION": "ELEC_MODE",
                "YEAR": 2025, "VALUE": 1.5,
            },
        ]
        out = [
            {
                "REGION": "REGION1", "TECHNOLOGY": "CHP",
                "FUEL": "ELEC", "MODE_OF_OPERATION": "CHP_MODE",
                "YEAR": 2025, "VALUE": 1.0,
            },
        ]
        perf.input_activity_ratio = perf.add_to_dataframe(
            perf.input_activity_ratio, inp,
            key_columns=[
                "REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR"
            ],
        )
        perf.output_activity_ratio = perf.add_to_dataframe(
            perf.output_activity_ratio, out,
            key_columns=[
                "REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR"
            ],
        )
        assert perf.modes == {'ELEC_MODE', 'CHP_MODE'}


# =============================================================================
# Validation Tests - Activity Ratios
# =============================================================================

class TestValidateActivityRatios:
    """Test _validate_activity_ratios and validate."""

    def test_validate_empty_passes(self, perf):
        """Empty component passes validation."""
        perf.validate()  # Should not raise

    def test_validate_complete_passes(self, perf_with_ratios):
        """Component with matching OL + output ratios passes."""
        perf_with_ratios.validate()  # Should not raise

    def test_validate_no_output_raises(self, perf_with_tech):
        """Technology with OL but no output ratio fails."""
        with pytest.raises(ValueError, match="Activity ratio validation failed"):
            perf_with_tech.validate()

    def test_validate_partial_output_raises(self, perf):
        """Some techs with outputs, others without, fails."""
        # Two techs in OL
        perf.operational_life = perf.add_to_dataframe(
            perf.operational_life,
            [
                {"REGION": "REGION1", "TECHNOLOGY": "SOLAR", "VALUE": 25},
                {"REGION": "REGION1", "TECHNOLOGY": "WIND", "VALUE": 25},
            ],
            key_columns=["REGION", "TECHNOLOGY"],
        )
        # Only SOLAR has output
        perf.output_activity_ratio = perf.add_to_dataframe(
            perf.output_activity_ratio,
            [
                {
                    "REGION": "REGION1", "TECHNOLOGY": "SOLAR",
                    "FUEL": "ELEC", "MODE_OF_OPERATION": "MODE1",
                    "YEAR": 2025, "VALUE": 1.0,
                },
            ],
            key_columns=[
                "REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR"
            ],
        )
        with pytest.raises(ValueError, match="WIND.*no outputs"):
            perf.validate()

    def test_validate_non_positive_input_ratio_raises(self, perf_with_ratios):
        """Non-positive input ratio fails validation."""
        # Overwrite with zero value
        perf_with_ratios.input_activity_ratio.loc[0, 'VALUE'] = 0.0
        with pytest.raises(ValueError, match="Non-positive InputActivityRatio"):
            perf_with_ratios.validate()

    def test_validate_negative_output_ratio_raises(self, perf_with_ratios):
        """Negative output ratio fails validation."""
        perf_with_ratios.output_activity_ratio.loc[0, 'VALUE'] = -1.0
        with pytest.raises(ValueError, match="Non-positive OutputActivityRatio"):
            perf_with_ratios.validate()

    def test_validate_error_message_includes_tech(self, perf):
        """Error message includes technology name when some techs have outputs."""
        # Two techs: only one has output → error names the missing one
        perf.operational_life = perf.add_to_dataframe(
            perf.operational_life,
            [
                {"REGION": "REGION1", "TECHNOLOGY": "GAS_CCGT", "VALUE": 30},
                {"REGION": "REGION1", "TECHNOLOGY": "SOLAR", "VALUE": 25},
            ],
            key_columns=["REGION", "TECHNOLOGY"],
        )
        perf.output_activity_ratio = perf.add_to_dataframe(
            perf.output_activity_ratio,
            [
                {
                    "REGION": "REGION1", "TECHNOLOGY": "SOLAR",
                    "FUEL": "ELEC", "MODE_OF_OPERATION": "MODE1",
                    "YEAR": 2025, "VALUE": 1.0,
                },
            ],
            key_columns=[
                "REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR"
            ],
        )
        with pytest.raises(ValueError, match="GAS_CCGT"):
            perf.validate()


# =============================================================================
# Validation Tests - Factor Bounds
# =============================================================================

class TestValidateFactorBounds:
    """Test _validate_factor_bounds."""

    def test_valid_capacity_factor(self, perf_full):
        """Capacity factor in [0, 1] passes."""
        perf_full.validate()  # Should not raise

    def test_capacity_factor_above_one_raises(self, perf_full):
        """Capacity factor > 1 fails."""
        perf_full.capacity_factor.loc[0, 'VALUE'] = 1.5
        with pytest.raises(ValueError, match="CapacityFactor"):
            perf_full.validate()

    def test_capacity_factor_below_zero_raises(self, perf_full):
        """Capacity factor < 0 fails."""
        perf_full.capacity_factor.loc[0, 'VALUE'] = -0.1
        with pytest.raises(ValueError, match="CapacityFactor"):
            perf_full.validate()

    def test_capacity_factor_zero_valid(self, perf_full):
        """Capacity factor == 0 is valid."""
        perf_full.capacity_factor['VALUE'] = 0.0
        perf_full.validate()  # Should not raise

    def test_capacity_factor_one_valid(self, perf_full):
        """Capacity factor == 1 is valid."""
        perf_full.capacity_factor['VALUE'] = 1.0
        perf_full.validate()  # Should not raise

    def test_availability_factor_above_one_raises(self, perf_full):
        """Availability factor > 1 fails."""
        perf_full.availability_factor.loc[0, 'VALUE'] = 1.01
        with pytest.raises(ValueError, match="AvailabilityFactor"):
            perf_full.validate()

    def test_availability_factor_below_zero_raises(self, perf_full):
        """Availability factor < 0 fails."""
        perf_full.availability_factor.loc[0, 'VALUE'] = -0.01
        with pytest.raises(ValueError, match="AvailabilityFactor"):
            perf_full.validate()

    def test_availability_factor_zero_valid(self, perf_full):
        """Availability factor == 0 is valid."""
        perf_full.availability_factor['VALUE'] = 0.0
        perf_full.validate()  # Should not raise

    def test_availability_factor_one_valid(self, perf_full):
        """Availability factor == 1 is valid."""
        perf_full.availability_factor['VALUE'] = 1.0
        perf_full.validate()  # Should not raise

    def test_empty_factors_pass(self, perf_with_ratios):
        """Empty capacity/availability DataFrames pass bounds check."""
        # perf_with_ratios has no CF/AF rows
        perf_with_ratios.validate()  # Should not raise


# =============================================================================
# Load Tests
# =============================================================================

class TestPerformanceLoad:
    """Test load method."""

    def test_load_round_trip(self, perf_full):
        """Save then load preserves all DataFrames."""
        perf_full.save()

        loaded = PerformanceComponent(perf_full.scenario_dir)
        loaded.load()

        assert set(loaded.technologies) == set(perf_full.technologies)
        assert loaded.defined_fuels == perf_full.defined_fuels
        assert len(loaded.operational_life) == len(perf_full.operational_life)
        assert len(loaded.input_activity_ratio) == len(
            perf_full.input_activity_ratio
        )
        assert len(loaded.output_activity_ratio) == len(
            perf_full.output_activity_ratio
        )
        assert len(loaded.capacity_factor) == len(perf_full.capacity_factor)
        assert len(loaded.availability_factor) == len(
            perf_full.availability_factor
        )

    def test_load_preserves_values(self, perf_full):
        """Loaded values match saved values."""
        perf_full.save()

        loaded = PerformanceComponent(perf_full.scenario_dir)
        loaded.load()

        # Check OperationalLife value
        ol_row = loaded.operational_life[
            loaded.operational_life['TECHNOLOGY'] == 'GAS_CCGT'
        ]
        assert ol_row['VALUE'].iloc[0] == 30

        # Check CAU value
        cau_row = loaded.capacity_to_activity_unit[
            loaded.capacity_to_activity_unit['TECHNOLOGY'] == 'GAS_CCGT'
        ]
        assert cau_row['VALUE'].iloc[0] == 31.536

        # Check InputActivityRatio value
        iar_row = loaded.input_activity_ratio[
            (loaded.input_activity_ratio['TECHNOLOGY'] == 'GAS_CCGT')
            & (loaded.input_activity_ratio['YEAR'] == 2025)
        ]
        assert math.isclose(iar_row['VALUE'].iloc[0], 1.0 / 0.55, rel_tol=1e-6)

        # Check CapacityFactor value
        cf_row = loaded.capacity_factor[
            (loaded.capacity_factor['TECHNOLOGY'] == 'GAS_CCGT')
            & (loaded.capacity_factor['YEAR'] == 2025)
        ]
        assert (cf_row['VALUE'] == 0.9).all()

        # Check AvailabilityFactor value
        af_row = loaded.availability_factor[
            (loaded.availability_factor['TECHNOLOGY'] == 'GAS_CCGT')
            & (loaded.availability_factor['YEAR'] == 2025)
        ]
        assert af_row['VALUE'].iloc[0] == 0.95

    def test_load_validates_after_round_trip(self, perf_full):
        """Loaded data still passes validation."""
        perf_full.save()
        loaded = PerformanceComponent(perf_full.scenario_dir)
        loaded.load()
        loaded.validate()  # Should not raise


# =============================================================================
# Save Tests
# =============================================================================

class TestPerformanceSave:
    """Test save method."""

    def test_save_creates_all_files(self, perf_full):
        """save creates all six owned CSV files."""
        perf_full.save()

        for filename in PerformanceComponent.owned_files:
            path = os.path.join(perf_full.scenario_dir, filename)
            assert os.path.exists(path), f"Missing: {filename}"

    def test_save_empty_creates_files(self, perf):
        """save with empty DataFrames still creates files."""
        perf.save()

        for filename in PerformanceComponent.owned_files:
            path = os.path.join(perf.scenario_dir, filename)
            assert os.path.exists(path), f"Missing: {filename}"

    def test_save_sorted_output(self, perf):
        """Saved DataFrames are sorted by key columns."""
        # Add two techs in reverse order
        perf.operational_life = perf.add_to_dataframe(
            perf.operational_life,
            [
                {"REGION": "REGION1", "TECHNOLOGY": "WIND", "VALUE": 25},
                {"REGION": "REGION1", "TECHNOLOGY": "GAS", "VALUE": 30},
            ],
            key_columns=["REGION", "TECHNOLOGY"],
        )
        perf.save()

        df = pd.read_csv(
            os.path.join(perf.scenario_dir, 'OperationalLife.csv')
        )
        techs = df['TECHNOLOGY'].tolist()
        assert techs == sorted(techs)

    def test_save_correct_columns(self, perf_full):
        """Saved CSVs have correct column sets."""
        perf_full.save()

        ol_df = pd.read_csv(
            os.path.join(perf_full.scenario_dir, 'OperationalLife.csv')
        )
        assert list(ol_df.columns) == ['REGION', 'TECHNOLOGY', 'VALUE']

        iar_df = pd.read_csv(
            os.path.join(perf_full.scenario_dir, 'InputActivityRatio.csv')
        )
        assert list(iar_df.columns) == [
            'REGION', 'TECHNOLOGY', 'FUEL', 'MODE_OF_OPERATION',
            'YEAR', 'VALUE',
        ]

        cf_df = pd.read_csv(
            os.path.join(perf_full.scenario_dir, 'CapacityFactor.csv')
        )
        assert list(cf_df.columns) == [
            'REGION', 'TECHNOLOGY', 'TIMESLICE', 'YEAR', 'VALUE',
        ]

        af_df = pd.read_csv(
            os.path.join(perf_full.scenario_dir, 'AvailabilityFactor.csv')
        )
        assert list(af_df.columns) == [
            'REGION', 'TECHNOLOGY', 'YEAR', 'VALUE',
        ]


# =============================================================================
# Multiple Technologies / Multi-Region
# =============================================================================

class TestMultipleTechnologies:
    """Test with multiple technologies and regions."""

    def test_two_technologies(self, perf):
        """Two technologies tracked independently."""
        perf.operational_life = perf.add_to_dataframe(
            perf.operational_life,
            [
                {"REGION": "REGION1", "TECHNOLOGY": "GAS", "VALUE": 30},
                {"REGION": "REGION1", "TECHNOLOGY": "SOLAR", "VALUE": 25},
            ],
            key_columns=["REGION", "TECHNOLOGY"],
        )

        techs = set(perf.technologies)
        assert techs == {'GAS', 'SOLAR'}

    def test_different_operational_lives(self, perf):
        """Different techs can have different OL values."""
        records = [
            {"REGION": "REGION1", "TECHNOLOGY": "GAS", "VALUE": 30},
            {"REGION": "REGION1", "TECHNOLOGY": "NUCLEAR", "VALUE": 60},
        ]
        perf.operational_life = perf.add_to_dataframe(
            perf.operational_life, records,
            key_columns=["REGION", "TECHNOLOGY"],
        )

        gas_ol = perf.operational_life[
            perf.operational_life['TECHNOLOGY'] == 'GAS'
        ]['VALUE'].iloc[0]
        nuke_ol = perf.operational_life[
            perf.operational_life['TECHNOLOGY'] == 'NUCLEAR'
        ]['VALUE'].iloc[0]

        assert gas_ol == 30
        assert nuke_ol == 60

    def test_multi_region(self, multi_region_time_dir):
        """Component works with multiple regions."""
        perf = PerformanceComponent(multi_region_time_dir)
        records = [
            {"REGION": "North", "TECHNOLOGY": "WIND", "VALUE": 25},
            {"REGION": "South", "TECHNOLOGY": "SOLAR", "VALUE": 25},
            {"REGION": "East", "TECHNOLOGY": "GAS", "VALUE": 30},
        ]
        perf.operational_life = perf.add_to_dataframe(
            perf.operational_life, records,
            key_columns=["REGION", "TECHNOLOGY"],
        )

        assert len(perf.technologies) == 3
        assert set(perf.regions) == {'North', 'South', 'East'}

    def test_multi_fuel_tracking(self, perf):
        """Multiple fuels across technologies tracked."""
        records = [
            {
                "REGION": "REGION1", "TECHNOLOGY": "GAS",
                "FUEL": "GAS", "MODE_OF_OPERATION": "MODE1",
                "YEAR": 2025, "VALUE": 1.8,
            },
            {
                "REGION": "REGION1", "TECHNOLOGY": "GAS",
                "FUEL": "ELEC", "MODE_OF_OPERATION": "MODE1",
                "YEAR": 2025, "VALUE": 1.0,
            },
            {
                "REGION": "REGION1", "TECHNOLOGY": "COAL",
                "FUEL": "COAL", "MODE_OF_OPERATION": "MODE1",
                "YEAR": 2025, "VALUE": 2.5,
            },
        ]
        perf.input_activity_ratio = perf.add_to_dataframe(
            perf.input_activity_ratio, records,
            key_columns=[
                "REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR"
            ],
        )

        out = [
            {
                "REGION": "REGION1", "TECHNOLOGY": "GAS",
                "FUEL": "ELEC", "MODE_OF_OPERATION": "MODE1",
                "YEAR": 2025, "VALUE": 1.0,
            },
            {
                "REGION": "REGION1", "TECHNOLOGY": "COAL",
                "FUEL": "ELEC", "MODE_OF_OPERATION": "MODE1",
                "YEAR": 2025, "VALUE": 1.0,
            },
        ]
        perf.output_activity_ratio = perf.add_to_dataframe(
            perf.output_activity_ratio, out,
            key_columns=[
                "REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR"
            ],
        )

        assert perf.defined_fuels == {'GAS', 'ELEC', 'COAL'}


# =============================================================================
# DataFrame Overwrite / Upsert Tests
# =============================================================================

class TestDataFrameUpsert:
    """Test add_to_dataframe upsert behavior for performance data."""

    def test_overwrite_operational_life(self, perf_with_tech):
        """Updating OL for same tech keeps latest value."""
        perf_with_tech.operational_life = perf_with_tech.add_to_dataframe(
            perf_with_tech.operational_life,
            [{"REGION": "REGION1", "TECHNOLOGY": "GAS_CCGT", "VALUE": 40}],
            key_columns=["REGION", "TECHNOLOGY"],
        )

        row = perf_with_tech.operational_life[
            perf_with_tech.operational_life['TECHNOLOGY'] == 'GAS_CCGT'
        ]
        assert len(row) == 1
        assert row['VALUE'].iloc[0] == 40

    def test_overwrite_capacity_factor(self, perf):
        """Updating CF for same key replaces value."""
        ts = perf.timeslices[0]
        records_v1 = [
            {
                "REGION": "REGION1", "TECHNOLOGY": "SOLAR",
                "TIMESLICE": ts, "YEAR": 2025, "VALUE": 0.8,
            },
        ]
        perf.capacity_factor = perf.add_to_dataframe(
            perf.capacity_factor, records_v1,
            key_columns=["REGION", "TECHNOLOGY", "TIMESLICE", "YEAR"],
        )
        assert perf.capacity_factor['VALUE'].iloc[0] == 0.8

        records_v2 = [
            {
                "REGION": "REGION1", "TECHNOLOGY": "SOLAR",
                "TIMESLICE": ts, "YEAR": 2025, "VALUE": 0.5,
            },
        ]
        perf.capacity_factor = perf.add_to_dataframe(
            perf.capacity_factor, records_v2,
            key_columns=["REGION", "TECHNOLOGY", "TIMESLICE", "YEAR"],
        )
        row = perf.capacity_factor[
            (perf.capacity_factor['TECHNOLOGY'] == 'SOLAR')
            & (perf.capacity_factor['YEAR'] == 2025)
            & (perf.capacity_factor['TIMESLICE'] == ts)
        ]
        assert len(row) == 1
        assert row['VALUE'].iloc[0] == 0.5


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_validate_called_twice(self, perf_full):
        """Calling validate twice is idempotent."""
        perf_full.validate()
        perf_full.validate()

    def test_save_load_empty(self, perf):
        """Round-trip with empty DataFrames works."""
        perf.save()
        loaded = PerformanceComponent(perf.scenario_dir)
        loaded.load()

        assert loaded.technologies == []
        assert loaded.defined_fuels == set()
        assert loaded.modes == {'MODE1'}

    def test_capacity_factor_all_years_timeslices(self, perf):
        """CF can be populated for all year × timeslice combinations."""
        years = perf.years
        timeslices = perf.timeslices
        expected_count = len(years) * len(timeslices)

        records = [
            {
                "REGION": "REGION1", "TECHNOLOGY": "SOLAR",
                "TIMESLICE": ts, "YEAR": y, "VALUE": 0.5,
            }
            for y in years
            for ts in timeslices
        ]
        perf.capacity_factor = perf.add_to_dataframe(
            perf.capacity_factor, records,
            key_columns=["REGION", "TECHNOLOGY", "TIMESLICE", "YEAR"],
        )

        assert len(perf.capacity_factor) == expected_count

    def test_availability_factor_all_years(self, perf):
        """AF can be populated for all years."""
        years = perf.years

        records = [
            {
                "REGION": "REGION1", "TECHNOLOGY": "GAS",
                "YEAR": y, "VALUE": 0.9,
            }
            for y in years
        ]
        perf.availability_factor = perf.add_to_dataframe(
            perf.availability_factor, records,
            key_columns=["REGION", "TECHNOLOGY", "YEAR"],
        )

        assert len(perf.availability_factor) == len(years)
        assert (perf.availability_factor['VALUE'] == 0.9).all()


# =============================================================================
# Representation Tests
# =============================================================================

class TestPerformanceRepr:
    """Test __repr__ output."""

    def test_repr_empty(self, perf):
        """repr shows component info with zero counts."""
        repr_str = repr(perf)
        assert "PerformanceComponent" in repr_str
        assert "technologies=0" in repr_str
        assert "fuels=0" in repr_str

    def test_repr_populated(self, perf_with_ratios):
        """repr shows correct counts."""
        repr_str = repr(perf_with_ratios)
        assert "PerformanceComponent" in repr_str
        assert "technologies=1" in repr_str
        assert "fuels=2" in repr_str

    def test_repr_includes_dir(self, perf):
        """repr includes scenario_dir."""
        repr_str = repr(perf)
        assert "scenario_dir=" in repr_str


# =============================================================================
# Integration with SupplyComponent
# =============================================================================

class TestPerformanceSupplyIntegration:
    """Test PerformanceComponent as used by SupplyComponent."""

    def test_supply_writes_to_performance(self, complete_scenario_dir):
        """SupplyComponent writes to PerformanceComponent DataFrames."""
        from pyoscomp.scenario.components.supply import SupplyComponent

        perf = PerformanceComponent(complete_scenario_dir)
        supply = SupplyComponent(complete_scenario_dir, performance=perf)

        supply.add_technology('REGION1', 'GAS_CCGT', operational_life=30)
        supply.set_conversion_technology(
            'REGION1', 'GAS_CCGT',
            input_fuel='GAS', output_fuel='ELEC',
            efficiency=0.55,
        )

        # Verify data landed in perf
        assert 'GAS_CCGT' in perf.technologies
        assert not perf.input_activity_ratio.empty
        assert not perf.output_activity_ratio.empty
        assert perf.defined_fuels == {'GAS', 'ELEC'}

    def test_supply_process_populates_factors(self, complete_scenario_dir):
        """SupplyComponent.process() populates CF and AF on perf."""
        from pyoscomp.scenario.components.supply import SupplyComponent

        perf = PerformanceComponent(complete_scenario_dir)
        supply = SupplyComponent(complete_scenario_dir, performance=perf)

        supply.add_technology('REGION1', 'SOLAR', operational_life=25)
        supply.set_resource_technology('REGION1', 'SOLAR', 'ELEC')
        supply.process()

        assert not perf.capacity_factor.empty
        assert not perf.availability_factor.empty
        # Default values should be 1.0
        assert (perf.capacity_factor['VALUE'] == 1.0).all()
        assert (perf.availability_factor['VALUE'] == 1.0).all()

    def test_full_workflow_save_load(self, complete_scenario_dir):
        """Full save + load round-trip through supply + performance."""
        from pyoscomp.scenario.components.supply import SupplyComponent

        perf = PerformanceComponent(complete_scenario_dir)
        supply = SupplyComponent(complete_scenario_dir, performance=perf)

        supply.add_technology('REGION1', 'GAS_CCGT', operational_life=30)
        supply.set_conversion_technology(
            'REGION1', 'GAS_CCGT',
            input_fuel='GAS', output_fuel='ELEC',
            efficiency=0.55,
        )
        supply.process()
        supply.save()
        perf.save()

        # Load fresh
        perf2 = PerformanceComponent(complete_scenario_dir)
        perf2.load()
        supply2 = SupplyComponent(complete_scenario_dir, performance=perf2)
        supply2.load()

        assert 'GAS_CCGT' in perf2.technologies
        assert 'GAS_CCGT' in supply2.technologies
        assert perf2.defined_fuels == {'GAS', 'ELEC'}
        perf2.validate()  # Should not raise
