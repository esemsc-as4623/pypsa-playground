from .components.topology import TopologyComponent
from .components.time import TimeComponent
from .components.demand import DemandComponent

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

        # State tracking 
        self.node_list = []
        self.year_list = []
        self.time_list = []

    def set_topology_structure(self, nodes):
        """
        Define the spatial resolution of the model.

        :param nodes: int (number of nodes) or list[str] (names of nodes)
        :param start_year: int
        :param end_year: int
        :param step: int (default 1) - interval between years
        """
        self.node_list = self.topology.process(nodes)

    def set_time_structure(self, years, seasons=None, daytypes=None, brackets=None):
        """
        Define the temporal resolution of the model.
        
        :param years: tuple (start, end, step) or list of ints
        :param seasons: dict {Name: Weight/Days} (e.g. {'Winter': 1, 'Summer': 1})
        :param daytypes: dict {Name: Weight}
        :param brackets: dict {Name: Weight/Hours}
        """
        # Defaults if not provided (Simplest possible model: 1 Season, 1 DayType, 1 Bracket)
        if not seasons: seasons = {"Yearly": 1}
        if not daytypes: daytypes = {"Day": 1}
        if not brackets: brackets = {"Avg": 1}

        # process() returns the master list of (Year, Timeslice) tuples
        self.time_list = self.time.process(years, seasons, daytypes, brackets)
        
        # Update local year list cache for convenience
        self.year_list = self.time.years

    def set_interyear_demand(self, region, fuel, 
                              trajectory, trend_function=None, interpolation: str=None):
        """
        Primary entry point for adding annual demand.
        
        :param region: Name of the node
        :param fuel: Name of the fuel (e.g., 'ELEC')
        :param trajectory: dict {Year: Value} for annual demand points (inter-year)
        :param trend_function: function(year) -> float (optional) for continuous trend
        :param interpolation: 'linear', 'cagr', or 'step' (constant until next point)
        """
        self.demand.add_annual_demand(region, fuel, self.year_list,
                                      trajectory, trend_function=trend_function, interpolation=interpolation)
    
    def set_intrayear_demand(self, region, fuel, weights_timeslice=None,
                              weights_seasons=None, weights_daytypes=None, weights_brackets=None):
        """
        Primary entry point for adding demand profile.
        
        :param region: Name of the node
        :param fuel: Name of the fuel (e.g., 'ELEC')
        :param weights_*: dicts for weighting profiles (e.g. {'Winter': 2})
        
        ordered by seasons, daytypes, brackets, timeslices
        1. If weights_timeslice is provided, it overrides all other weights.
        2. If provided, weights_seasons, weights_daytypes, weights_brackets are used.
        3. Defaults to 'flat' shape if no weights provided.
        """
        self.demand.set_profile(region, fuel,
                                timeslice_weights=weights_timeslice,
                                season_weights=weights_seasons,
                                day_weights=weights_daytypes,
                                hourly_weights=weights_brackets)

    def add_flexible_demand(self, region, fuel, year, value):
        """Adds AccumulatedAnnualDemand (Time independent)"""
        self.demand.add_flexible_demand(region, fuel, year, value)

    def build(self):
        """
        Finalize the scenario logic.
        """
        # Process demand (requires Time to be done first)
        self.demand.process(self.year_list)
        # self.supply.process(self.year_list)
        print(f"Scenario built successfully in: {self.scenario_dir}")