import numpy as np
import pandas as pd
from typing import Tuple, Dict, Optional
from dataclasses import dataclass

@dataclass
class TimesliceStructure:
    """Container for timeslice hierarchy results"""
    seasons: np.ndarray          # Array of season assignments per segment
    daytypes: np.ndarray         # Array of daytype assignments per segment
    timebrackets: np.ndarray     # Array of timebracket assignments per segment
    timeslice_ids: np.ndarray    # Combined (s,d,t) ID per segment
    representative_values: Dict[Tuple[int,int,int], float]  # Mean y-value per timeslice
    representative_times: Dict[Tuple[int,int,int], pd.Timestamp]  # Representative time per timeslice
    segment_weights: np.ndarray  # Duration/weight of each segment
    
    @property
    def n_seasons(self) -> int:
        return len(np.unique(self.seasons))
    
    @property
    def n_daytypes(self) -> int:
        return len(np.unique(self.daytypes))
    
    @property
    def n_timebrackets(self) -> int:
        return len(np.unique(self.timebrackets))
    
    @property
    def n_timeslices(self) -> int:
        return len(self.representative_values)
    

@dataclass
class DiscretizationResult:
    """
    Enriched output from discretization with optional hierarchical metadata.
    
    This allows discretizers to provide additional structure information
    that can be consumed by TimesliceGenerators.
    """
    indices: np.ndarray                    # Core output: discrete point indices
    hierarchical_labels: Optional[np.ndarray] = None  # Optional: cluster labels at each level
    n_levels: Optional[int] = None         # Optional: number of hierarchy levels
    level_sizes: Optional[Tuple[int, ...]] = None  # Optional: (n_level1, n_level2, ...)
    
    @property
    def n_segments(self) -> int:
        """Number of discrete segments"""
        return len(self.indices) - 1
    
    @property
    def has_hierarchy(self) -> bool:
        """Whether hierarchical information is available"""
        return self.hierarchical_labels is not None