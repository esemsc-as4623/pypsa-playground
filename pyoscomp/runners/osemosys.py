# pyoscomp/runners/osemosys.py

"""
Executes the OSeMOSYS model using translated input data. Option to use otoole or Pyomo.
See otoole documentation: https://otoole.readthedocs.io/en/latest/
See Pyomo GitHub implementation: https://github.com/OSeMOSYS/OSeMOSYS_Pyomo
"""
import subprocess
import os

class OSeMOSYSRunner:
    def __init__(self, input_dir: str, working_dir: str, use_otoole: bool = True):
        """
        input_dir: Directory with scenario CSVs and config
        working_dir: Directory for intermediate and output files
        use_otoole: If True, use otoole to convert CSVs to datafile; else, use direct Pyomo execution
        """
        self.input_dir = input_dir
        self.working_dir = working_dir
        self.use_otoole = use_otoole
        self.model_file = os.path.abspath(os.path.join("start", "OSeMOSYS.txt"))
        os.makedirs(self.working_dir, exist_ok=True)

    def write_input_files_otoole(self) -> (str, str):
        """
        Use otoole to convert CSVs to datafile and config.
        Returns paths to datafile and configfile.
        """
        datafile = os.path.join(self.working_dir, "scenario.txt")
        configfile = os.path.join(self.input_dir, "osemosys_config.yaml")
        cmd = [
            "otoole", "convert", "csv", "datafile",
            self.input_dir, datafile, configfile
        ]
        subprocess.run(cmd, check=True)
        return datafile, configfile

    def run(self) -> str:
        """
        Run OSeMOSYS using otoole+glpsol or direct Pyomo+glpsol.
        Returns path to results directory.
        """
        if self.use_otoole:
            datafile, configfile = self.write_input_files_otoole()
            solution_file = os.path.join(self.working_dir, "solution.sol")
            glp_file = os.path.join(self.working_dir, "scenario.glp")
            cmd = [
                "glpsol",
                "-m", self.model_file,
                "-d", datafile,
                "--wglp", glp_file,
                "--write", solution_file
            ]
            subprocess.run(cmd, check=True, cwd=self.working_dir)
            # Use otoole to extract results
            results_dir = os.path.join(self.working_dir, "results")
            os.makedirs(results_dir, exist_ok=True)
            cmd = [
                "otoole", "results", "glpk", "csv",
                solution_file, results_dir, "datafile", datafile, configfile,
                "--glpk_model", glp_file
            ]
            subprocess.run(cmd, check=True)
            return results_dir
        else:
            # Direct Pyomo execution (requires pyomo and glpk)
            from pyomo.environ import SolverFactory, AbstractModel, DataPortal
            import pyomo.environ as pyo
            # Assume OSeMOSYS AbstractModel is importable as osemosys_model
            # and input_dir contains CSVs for DataPortal
            # This is a placeholder for actual Pyomo execution logic
            raise NotImplementedError("Direct Pyomo execution not yet implemented. Use use_otoole=True.")
