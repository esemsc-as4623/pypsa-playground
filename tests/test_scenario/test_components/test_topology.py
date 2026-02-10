# tests/test_scenario/test_components/test_topology.py

"""
Tests for TopologyComponent.

Tests cover:
- Initialization
- Properties (regions, num_regions)
- add_nodes (int and list variations)
- add_region / remove_region
- load / save operations
- validate method
- Magic methods (__repr__, __contains__)
"""

import os
import pytest
import pandas as pd

from pyoscomp.scenario.components.topology import TopologyComponent


# =============================================================================
# Initialization Tests
# =============================================================================

class TestTopologyInit:
    """Test TopologyComponent initialization."""

    def test_init_creates_empty_df(self, empty_scenario_dir):
        """Initialization creates empty regions DataFrame."""
        topology = TopologyComponent(empty_scenario_dir)

        assert topology.regions_df.empty
        assert "VALUE" in topology.regions_df.columns

    def test_owned_files(self):
        """owned_files should be REGION.csv only."""
        assert TopologyComponent.owned_files == ['REGION.csv']


# =============================================================================
# Properties Tests
# =============================================================================

class TestTopologyProperties:
    """Test topology properties."""

    def test_regions_empty(self, empty_scenario_dir):
        """regions property on empty topology."""
        topology = TopologyComponent(empty_scenario_dir)
        assert topology.regions == []

    def test_regions_with_data(self, empty_scenario_dir):
        """regions property returns list of region names."""
        topology = TopologyComponent(empty_scenario_dir)
        topology.add_nodes(['A', 'B', 'C'])

        assert set(topology.regions) == {'A', 'B', 'C'}

    def test_num_regions_empty(self, empty_scenario_dir):
        """num_regions on empty topology."""
        topology = TopologyComponent(empty_scenario_dir)
        assert topology.num_regions == 0

    def test_num_regions_with_data(self, empty_scenario_dir):
        """num_regions returns correct count."""
        topology = TopologyComponent(empty_scenario_dir)
        topology.add_nodes(5)

        assert topology.num_regions == 5


# =============================================================================
# add_nodes Tests
# =============================================================================

class TestAddNodes:
    """Test add_nodes method."""

    def test_add_nodes_with_int(self, empty_scenario_dir):
        """Add N generic nodes using integer."""
        topology = TopologyComponent(empty_scenario_dir)
        result = topology.add_nodes(3)

        assert result == ['Node_1', 'Node_2', 'Node_3']
        assert topology.regions == ['Node_1', 'Node_2', 'Node_3']

    def test_add_nodes_with_list(self, empty_scenario_dir):
        """Add named nodes using list."""
        topology = TopologyComponent(empty_scenario_dir)
        result = topology.add_nodes(['Germany', 'France', 'Spain'])

        assert result == ['Germany', 'France', 'Spain']
        assert topology.regions == ['Germany', 'France', 'Spain']

    def test_add_nodes_replaces_existing(self, empty_scenario_dir):
        """add_nodes replaces any existing regions."""
        topology = TopologyComponent(empty_scenario_dir)
        topology.add_nodes(['A', 'B'])
        topology.add_nodes(['X', 'Y', 'Z'])

        assert topology.regions == ['X', 'Y', 'Z']
        assert 'A' not in topology.regions

    def test_add_nodes_zero_raises(self, empty_scenario_dir):
        """add_nodes(0) should raise ValueError."""
        topology = TopologyComponent(empty_scenario_dir)

        with pytest.raises(ValueError, match="positive"):
            topology.add_nodes(0)

    def test_add_nodes_negative_raises(self, empty_scenario_dir):
        """add_nodes with negative int should raise ValueError."""
        topology = TopologyComponent(empty_scenario_dir)

        with pytest.raises(ValueError, match="positive"):
            topology.add_nodes(-1)

    def test_add_nodes_duplicate_names_raises(self, empty_scenario_dir):
        """add_nodes with duplicate names should raise ValueError."""
        topology = TopologyComponent(empty_scenario_dir)

        with pytest.raises(ValueError, match="unique"):
            topology.add_nodes(['A', 'B', 'A'])

    def test_add_nodes_invalid_type_raises(self, empty_scenario_dir):
        """add_nodes with invalid type should raise ValueError."""
        topology = TopologyComponent(empty_scenario_dir)

        with pytest.raises(ValueError, match="int or list"):
            topology.add_nodes("single_string")

    def test_add_nodes_converts_to_string(self, empty_scenario_dir):
        """add_nodes converts non-string list items to string."""
        topology = TopologyComponent(empty_scenario_dir)
        topology.add_nodes([1, 2, 3])

        assert topology.regions == ['1', '2', '3']


# =============================================================================
# add_region / remove_region Tests
# =============================================================================

class TestAddRemoveRegion:
    """Test add_region and remove_region methods."""

    def test_add_region(self, empty_scenario_dir):
        """add_region adds single region."""
        topology = TopologyComponent(empty_scenario_dir)
        topology.add_nodes(['A'])
        topology.add_region('B')

        assert set(topology.regions) == {'A', 'B'}

    def test_add_region_to_empty(self, empty_scenario_dir):
        """add_region to empty topology."""
        topology = TopologyComponent(empty_scenario_dir)
        topology.add_region('First')

        assert topology.regions == ['First']

    def test_add_region_duplicate_raises(self, empty_scenario_dir):
        """add_region with existing name raises ValueError."""
        topology = TopologyComponent(empty_scenario_dir)
        topology.add_nodes(['A', 'B'])

        with pytest.raises(ValueError, match="already exists"):
            topology.add_region('A')

    def test_remove_region(self, empty_scenario_dir):
        """remove_region removes specified region."""
        topology = TopologyComponent(empty_scenario_dir)
        topology.add_nodes(['A', 'B', 'C'])
        topology.remove_region('B')

        assert set(topology.regions) == {'A', 'C'}

    def test_remove_region_not_found_raises(self, empty_scenario_dir):
        """remove_region with non-existent region raises ValueError."""
        topology = TopologyComponent(empty_scenario_dir)
        topology.add_nodes(['A'])

        with pytest.raises(ValueError, match="not found"):
            topology.remove_region('X')

    def test_remove_all_regions(self, empty_scenario_dir):
        """Removing all regions leaves empty topology."""
        topology = TopologyComponent(empty_scenario_dir)
        topology.add_nodes(['A'])
        topology.remove_region('A')

        assert topology.num_regions == 0


# =============================================================================
# Load / Save Tests
# =============================================================================

class TestTopologyLoadSave:
    """Test load and save operations."""

    def test_save_creates_file(self, empty_scenario_dir):
        """save creates REGION.csv."""
        topology = TopologyComponent(empty_scenario_dir)
        topology.add_nodes(['R1', 'R2'])
        topology.save()

        assert os.path.exists(os.path.join(empty_scenario_dir, "REGION.csv"))

    def test_save_content(self, empty_scenario_dir):
        """save writes correct content."""
        topology = TopologyComponent(empty_scenario_dir)
        topology.add_nodes(['North', 'South'])
        topology.save()

        df = pd.read_csv(os.path.join(empty_scenario_dir, "REGION.csv"))
        assert set(df['VALUE']) == {'North', 'South'}

    def test_load_restores_data(self, empty_scenario_dir):
        """load restores data from REGION.csv."""
        # First save
        topology1 = TopologyComponent(empty_scenario_dir)
        topology1.add_nodes(['A', 'B', 'C'])
        topology1.save()

        # Then load
        topology2 = TopologyComponent(empty_scenario_dir)
        topology2.load()

        assert set(topology2.regions) == {'A', 'B', 'C'}

    def test_load_missing_file_raises(self, empty_scenario_dir):
        """load raises FileNotFoundError if REGION.csv missing."""
        topology = TopologyComponent(empty_scenario_dir)

        with pytest.raises(FileNotFoundError):
            topology.load()

    def test_round_trip(self, empty_scenario_dir):
        """Save and load preserves data."""
        regions = ['Germany', 'France', 'Italy', 'Spain', 'Poland']

        topology1 = TopologyComponent(empty_scenario_dir)
        topology1.add_nodes(regions)
        topology1.save()

        topology2 = TopologyComponent(empty_scenario_dir)
        topology2.load()

        assert topology2.regions == regions


# =============================================================================
# Validation Tests
# =============================================================================

class TestTopologyValidation:
    """Test validate method."""

    def test_validate_success(self, empty_scenario_dir):
        """Valid topology passes validation."""
        topology = TopologyComponent(empty_scenario_dir)
        topology.add_nodes(['R1', 'R2'])

        # Should not raise
        topology.validate()

    def test_validate_empty_raises(self, empty_scenario_dir):
        """Empty topology fails validation."""
        topology = TopologyComponent(empty_scenario_dir)

        with pytest.raises(ValueError, match="No regions defined"):
            topology.validate()

    def test_validate_duplicates_raises(self, empty_scenario_dir):
        """Duplicates in DataFrame fail validation."""
        topology = TopologyComponent(empty_scenario_dir)
        # Manually create duplicate (bypassing add_nodes validation)
        topology.regions_df = pd.DataFrame({"VALUE": ['A', 'A', 'B']})

        with pytest.raises(ValueError, match="Duplicate"):
            topology.validate()


# =============================================================================
# Magic Methods Tests
# =============================================================================

class TestTopologyMagicMethods:
    """Test magic methods."""

    def test_repr(self, empty_scenario_dir):
        """__repr__ shows component info."""
        topology = TopologyComponent(empty_scenario_dir)
        repr_str = repr(topology)

        assert "TopologyComponent" in repr_str
        assert empty_scenario_dir in repr_str

    def test_contains(self, empty_scenario_dir):
        """__contains__ checks region membership."""
        topology = TopologyComponent(empty_scenario_dir)
        topology.add_nodes(['A', 'B'])

        assert 'A' in topology
        assert 'B' in topology
        assert 'C' not in topology


# =============================================================================
# Integration Tests
# =============================================================================

class TestTopologyIntegration:
    """Integration tests for topology component."""

    def test_full_workflow(self, empty_scenario_dir):
        """Complete workflow: create, modify, save, load, validate."""
        # Create and set up
        topology = TopologyComponent(empty_scenario_dir)
        topology.add_nodes(['Initial'])
        topology.add_region('Added1')
        topology.add_region('Added2')
        topology.remove_region('Initial')

        # Validate before save
        topology.validate()

        # Save
        topology.save()

        # Load in new instance
        loaded = TopologyComponent(empty_scenario_dir)
        loaded.load()

        # Verify
        assert set(loaded.regions) == {'Added1', 'Added2'}
        loaded.validate()

    def test_modify_after_load(self, topology_scenario_dir):
        """Modify topology after loading."""
        topology = TopologyComponent(topology_scenario_dir)
        topology.load()

        original_count = topology.num_regions
        topology.add_region('NewRegion')

        assert topology.num_regions == original_count + 1
        assert 'NewRegion' in topology.regions
