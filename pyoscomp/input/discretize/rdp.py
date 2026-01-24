# pyoscomp/input/discretize/rdp.py

"""
Ramer-Douglas-Peucker discretization method for time series aggregation in PyPSA-OSeMOSYS Comparison Framework.
"""
import numpy as np
import pandas as pd
from typing import Union, Tuple

from .base import Discretizer

class RamerDouglasPeucker(Discretizer):
    """
    Ramer-Douglas-Peucker algorithm for timeseries discretization.
    :param epsilon: float
        Maximum perpendicular distance threshold for point removal.
        Larger values result in more aggressive simplification.
    """
    
    def __init__(self, epsilon: float = 1.0):
        self.epsilon = epsilon
        super().__init__()
    
    def _validate_parameters(self) -> None:
        if self.epsilon <= 0:
            raise ValueError(f"epsilon must be positive, got {self.epsilon}")
    
    def __repr__(self) -> str:
        return f"RDP(ε={self.epsilon})"
    
    def discretize(self,
                   y: Union[np.ndarray, pd.Series],
                   x: Union[np.ndarray, pd.Series, None] = None) -> np.ndarray:
        y_arr = np.asarray(y)
        
        if x is None:
            x_arr = np.arange(len(y_arr))
        else:
            x_arr = np.asarray(x)
        
        if len(x_arr) != len(y_arr):
            raise ValueError(f"x and y must have same length: {len(x_arr)} vs {len(y_arr)}")
        
        if len(y_arr) < 3:
            return np.arange(len(y_arr))
        
        # Convert datetime to numeric if needed
        if np.issubdtype(x_arr.dtype, np.datetime64):
            x_numeric = x_arr.astype('datetime64[ns]').astype(np.float64)
        else:
            x_numeric = x_arr.astype(np.float64)
        
        # Normalize coordinates for perpendicular distance calculation
        points = np.column_stack([x_numeric, y_arr])
        indices = self._rdp_recursive(points, 0, len(points) - 1)
        
        return np.sort(np.array(list(indices)))
    
    def _rdp_recursive(self, points: np.ndarray, start: int, end: int) -> set:
        """Recursive RDP implementation."""
        if end - start < 2:
            return {start, end}
        
        # Find point with maximum distance from line segment
        max_dist = 0
        max_idx = start
        
        for i in range(start + 1, end):
            dist = self._perpendicular_distance(points[i], points[start], points[end])
            if dist > max_dist:
                max_dist = dist
                max_idx = i
        
        # If max distance exceeds threshold, split and recurse
        if max_dist > self.epsilon:
            left = self._rdp_recursive(points, start, max_idx)
            right = self._rdp_recursive(points, max_idx, end)
            return left | right
        else:
            return {start, end}
    
    @staticmethod
    def _perpendicular_distance(point: np.ndarray, 
                               line_start: np.ndarray, 
                               line_end: np.ndarray) -> float:
        """Calculate perpendicular distance from point to line segment."""
        if np.array_equal(line_start, line_end):
            return np.linalg.norm(point - line_start)
        
        # Vector from line_start to line_end
        line_vec = line_end - line_start
        # Vector from line_start to point
        point_vec = point - line_start
        
        # Project point onto line
        line_len = np.linalg.norm(line_vec)
        line_unitvec = line_vec / line_len
        projection_length = np.dot(point_vec, line_unitvec)
        
        # Calculate perpendicular distance
        projection = projection_length * line_unitvec
        perpendicular = point_vec - projection
        
        return np.linalg.norm(perpendicular)