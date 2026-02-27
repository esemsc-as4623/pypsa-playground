"""
Greedy point selection for time series discretization.

Provides a simple statistical method to select exactly n points from a time series
by greedily selecting points that maximize the perpendicular distance from 
line segments.
"""

import numpy as np


def greedy_select_points(y, x=None, n_points=10):
    """
    Select exactly n_points from the time series using greedy max-distance selection.
    
    This is conceptually similar to Ramer-Douglas-Peucker but inverted: instead of
    simplifying until an error threshold is met, we greedily add points until we
    reach the target count.
    
    Algorithm:
    1. Start with first and last points
    2. Iteratively add the point with maximum perpendicular distance from its 
       current segment
    3. Stop when n_points is reached
    
    Parameters
    ----------
    y : array-like
        Time series values
    x : array-like, optional
        Time values (if None, uses integer indices)
    n_points : int
        Target number of discrete points to select
        
    Returns
    -------
    indices : np.ndarray
        Indices of selected points, sorted in ascending order
        
    Raises
    ------
    ValueError
        If n_points < 2 or n_points > len(y)
    """
    y = np.asarray(y)
    n = len(y)
    
    if n_points < 2:
        raise ValueError("n_points must be at least 2")
    if n_points > n:
        raise ValueError(f"n_points ({n_points}) cannot exceed data length ({n})")
    
    if x is None:
        x = np.arange(n)
    else:
        x = np.asarray(x)
    
    # Special case: if we want all points, return all indices
    if n_points == n:
        return np.arange(n)
    
    # Start with first and last points
    selected = [0, n - 1]
    
    # Greedily add points until we reach n_points
    while len(selected) < n_points:
        max_distance = -1
        max_index = -1
        max_segment_idx = -1
        
        # Check each segment between consecutive selected points
        for i in range(len(selected) - 1):
            start_idx = selected[i]
            end_idx = selected[i + 1]
            
            # Find point with max perpendicular distance in this segment
            for j in range(start_idx + 1, end_idx):
                distance = perpendicular_distance(
                    x[j], y[j],
                    x[start_idx], y[start_idx],
                    x[end_idx], y[end_idx]
                )
                
                if distance > max_distance:
                    max_distance = distance
                    max_index = j
                    max_segment_idx = i
        
        # Insert the point with maximum distance into the selected list
        if max_index != -1:
            selected.insert(max_segment_idx + 1, max_index)
        else:
            # Should not happen, but break if no valid point found
            break
    
    return np.array(sorted(selected))


def perpendicular_distance(px, py, x1, y1, x2, y2):
    """
    Calculate perpendicular distance from point (px, py) to line segment (x1,y1)-(x2,y2).
    
    Uses normalized coordinates to handle datetime and varying scales.
    
    Parameters
    ----------
    px, py : float
        Point coordinates
    x1, y1 : float
        Line segment start coordinates
    x2, y2 : float
        Line segment end coordinates
        
    Returns
    -------
    float
        Perpendicular distance
    """
    # Normalize to unit square to handle different scales
    dx = x2 - x1
    dy = y2 - y1
    
    if dx == 0 and dy == 0:
        # Degenerate case: line segment is a point
        return np.sqrt((px - x1)**2 + (py - y1)**2)
    
    # Normalize x and y to similar scales (approximate)
    x_range = abs(dx) if dx != 0 else 1
    y_range = abs(dy) if dy != 0 else 1
    
    # Normalize all coordinates
    px_norm = (px - x1) / x_range
    py_norm = (py - y1) / y_range
    x2_norm = (x2 - x1) / x_range
    y2_norm = (y2 - y1) / y_range
    x1_norm = 0
    y1_norm = 0
    
    # Calculate perpendicular distance in normalized space
    # Using the cross product formula: |cross(AB, AP)| / |AB|
    numerator = abs(x2_norm * py_norm - y2_norm * px_norm)
    denominator = np.sqrt(x2_norm**2 + y2_norm**2)
    
    if denominator == 0:
        return np.sqrt(px_norm**2 + py_norm**2)
    
    return numerator / denominator
