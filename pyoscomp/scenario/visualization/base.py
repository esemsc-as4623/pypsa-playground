# pyoscomp/scenario/visualization/base.py

"""
Base visualization class and shared style constants.

This module defines the abstract base class for all component visualizers
and the common visual style palette used across the package.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ..components.base import ScenarioComponent


# =========================================================================
# Shared Style Constants
# =========================================================================

#: Colour-blind-safe palette (Wong, 2011)
CB_PALETTE: List[str] = [
    '#56B4E9', '#D55E00', '#009E73', '#F0E442',
    '#0072B2', '#CC79A7', '#E69F00',
]

#: Hatch patterns for secondary visual encoding
HATCHES: List[str] = ['', '//', '..', 'xx', '++', '**', 'OO']

#: Default matplotlib rcParams overrides applied by every visualizer
DEFAULT_RC: Dict[str, Any] = {
    'font.size': 14,
    'text.color': 'black',
    'axes.labelcolor': 'black',
    'xtick.color': 'black',
    'ytick.color': 'black',
    'font.family': 'sans-serif',
}


class ComponentVisualizer(ABC):
    """
    Abstract base class for scenario component visualizers.

    Each concrete visualizer wraps a single :class:`ScenarioComponent`
    instance and exposes one or more ``plot_*`` methods.

    Attributes
    ----------
    component : ScenarioComponent
        The scenario component to visualize.

    Parameters
    ----------
    component : ScenarioComponent
        A loaded (or loadable) scenario component instance.
    auto_load : bool, optional
        If ``True`` (default), call ``component.load()`` when the data
        frames appear empty. Set to ``False`` if the component is
        already populated in memory.

    Notes
    -----
    Subclasses must define at least one ``plot_*`` method. A convenience
    ``show()`` method is provided that calls the primary plot.
    """

    def __init__(
        self,
        component: ScenarioComponent,
        auto_load: bool = True,
    ):
        self.component = component
        self._auto_load = auto_load

    # ------------------------------------------------------------------
    # Helpers available to all subclasses
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_style() -> None:
        """Apply the default matplotlib rcParams."""
        import matplotlib.pyplot as plt
        plt.rcParams.update(DEFAULT_RC)

    @staticmethod
    def _color_for_index(index: int) -> str:
        """Return a colour from the palette, cycling if necessary."""
        return CB_PALETTE[index % len(CB_PALETTE)]

    @staticmethod
    def _hatch_for_index(index: int) -> str:
        """Return a hatch pattern, cycling if necessary."""
        return HATCHES[index % len(HATCHES)]

    @staticmethod
    def _strip_spines(ax, keep: Optional[List[str]] = None) -> None:
        """
        Hide axis spines, keeping only those in *keep*.

        Parameters
        ----------
        ax : matplotlib.axes.Axes
            Target axes.
        keep : list of str, optional
            Spine names to keep visible (e.g. ``['bottom']``).
            Defaults to ``['bottom']``.
        """
        keep = keep or ['bottom']
        for spine in ('top', 'right', 'left', 'bottom'):
            ax.spines[spine].set_visible(spine in keep)

    @abstractmethod
    def show(self, **kwargs) -> None:
        """
        Display the primary visualization for this component.

        Concrete subclasses should call their main ``plot_*`` method here.
        """
        ...
