from .components.topology import TopologyComponent
from .components.time import TimeComponent

class Scenario:
    def __init__(self, scenario_dir):
        """
        :param scenario_dir: The full path to the scenario directory (e.g., /path/to/project/tag_123)
        """
        self.scenario_dir = scenario_dir
        
        # Initialize components, passing the directory path down
        self.topology = TopologyComponent(scenario_dir)
        self.time = TimeComponent(scenario_dir)

        # State tracking 
        self.node_list = []
        self.year_list = []

    def set_topology_structure(self, nodes):
        """
        :param nodes: int (number of nodes) or list[str] (names of nodes)
        :param start_year: int
        :param end_year: int
        :param step: int (default 1) - interval between years
        """
        self.node_list = self.topology.process(nodes)

    def set_time_structure(self, years, seasons=None, daytypes=None, brackets=None):
        """
        :param years: tuple (start, end, step) or list of ints
        :param seasons: dict {Name: Weight}
        :param daytypes: dict {Name: Weight}
        :param brackets: dict {Name: Weight}
        """
        # Defaults if not provided (Simplest possible model: 1 Season, 1 DayType, 1 Bracket)
        if not seasons: seasons = {"Yearly": 1}
        if not daytypes: daytypes = {"Day": 1}
        if not brackets: brackets = {"Avg": 1}

        self.year_list = self.time.process_years(years)
        self.time.process_time_structure(seasons, daytypes, brackets)

    def add_demand(self, node, base_value, rule_strategy):
        pass