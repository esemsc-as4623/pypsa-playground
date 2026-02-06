# pyoscomp/scenario/components/topology.py

"""
Topology component for scenario building in PyPSA-OSeMOSYS Comparison Framework.
Note: This component handles the creation of nodes for the scenario.
Nodes are referred to as REGION in OSeMOSYS.
Nodes are referered to as Buses in PyPSA.
"""
import pandas as pd

from .base import ScenarioComponent

class TopologyComponent(ScenarioComponent):
    """
    Topology component for node definitions.
    Handels OSeMOSYS REGION creation.

    Prerequisites:
        - None

    Example usage::
        topology = TopologyComponent(scenario_dir)
        nodes = topology.add_nodes(5)  # Creates 5 generic nodes
        # or
        nodes = topology.add_nodes(['NodeA', 'NodeB', 'NodeC'])  # Uses specified names
    """
    def __init__(self, scenario_dir):
        super().__init__(scenario_dir)

        # Node parameters
        self.regions_df = self.init_dataframe("REGION")

    # === Load and Save Methods ===
    def load(self):
        """
        Load topology parameter CSV files into DataFrames.
        Uses read_csv from base class.
        :raises FileNotFoundError if any required file is missing.
        :raises ValueError if any file has missing or incorrect columns.
        """
        self.regions_df = self.read_csv("REGION.csv")

    def save(self):
        """
        Save topology parameter DataFrames to CSV files in the scenario directory.
        Uses write_csv and write_dataframe from base class.
        """
        self.write_dataframe("REGION.csv", self.regions_df)

    # === User Input Methods ===
    def add_nodes(self, nodes_input):
        """
        Generates the list of nodes and writes to REGION.csv.

        :param nodes_input: int (create N generic nodes) or list[str] (use specific names)
        :return: list[str] The list of node names
        """
        node_list = []

        if isinstance(nodes_input, int):
            # Create N generically named nodes: Node_1, Node_2, etc.
            node_list = [f"Node_{i+1}" for i in range(nodes_input)]
        elif isinstance(nodes_input, list):
            # Use provided names
            node_list = [str(n) for n in nodes_input]
        else:
            raise ValueError("nodes_input must be an integer or a list of strings.")
        
        self.regions_df = pd.DataFrame({"VALUE": node_list})