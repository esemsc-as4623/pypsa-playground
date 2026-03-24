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
    StorageParameters,
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
    DispatchResult,
    StorageResult,
    EconomicsResult,
    TradeResult,
    ModelResults,
    compare,
    DivergenceFlag,
    divergence_analysis,
)
from .harmonization import (
    HarmonizationTolerances,
    MetricResult,
    HarmonizationReport,
    validate_input_harmonization,
    validate_pypsa_translation_harmonization,
    reconstruct_pypsa_npv,
    compare_npv_to_osemosys,
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
    'StorageParameters',
    # Input container
    'ScenarioData',
    # Output containers
    'TopologyResult',
    'SupplyResult',
    'DispatchResult',
    'StorageResult',
    'EconomicsResult',
    'TradeResult',
    'ModelResults',
    # Comparison
    'compare',
    'DivergenceFlag',
    'divergence_analysis',
    # Harmonization protocol
    'HarmonizationTolerances',
    'MetricResult',
    'HarmonizationReport',
    'validate_input_harmonization',
    'validate_pypsa_translation_harmonization',
    'reconstruct_pypsa_npv',
    'compare_npv_to_osemosys',
    # Utilities
    'ScenarioDataLoader',
    'ScenarioDataExporter',
    # Helper functions
    'load_set_csv',
    'load_param_csv',
    'save_set_csv',
    'save_param_csv',
]