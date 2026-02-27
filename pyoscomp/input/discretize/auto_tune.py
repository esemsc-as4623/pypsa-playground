# pyoscomp/input/discretize/auto_tune.py

"""
Automatic parameter tuning for discretization methods to achieve target number of points.
"""
import numpy as np
import pandas as pd
from typing import Union, Optional, Tuple
import warnings


def auto_discretize(discretizer_class,
                   y: Union[np.ndarray, pd.Series],
                   x: Union[np.ndarray, pd.Series, None] = None,
                   n_points: Optional[int] = None,
                   param_name: str = 'penalty',
                   param_range: Tuple[float, float] = (0.001, 100.0),
                   tolerance: int = 2,
                   max_iterations: int = 50,
                   **kwargs) -> Tuple[np.ndarray, dict]:
    """
    Automatically tune discretization parameters to achieve target number of points.
    
    Uses binary search to find the optimal parameter value that produces approximately
    the desired number of discrete points.
    
    Parameters
    ----------
    discretizer_class : class
        Discretizer class (e.g., PELT, RamerDouglasPeucker)
    y : array-like
        Values of the timeseries
    x : array-like, optional
        Time or x-coordinates
    n_points : int, optional
        Target number of discrete points. If None, uses the discretizer with default params.
    param_name : str
        Name of the parameter to tune (e.g., 'penalty', 'epsilon')
    param_range : tuple of float
        (min, max) range for the parameter search
    tolerance : int
        Acceptable deviation from target n_points
    max_iterations : int
        Maximum number of binary search iterations
    **kwargs
        Additional fixed parameters to pass to the discretizer
        
    Returns
    -------
    indices : np.ndarray
        Indices of selected discrete points
    info : dict
        Information about the tuning process:
        - 'param_value': Final parameter value found
        - 'n_points_achieved': Actual number of points achieved
        - 'iterations': Number of iterations used
        - 'converged': Whether tuning converged within tolerance
    """
    if n_points is None:
        # No tuning needed, use default parameters
        discretizer = discretizer_class(**kwargs)
        indices = discretizer.discretize(y, x)
        return indices, {
            'param_value': getattr(discretizer, param_name),
            'n_points_achieved': len(indices),
            'iterations': 0,
            'converged': True
        }
    
    y_arr = np.asarray(y)
    if n_points < 2:
        raise ValueError(f"n_points must be at least 2, got {n_points}")
    if n_points > len(y_arr):
        raise ValueError(f"n_points ({n_points}) cannot exceed data length ({len(y_arr)})")
    
    # Binary search for optimal parameter
    param_min, param_max = param_range
    best_indices = None
    best_param = None
    best_diff = float('inf')
    iterations = 0
    
    # Determine search direction (does increasing parameter increase or decrease points?)
    # Test with min and max values
    test_params = {}
    test_params.update(kwargs)
    
    test_params[param_name] = param_min
    discretizer_min = discretizer_class(**test_params)
    n_points_min = len(discretizer_min.discretize(y, x))
    
    test_params[param_name] = param_max
    discretizer_max = discretizer_class(**test_params)
    n_points_max = len(discretizer_max.discretize(y, x))
    
    # Determine if parameter is inversely related to number of points
    inverse_relation = n_points_min > n_points_max
    
    while iterations < max_iterations and param_max - param_min > 1e-10:
        iterations += 1
        param_mid = (param_min + param_max) / 2
        
        # Create discretizer with current parameter
        current_params = {}
        current_params.update(kwargs)
        current_params[param_name] = param_mid
        
        try:
            discretizer = discretizer_class(**current_params)
            indices = discretizer.discretize(y, x)
            n_points_achieved = len(indices)
        except Exception as e:
            warnings.warn(f"Error with {param_name}={param_mid}: {e}")
            # Adjust search range and continue
            if inverse_relation:
                param_max = param_mid
            else:
                param_min = param_mid
            continue
        
        diff = abs(n_points_achieved - n_points)
        
        # Track best result
        if diff < best_diff:
            best_diff = diff
            best_indices = indices
            best_param = param_mid
        
        # Check convergence
        if diff <= tolerance:
            return indices, {
                'param_value': param_mid,
                'n_points_achieved': n_points_achieved,
                'iterations': iterations,
                'converged': True
            }
        
        # Adjust search range based on whether we have too many or too few points
        if inverse_relation:
            if n_points_achieved > n_points:
                # Need fewer points, increase parameter
                param_min = param_mid
            else:
                # Need more points, decrease parameter
                param_max = param_mid
        else:
            if n_points_achieved > n_points:
                # Need fewer points, increase parameter
                param_max = param_mid
            else:
                # Need more points, decrease parameter
                param_min = param_mid
    
    # Return best result found
    warnings.warn(
        f"Did not converge within {max_iterations} iterations. "
        f"Target: {n_points}, achieved: {len(best_indices)}, "
        f"difference: {best_diff}"
    )
    
    return best_indices, {
        'param_value': best_param,
        'n_points_achieved': len(best_indices),
        'iterations': iterations,
        'converged': False
    }


def auto_pelt(y: Union[np.ndarray, pd.Series],
             x: Union[np.ndarray, pd.Series, None] = None,
             n_points: Optional[int] = None,
             param_range: Tuple[float, float] = (0.001, 100.0),
             **kwargs) -> Tuple[np.ndarray, dict]:
    """
    Convenience function for auto-tuning PELT discretization.
    
    Parameters
    ----------
    y : array-like
        Values of the timeseries
    x : array-like, optional
        Time coordinates
    n_points : int, optional
        Target number of discrete points
    param_range : tuple
        (min, max) range for penalty parameter
    **kwargs
        Additional PELT parameters (model, min_size)
        
    Returns
    -------
    indices : np.ndarray
        Indices of selected discrete points
    info : dict
        Tuning information
    """
    from .pelt import PELT
    return auto_discretize(
        PELT, y, x, n_points,
        param_name='penalty',
        param_range=param_range,
        **kwargs
    )


def auto_rdp(y: Union[np.ndarray, pd.Series],
            x: Union[np.ndarray, pd.Series, None] = None,
            n_points: Optional[int] = None,
            param_range: Tuple[float, float] = (0.0001, 10.0),
            **kwargs) -> Tuple[np.ndarray, dict]:
    """
    Convenience function for auto-tuning RDP discretization.
    
    Parameters
    ----------
    y : array-like
        Values of the timeseries
    x : array-like, optional
        Time coordinates
    n_points : int, optional
        Target number of discrete points
    param_range : tuple
        (min, max) range for epsilon parameter
    **kwargs
        Additional RDP parameters
        
    Returns
    -------
    indices : np.ndarray
        Indices of selected discrete points
    info : dict
        Tuning information
    """
    from .rdp import RamerDouglasPeucker
    return auto_discretize(
        RamerDouglasPeucker, y, x, n_points,
        param_name='epsilon',
        param_range=param_range,
        **kwargs
    )
