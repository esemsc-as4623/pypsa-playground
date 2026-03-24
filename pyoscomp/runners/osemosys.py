# pyoscomp/runners/osemosys.py

"""
Executes the OSeMOSYS model using translated input data. Option to use otoole or Pyomo.
See otoole documentation: https://otoole.readthedocs.io/en/latest/
See Pyomo GitHub implementation: https://github.com/OSeMOSYS/OSeMOSYS_Pyomo
"""
import atexit
import subprocess
import os
import tempfile
from typing import Tuple
import importlib.resources

from pyoscomp.interfaces import ScenarioData
from pyoscomp.translation import OSeMOSYSInputTranslator

class OSeMOSYSRunner:
    """
    Executes the OSeMOSYS model using translated input data. Option to use otoole or Pyomo.
    Can be constructed from a ScenarioData object or from a directory of scenario CSVs.
    """

    def __init__(self, scenario_dir: str, scenario_name: str = "scenario1",
                 modelfile: str = None, configfile: str = None,
                 use_otoole: bool = True):
        """
        Parameters
        ----------
        scenario_dir : str
            Master directory that will contain scenario CSVs, result CSVs, and artefacts.
        modelfile : str, optional
            Path to OSeMOSYS model file (i.e. OSeMOSYS.txt)
        configfile : str, optional
            Path to OSeMOSYS config file (i.e. OSeMOSYS_config.yaml)
        use_otoole : bool, optional
            If True, use otoole to convert CSVs to datafile; else, use direct Pyomo execution
        """
        self.scenario_dir = scenario_dir
        self.setup_dir = os.path.join(scenario_dir, "SETUP")
        self.results_dir = os.path.join(scenario_dir, "RESULTS")
        if modelfile is None:
            modelfile = importlib.resources.files("pyoscomp").joinpath("OSeMOSYS.txt")
        self.modelfile = modelfile # Model file path (OSeMOSYS.txt)
        if configfile is None:
            configfile = importlib.resources.files("pyoscomp").joinpath("OSeMOSYS_config.yaml")
        self.configfile = configfile # Config file path (OSeMOSYS_config.yaml)
        self.use_otoole = use_otoole
        self.scenario_name = scenario_name
        os.makedirs(self.setup_dir, exist_ok=True)
        os.makedirs(self.results_dir, exist_ok=True)

    @classmethod
    def from_scenario_data(cls, scenario_data: ScenarioData, use_otoole: bool = True):
        """
        Create an OSeMOSYSRunner from a validated ScenarioData object.

        Parameters
        ----------
        scenario_data : ScenarioData
            Validated ScenarioData dataclass (from pyoscomp.interfaces)
        use_otoole : bool, optional
            If True, use otoole to convert CSVs to datafile; else, use direct Pyomo execution

        Returns
        -------
        OSeMOSYSRunner
            Configured runner instance
        """
        tmpdir_obj = tempfile.TemporaryDirectory(prefix="pyoscomp_osemosys_")
        atexit.register(tmpdir_obj.cleanup)
        scenario_dir = tmpdir_obj.name
        setup_dir = os.path.join(scenario_dir, "SETUP")
        os.makedirs(setup_dir, exist_ok=True)
        translator = OSeMOSYSInputTranslator(scenario_data)
        translator.export_to_csv(setup_dir)
        runner = cls(scenario_dir=scenario_dir, use_otoole=use_otoole)
        # Keep reference so the TemporaryDirectory isn't garbage-collected
        # while the runner is still alive.
        runner._tmpdir = tmpdir_obj
        return runner
        
    def write_input_files_otoole(self) -> Tuple[str, str]:
        """
        Use otoole to convert CSVs to datafile and config.

        Parameters
        ----------
        configfile : str, optional
             Path to otoole config file. If None, uses ../pyoscomp/OSeMOSYS_config.yaml

        Returns
        -------
        Paths to datafile and configfile.
        """
        input_dir = self.setup_dir
        datafile = os.path.join(self.scenario_dir, f"{self.scenario_name}.txt")
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
            solution_file = os.path.join(self.scenario_dir, f"{self.scenario_name}.sol")
            glp_file = os.path.join(self.scenario_dir, f"{self.scenario_name}.glp")
            cmd = [
                "glpsol",
                "-m", self.modelfile,
                "-d", datafile,
                "--wglp", glp_file,
                "--write", solution_file
            ]
            subprocess.run(cmd, check=True)
            results_dir = self.results_dir
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
