# pyoscomp/__init__.py

"""
PyPSA-OSeMOSYS Comparison Framework (PyOSComp).

A framework for building energy system scenarios and running them in both
OSeMOSYS and PyPSA for comparative analysis.

Main Components
---------------
ScenarioData : dataclass
    The unified data container that bridges scenario building and translation.
Scenario : class
    Orchestrates scenario component building.
run : function
    Unified entry point to run scenarios in one or both models.

Subpackages
-----------
scenario : Scenario building components (topology, time, demand, supply, performance, economics, etc.)
translation : Translators between OSeMOSYS and PyPSA formats
interfaces : Data containers and type definitions
runners : Model execution infrastructure

Example
-------
>>> from pyoscomp import ScenarioData, run
>>> data = ScenarioData.from_directory('/path/to/scenario')
>>> results = run(data, model='both')
>>> print(results.compare_objectives())
"""

from .interfaces import ScenarioData
from .scenario import Scenario
from .run import run, run_pypsa, run_osemosys, run_from_directory
from .run import ModelResult, ComparisonResult

__all__ = [
    # Core classes
    'ScenarioData',
    'Scenario',
    # Run functions
    'run',
    'run_pypsa',
    'run_osemosys',
    'run_from_directory',
    # Result containers
    'ModelResult',
    'ComparisonResult',
]

__version__ = '0.1.0'
