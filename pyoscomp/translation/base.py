from abc import ABC, abstractmethod
from typing import Dict, Any, Union
import pandas as pd

class InputTranslator(ABC):
    """
    Abstract base class for translating generic scenario input data to model-specific formats.
    """
    def __init__(self, input_data: Dict[str, pd.DataFrame], config: Dict[str, Any] = None):
        self.input_data = input_data
        self.config = config or {}

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
    def translate(self) -> Dict[str, pd.DataFrame]:
        """Translate model output to standardized output DataFrames."""
        pass