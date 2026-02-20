# pyoscomp/run.py

"""
Unified run interface for PyOSComp.

This module provides a simple, unified interface to run energy system
scenarios in both OSeMOSYS and PyPSA from a single ScenarioData object.

Example
-------
>>> from pyoscomp import ScenarioData, run
>>> data = ScenarioData.from_directory('/path/to/scenario')
>>> results = run(data, model='both')
>>> print(results.pypsa.objective, results.osemosys.objective)
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional, Literal, Union
import pandas as pd
import tempfile
import os

from .interfaces import ScenarioData
from .translation.pypsa_translator import PyPSAInputTranslator, PyPSAOutputTranslator
from .translation.osemosys_translator import OSeMOSYSInputTranslator, OSeMOSYSOutputTranslator

logger = logging.getLogger(__name__)


@dataclass
class ModelResult:
    """
    Container for results from a single model run.
    
    Attributes
    ----------
    model_name : str
        Name of the model ('pypsa' or 'osemosys').
    objective : float
        Objective function value (total cost).
    optimal_capacities : pd.DataFrame
        Optimal capacity by technology.
    dispatch : pd.DataFrame
        Time-series dispatch/generation.
    costs : pd.DataFrame
        Cost breakdown by component.
    raw_results : Dict[str, pd.DataFrame]
        All raw result DataFrames from the translator.
    status : str
        Solver status ('optimal', 'infeasible', 'error', etc.).
    solve_time : float
        Time taken to solve (seconds).
    model_object : Any
        The underlying model object (pypsa.Network or results dict).
    """
    model_name: str
    objective: float = 0.0
    optimal_capacities: pd.DataFrame = field(default_factory=pd.DataFrame)
    dispatch: pd.DataFrame = field(default_factory=pd.DataFrame)
    costs: pd.DataFrame = field(default_factory=pd.DataFrame)
    raw_results: Dict[str, pd.DataFrame] = field(default_factory=dict)
    status: str = "not_run"
    solve_time: float = 0.0
    model_object: Any = None


@dataclass
class ComparisonResult:
    """
    Container for results from running both models.
    
    Attributes
    ----------
    pypsa : ModelResult
        Results from PyPSA run.
    osemosys : ModelResult
        Results from OSeMOSYS run.
    scenario_data : ScenarioData
        The input scenario data used.
    """
    pypsa: Optional[ModelResult] = None
    osemosys: Optional[ModelResult] = None
    scenario_data: Optional[ScenarioData] = None
    
    def compare_objectives(self) -> Dict[str, float]:
        """Compare objective values between models."""
        result = {}
        if self.pypsa:
            result['pypsa'] = self.pypsa.objective
        if self.osemosys:
            result['osemosys'] = self.osemosys.objective
        if self.pypsa and self.osemosys:
            result['difference'] = self.pypsa.objective - self.osemosys.objective
            result['ratio'] = self.pypsa.objective / self.osemosys.objective if self.osemosys.objective != 0 else float('inf')
        return result
    
    def compare_capacities(self) -> pd.DataFrame:
        """Compare optimal capacities between models."""
        dfs = []
        if self.pypsa and not self.pypsa.optimal_capacities.empty:
            pypsa_cap = self.pypsa.optimal_capacities.copy()
            pypsa_cap['model'] = 'pypsa'
            dfs.append(pypsa_cap)
        if self.osemosys and not self.osemosys.optimal_capacities.empty:
            osemosys_cap = self.osemosys.optimal_capacities.copy()
            osemosys_cap['model'] = 'osemosys'
            dfs.append(osemosys_cap)
        
        if dfs:
            return pd.concat(dfs, ignore_index=True)
        return pd.DataFrame()


def run_pypsa(
    scenario_data: ScenarioData,
    solver_name: str = 'glpk',
    solver_options: Optional[Dict] = None,
    **kwargs
) -> ModelResult:
    """
    Run scenario in PyPSA.
    
    Parameters
    ----------
    scenario_data : ScenarioData
        The scenario to run.
    solver_name : str, optional
        Solver to use (default: 'glpk').
    solver_options : dict, optional
        Additional solver options.
    **kwargs
        Additional arguments passed to network.optimize().
    
    Returns
    -------
    ModelResult
        Results from the PyPSA run.
    """
    import time
    
    result = ModelResult(model_name='pypsa')
    
    try:
        # Translate to PyPSA network
        translator = PyPSAInputTranslator(scenario_data)
        network = translator.translate()
        
        # Run optimization
        start_time = time.time()
        status = network.optimize(
            solver_name=solver_name,
            solver_options=solver_options or {},
            **kwargs
        )
        result.solve_time = time.time() - start_time
        
        # Extract results
        result.status = 'optimal' if status == 'ok' else str(status)
        result.objective = network.objective
        result.model_object = network
        
        # Extract optimal capacities
        if hasattr(network.generators, 'p_nom_opt'):
            result.optimal_capacities = network.generators[['p_nom_opt']].copy()
            result.optimal_capacities.columns = ['VALUE']
            result.optimal_capacities['TECHNOLOGY'] = result.optimal_capacities.index
        
        # Extract dispatch
        if not network.generators_t.p.empty:
            result.dispatch = network.generators_t.p.copy()
        
        # Use output translator for standardized results
        output_translator = PyPSAOutputTranslator(network)
        result.raw_results = output_translator.translate()
        
        logger.info(f"PyPSA optimization completed: {result.status}, objective={result.objective:.2f}")
        
    except Exception as e:
        result.status = 'error'
        logger.error(f"PyPSA run failed: {e}")
        raise
    
    return result


def run_osemosys(
    scenario_data: ScenarioData,
    working_dir: Optional[str] = None,
    config_file: Optional[str] = None,
    model_file: Optional[str] = None,
    keep_files: bool = False,
    **kwargs
) -> ModelResult:
    """
    Run scenario in OSeMOSYS using otoole + glpsol.
    
    Parameters
    ----------
    scenario_data : ScenarioData
        The scenario to run.
    working_dir : str, optional
        Directory for intermediate files. Uses temp dir if not specified.
    config_file : str, optional
        Path to otoole config file. Uses default if not specified.
    model_file : str, optional
        Path to OSeMOSYS.txt model file.
    keep_files : bool, optional
        If True, don't delete intermediate files (default: False).
    **kwargs
        Additional arguments.
    
    Returns
    -------
    ModelResult
        Results from the OSeMOSYS run.
    """
    import time
    import subprocess
    import importlib.resources
    
    result = ModelResult(model_name='osemosys')
    
    # Set up working directory
    if working_dir is None:
        temp_dir = tempfile.mkdtemp(prefix='pyoscomp_osemosys_')
        working_dir = temp_dir
    else:
        temp_dir = None
        os.makedirs(working_dir, exist_ok=True)
    
    try:
        working_path = Path(working_dir)
        
        # Export scenario data to CSVs
        input_dir = working_path / 'input'
        translator = OSeMOSYSInputTranslator(scenario_data)
        translator.export_to_csv(str(input_dir))
        
        # Paths for intermediate files
        datafile = working_path / 'scenario.txt'
        solution_file = working_path / 'solution.sol'
        glp_file = working_path / 'scenario.glp'
        results_dir = working_path / 'results'
        results_dir.mkdir(exist_ok=True)
        
        # Find config file
        if config_file is None:
            # Look for config in standard locations
            config_file = importlib.resources.files("pyoscomp").joinpath(
                "OSeMOSYS_config.yaml"
            )
            if config_file is None:
                raise FileNotFoundError(
                    "No OSeMOSYS config file found. Provide config_file parameter."
                )
        
        # Find model file
        if model_file is None:
            possible_models = [
                Path(__file__).parent.parent / 'docs' / 'OSeMOSYS.txt',
                Path('OSeMOSYS.txt'),
            ]
            for mdl in possible_models:
                if mdl.exists():
                    model_file = str(mdl)
                    break
            if model_file is None:
                raise FileNotFoundError(
                    "No OSeMOSYS.txt model file found. Provide model_file parameter."
                )
        
        start_time = time.time()
        
        # Step 1: Convert CSVs to datafile using otoole
        logger.info("Converting CSVs to datafile with otoole...")
        cmd_convert = [
            'otoole', 'convert', 'csv', 'datafile',
            str(input_dir), str(datafile), config_file
        ]
        subprocess.run(cmd_convert, check=True, capture_output=True)
        
        # Step 2: Run glpsol
        logger.info("Running glpsol...")
        cmd_solve = [
            'glpsol',
            '-m', model_file,
            '-d', str(datafile),
            '--wglp', str(glp_file),
            '--write', str(solution_file)
        ]
        subprocess.run(cmd_solve, check=True, capture_output=True)
        
        # Step 3: Extract results using otoole
        logger.info("Extracting results with otoole...")
        cmd_results = [
            'otoole', 'results', 'glpk', 'csv',
            str(solution_file), str(results_dir),
            'datafile', str(datafile), config_file,
            '--glpk_model', str(glp_file)
        ]
        subprocess.run(cmd_results, check=True, capture_output=True)
        
        result.solve_time = time.time() - start_time
        result.status = 'optimal'
        
        # Load results using output translator
        output_translator = OSeMOSYSOutputTranslator(str(results_dir))
        result.raw_results = output_translator.translate()
        result.objective = output_translator.get_objective()
        result.optimal_capacities = output_translator.get_optimal_capacity()
        
        # Store dispatch if available
        if 'RateOfActivity' in result.raw_results:
            result.dispatch = result.raw_results['RateOfActivity']
        
        logger.info(f"OSeMOSYS optimization completed: {result.status}, objective={result.objective:.2f}")
        
    except subprocess.CalledProcessError as e:
        result.status = 'error'
        logger.error(f"OSeMOSYS run failed: {e.stderr.decode() if e.stderr else e}")
        raise
    except Exception as e:
        result.status = 'error'
        logger.error(f"OSeMOSYS run failed: {e}")
        raise
    finally:
        # Clean up temp directory if we created one
        if temp_dir and not keep_files:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    return result


def run(
    scenario_data: ScenarioData,
    model: Literal['pypsa', 'osemosys', 'both'] = 'both',
    pypsa_options: Optional[Dict] = None,
    osemosys_options: Optional[Dict] = None,
) -> ComparisonResult:
    """
    Run a scenario in one or both models.
    
    This is the main entry point for running scenarios. It provides
    a unified interface to execute the same scenario in OSeMOSYS
    and/or PyPSA and compare results.
    
    Parameters
    ----------
    scenario_data : ScenarioData
        The scenario to run.
    model : {'pypsa', 'osemosys', 'both'}, optional
        Which model(s) to run (default: 'both').
    pypsa_options : dict, optional
        Options passed to run_pypsa().
    osemosys_options : dict, optional
        Options passed to run_osemosys().
    
    Returns
    -------
    ComparisonResult
        Results from the model run(s).
    
    Example
    -------
    >>> from pyoscomp import ScenarioData
    >>> from pyoscomp.run import run
    >>> data = ScenarioData.from_directory('/path/to/scenario')
    >>> results = run(data, model='both')
    >>> print(results.compare_objectives())
    """
    result = ComparisonResult(scenario_data=scenario_data)
    
    pypsa_options = pypsa_options or {}
    osemosys_options = osemosys_options or {}
    
    if model in ('pypsa', 'both'):
        try:
            result.pypsa = run_pypsa(scenario_data, **pypsa_options)
        except Exception as e:
            logger.error(f"PyPSA run failed: {e}")
            result.pypsa = ModelResult(model_name='pypsa', status='error')
    
    if model in ('osemosys', 'both'):
        try:
            result.osemosys = run_osemosys(scenario_data, **osemosys_options)
        except Exception as e:
            logger.error(f"OSeMOSYS run failed: {e}")
            result.osemosys = ModelResult(model_name='osemosys', status='error')
    
    return result


# Convenience function to run from scenario directory
def run_from_directory(
    scenario_dir: str,
    model: Literal['pypsa', 'osemosys', 'both'] = 'both',
    **kwargs
) -> ComparisonResult:
    """
    Load and run a scenario from a directory.
    
    Parameters
    ----------
    scenario_dir : str
        Path to scenario directory with CSV files.
    model : {'pypsa', 'osemosys', 'both'}, optional
        Which model(s) to run (default: 'both').
    **kwargs
        Additional arguments passed to run().
    
    Returns
    -------
    ComparisonResult
        Results from the model run(s).
    """
    scenario_data = ScenarioData.from_directory(scenario_dir)
    return run(scenario_data, model=model, **kwargs)
