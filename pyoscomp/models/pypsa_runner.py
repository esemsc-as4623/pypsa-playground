"""
pyoscomp/models/pypsa_runner.py

Executes the PyPSA model using translated input data.
"""
import pypsa
import pandas as pd
import os
from typing import Dict, Any, Optional

class PyPSARunner:
    def __init__(self, input_dir: str):
        self.input_dir = input_dir
        self.network = None

    def build_network(self):
        self.network = pypsa.Network()
        # Load all CSVs in input_dir that match PyPSA components
        component_files = [f for f in os.listdir(self.input_dir) if f.endswith('.csv')]
        for file in component_files:
            component = file.replace('.csv', '')
            path = os.path.join(self.input_dir, file)
            df = pd.read_csv(path)
            # Use PyPSA's built-in import for known components
            if hasattr(self.network, component):
                # Set index if 'name' column exists
                if 'name' in df.columns:
                    df = df.set_index('name', drop=False)
                getattr(self.network, component).import_from_dataframe(df)
            else:
                # Store as extra attribute for user reference
                setattr(self.network, f"extra_{component}", df)

    def run(self):
        if self.network is None:
            self.build_network()
        self.network.lopf()
        return self.network
