from .components.topology import TopologyComponent
from .components.time import TimeComponent
from .components.demand import DemandComponent
from .components.supply import SupplyComponent

class Scenario:
    def __init__(self, scenario_dir):
        """
        :param scenario_dir: The full path to the scenario directory (e.g., /path/to/project/tag_123)
        """
        self.scenario_dir = scenario_dir
        
        # Initialize components, passing the directory path down
        self.topology = TopologyComponent(scenario_dir)
        self.time = TimeComponent(scenario_dir)
        self.demand = DemandComponent(scenario_dir)
        self.supply = SupplyComponent(scenario_dir)
        # self.performance = PerformanceComponent(scenario_dir)  # Future component
        # self.economics = EconomicsComponent(scenario_dir)  # Future component
        # self.storage = StorageComponent(scenario_dir)  # Future component

    def build(self):
        """
        Finalize the scenario logic.
        """
        # Load all necessary data
        self.topology.load()
        self.time.load()
        self.demand.load()
        self.supply.load()

        # Process demand, supply
        self.demand.process()
        self.supply.process()

        # Save all components
        self.topology.save()
        self.time.save()
        self.demand.save()
        self.supply.save()

        print(f"Scenario built successfully in: {self.scenario_dir}")