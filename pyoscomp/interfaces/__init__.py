# pyoscomp/interfaces/__init__.py

"""
ScenarioData interface module for PyPSA-OSeMOSYS translation.

This module provides the typed interface that bridges scenario building
(components) and model translation.
"""

from .sets import OSeMOSYSSets
from .parameters import (
    TimeParameters,
    DemandParameters,
    SupplyParameters,
    EconomicsParameters,
    PerformanceParameters,
)
from .containers import ScenarioData
from .utilities import (
    ScenarioDataLoader,
    ScenarioDataExporter,
    load_set_csv,
    load_param_csv,
    save_set_csv,
    save_param_csv,
)

__all__ = [
    # Sets
    'OSeMOSYSSets',
    # Parameters
    'TimeParameters',
    'DemandParameters',
    'SupplyParameters',
    'PerformanceParameters',
    'EconomicsParameters',
    # Container
    'ScenarioData',
    # Utilities
    'ScenarioDataLoader',
    'ScenarioDataExporter',
    # Helper functions
    'load_set_csv',
    'load_param_csv',
    'save_set_csv',
    'save_param_csv',
]