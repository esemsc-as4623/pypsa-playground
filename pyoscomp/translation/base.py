from abc import ABC, abstractmethod
from typing import Dict, Any
import pandas as pd

from ..interfaces import ScenarioData

class InputTranslator(ABC):
    """
    Abstract base class for translating generic scenario input data to model-specific formats.
    """
    def __init__(self, scenario_data: ScenarioData):
        self.scenario_data = scenario_data

    @abstractmethod
    def translate(self) -> Any:
        """Translate input data to model-specific format."""
        pass

class OutputTranslator(ABC):
    """
    Abstract base class for translating model-specific outputs to standardized format.
    """
    def __init__(self, model_output: Any):
        self.model_output = model_output

    @abstractmethod
    def translate(self):
        """Translate model output to standardized output DataFrames."""
        pass