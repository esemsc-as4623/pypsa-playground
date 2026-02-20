from abc import ABC, abstractmethod
from typing import Any

from ..interfaces import ScenarioData
from ..interfaces.results import ModelResults


class InputTranslator(ABC):
    """
    Abstract base class for translating ScenarioData to
    model-specific input formats.
    """
    def __init__(self, scenario_data: ScenarioData):
        self.scenario_data = scenario_data

    @abstractmethod
    def translate(self) -> Any:
        """Translate input data to model-specific format."""
        pass


class OutputTranslator(ABC):
    """
    Abstract base class for translating model-specific outputs
    to the harmonized ``ModelResults`` interface.

    Subclasses accept raw model output (a PyPSA Network, a
    results directory path, etc.) and produce an immutable
    ``ModelResults`` container that enables cross-model
    comparison.
    """
    def __init__(self, model_output: Any):
        self.model_output = model_output

    @abstractmethod
    def translate(self) -> ModelResults:
        """
        Translate model output to harmonized ModelResults.

        Returns
        -------
        ModelResults
            Immutable, model-agnostic result container.
        """
        pass