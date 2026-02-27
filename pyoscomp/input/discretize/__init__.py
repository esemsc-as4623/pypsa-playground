# pyoscomp/input/discretize/__init__.py

"""
Input discretization submodule for PyPSA-OSeMOSYS Comparison Framework
"""

from .rdp import RamerDouglasPeucker
from .cp import CriticalPoint
from .pelt import PELT
from .kmeans import WindowKMeans
from .hierarchical import HierarchicalClustering
from .auto_tune import auto_discretize, auto_pelt, auto_rdp
from .greedy_selection import greedy_select_points

__all__ = [
    'RamerDouglasPeucker', 
    'CriticalPoint', 
    'PELT', 
    'WindowKMeans', 
    'HierarchicalClustering',
    'auto_discretize',
    'auto_pelt',
    'auto_rdp',
    'greedy_select_points'
]