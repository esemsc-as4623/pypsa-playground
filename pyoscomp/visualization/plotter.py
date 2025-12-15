"""
pyoscomp/visualization/plotter.py

Provides visualization utilities for model outputs using matplotlib and PyPSA tools.
"""
import matplotlib.pyplot as plt
import pandas as pd
from typing import Dict

class OutputPlotter:
    """
    Plots standardized output data using matplotlib.
    """
    def __init__(self, output_data: Dict[str, pd.DataFrame]):
        self.output_data = output_data

    def plot_summary(self, save_path: str = None):
        """Example: Plot a summary result from output data."""
        if "summary" in self.output_data:
            df = self.output_data["summary"]
            ax = df.plot(kind="bar")
            plt.title("Model Output Summary")
            plt.xlabel("Index")
            plt.ylabel("Value")
            if save_path:
                plt.savefig(save_path)
            else:
                plt.show()

# Extend with more specific plotting functions as needed
