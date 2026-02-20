# pyoscomp/scenario/core.py

from typing import Optional

from .components.topology import TopologyComponent
from .components.time import TimeComponent
from .components.demand import DemandComponent
from .components.performance import PerformanceComponent
from .components.supply import SupplyComponent
from .components.economics import EconomicsComponent
from .validation.cross_reference import validate_scenario
from ..interfaces import ScenarioData


class Scenario:
    """
    Scenario class for orchestrating all scenario components and ensuring
    cross-component reference integrity.

    Component creation order matters due to prerequisites:
    1. TopologyComponent (no prerequisites)
    2. TimeComponent (no prerequisites)
    3. DemandComponent (requires topology + time)
    4. SupplyComponent (requires topology + time)
    5. PerformanceComponent (requires topology + time + supply on disk)
    6. EconomicsComponent (requires topology + time)

    SupplyComponent defines WHAT technologies exist. PerformanceComponent
    defines HOW they operate, reading supply registry from disk.
    """
    def __init__(self, scenario_dir: str):
        """
        Initialize all scenario components and store the scenario directory
        path.

        Parameters
        ----------
        scenario_dir : str
            The full path to the scenario directory.
        """
        self.scenario_dir = scenario_dir

        # Initialize components in prerequisite order
        self.topology = TopologyComponent(scenario_dir)
        self.time = TimeComponent(scenario_dir)
        self.demand = DemandComponent(scenario_dir)
        self.supply = SupplyComponent(scenario_dir)
        self.performance = PerformanceComponent(scenario_dir)
        self.economics = EconomicsComponent(scenario_dir)

    def build(self, return_data: bool = False) -> Optional[ScenarioData]:
        """
        Finalize the scenario: load, process, validate, and save all
        components. Runs cross-component reference validation after
        processing.

        Parameters
        ----------
        return_data : bool, optional
            If True, return a ScenarioData instance built directly from
            the in-memory components (default: False).

        Returns
        -------
        ScenarioData or None
            ScenarioData if return_data is True, else None.

        Raises
        ------
        ValueError
            If scenario validation fails.
        """
        # Load all components
        self.topology.load()
        self.time.load()
        self.demand.load()
        self.supply.load()
        self.performance.load()
        self.economics.load()

        # Process demand, then supply (saves to disk), then performance
        self.demand.process()
        self.supply.save()          # Supply must save first for performance
        self.performance.process()  # Performance reads supply registry

        # Save all components
        self.topology.save()
        self.time.save()
        self.demand.save()
        self.supply.save()
        self.performance.save()
        self.economics.save()

        # Cross-component reference validation (after all saves)
        try:
            validate_scenario(self.scenario_dir)
        except Exception as e:
            raise ValueError(f"Scenario validation failed: {e}")

        print(f"Scenario built successfully in: {self.scenario_dir}")

        if return_data:
            return self.to_scenario_data()
        return None

    def to_scenario_data(self, validate: bool = True) -> ScenarioData:
        """
        Convert in-memory components to ScenarioData without re-reading
        CSV files.

        Parameters
        ----------
        validate : bool, optional
            If True, run ScenarioData validation (default: True).

        Returns
        -------
        ScenarioData
            Structured scenario data ready for translation.
        """
        return ScenarioData.from_components(
            topology_component=self.topology,
            time_component=self.time,
            demand_component=self.demand,
            supply_component=self.supply,
            economics_component=self.economics,
            performance_component=self.performance,
            validate=validate,
        )