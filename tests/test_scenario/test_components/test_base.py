# tests/test_scenario/test_components/test_base.py

"""
Tests for ScenarioComponent base class.

Tests cover:
- Initialization and directory creation
- Schema-validated CSV I/O (read_csv, write_dataframe)
- DataFrame utilities (init_dataframe, add_to_dataframe)
- Prerequisite loading (load_years, load_regions, load_timeslices)
- check_prerequisites method
- Scenario directory operations (copy_scenario, file_exists)
"""

import os
import pytest
import pandas as pd
from pathlib import Path

from pyoscomp.scenario.components.base import ScenarioComponent
from pyoscomp.scenario.components.topology import TopologyComponent


# =============================================================================
# Test Fixtures
# =============================================================================

class ConcreteComponent(ScenarioComponent):
    """Concrete implementation for testing abstract base class."""

    owned_files = ['TestFile.csv']

    def load(self):
        pass

    def save(self):
        pass


@pytest.fixture
def component(empty_scenario_dir):
    """Create a concrete component instance for testing."""
    return ConcreteComponent(empty_scenario_dir)


# =============================================================================
# Initialization Tests
# =============================================================================

class TestScenarioComponentInit:
    """Test component initialization."""

    def test_init_creates_directory(self, tmp_path):
        """Directory should be created if it doesn't exist."""
        scenario_dir = tmp_path / "new_scenario"
        assert not scenario_dir.exists()

        component = ConcreteComponent(str(scenario_dir))

        assert scenario_dir.exists()
        assert component.scenario_dir == str(scenario_dir)

    def test_init_existing_directory(self, empty_scenario_dir):
        """Should work with existing directory."""
        component = ConcreteComponent(empty_scenario_dir)
        assert component.scenario_dir == empty_scenario_dir

    def test_schema_loaded(self, component):
        """Schema registry should be loaded."""
        assert component.schema is not None
        # Schema should have standard OSeMOSYS types
        assert component.schema.get_csv_columns("YEAR") is not None

    def test_owned_files_attribute(self):
        """owned_files should be defined by subclasses."""
        assert ConcreteComponent.owned_files == ['TestFile.csv']
        assert ScenarioComponent.owned_files == []


# =============================================================================
# DataFrame Initialization Tests
# =============================================================================

class TestInitDataframe:
    """Test init_dataframe method."""

    def test_init_year_dataframe(self, component):
        """Create empty YEAR DataFrame with correct schema."""
        df = component.init_dataframe("YEAR")

        assert isinstance(df, pd.DataFrame)
        assert df.empty
        assert "VALUE" in df.columns

    def test_init_yearsplit_dataframe(self, component):
        """Create empty YearSplit DataFrame with correct columns."""
        df = component.init_dataframe("YearSplit")

        assert "TIMESLICE" in df.columns
        assert "YEAR" in df.columns
        assert "VALUE" in df.columns

    def test_init_technology_dataframe(self, component):
        """Create empty TECHNOLOGY DataFrame."""
        df = component.init_dataframe("TECHNOLOGY")

        assert "VALUE" in df.columns
        assert df.empty

    def test_invalid_schema_raises(self, component):
        """Invalid schema name should raise ValueError."""
        with pytest.raises(ValueError):
            component.init_dataframe("NonExistentSchema")


# =============================================================================
# CSV Read/Write Tests
# =============================================================================

class TestReadWriteCsv:
    """Test CSV read/write operations."""

    def test_write_and_read_csv(self, component):
        """Round-trip write then read."""
        df = pd.DataFrame({"VALUE": [2025, 2026, 2027]})
        component.write_dataframe("YEAR.csv", df)

        loaded = component.read_csv("YEAR.csv")

        assert len(loaded) == 3
        assert list(loaded["VALUE"]) == [2025, 2026, 2027]

    def test_read_missing_file_raises(self, component):
        """Reading non-existent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            component.read_csv("NonExistent.csv")

    def test_read_optional_missing_returns_none(self, component):
        """read_csv with optional=True returns None for missing file."""
        result = component.read_csv("NonExistent.csv", optional=True)
        assert result is None

    def test_read_csv_optional_method(self, component):
        """read_csv_optional convenience method."""
        result = component.read_csv_optional("NonExistent.csv")
        assert result is None

    def test_read_csv_optional_existing(self, component):
        """read_csv_optional returns DataFrame for existing file."""
        df = pd.DataFrame({"VALUE": [2025]})
        component.write_dataframe("YEAR.csv", df)

        result = component.read_csv_optional("YEAR.csv")
        assert result is not None
        assert len(result) == 1

    def test_write_validates_schema(self, component):
        """Writing DataFrame with wrong columns should fail validation."""
        df = pd.DataFrame({"WRONG_COL": [1, 2, 3]})

        with pytest.raises(ValueError):
            component.write_dataframe("YEAR.csv", df)

    def test_file_exists(self, component):
        """file_exists method."""
        assert not component.file_exists("YEAR.csv")

        df = pd.DataFrame({"VALUE": [2025]})
        component.write_dataframe("YEAR.csv", df)

        assert component.file_exists("YEAR.csv")


# =============================================================================
# add_to_dataframe Tests
# =============================================================================

class TestAddToDataframe:
    """Test add_to_dataframe method for DataFrame manipulation."""

    def test_add_to_empty_dataframe(self, component):
        """Adding records to empty DataFrame."""
        df = pd.DataFrame(columns=["REGION", "VALUE"])
        records = [
            {"REGION": "R1", "VALUE": 100},
            {"REGION": "R2", "VALUE": 200}
        ]

        result = component.add_to_dataframe(df, records, key_columns=["REGION"])

        assert len(result) == 2
        assert set(result["REGION"]) == {"R1", "R2"}

    def test_add_with_duplicates_keep_last(self, component):
        """Duplicate keys: keep='last' (default)."""
        df = pd.DataFrame({"REGION": ["R1"], "VALUE": [100]})
        records = [{"REGION": "R1", "VALUE": 999}]

        result = component.add_to_dataframe(
            df, records, key_columns=["REGION"], keep='last'
        )

        assert len(result) == 1
        assert result.iloc[0]["VALUE"] == 999  # New value

    def test_add_with_duplicates_keep_first(self, component):
        """Duplicate keys: keep='first'."""
        df = pd.DataFrame({"REGION": ["R1"], "VALUE": [100]})
        records = [{"REGION": "R1", "VALUE": 999}]

        result = component.add_to_dataframe(
            df, records, key_columns=["REGION"], keep='first'
        )

        assert len(result) == 1
        assert result.iloc[0]["VALUE"] == 100  # Original value

    def test_add_compound_key(self, component):
        """Compound key columns."""
        df = pd.DataFrame({
            "REGION": ["R1", "R1"],
            "YEAR": [2025, 2030],
            "VALUE": [100, 200]
        })
        records = [{"REGION": "R1", "YEAR": 2025, "VALUE": 150}]

        result = component.add_to_dataframe(
            df, records, key_columns=["REGION", "YEAR"]
        )

        assert len(result) == 2  # Still 2 rows
        r1_2025 = result[(result["REGION"] == "R1") & (result["YEAR"] == 2025)]
        assert r1_2025["VALUE"].iloc[0] == 150  # Updated

    def test_invalid_keep_raises(self, component):
        """Invalid 'keep' parameter should raise ValueError."""
        df = pd.DataFrame(columns=["VALUE"])
        with pytest.raises(ValueError, match="'keep' must be"):
            component.add_to_dataframe(df, [], key_columns=["VALUE"], keep='invalid')


# =============================================================================
# Prerequisite Loading Tests
# =============================================================================

class TestPrerequisiteLoading:
    """Test prerequisite loading methods."""

    def test_load_years(self, time_scenario_dir):
        """load_years returns sorted year list."""
        component = ConcreteComponent(time_scenario_dir)
        years = component.load_years()

        assert years == [2025, 2030]

    def test_load_years_missing_raises(self, empty_scenario_dir):
        """load_years raises FileNotFoundError if YEAR.csv missing."""
        component = ConcreteComponent(empty_scenario_dir)

        with pytest.raises(FileNotFoundError):
            component.load_years()

    def test_load_years_empty_raises(self, empty_scenario_dir):
        """load_years raises ValueError if YEAR.csv is empty."""
        component = ConcreteComponent(empty_scenario_dir)
        # Write empty YEAR.csv
        pd.DataFrame({"VALUE": []}).to_csv(
            os.path.join(empty_scenario_dir, "YEAR.csv"), index=False
        )

        with pytest.raises(ValueError, match="No years defined"):
            component.load_years()

    def test_load_regions(self, topology_scenario_dir):
        """load_regions returns region list."""
        component = ConcreteComponent(topology_scenario_dir)
        regions = component.load_regions()

        assert set(regions) == {"REGION1", "REGION2"}

    def test_load_regions_missing_raises(self, empty_scenario_dir):
        """load_regions raises FileNotFoundError if REGION.csv missing."""
        component = ConcreteComponent(empty_scenario_dir)

        with pytest.raises(FileNotFoundError):
            component.load_regions()

    def test_load_timeslices(self, time_scenario_dir):
        """load_timeslices returns timeslice list."""
        component = ConcreteComponent(time_scenario_dir)
        timeslices = component.load_timeslices()

        assert len(timeslices) == 4  # 2 seasons × 2 brackets

    def test_load_technologies_no_file(self, empty_scenario_dir):
        """load_technologies returns empty set if file doesn't exist."""
        component = ConcreteComponent(empty_scenario_dir)
        technologies = component.load_technologies()

        assert technologies == set()

    def test_load_fuels_no_file(self, empty_scenario_dir):
        """load_fuels returns empty set if file doesn't exist."""
        component = ConcreteComponent(empty_scenario_dir)
        fuels = component.load_fuels()

        assert fuels == set()


# =============================================================================
# check_prerequisites Tests
# =============================================================================

class TestCheckPrerequisites:
    """Test check_prerequisites method."""

    def test_check_no_requirements(self, empty_scenario_dir):
        """No requirements returns empty dict values."""
        component = ConcreteComponent(empty_scenario_dir)
        result = component.check_prerequisites()

        assert result['years'] is None
        assert result['regions'] is None
        assert result['timeslices'] is None

    def test_check_require_years_success(self, time_scenario_dir):
        """Requiring years with YEAR.csv present succeeds."""
        component = ConcreteComponent(time_scenario_dir)
        result = component.check_prerequisites(require_years=True)

        assert result['years'] == [2025, 2030]

    def test_check_require_years_failure(self, empty_scenario_dir):
        """Requiring years without YEAR.csv raises AttributeError."""
        component = ConcreteComponent(empty_scenario_dir)

        with pytest.raises(AttributeError, match="YEAR.csv required"):
            component.check_prerequisites(require_years=True)

    def test_check_require_regions_success(self, topology_scenario_dir):
        """Requiring regions with REGION.csv present succeeds."""
        component = ConcreteComponent(topology_scenario_dir)
        result = component.check_prerequisites(require_regions=True)

        assert set(result['regions']) == {"REGION1", "REGION2"}

    def test_check_require_regions_failure(self, empty_scenario_dir):
        """Requiring regions without REGION.csv raises AttributeError."""
        component = ConcreteComponent(empty_scenario_dir)

        with pytest.raises(AttributeError, match="REGION.csv required"):
            component.check_prerequisites(require_regions=True)

    def test_check_require_timeslices_success(self, time_scenario_dir):
        """Requiring timeslices with TIMESLICE.csv present succeeds."""
        component = ConcreteComponent(time_scenario_dir)
        result = component.check_prerequisites(require_timeslices=True)

        assert len(result['timeslices']) == 4

    def test_check_multiple_requirements(self, time_scenario_dir):
        """Multiple requirements checked together."""
        component = ConcreteComponent(time_scenario_dir)
        result = component.check_prerequisites(
            require_years=True,
            require_regions=True,
            require_timeslices=True
        )

        assert result['years'] == [2025, 2030]
        assert result['regions'] == ['REGION1']
        assert len(result['timeslices']) == 4


# =============================================================================
# Scenario Directory Operations Tests
# =============================================================================

class TestScenarioDirectoryOps:
    """Test scenario directory operations."""

    def test_copy_scenario(self, time_scenario_dir, tmp_path):
        """copy_scenario copies entire directory."""
        target = tmp_path / "copy_target"

        ScenarioComponent.copy_scenario(time_scenario_dir, str(target))

        assert target.exists()
        assert (target / "YEAR.csv").exists()
        assert (target / "REGION.csv").exists()

    def test_copy_scenario_overwrite(self, time_scenario_dir, tmp_path):
        """copy_scenario with overwrite=True replaces existing."""
        target = tmp_path / "copy_target"
        target.mkdir()
        (target / "EXTRA.txt").write_text("should be deleted")

        ScenarioComponent.copy_scenario(
            time_scenario_dir, str(target), overwrite=True
        )

        assert (target / "YEAR.csv").exists()
        assert not (target / "EXTRA.txt").exists()

    def test_copy_scenario_merge(self, time_scenario_dir, tmp_path):
        """copy_scenario without overwrite merges files."""
        target = tmp_path / "merge_target"
        target.mkdir()
        (target / "EXTRA.txt").write_text("should remain")
        # Write a file that exists in source
        (target / "YEAR.csv").write_text("original")

        ScenarioComponent.copy_scenario(
            time_scenario_dir, str(target), overwrite=False
        )

        # EXTRA.txt should still exist
        assert (target / "EXTRA.txt").exists()
        # YEAR.csv should NOT be overwritten (merge mode)
        assert (target / "YEAR.csv").read_text() == "original"

    def test_get_file_path(self, component):
        """get_file_path returns correct Path."""
        path = component.get_file_path("YEAR.csv")

        assert isinstance(path, Path)
        assert path.name == "YEAR.csv"
        assert str(path.parent) == component.scenario_dir

    def test_repr(self, component):
        """Component repr shows class name and directory."""
        repr_str = repr(component)

        assert "ConcreteComponent" in repr_str
        assert component.scenario_dir in repr_str
