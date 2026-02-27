# pyoscomp/scenario/visualization/__init__.py

"""
Visualization submodule for scenario components.

Provides visualization classes for inspecting and presenting the temporal,
spatial, and techno-economic structure of a scenario. Each visualizer wraps
a scenario component and exposes one or more plotting methods.

Example
-------
Visualize a time component::

    from pyoscomp.scenario.components import TimeComponent
    from pyoscomp.scenario.visualization import TimeVisualizer

    time = TimeComponent("path/to/scenario")
    time.load()

    viz = TimeVisualizer(time)
    viz.plot_timeslice_structure()
"""

from .base import ComponentVisualizer
from .time import TimeVisualizer
from .demand import DemandVisualizer

__all__ = [
    'ComponentVisualizer',
    'TimeVisualizer',
    'DemandVisualizer',
]
