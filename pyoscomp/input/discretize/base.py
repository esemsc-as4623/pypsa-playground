# pyoscomp/input/discretize/base.py

"""
Base class for time-series discretization in PyPSA-OSeMOSYS Comparison Framework
"""
from abc import ABC, abstractmethod
import numpy as np
from typing import Union, Tuple
import pandas as pd

class Discretizer(ABC):
    """
    Base class for timeseries discretization algorithms.
    
    Design principles:
    - Algorithm parameters are set at initialization
    - Data is passed to discretize() method
    - Returns indices of selected points (or DiscretizationResult for enriched output)
    """
    
    def __init__(self):
        """Initialize discretizer with algorithm-specific parameters."""
        self._validate_parameters()
    
    @abstractmethod
    def _validate_parameters(self) -> None:
        """Validate algorithm-specific parameters. Raise ValueError if invalid."""
        pass
    
    @abstractmethod
    def discretize(self, 
                   y: Union[np.ndarray, pd.Series],
                   x: Union[np.ndarray, pd.Series, None] = None) -> Union[np.ndarray, 'DiscretizationResult']:
        """
        Discretize the timeseries by selecting representative points.
        
        Parameters
        ----------
        y : array-like
            Values of the timeseries
        x : array-like, optional
            Time or x-coordinates. If None, uses integer indices.
            
        Returns
        -------
        np.ndarray or DiscretizationResult
            Integer array of indices of selected points from original series,
            or enriched DiscretizationResult with hierarchical metadata.
            User can retrieve selected points via: y[indices], x[indices]
        """
        pass
    
    def fit_discretize(self,
                      y: Union[np.ndarray, pd.Series],
                      x: Union[np.ndarray, pd.Series, None] = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        Convenience method that returns the discretized data directly.
        
        Returns
        -------
        tuple of np.ndarray
            The selected points from the timeseries (x_discrete, y_discrete)
        """
        result = self.discretize(y, x)
        
        # Handle both return types
        from ..structures import DiscretizationResult
        if isinstance(result, DiscretizationResult):
            indices = result.indices
        else:
            indices = result
        
        if x is None:
            x = np.arange(len(y))
        
        x_arr = np.asarray(x)
        y_arr = np.asarray(y)
        
        return x_arr[indices], y_arr[indices]
    
    def fill_discretized(self,
                        y: Union[np.ndarray, pd.Series],
                        indices: np.ndarray,
                        x: Union[np.ndarray, pd.Series, None] = None,
                        method: callable = np.mean) -> Tuple[np.ndarray, np.ndarray]:
        """
        Fill original timeseries with representative values from discretization.
        
        For each segment between consecutive discrete points, calculates a 
        representative value using the specified method and fills all points
        in that segment with that value. This produces a continuous array
        at the same resolution as the original data for easy comparison.
        
        Parameters
        ----------
        y : array-like
            Original timeseries values
        indices : array-like
            Indices of discrete points (e.g., from discretize())
        x : array-like, optional
            Original x-coordinates. If None, uses integer indices.
        method : callable, default=np.mean
            Function to calculate representative value for each segment
            (e.g., np.mean, np.median, np.max, np.min)
            
        Returns
        -------
        tuple of np.ndarray
            (x_original, y_filled) where y_filled has same shape as y,
            with each segment filled with its representative value
            
        Examples
        --------
        >>> discretizer = RamerDouglasPeucker(epsilon=0.1)
        >>> indices = discretizer.discretize(y, x)
        >>> x_filled, y_filled = discretizer.fill_discretized(y, indices, x, method=np.mean)
        >>> # y_filled can now be compared directly with y at the same resolution
        >>> mae = np.mean(np.abs(y - y_filled))
        """
        y_arr = np.asarray(y)
        indices_arr = np.asarray(indices)
        
        if x is None:
            x_arr = np.arange(len(y_arr))
        else:
            x_arr = np.asarray(x)
        
        # Initialize filled array
        y_filled = np.zeros_like(y_arr, dtype=float)
        
        # Fill each segment with its representative value
        for i in range(len(indices_arr)):
            if i < len(indices_arr) - 1:
                # Get segment bounds
                start_idx = indices_arr[i]
                end_idx = indices_arr[i + 1]
                
                # Calculate representative value for this segment
                segment_value = method(y_arr[start_idx:end_idx])
                
                # Fill all points in segment
                y_filled[start_idx:end_idx] = segment_value
            else:
                # Last segment: from last index to end
                start_idx = indices_arr[i]
                segment_value = method(y_arr[start_idx:])
                y_filled[start_idx:] = segment_value
        
        return x_arr, y_filled
    
    def get_params(self) -> dict:
        """Return algorithm parameters for reproducibility."""
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}