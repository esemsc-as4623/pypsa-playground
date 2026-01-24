# pyoscomp/input/discretize/pelt.py

"""
PELT (Pruned Exact Linear Time) change point detection for time series discretization.
"""
import numpy as np
import pandas as pd
from typing import Union

from .base import Discretizer

class PELT(Discretizer):
    """
    PELT change point detection algorithm for timeseries discretization.
    
    Detects points where the statistical properties of the timeseries change,
    creating segments with homogeneous behavior.
    
    Parameters
    ----------
    penalty : float, optional (default=1.0)
        Penalty value for adding a change point. Higher values result in fewer
        change points (more conservative). Lower values detect more changes.
    model : str, optional (default='rbf')
        Cost function model:
        - 'l1': L1 norm (absolute difference)
        - 'l2': L2 norm (squared difference) 
        - 'rbf': Radial basis function kernel
        - 'normal': Gaussian likelihood
    min_size : int, optional (default=2)
        Minimum segment size between change points
    """
    
    def __init__(self, penalty: float = 1.0, model: str = 'rbf', min_size: int = 2):
        self.penalty = penalty
        self.model = model
        self.min_size = min_size
        super().__init__()
    
    def _validate_parameters(self) -> None:
        if self.penalty <= 0:
            raise ValueError(f"penalty must be positive, got {self.penalty}")
        if self.min_size < 1:
            raise ValueError(f"min_size must be at least 1, got {self.min_size}")
        valid_models = ['l1', 'l2', 'rbf', 'normal']
        if self.model not in valid_models:
            raise ValueError(f"model must be one of {valid_models}, got {self.model}")
    
    def __repr__(self) -> str:
        return f"PELT(penalty={self.penalty}, model='{self.model}', min_size={self.min_size})"
    
    def discretize(self,
                   y: Union[np.ndarray, pd.Series],
                   x: Union[np.ndarray, pd.Series, None] = None) -> np.ndarray:
        """
        Detect change points in the timeseries using PELT algorithm.
        
        Parameters
        ----------
        y : array-like
            Values of the timeseries
        x : array-like, optional
            Time or x-coordinates (not used in PELT, included for API consistency)
            
        Returns
        -------
        indices : np.ndarray
            Integer array of indices where change points occur
        """
        try:
            import ruptures as rpt
        except ImportError:
            raise ImportError(
                "ruptures library is required for PELT discretization. "
                "Install it with: pip install ruptures"
            )
        
        y_arr = np.asarray(y).flatten()
        
        if len(y_arr) < self.min_size * 2:
            # Not enough data for change detection
            return np.array([0, len(y_arr) - 1])
        
        # PELT algorithm
        algo = rpt.Pelt(model=self.model, min_size=self.min_size)
        algo.fit(y_arr)
        
        # Detect change points
        change_points = algo.predict(pen=self.penalty)
        
        # ruptures returns indices including the last point, convert to our format
        # It returns 1-indexed positions of segment ends
        indices = np.array([0] + change_points)
        
        # Ensure last index is included and remove duplicates
        if indices[-1] != len(y_arr) - 1:
            indices = np.append(indices[:-1], len(y_arr) - 1)
        
        return np.unique(indices)
