# pyoscomp/input/discretize/cp.py

"""
Critical Point discretization method for time series aggregation in PyPSA-OSeMOSYS Comparison Framework.
"""
import numpy as np
import pandas as pd
from typing import Union, Tuple

from .base import Discretizer

class CriticalPoint(Discretizer):
    """
    Discretize by selecting critical points (local extrema and inflection points).
    :param min_prominence: float, optional
        Minimum prominence for peaks/troughs to be considered significant.
    :param include_inflection: bool
        Whether to include inflection points (zero crossings of second derivative).
    """
    
    def __init__(self, min_prominence: float = 0.0, include_inflection: bool = False):
        self.min_prominence = min_prominence
        self.include_inflection = include_inflection
        super().__init__()
    
    def _validate_parameters(self) -> None:
        if self.min_prominence < 0:
            raise ValueError(f"min_prominence must be non-negative, got {self.min_prominence}")
    
    def __repr__(self) -> str:
        inflection_str = "+inflection" if self.include_inflection else ""
        return f"CriticalPoint(prominence={self.min_prominence}{inflection_str})"
    
    def discretize(self,
                   y: Union[np.ndarray, pd.Series],
                   x: Union[np.ndarray, pd.Series, None] = None) -> np.ndarray:
        from scipy.signal import find_peaks, argrelextrema
        
        y_arr = np.asarray(y)
        
        if len(y_arr) < 3:
            return np.arange(len(y_arr))
        
        critical_indices = {0, len(y_arr) - 1}  # Always include endpoints
        
        # Find local maxima
        peaks, _ = find_peaks(y_arr, prominence=self.min_prominence)
        critical_indices.update(peaks)
        
        # Find local minima
        troughs, _ = find_peaks(-y_arr, prominence=self.min_prominence)
        critical_indices.update(troughs)
        
        # Optionally add inflection points
        if self.include_inflection and len(y_arr) > 4:
            second_derivative = np.diff(y_arr, n=2)
            # Find zero crossings in second derivative
            sign_changes = np.where(np.diff(np.sign(second_derivative)))[0] + 1
            critical_indices.update(sign_changes)
        
        return np.sort(np.array(list(critical_indices)))