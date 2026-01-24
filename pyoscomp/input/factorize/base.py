# pyoscomp/input/factorize/base.py

"""
Base class for time-series factorization in PyPSA-OSeMOSYS Comparison Framework
Note: Factorizes an input timeseries into the hierarchical TIMESLICE structure for OSeMOSYS.
"""
from abc import ABC, abstractmethod
import numpy as np
import pandas as pd
from typing import Tuple, Optional, Dict

from ..structures import TimesliceStructure

class TimesliceGenerator(ABC):
    """
    Base class for hierarchical timeslice generation from timeseries data.
    
    Supports two workflows:
    1. From discrete segments: Map N pre-discretized segments to S×D×T timeslices
    2. Direct from timeseries: Partition full timeseries into S×D×T timeslices
    
    Design principles:
    - Strategy determines hierarchical assignment approach
    - Factorization can be fixed or auto-selected
    - Load duration curve preservation
    """
    
    def __init__(self, 
                 n_seasons: Optional[int] = None,
                 n_daytypes: Optional[int] = None, 
                 n_timebrackets: Optional[int] = None,
                 auto_factorize: bool = True,
                 preserve_ldc: bool = True):
        """
        Parameters
        ----------
        n_seasons : int, optional
            Number of seasons. If None and auto_factorize=True, will be determined.
        n_daytypes : int, optional
            Number of day types. If None and auto_factorize=True, will be determined.
        n_timebrackets : int, optional
            Number of time brackets. If None and auto_factorize=True, will be determined.
        auto_factorize : bool
            If True, automatically determine optimal factorization.
        preserve_ldc : bool
            If True, ensure load duration curve is preserved.
        """
        self.n_seasons = n_seasons
        self.n_daytypes = n_daytypes
        self.n_timebrackets = n_timebrackets
        self.auto_factorize = auto_factorize
        self.preserve_ldc = preserve_ldc
        
        self._validate_parameters()
    
    def _validate_parameters(self) -> None:
        """Validate initialization parameters"""
        if not self.auto_factorize:
            if self.n_seasons is None or self.n_daytypes is None or self.n_timebrackets is None:
                raise ValueError("Must specify all of (n_seasons, n_daytypes, n_timebrackets) "
                               "when auto_factorize=False")
        
        if self.n_seasons is not None and self.n_seasons < 1:
            raise ValueError(f"n_seasons must be >= 1, got {self.n_seasons}")
        if self.n_daytypes is not None and self.n_daytypes < 1:
            raise ValueError(f"n_daytypes must be >= 1, got {self.n_daytypes}")
        if self.n_timebrackets is not None and self.n_timebrackets < 1:
            raise ValueError(f"n_timebrackets must be >= 1, got {self.n_timebrackets}")
    
    # ==================== Public API ====================
    
    def generate_from_discrete(self,
                               discrete_indices: np.ndarray,
                               y_values: np.ndarray,
                               x_times: np.ndarray,
                               segment_values: Optional[np.ndarray] = None) -> TimesliceStructure:
        """
        Generate timeslices from pre-discretized segments.
        
        Workflow 1: N discrete segments → S×D×T timeslices
        
        Parameters
        ----------
        discrete_indices : array-like
            Indices of discrete points (from Discretizer)
        y_values : array-like
            Original full timeseries values
        x_times : array-like
            Original full timeseries timestamps
        segment_values : array-like, optional
            Pre-computed representative values for each segment.
            If None, will compute from y_values using segment bounds.
            
        Returns
        -------
        TimesliceStructure
            Hierarchical timeslice assignments and representative values
        """
        N = len(discrete_indices) - 1  # Number of segments
        
        # Auto-factorize if needed
        if self.auto_factorize:
            self.n_seasons, self.n_daytypes, self.n_timebrackets = \
                self._select_factorization(N, x_times, discrete_indices)
        
        # Validate factorization
        if N != self.n_seasons * self.n_daytypes * self.n_timebrackets:
            raise ValueError(
                f"Number of segments ({N}) must equal "
                f"n_seasons × n_daytypes × n_timebrackets "
                f"({self.n_seasons}×{self.n_daytypes}×{self.n_timebrackets}="
                f"{self.n_seasons * self.n_daytypes * self.n_timebrackets})"
            )
        
        # Compute segment features
        segment_features = self._extract_segment_features(
            discrete_indices, y_values, x_times, segment_values
        )
        
        # Perform hierarchical assignment (strategy-specific)
        return self._assign_hierarchy(segment_features)
    
    def generate_direct(self,
                       y_values: np.ndarray,
                       x_times: np.ndarray,
                       n_target: Optional[int] = None) -> TimesliceStructure:
        """
        Generate timeslices directly from full timeseries.
        
        Workflow 2: Full timeseries → S×D×T timeslices (with N representative points)
        
        Parameters
        ----------
        y_values : array-like
            Full timeseries values
        x_times : array-like
            Full timeseries timestamps
        n_target : int, optional
            Target number of total points (N = S×D×T).
            If None, uses S×D×T specified in __init__.
            
        Returns
        -------
        TimesliceStructure
            Hierarchical timeslice assignments and representative values
        """
        # Determine target N
        if n_target is None:
            if self.auto_factorize:
                raise ValueError("Must specify n_target when auto_factorize=True "
                               "for direct generation")
            n_target = self.n_seasons * self.n_daytypes * self.n_timebrackets
        
        # Auto-factorize if needed
        if self.auto_factorize:
            self.n_seasons, self.n_daytypes, self.n_timebrackets = \
                self._select_factorization(n_target, x_times)
        
        # Validate
        if n_target != self.n_seasons * self.n_daytypes * self.n_timebrackets:
            raise ValueError(
                f"n_target ({n_target}) must equal "
                f"n_seasons × n_daytypes × n_timebrackets "
                f"({self.n_seasons * self.n_daytypes * self.n_timebrackets})"
            )
        
        # Extract features for all points
        point_features = self._extract_point_features(y_values, x_times)
        
        # Perform hierarchical partitioning (strategy-specific)
        return self._partition_hierarchy(point_features, y_values, x_times)
    
    # ==================== Strategy-Specific Methods (Abstract) ====================
    
    @abstractmethod
    def _select_factorization(self, 
                             n_target: int,
                             x_times: np.ndarray,
                             discrete_indices: Optional[np.ndarray] = None) -> Tuple[int, int, int]:
        """
        Select optimal (s, d, t) factorization for given target N.
        
        Returns (n_seasons, n_daytypes, n_timebrackets)
        """
        pass
    
    @abstractmethod
    def _assign_hierarchy(self, segment_features: Dict) -> TimesliceStructure:
        """
        Assign N segments to (season, daytype, timebracket) hierarchy.
        
        Used in Workflow 1: discrete segments → timeslices
        """
        pass
    
    @abstractmethod
    def _partition_hierarchy(self, 
                            point_features: Dict,
                            y_values: np.ndarray,
                            x_times: np.ndarray) -> TimesliceStructure:
        """
        Partition full timeseries into (season, daytype, timebracket) hierarchy.
        
        Used in Workflow 2: direct timeslice generation
        """
        pass
    
    # ==================== Helper Methods (Shared) ====================
    
    def _extract_segment_features(self,
                                  discrete_indices: np.ndarray,
                                  y_values: np.ndarray,
                                  x_times: np.ndarray,
                                  segment_values: Optional[np.ndarray] = None) -> Dict:
        """Extract features for each discrete segment"""
        N = len(discrete_indices) - 1
        features = {
            'segment_means': segment_values if segment_values is not None else np.zeros(N),
            'segment_starts': [],
            'segment_ends': [],
            'segment_durations': [],
            'months': [],
            'days_of_week': [],
            'hours_of_day': [],
        }
        
        for i in range(N):
            start_idx = discrete_indices[i]
            end_idx = discrete_indices[i+1]
            
            segment_times = pd.to_datetime(x_times[start_idx:end_idx])
            features['segment_starts'].append(segment_times[0])
            features['segment_ends'].append(segment_times[-1])
            features['segment_durations'].append(len(segment_times))
            
            # Temporal features
            features['months'].append(segment_times[0].month)
            features['days_of_week'].append(segment_times[0].dayofweek)
            features['hours_of_day'].append(segment_times[0].hour)
            
            # Compute mean if not provided
            if segment_values is None:
                features['segment_means'][i] = np.mean(y_values[start_idx:end_idx])
        
        return features
    
    def _extract_point_features(self,
                               y_values: np.ndarray,
                               x_times: np.ndarray) -> Dict:
        """Extract features for each point in full timeseries"""
        times = pd.to_datetime(x_times)
        return {
            'values': y_values,
            'times': times,
            'months': times.month.values,
            'days_of_week': times.dayofweek.values,
            'hours_of_day': times.hour.values,
        }
    
    def _build_timeslice_structure(self,
                                   season_assignments: np.ndarray,
                                   daytype_assignments: np.ndarray,
                                   timebracket_assignments: np.ndarray,
                                   segment_features: Dict) -> TimesliceStructure:
        """Build TimesliceStructure from segment assignments"""
        N = len(season_assignments)
        
        # Create timeslice IDs
        timeslice_ids = np.zeros(N, dtype=int)
        for i in range(N):
            s = season_assignments[i]
            d = daytype_assignments[i]
            t = timebracket_assignments[i]
            timeslice_ids[i] = s * (self.n_daytypes * self.n_timebrackets) + \
                              d * self.n_timebrackets + t
        
        # Compute representative values and times for each unique timeslice
        unique_timeslices = {}
        for i in range(N):
            ts_id = (season_assignments[i], daytype_assignments[i], timebracket_assignments[i])
            if ts_id not in unique_timeslices:
                unique_timeslices[ts_id] = []
            unique_timeslices[ts_id].append(i)
        
        representative_values = {}
        representative_times = {}
        segment_weights = segment_features['segment_durations']
        
        for ts_id, segment_indices in unique_timeslices.items():
            # Representative value: weighted mean
            values = [segment_features['segment_means'][i] for i in segment_indices]
            weights = [segment_weights[i] for i in segment_indices]
            representative_values[ts_id] = np.average(values, weights=weights)
            
            # Representative time: median time
            times = [segment_features['segment_starts'][i] for i in segment_indices]
            representative_times[ts_id] = times[len(times) // 2]
        
        return TimesliceStructure(
            seasons=season_assignments,
            daytypes=daytype_assignments,
            timebrackets=timebracket_assignments,
            timeslice_ids=timeslice_ids,
            representative_values=representative_values,
            representative_times=representative_times,
            segment_weights=np.array(segment_weights)
        )
    
    def _build_timeslice_structure_from_points(self,
                                               season_assignments: np.ndarray,
                                               daytype_assignments: np.ndarray,
                                               timebracket_assignments: np.ndarray,
                                               point_features: Dict,
                                               y_values: np.ndarray,
                                               x_times: np.ndarray) -> TimesliceStructure:
        """Build TimesliceStructure from point-wise assignments"""
        N = len(season_assignments)
        
        # Create timeslice IDs
        timeslice_ids = np.zeros(N, dtype=int)
        for i in range(N):
            s = season_assignments[i]
            d = daytype_assignments[i]
            t = timebracket_assignments[i]
            timeslice_ids[i] = s * (self.n_daytypes * self.n_timebrackets) + \
                              d * self.n_timebrackets + t
        
        # Compute representative values and times for each unique timeslice
        unique_timeslices = {}
        for i in range(N):
            ts_id = (season_assignments[i], daytype_assignments[i], timebracket_assignments[i])
            if ts_id not in unique_timeslices:
                unique_timeslices[ts_id] = []
            unique_timeslices[ts_id].append(i)
        
        representative_values = {}
        representative_times = {}
        
        for ts_id, point_indices in unique_timeslices.items():
            # Representative value: mean of points in this timeslice
            values = y_values[point_indices]
            representative_values[ts_id] = np.mean(values)
            
            # Representative time: median time
            times = point_features['times'][point_indices]
            representative_times[ts_id] = times[len(times) // 2]
        
        # Segment weights: each point has weight 1
        segment_weights = np.ones(N)
        
        return TimesliceStructure(
            seasons=season_assignments,
            daytypes=daytype_assignments,
            timebrackets=timebracket_assignments,
            timeslice_ids=timeslice_ids,
            representative_values=representative_values,
            representative_times=representative_times,
            segment_weights=segment_weights
        )
    
    def __repr__(self) -> str:
        if self.auto_factorize:
            return f"{self.__class__.__name__}(auto)"
        return f"{self.__class__.__name__}(s={self.n_seasons}, d={self.n_daytypes}, t={self.n_timebrackets})"