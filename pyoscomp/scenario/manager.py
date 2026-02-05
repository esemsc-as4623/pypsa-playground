import os
import csv
import yaml
from uuid_extensions import uuid7str
from .core import Scenario

# Default paths
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "osemosys_config.yaml")
DEFAULT_MASTER_LIST_PATH = os.path.join(os.path.dirname(__file__), "..", "scenarios_master_list.csv")


# TODO: add support for scenario duplication and modification
# TODO: add utility method to clone and modify scenarios to create variants
class ScenarioManager:
    def __init__(self, tag: str = None, parent_dir: str = "", 
                 config_path=DEFAULT_CONFIG_PATH, master_path=DEFAULT_MASTER_LIST_PATH):
        """
        Initialize a Scenario Manager.
        
        :param tag: str, name for new scenario (required for creation)
        :param parent_dir: str, base directory for scenarios
        :param config_path: str, path to OSeMOSYS configuration YAML
        :param master_path: str, path to master list CSV for tracking
        """
        self.tag = tag
        self.parent_dir = parent_dir if parent_dir else os.getcwd()
        self.config_path = config_path
        self.master_path = master_path
        
        # Generate UUID for new scenarios, otherwise will be set when loading
        self.uuid = uuid7str() if tag else None
        self.scenario_dir = None

    @classmethod
    def from_uuid(cls, uuid: str, parent_dir: str = "", 
                  master_path=DEFAULT_MASTER_LIST_PATH, config_path=DEFAULT_CONFIG_PATH):
        """
        Factory method to load an existing scenario by UUID.
        
        :param uuid: str, UUID of existing scenario
        :param parent_dir: str, base directory for scenarios
        :return: ScenarioManager instance
        """
        if not uuid:
            raise ValueError("UUID must be provided to load a scenario.")
            
        instance = cls(tag=None, parent_dir=parent_dir, 
                      master_path=master_path, config_path=config_path)
        instance.uuid = uuid
        
        # Find the tag from master list
        tag = instance._find_tag_by_uuid(uuid)
        if not tag:
            raise FileNotFoundError(f"No scenario found for UUID: {uuid}")
            
        instance.tag = tag
        instance.scenario_dir = os.path.join(instance.parent_dir, tag)
        
        return instance

    def create_scenario(self):
        """
        Create a new scenario directory and initialize it.
        
        :return: Scenario object ready for configuration
        """
        if not self.tag:
            raise ValueError("Tag must be provided to create a scenario.")
            
        # 1. Create the scenario directory
        self.scenario_dir = os.path.join(self.parent_dir, self.tag)
        os.makedirs(self.scenario_dir, exist_ok=True)
        
        # 2. Create placeholder CSV files based on config
        self._create_empty_csv_files()
        
        # 3. Update master list with new scenario
        self._update_master_list(self.uuid, self.tag)
        
        print(f"Scenario '{self.tag}' created with UUID: {self.uuid}")
        print(f"Directory: {self.scenario_dir}")
        
        # 4. Return a Scenario object for further configuration
        return Scenario(self.scenario_dir)

    def load_scenario(self):
        """
        Load an existing scenario.
        
        :return: Scenario object for the loaded scenario
        """
        if not self.uuid:
            raise ValueError("UUID must be provided to load a scenario.")
            
        if not self.scenario_dir:
            # If scenario_dir isn't set (e.g., when using from_uuid), find it
            tag = self._find_tag_by_uuid(self.uuid)
            if not tag:
                raise FileNotFoundError(f"No scenario found for UUID: {self.uuid}")
            self.scenario_dir = os.path.join(self.parent_dir, tag)
            self.tag = tag
        
        if not os.path.exists(self.scenario_dir):
            raise FileNotFoundError(f"Scenario directory not found: {self.scenario_dir}")
            
        print(f"Loaded scenario '{self.tag}' with UUID: {self.uuid}")
        print(f"Directory: {self.scenario_dir}")
        
        return Scenario(self.scenario_dir)

    def _create_empty_csv_files(self):
        """
        Create empty CSV files based on the OSeMOSYS config YAML.
        This ensures all expected files exist, even if empty.
        """
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found at {self.config_path}")
            
        with open(self.config_path, "r") as f:
            config = yaml.safe_load(f)
        
        # Create empty files for all defined tables
        for table_name, table_config in config.items():
            file_type = table_config.get("type", "")
            if file_type in ("set", "param"):  # Create files for both sets and parameters
                filename = f"{table_name}.csv"
                filepath = os.path.join(self.scenario_dir, filename)
                
                # Create file with appropriate headers if needed
                with open(filepath, "w", newline="") as f:
                    writer = csv.writer(f)
                    
                    # Write headers based on file type and expected columns
                    if file_type == "set":
                        # Sets typically have a single 'VALUE' column
                        writer.writerow(["VALUE"])
                    elif file_type == "param":
                        # Parameters have columns defined in config
                        # Default to [table_name, VALUE] if not specified
                        columns = table_config.get("columns", [table_name.upper(), "VALUE"])
                        writer.writerow(columns)

    def _update_master_list(self, uuid: str, tag: str):
        """
        Add a new scenario to the master tracking CSV.
        
        :param uuid: str, UUID of the scenario
        :param tag: str, tag/name of the scenario
        """
        exists = os.path.exists(self.master_path)
        
        with open(self.master_path, "a", newline="") as f:
            writer = csv.writer(f)
            if not exists:
                writer.writerow(["uuid", "tag", "path", "created_at"])
            
            # Add timestamp for tracking
            from datetime import datetime
            created_at = datetime.now().isoformat()
            path = os.path.join(self.parent_dir, tag)
            
            writer.writerow([uuid, tag, path, created_at])

    def _find_tag_by_uuid(self, uuid: str):
        """
        Look up a scenario tag by UUID in the master list.
        
        :param uuid: str, UUID to search for
        :return: str or None, tag if found
        """
        if not os.path.exists(self.master_path):
            return None
            
        with open(self.master_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("uuid") == uuid:
                    return row.get("tag")
        return None

    def list_scenarios(self):
        """
        List all tracked scenarios.
        
        :return: list of dicts with scenario info
        """
        if not os.path.exists(self.master_path):
            return []
            
        scenarios = []
        with open(self.master_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                scenarios.append({
                    "uuid": row.get("uuid"),
                    "tag": row.get("tag"),
                    "path": row.get("path"),
                    "created_at": row.get("created_at")
                })
        
        return scenarios

    def delete_scenario(self, uuid: str = None, tag: str = None):
        """
        Delete a scenario from tracking (does not delete files).
        
        :param uuid: str, UUID of scenario to delete
        :param tag: str, tag of scenario to delete
        :return: bool, True if deleted
        """
        if not uuid and not tag:
            raise ValueError("Must provide either UUID or tag to delete scenario.")
            
        # Create a temporary file to write all rows except the one to delete
        temp_path = self.master_path + ".tmp"
        deleted = False
        
        with open(self.master_path, "r") as infile, open(temp_path, "w", newline="") as outfile:
            reader = csv.DictReader(infile)
            writer = csv.writer(outfile)
            
            # Write header
            writer.writerow(["uuid", "tag", "path", "created_at"])
            
            for row in reader:
                if (uuid and row.get("uuid") == uuid) or (tag and row.get("tag") == tag):
                    deleted = True
                    continue  # Skip this row (delete it)
                writer.writerow([row["uuid"], row["tag"], row["path"], row["created_at"]])
        
        # Replace original file with temp file
        if deleted:
            os.replace(temp_path, self.master_path)
        else:
            os.remove(temp_path)
            
        return deleted