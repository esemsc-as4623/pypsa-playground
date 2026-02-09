from .components.topology import TopologyComponent
from .components.time import TimeComponent
from .components.demand import DemandComponent
from .components.supply import SupplyComponent
from .components.economics import EconomicsComponent
from .components.performance import PerformanceComponent
from .validation.reference import validate_column_reference, validate_multi_column_reference

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

        # Cross-component reference validation
        self.validate_references()

        # Save all components
        self.topology.save()
        self.time.save()
        self.demand.save()
        self.supply.save()
        self.economics.save()

        print(f"Scenario built successfully in: {self.scenario_dir}")

    def validate_references(self):
        """
        Validate cross-component references to ensure all IDs used in one component exist in the relevant set files.
        Raises SchemaError if any reference is invalid.

        Checks performed:
        - TECHNOLOGYs in supply exist in TECHNOLOGY.csv
        - FUELs in supply exist in FUEL.csv
        - REGIONs in demand/supply exist in REGION.csv
        - (Extend as needed for other cross-references)
        """
        # TECHNOLOGY reference check
        if hasattr(self.supply, 'supply_df') and hasattr(self.topology, 'technology_df'):
            validate_column_reference(self.supply.supply_df, self.topology.technology_df, 'TECHNOLOGY', 'TECHNOLOGY', error_type="TECHNOLOGY ReferenceError")
        # FUEL reference check
        if hasattr(self.supply, 'supply_df') and hasattr(self.topology, 'fuel_df'):
            validate_column_reference(self.supply.supply_df, self.topology.fuel_df, 'FUEL', 'FUEL', error_type="FUEL ReferenceError")
        # REGION reference check (demand)
        if hasattr(self.demand, 'annual_demand_df') and hasattr(self.topology, 'region_df'):
            validate_column_reference(self.demand.annual_demand_df, self.topology.region_df, 'REGION', 'VALUE', error_type="REGION ReferenceError")
        # REGION reference check (supply)
        if hasattr(self.supply, 'supply_df') and hasattr(self.topology, 'region_df'):
            validate_column_reference(self.supply.supply_df, self.topology.region_df, 'REGION', 'VALUE', error_type="REGION ReferenceError")
        # Extend with more checks as needed