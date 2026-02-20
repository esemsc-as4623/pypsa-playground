# pyoscomp/runners/osemosys.py

"""
Executes the OSeMOSYS model using translated input data. Option to use otoole or Pyomo.
See otoole documentation: https://otoole.readthedocs.io/en/latest/
See Pyomo GitHub implementation: https://github.com/OSeMOSYS/OSeMOSYS_Pyomo
"""
import subprocess
import os
import importlib.resources

from ..interfaces import ScenarioData


class OSeMOSYSRunner:
    """
    Executes the OSeMOSYS model using translated input data. Option to use otoole or Pyomo.
    Can be constructed from a ScenarioData object or from a directory of scenario CSVs.
    """

    def __init__(self, scenario_dir: str, output_dir: str,
                 modelfile: str = None, configfile: str = None,
                 use_otoole: bool = True):
        """
        Parameters
        ----------
        scenario_dir : str
            Directory with scenario CSVs
        output_dir : str
            Directory for intermediate and output files
        modelfile : str, optional
            Path to OSeMOSYS model file (i.e. OSeMOSYS.txt)
        configfile : str, optional
            Path to OSeMOSYS config file (i.e. OSeMOSYS_config.yaml)
        use_otoole : bool, optional
            If True, use otoole to convert CSVs to datafile; else, use direct Pyomo execution
        """
        self.scenario_dir = scenario_dir
        self.output_dir = output_dir
        if modelfile is None:
            modelfile = importlib.resources.files("pyoscomp").joinpath("OSeMOSYS.txt")
        self.modelfile = modelfile # Model file path (OSeMOSYS.txt)
        if configfile is None:
            configfile = importlib.resources.files("pyoscomp").joinpath("OSeMOSYS_config.yaml")
        self.configfile = configfile # Config file path (OSeMOSYS_config.yaml)
        self.use_otoole = use_otoole
        os.makedirs(self.output_dir, exist_ok=True)

    @classmethod
    def from_scenario_data(cls, scenario_data: ScenarioData, output_dir: str = None, use_otoole: bool = True):
        """
        Create an OSeMOSYSRunner from a validated ScenarioData object.

        Parameters
        ----------
        scenario_data : ScenarioData
            Validated ScenarioData dataclass (from pyoscomp.interfaces)
        output_dir : str, optional
            Directory for intermediate and output files. If None, uses scenario_data.directory or 'scenario_run'.
        use_otoole : bool, optional
            If True, use otoole to convert CSVs to datafile; else, use direct Pyomo execution

        Returns
        -------
        OSeMOSYSRunner
            Configured runner instance
        """
        # Save scenario data to directory if not already saved
        if hasattr(scenario_data, 'directory') and scenario_data.directory:
            input_dir = scenario_data.directory
        else:
            # Save to a temp directory if not present
            import tempfile
            input_dir = tempfile.mkdtemp(prefix="scenario_")
            scenario_data.save_to_directory(input_dir)
        if output_dir is None:
            output_dir = os.path.join(input_dir, "results")
        return cls(scenario_dir=input_dir, output_dir=output_dir, use_otoole=use_otoole)

    def write_input_files_otoole(self, configfile: str = None) -> (str, str):
        """
        Use otoole to convert CSVs to datafile and config.

        Parameters
        ----------
        configfile : str, optional
             Path to otoole config file. If None, uses ../docs/OSeMOSYS_config.yaml

        Returns
        -------
        Paths to datafile and configfile.
        """
        input_dir = self.scenario_dir
        datafile = os.path.join(input_dir, "scenario1.txt")
        cmd = [
            "otoole", "convert", "csv", "datafile",
            input_dir, datafile, self.configfile
        ]
        subprocess.run(cmd, check=True)
        return datafile, self.configfile

    def run(self) -> str:
        """
        Run OSeMOSYS using otoole+glpsol or direct Pyomo+glpsol.
        Returns path to results directory.
        """
        if self.use_otoole:
            datafile, configfile = self.write_input_files_otoole()
            # Paths
            solution_file = os.path.join(self.scenario_dir, "scenario1.sol")
            glp_file = os.path.join(self.scenario_dir, "scenario1.glp")
            # Run glpsol
            cmd = [
                "glpsol",
                "-m", self.modelfile,
                "-d", datafile,
                "--wglp", glp_file,
                "--write", solution_file
            ]
            subprocess.run(cmd, check=True)
            # Use otoole to extract results
            results_dir = os.path.join(self.scenario_dir, "results")
            os.makedirs(results_dir, exist_ok=True)
            cmd = [
                "otoole", "results", "glpk", "csv",
                solution_file, results_dir, "datafile", datafile, self.configfile,
                "--glpk_model", glp_file
            ]
            subprocess.run(cmd, check=True)
            return results_dir
        else:
            # Direct Pyomo execution (requires pyomo and glpk)
            # This is a placeholder for actual Pyomo execution logic
            raise NotImplementedError("Direct Pyomo execution not yet implemented. Use use_otoole=True.")
