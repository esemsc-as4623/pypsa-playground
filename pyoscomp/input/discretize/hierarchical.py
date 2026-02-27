# pyoscomp/input/discretize/hierarchical.py

"""
Hierarchical clustering discretization for time series with multi-level structure.
"""
import numpy as np
import pandas as pd
from typing import Union, Optional, Tuple
from scipy.cluster.hierarchy import linkage, fcluster, dendrogram
from scipy.spatial.distance import pdist

from .base import Discretizer
from ..structures import DiscretizationResult


class HierarchicalClustering(Discretizer):
    """
    Hierarchical clustering discretization with multi-level structure.
    
    Performs agglomerative clustering on timeseries segments to create
    a hierarchical partitioning. Can be used standalone for discretization
    or as input to TimesliceGenerator for structured timeslice creation.
    
    Parameters
    ----------
    n_clusters : int
        Target number of final clusters (leaf nodes)
    method : str (default='ward')
        Linkage method: 'ward', 'single', 'complete', 'average', 'weighted', 'centroid', 'median'
    metric : str (default='euclidean')
        Distance metric for clustering. Options: 'euclidean', 'manhattan', 'correlation', etc.
    window_size : int (default=24)
        Size of windows to cluster (hours for hourly data)
    preserve_hierarchy : bool (default=True)
        If True, stores hierarchical structure for use by TimesliceGenerator
    hierarchy_levels : Optional[Tuple[int, ...]] (default=None)
        Explicit hierarchy structure as (n_level1, n_level2, n_level3).
        E.g., (4, 2, 3) creates 4×2×3=24 clusters with 3-level hierarchy.
        Cannot be used with n_hierarchy_levels.
    n_hierarchy_levels : Optional[int] (default=None)
        Number of hierarchy levels to extract using natural breakpoints from the dendrogram.
        The algorithm finds large gaps in merge distances to identify natural cluster boundaries.
        If None and hierarchy_levels is also None, uses log2(n_clusters) as heuristic.
        Cannot be used with hierarchy_levels.
    """
    
    def __init__(self,
                 n_clusters: int,
                 method: str = 'ward',
                 metric: str = 'euclidean',
                 window_size: int = 24,
                 preserve_hierarchy: bool = True,
                 hierarchy_levels: Optional[Tuple[int, ...]] = None,
                 n_hierarchy_levels: Optional[int] = None):
        self.n_clusters = n_clusters
        self.method = method
        self.metric = metric
        self.window_size = window_size
        self.preserve_hierarchy = preserve_hierarchy
        self.hierarchy_levels = hierarchy_levels
        self.n_hierarchy_levels = n_hierarchy_levels
        
        # Validate and set hierarchy
        if hierarchy_levels is not None:
            product = np.prod(hierarchy_levels)
            if product != n_clusters:
                raise ValueError(
                    f"Product of hierarchy_levels {hierarchy_levels} = {product} "
                    f"must equal n_clusters {n_clusters}"
                )
        
        if hierarchy_levels is not None and n_hierarchy_levels is not None:
            raise ValueError(
                "Cannot specify both hierarchy_levels and n_hierarchy_levels. "
                "Use hierarchy_levels for explicit structure or n_hierarchy_levels for natural breakpoints."
            )
        
        super().__init__()
    
    def _validate_parameters(self) -> None:
        if self.n_clusters < 2:
            raise ValueError(f"n_clusters must be at least 2, got {self.n_clusters}")
        if self.window_size < 1:
            raise ValueError(f"window_size must be positive, got {self.window_size}")
        
        valid_methods = ['single', 'complete', 'average', 'weighted', 'centroid', 'median', 'ward']
        if self.method not in valid_methods:
            raise ValueError(f"method must be one of {valid_methods}, got {self.method}")
    
    def discretize(self,
                   y: Union[np.ndarray, pd.Series],
                   x: Union[np.ndarray, pd.Series, None] = None) -> Union[np.ndarray, DiscretizationResult]:
        """
        Perform hierarchical clustering on timeseries windows.
        
        Returns DiscretizationResult with hierarchical structure if preserve_hierarchy=True,
        otherwise returns simple indices array for backward compatibility.
        """
        y_arr = np.asarray(y).flatten()
        n = len(y_arr)
        
        if n < self.window_size:
            raise ValueError(
                f"Timeseries length ({n}) must be at least window_size ({self.window_size})"
            )
        
        # Create sliding windows
        n_windows = n - self.window_size + 1
        windows = np.array([y_arr[i:i+self.window_size] for i in range(n_windows)])
        
        # Perform hierarchical clustering
        if len(windows) < self.n_clusters:
            raise ValueError(
                f"Number of windows ({len(windows)}) must be >= n_clusters ({self.n_clusters})"
            )
        
        # Compute linkage
        Z = linkage(windows, method=self.method, metric=self.metric)
        
        # Cut dendrogram to get cluster labels
        labels = fcluster(Z, t=self.n_clusters, criterion='maxclust')
        
        # Extract hierarchical structure if requested
        hierarchical_labels = None
        actual_hierarchy_levels = None
        if self.preserve_hierarchy:
            if self.hierarchy_levels is not None:
                # Use user-specified hierarchy
                hierarchical_labels = self._extract_hierarchy_levels(Z, labels)
                actual_hierarchy_levels = self.hierarchy_levels
            else:
                # Auto-detect hierarchy from dendrogram
                n_levels = self.n_hierarchy_levels if self.n_hierarchy_levels is not None else None
                hierarchical_labels, actual_hierarchy_levels = self._extract_natural_hierarchy(Z, labels, n_levels)
        
        # Find cluster boundaries (where labels change)
        boundaries = [0]
        for i in range(1, len(labels)):
            if labels[i] != labels[i-1]:
                # Boundary at center of window
                boundary_idx = i + self.window_size // 2
                if boundary_idx < n:
                    boundaries.append(boundary_idx)
        
        # Always include last point
        boundaries.append(n - 1)
        indices = np.unique(np.array(boundaries))
        
        # Return enriched result or simple array
        if self.preserve_hierarchy:
            return DiscretizationResult(
                indices=indices,
                hierarchical_labels=hierarchical_labels,
                n_levels=len(actual_hierarchy_levels) if actual_hierarchy_levels else None,
                level_sizes=actual_hierarchy_levels
            )
        else:
            return indices
    
    def _extract_hierarchy_levels(self, 
                                  linkage_matrix: np.ndarray,
                                  leaf_labels: np.ndarray) -> np.ndarray:
        """
        Extract multi-level hierarchical labels from linkage matrix.
        
        Returns array of shape (n_segments, n_levels) with cluster assignment at each level.
        """
        n_levels = len(self.hierarchy_levels)
        n_segments = len(leaf_labels) - 1
        
        # Create hierarchical labels by cutting at different heights
        hierarchical_labels = np.zeros((n_segments, n_levels), dtype=int)
        
        # Level 0 (coarsest): Cut to get first hierarchy level
        cumulative_clusters = [self.hierarchy_levels[0]]
        hierarchical_labels[:, 0] = fcluster(
            linkage_matrix, t=self.hierarchy_levels[0], criterion='maxclust'
        )[:-1]  # Exclude last window
        
        # Subsequent levels: Progressive refinement
        for level in range(1, n_levels):
            cumulative_clusters.append(cumulative_clusters[-1] * self.hierarchy_levels[level])
            hierarchical_labels[:, level] = fcluster(
                linkage_matrix, t=cumulative_clusters[-1], criterion='maxclust'
            )[:-1]
        
        return hierarchical_labels
    
    def _extract_natural_hierarchy(self,
                                   linkage_matrix: np.ndarray,
                                   leaf_labels: np.ndarray,
                                   requested_levels: Optional[int] = None) -> Tuple[np.ndarray, Tuple[int, ...]]:
        """
        Auto-extract hierarchical structure from dendrogram using natural breakpoints.
        
        Finds natural cluster boundaries by analyzing large gaps in merge distances,
        then maps them to the requested number of levels.
        
        Parameters
        ----------
        linkage_matrix : np.ndarray
            Scipy linkage matrix
        leaf_labels : np.ndarray
            Final cluster labels
        requested_levels : Optional[int]
            Number of hierarchy levels desired. If None, uses heuristic (log2(n_clusters))
        
        Returns
        -------
        tuple of (hierarchical_labels, hierarchy_levels)
            hierarchical_labels: array of shape (n_segments, n_levels)
            hierarchy_levels: tuple of cluster counts at each level
        """
        n_segments = len(leaf_labels) - 1
        n_observations = len(leaf_labels)
        
        # Determine target number of levels
        if requested_levels is None:
            requested_levels = max(2, int(np.ceil(np.log2(self.n_clusters))))
        
        # Find natural breakpoints in the dendrogram
        cluster_counts = self._find_natural_breakpoints(linkage_matrix, requested_levels, n_observations)
        
        n_levels = len(cluster_counts)
        hierarchical_labels = np.zeros((n_segments, n_levels), dtype=int)
        
        # Extract labels at each level
        for level, n_clust in enumerate(cluster_counts):
            level_labels = fcluster(linkage_matrix, t=n_clust, criterion='maxclust')
            hierarchical_labels[:, level] = level_labels[:-1]  # Exclude last window
        
        # Calculate hierarchy_levels as ratios between consecutive levels
        hierarchy_levels = []
        for i in range(len(cluster_counts)):
            if i == 0:
                hierarchy_levels.append(cluster_counts[0])
            else:
                ratio = cluster_counts[i] // cluster_counts[i-1]
                if ratio < 1:
                    ratio = 1
                hierarchy_levels.append(ratio)
        
        return hierarchical_labels, tuple(hierarchy_levels)
    
    def _find_natural_breakpoints(self,
                                 linkage_matrix: np.ndarray,
                                 requested_levels: int,
                                 n_observations: int) -> list:
        """
        Find natural breakpoints in dendrogram by analyzing merge distance gaps.
        
        Parameters
        ----------
        linkage_matrix : np.ndarray
            Scipy linkage matrix where column 2 contains merge distances
        requested_levels : int
            Number of hierarchy levels to create
        n_observations : int
            Number of leaf observations
        
        Returns
        -------
        list
            Cluster counts at each level, sorted from coarse to fine (exactly requested_levels items)
        """
        # Extract merge distances (column 2 of linkage matrix)
        distances = linkage_matrix[:, 2]
        
        # Calculate gaps between consecutive merges
        gaps = np.diff(distances)
        
        # We need (requested_levels - 1) cuts to create requested_levels levels
        n_cuts = requested_levels - 1
        
        # Find the indices of the largest gaps
        # These represent natural cluster boundaries
        if len(gaps) < n_cuts:
            # Fewer natural gaps than requested
            # Case 2: Use all available gaps
            largest_gap_indices = np.argsort(gaps)[::-1][:len(gaps)]
        else:
            # Equal or more gaps than requested
            # Case 1 & 3: Select the N largest gaps
            largest_gap_indices = np.argsort(gaps)[::-1][:n_cuts]
        
        # Convert gap indices to merge step indices and then to cluster counts
        cut_merge_indices = np.sort(largest_gap_indices)
        
        # Convert merge indices to number of clusters at each cut
        # After merge k, there are (n_observations - k - 1) clusters
        natural_cluster_counts = []
        for merge_idx in cut_merge_indices:
            n_clusters_at_cut = n_observations - merge_idx - 1
            if n_clusters_at_cut > 0:
                natural_cluster_counts.append(n_clusters_at_cut)
        
        # Remove duplicates and sort
        natural_cluster_counts = sorted(set(natural_cluster_counts))
        
        # Ensure final level is always n_clusters
        if not natural_cluster_counts or natural_cluster_counts[-1] != self.n_clusters:
            natural_cluster_counts.append(self.n_clusters)
        
        # Now adjust to exactly requested_levels
        if len(natural_cluster_counts) < requested_levels:
            # Case 2: Fewer natural levels than requested - pad at the beginning
            n_missing = requested_levels - len(natural_cluster_counts)
            padded = []
            for i in range(n_missing):
                # Add coarse levels: 1, 2, 3, ... or geometric progression
                if natural_cluster_counts:
                    # Use geometric spacing below the first natural level
                    first_natural = natural_cluster_counts[0]
                    coarse_count = max(1, int(first_natural ** ((i + 1) / (n_missing + 1))))
                else:
                    coarse_count = i + 1
                padded.append(coarse_count)
            cluster_counts = padded + natural_cluster_counts
        elif len(natural_cluster_counts) > requested_levels:
            # Case 3: More natural levels than requested - subsample
            # Keep first and last, then evenly space the middle levels
            indices = np.linspace(0, len(natural_cluster_counts) - 1, requested_levels, dtype=int)
            cluster_counts = [natural_cluster_counts[i] for i in indices]
        else:
            # Case 1: Exact match
            cluster_counts = natural_cluster_counts
        
        # Final validation: ensure we have exactly requested_levels
        cluster_counts = cluster_counts[:requested_levels]  # Truncate if needed
        while len(cluster_counts) < requested_levels:  # Pad if needed
            # This should rarely happen, but as a safety measure
            cluster_counts.insert(0, 1)
        
        return cluster_counts
    
    def __repr__(self) -> str:
        if self.hierarchy_levels:
            hierarchy_str = '×'.join(map(str, self.hierarchy_levels))
            return f"HierarchicalClustering({hierarchy_str}={self.n_clusters})"
        return f"HierarchicalClustering(k={self.n_clusters})"
