# pyoscomp/input/discretize/kmeans_windows.py

"""
K-Means clustering on windowed features for time series discretization.
"""
import numpy as np
import pandas as pd
from typing import Union, List, Callable

from .base import Discretizer

class WindowKMeans(Discretizer):
    """
    K-Means clustering on sliding window features for timeseries discretization.
    
    Creates feature vectors from local windows and clusters them to identify
    distinct operational regimes. Discretization points occur at cluster boundaries.
    
    Parameters
    ----------
    n_clusters : int (default=3)
        Number of clusters (regimes) to identify
    window_size : int (default=10)
        Size of sliding window for feature extraction
    features : list of str or callable, optional
        Features to extract from each window. Options:
        - 'mean': Window mean
        - 'std': Window standard deviation
        - 'min': Window minimum
        - 'max': Window maximum
        - 'trend': Linear trend slope
        - 'range': max - min
        - callable: Custom feature function taking window array
        Default: ['mean', 'std', 'trend']
    random_state : int, optional
        Random seed for reproducibility
    """
    
    def __init__(self, 
                 n_clusters: int = 3,
                 window_size: int = 10,
                 features: List[Union[str, Callable]] = None,
                 random_state: int = 42):
        self.n_clusters = n_clusters
        self.window_size = window_size
        self.features = features or ['mean', 'std', 'trend']
        self.random_state = random_state
        super().__init__()
    
    def _validate_parameters(self) -> None:
        if self.n_clusters < 2:
            raise ValueError(f"n_clusters must be at least 2, got {self.n_clusters}")
        if self.window_size < 2:
            raise ValueError(f"window_size must be at least 2, got {self.window_size}")
    
    def __repr__(self) -> str:
        features_str = ','.join(str(f) if isinstance(f, str) else 'custom' for f in self.features)
        return f"WindowKMeans(k={self.n_clusters}, window={self.window_size}, features=[{features_str}])"
    
    def _extract_window_features(self, window: np.ndarray) -> List[float]:
        """Extract features from a single window."""
        feature_values = []
        
        for feat in self.features:
            if callable(feat):
                # Custom feature function
                feature_values.append(feat(window))
            elif feat == 'mean':
                feature_values.append(np.mean(window))
            elif feat == 'std':
                feature_values.append(np.std(window))
            elif feat == 'min':
                feature_values.append(np.min(window))
            elif feat == 'max':
                feature_values.append(np.max(window))
            elif feat == 'range':
                feature_values.append(np.max(window) - np.min(window))
            elif feat == 'trend':
                # Linear trend (slope)
                x_vals = np.arange(len(window))
                slope = np.polyfit(x_vals, window, 1)[0]
                feature_values.append(slope)
            elif feat == 'median':
                feature_values.append(np.median(window))
            else:
                raise ValueError(f"Unknown feature: {feat}")
        
        return feature_values
    
    def discretize(self,
                   y: Union[np.ndarray, pd.Series],
                   x: Union[np.ndarray, pd.Series, None] = None) -> np.ndarray:
        """
        Cluster windows and identify regime boundaries.
        
        Parameters
        ----------
        y : array-like
            Values of the timeseries
        x : array-like, optional
            Time or x-coordinates (not used, included for API consistency)
            
        Returns
        -------
        indices : np.ndarray
            Integer array of indices where cluster boundaries occur
        """
        try:
            from sklearn.cluster import KMeans
        except ImportError:
            raise ImportError(
                "scikit-learn is required for KMeansWindows discretization. "
                "Install it with: pip install scikit-learn"
            )
        
        y_arr = np.asarray(y).flatten()
        n = len(y_arr)
        
        if n < self.window_size:
            raise ValueError(
                f"Timeseries length ({n}) must be at least window_size ({self.window_size})"
            )
        
        # Extract features from sliding windows
        feature_matrix = []
        for i in range(n - self.window_size + 1):
            window = y_arr[i:i + self.window_size]
            features = self._extract_window_features(window)
            feature_matrix.append(features)
        
        feature_matrix = np.array(feature_matrix)
        
        # Normalize features
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        feature_matrix_scaled = scaler.fit_transform(feature_matrix)
        
        # Cluster windows
        kmeans = KMeans(n_clusters=self.n_clusters, random_state=self.random_state, n_init=10)
        labels = kmeans.fit_predict(feature_matrix_scaled)
        
        # Find cluster boundaries (where label changes)
        boundaries = [0]  # Always include first point
        
        for i in range(1, len(labels)):
            if labels[i] != labels[i-1]:
                # Cluster boundary at center of window
                boundary_idx = i + self.window_size // 2
                if boundary_idx < n:
                    boundaries.append(boundary_idx)
        
        # Always include last point
        boundaries.append(n - 1)
        
        return np.unique(np.array(boundaries))
