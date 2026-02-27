# pyoscomp/scenario/components/topology.py

"""
Topology component for scenario building in PyPSA-OSeMOSYS Comparison Framework.

This component handles spatial structure definitions:
- REGION set (nodes/buses in the energy system network)

OSeMOSYS Terminology: REGION
PyPSA Terminology: Bus

This is typically the first component to be initialized in a scenario, as most
other components depend on regions being defined.
"""

import pandas as pd
from typing import List, Union

from .base import ScenarioComponent


class TopologyComponent(ScenarioComponent):
    """
    Topology component for spatial structure (regions/nodes).

    Handles OSeMOSYS REGION set creation and management. This component has no
    prerequisites and is typically initialized first.

    Attributes
    ----------
    regions_df : pd.DataFrame
        DataFrame containing region definitions (VALUE column).

    Owned Files
    -----------
    - REGION.csv: List of region identifiers

    Example
    -------
    Basic usage::

        topology = TopologyComponent(scenario_dir)

        # Create nodes by name
        topology.add_nodes(['North', 'South', 'East'])
        topology.save()

        # Or create N generic nodes
        topology.add_nodes(5)  # Creates Node_1, Node_2, ..., Node_5
        topology.save()

        # Load existing topology
        topology.load()
        print(topology.regions)  # ['North', 'South', 'East']

    See Also
    --------
    component_mapping.md : Full documentation of topology ownership
    """

    owned_files = ['REGION.csv']

    def __init__(self, scenario_dir: str):
        """
        Initialize topology component.

        Parameters
        ----------
        scenario_dir : str
            Path to the scenario directory.
        """
        super().__init__(scenario_dir)

        # Initialize empty regions DataFrame
        self.regions_df = self.init_dataframe("REGION")

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def regions(self) -> List[str]:
        """
        Get list of defined region identifiers.

        Returns
        -------
        list of str
            Region identifiers (empty list if none defined).
        """
        if self.regions_df.empty:
            return []
        return self.regions_df['VALUE'].tolist()

    @property
    def num_regions(self) -> int:
        """Get number of defined regions."""
        return len(self.regions_df)

    # =========================================================================
    # Load and Save
    # =========================================================================

    def load(self) -> None:
        """
        Load topology from REGION.csv.

        Raises
        ------
        FileNotFoundError
            If REGION.csv does not exist.
        ValueError
            If file fails schema validation.
        """
        self.regions_df = self.read_csv("REGION.csv")

    def save(self) -> None:
        """
        Save topology to REGION.csv.

        Raises
        ------
        ValueError
            If DataFrame fails schema validation.
        """
        self.write_dataframe("REGION.csv", self.regions_df)

    # =========================================================================
    # User Input Methods
    # =========================================================================

    def add_nodes(self, nodes_input: Union[int, List[str]]) -> List[str]:
        """
        Define regions (nodes) for the scenario.

        Parameters
        ----------
        nodes_input : int or list of str
            If int: Create N generically named nodes (Node_1, Node_2, ...).
            If list: Use the provided names as region identifiers.

        Returns
        -------
        list of str
            The list of region names that were created.

        Raises
        ------
        ValueError
            If nodes_input is not int or list, or if list contains duplicates.

        Examples
        --------
        Create generic nodes::

            >>> topology.add_nodes(3)
            ['Node_1', 'Node_2', 'Node_3']

        Create named nodes::

            >>> topology.add_nodes(['Germany', 'France', 'Spain'])
            ['Germany', 'France', 'Spain']
        """
        if isinstance(nodes_input, int):
            if nodes_input <= 0:
                raise ValueError("Number of nodes must be positive")
            node_list = [f"Node_{i+1}" for i in range(nodes_input)]

        elif isinstance(nodes_input, list):
            node_list = [str(n) for n in nodes_input]
            # Check for duplicates
            if len(node_list) != len(set(node_list)):
                raise ValueError("Node names must be unique")

        else:
            raise ValueError(
                f"nodes_input must be int or list of str, got {type(nodes_input)}"
            )

        self.regions_df = pd.DataFrame({"VALUE": node_list})
        return node_list

    def add_region(self, region_name: str) -> None:
        """
        Add a single region to the topology.

        Parameters
        ----------
        region_name : str
            Name of the region to add.

        Raises
        ------
        ValueError
            If region already exists.
        """
        if region_name in self.regions:
            raise ValueError(f"Region '{region_name}' already exists")

        new_record = [{"VALUE": region_name}]
        self.regions_df = self.add_to_dataframe(
            self.regions_df, new_record, key_columns=["VALUE"]
        )

    def remove_region(self, region_name: str) -> None:
        """
        Remove a region from the topology.

        Parameters
        ----------
        region_name : str
            Name of the region to remove.

        Raises
        ------
        ValueError
            If region does not exist.
        """
        if region_name not in self.regions:
            raise ValueError(f"Region '{region_name}' not found")

        self.regions_df = self.regions_df[
            self.regions_df['VALUE'] != region_name
        ].reset_index(drop=True)

    # =========================================================================
    # Validation
    # =========================================================================

    def validate(self) -> None:
        """
        Validate topology state.

        Raises
        ------
        ValueError
            If no regions defined or duplicate region names exist.
        """
        if self.regions_df.empty:
            raise ValueError("No regions defined in topology")

        # Check for duplicates
        if self.regions_df['VALUE'].duplicated().any():
            raise ValueError("Duplicate region names found")

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def clear(self) -> None:
        """Remove all regions."""
        self.regions_df = self.init_dataframe("REGION")

    def __repr__(self) -> str:
        return (
            f"TopologyComponent(scenario_dir='{self.scenario_dir}', "
            f"regions={self.num_regions})"
        )

    def __contains__(self, region: str) -> bool:
        """Check if a region exists."""
        return region in self.regions