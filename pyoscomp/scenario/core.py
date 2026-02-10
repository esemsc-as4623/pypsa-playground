from .components.topology import TopologyComponent
from .components.time import TimeComponent
from .components.demand import DemandComponent
from .components.supply import SupplyComponent
from .components.economics import EconomicsComponent
from .components.performance import PerformanceComponent
from .validation.cross_reference import validate_scenario

class Scenario:
    """
    Scenario class for orchestrating all scenario components and ensuring cross-component reference integrity.
    """
    def __init__(self, scenario_dir):
        """
        Initialize all scenario components and store the scenario directory path.

        Parameters
        ----------
        scenario_dir : str
            The full path to the scenario directory (e.g., /path/to/project/tag_123)
        """
        self.scenario_dir = scenario_dir
        # Initialize components, passing the directory path down
        self.topology = TopologyComponent(scenario_dir)
        self.time = TimeComponent(scenario_dir)
        self.demand = DemandComponent(scenario_dir)
        self.supply = SupplyComponent(scenario_dir)
        self.economics = EconomicsComponent(scenario_dir)
        # self.performance = PerformanceComponent(scenario_dir, self.supply)
        # self.storage = StorageComponent(scenario_dir)  # Future component


    def build(self):
        """
        Finalize the scenario logic: load, process, validate, and save all components.
        Runs cross-component reference validation after processing.
        """
        # Load all necessary data
        self.topology.load()
        self.time.load()
        self.demand.load()
        self.supply.load()
        self.economics.load()

        # Process demand, supply
        self.demand.process()
        self.supply.process()

        # Save all components
        self.topology.save()
        self.time.save()
        self.demand.save()
        self.supply.save()
        self.economics.save()

        # Cross-component reference validation (after all saves)
        try:
            validate_scenario(self.scenario_dir)
        except Exception as e:
            raise ValueError(f"Scenario validation failed: {e}")

        print(f"Scenario built successfully in: {self.scenario_dir}")