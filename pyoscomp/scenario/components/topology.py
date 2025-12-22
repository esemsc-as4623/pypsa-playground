# pyoscomp/scenario/components/topology.py

"""
Topology component for scenario building in PyPSA-OSeMOSYS Comparison Framework.
Note: This component handles the creation of nodes for the scenario.
Nodes are referred to as REGION in OSeMOSYS.
Nodes are referered to as Buses in PyPSA.
"""
from .base import ScenarioComponent

class TopologyComponent(ScenarioComponent):
    def process(self, nodes_input):
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

        # Save to REGION.csv in the correct directory
        self.write_csv("REGION.csv", node_list)
        
        return node_list