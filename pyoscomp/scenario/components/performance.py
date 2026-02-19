# pyoscomp/scenario/components/performance.py

"""
Performance component facade for technology operational characteristics.

This component provides a semantic interface for performance-related parameters
that are technically owned by SupplyComponent. It delegates to SupplyComponent
rather than duplicating functionality.

Note: This is a lightweight facade pattern. Most performance parameters should
be set directly via SupplyComponent methods.

See Also
--------
SupplyComponent : Contains the actual implementation for:
    - set_capacity_factor() : Timeslice-level capacity availability
    - set_availability_factor() : Annual availability (outages/maintenance)
    - set_conversion_technology() : Efficiency via activity ratios
"""

from typing import Dict, Optional, Union

from .base import ScenarioComponent


class PerformanceComponent(ScenarioComponent):
    """
    Facade for technology performance parameters.

    This component provides a semantically cleaner interface for performance
    characteristics while delegating to SupplyComponent for actual storage.

    This is NOT a standalone component - it does not own any CSV files.
    All parameters are stored via the underlying SupplyComponent.

    Warning
    -------
    This component is currently a stub. Use SupplyComponent directly for:
    - Capacity factors (sub-annual availability)
    - Availability factors (annual availability)
    - Efficiency (via activity ratios)

    Parameters
    ----------
    scenario_dir : str
        Path to the scenario directory.
    supply_component : SupplyComponent
        The supply component to delegate to.

    Example
    -------
    >>> from pyoscomp.scenario.components import SupplyComponent, PerformanceComponent
    >>> supply = SupplyComponent(scenario_dir)
    >>> perf = PerformanceComponent(scenario_dir, supply)
    >>> # Use supply directly for now:
    >>> supply.set_capacity_factor('REGION1', 'SOLAR_PV', bracket_weights={'Day': 0.8})
    """

    owned_files = []  # Facade - owns no files

    def __init__(self, scenario_dir: str, supply_component=None):
        """
        Initialize performance component facade.

        Parameters
        ----------
        scenario_dir : str
            Path to the scenario directory.
        supply_component : SupplyComponent, optional
            Supply component instance to delegate to.
        """
        super().__init__(scenario_dir)
        self._supply = supply_component

    @property
    def supply(self):
        """Get the underlying SupplyComponent."""
        return self._supply

    @supply.setter
    def supply(self, component) -> None:
        """Set the underlying SupplyComponent."""
        self._supply = component

    def load(self) -> None:
        """
        No-op: SupplyComponent handles loading.

        Performance parameters are stored in SupplyComponent's files.
        """
        pass

    def save(self) -> None:
        """
        No-op: SupplyComponent handles saving.

        Performance parameters are stored in SupplyComponent's files.
        """
        pass

    def set_efficiency(
        self,
        region: str,
        technology: str,
        efficiency: Union[float, Dict[int, float]],
        mode: str = 'MODE1'
    ) -> None:
        """
        Set technology conversion efficiency.

        Note
        ----
        This is a convenience method. Use `SupplyComponent.set_conversion_technology()`
        for full control over input/output fuels and modes.

        Raises
        ------
        NotImplementedError
            Always - use SupplyComponent directly.
        """
        raise NotImplementedError(
            "Use SupplyComponent.set_conversion_technology() to set efficiency. "
            "PerformanceComponent is a semantic facade."
        )

    def set_capacity_factor(
        self,
        region: str,
        technology: str,
        **kwargs
    ) -> None:
        """
        Set capacity factor profile.

        Delegates to SupplyComponent.set_capacity_factor().

        Raises
        ------
        NotImplementedError
            If supply_component not provided.
        """
        if self._supply is None:
            raise NotImplementedError(
                "No SupplyComponent provided. Use SupplyComponent.set_capacity_factor() directly."
            )
        self._supply.set_capacity_factor(region, technology, **kwargs)

    def set_availability_factor(
        self,
        region: str,
        technology: str,
        availability: Union[float, Dict[int, float]]
    ) -> None:
        """
        Set annual availability factor.

        Delegates to SupplyComponent.set_availability_factor().

        Raises
        ------
        NotImplementedError
            If supply_component not provided.
        """
        if self._supply is None:
            raise NotImplementedError(
                "No SupplyComponent provided. Use SupplyComponent.set_availability_factor() directly."
            )
        self._supply.set_availability_factor(region, technology, availability)

    def process(self):
        if self._supply is not None:
            self._supply.process()

    def __repr__(self) -> str:
        has_supply = self._supply is not None
        return f"PerformanceComponent(facade=True, supply_attached={has_supply})"
