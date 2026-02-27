# pyoscomp/interfaces/__init__.py

"""
ScenarioData interface module for PyPSA-OSeMOSYS translation.

This module provides the typed interface that bridges scenario building
(components) and model translation, as well as the harmonized result
containers for cross-model comparison.
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
from .results import (
    TopologyResult,
    SupplyResult,
    ModelResults,
    compare,
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
    # Input container
    'ScenarioData',
    # Output containers
    'TopologyResult',
    'SupplyResult',
    'ModelResults',
    # Comparison
    'compare',
    # Utilities
    'ScenarioDataLoader',
    'ScenarioDataExporter',
    # Helper functions
    'load_set_csv',
    'load_param_csv',
    'save_set_csv',
    'save_param_csv',
]