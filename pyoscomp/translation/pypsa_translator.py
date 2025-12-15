"""
pyoscomp/translation/pypsa_translator.py

Translates scenario input/output for PyPSA model.
"""
from .base import InputTranslator, OutputTranslator

import logging
from pathlib import Path

logger = logging.getLogger(__name__)
save_directory = Path(__file__).parent

import pypsa
from typing import Dict, Any
import pandas as pd
import numpy as np
import datetime
from itertools import product

class PyPSAInputTranslator(InputTranslator):
    def translate(self) -> Dict[str, Any]:
        """
        Convert generic scenario input to PyPSA network data format.
        Returns a PyPSA Network object.
        """
        n = pypsa.Network()
        n.add("Carrier", "AC", color="lightblue") # TODO: make configurable

        # create buses based on regions
        n.add("Bus", range(self._create_buses()))

        # create snapshots based on YEAR, SEASON, DAYTYPE, DAILYTIMEBRACKET
        n.set_snapshots(range(self._create_snapshots()))

        buses = n.buses.index
        snapshots = n.snapshots

        # add load (demand) profile
        n.add("Load", n.buses.index + " load", bus=buses,
              p_set=np.random.rand(len(snapshots), len(buses)))

        return n
    
    def _create_buses(self) -> int:
        """
        Helper method to create one bus per OSeMOSYS region.
        Returns the number of regions found.
        """
        regions_df = self.input_data.get("REGION")
        
        if regions_df is None:
            return 0
        
        elif regions_df.empty:
            # if no regions listed, assume single region model
            self.regions = {"DEFAULT_REGION"}

        else:
            self.regions = set(regions_df.values.flatten())
        
        # store mapping of region indices to region labels
        self.region_labels = dict(zip(range(len(self.regions)), self.regions))
        return len(self.regions)
    
    def _create_snapshots(self) -> int:
        """
        Helper method to determine number of snapshots from TIMESLICE data.
        Returns the number of TIMESLICE entries found.
        """
        year_df = self.input_data.get("YEAR")
        season_df = self.input_data.get("SEASON")
        daytype_df = self.input_data.get("DAYTYPE")
        dailytimebracket_df = self.input_data.get("DAILYTIMEBRACKET")

        if year_df is None or year_df.empty:
            # assume single year if none specified
            self.years = np.array([datetime.datetime.now().year])
        else:
            self.years = year_df.values.flatten()

        if season_df is None or season_df.empty:
            # assume single season if none specified
            self.seasons = np.array(["ANNUAL"])
        else:
            self.seasons = season_df.values.flatten()

        if daytype_df is None or daytype_df.empty:
            # assume single daytype if none specified
            self.daytypes = np.array(["ALLDAYS"])
        else:
            self.daytypes = daytype_df.values.flatten()

        if dailytimebracket_df is None or dailytimebracket_df.empty:
            # assume single dailytimebracket if none specified
            self.dailytimebrackets = np.array(["ALLHOURS"])
        else:
            self.dailytimebrackets = dailytimebracket_df.values.flatten()

        # store mapping of time indices to time labels
        timelabels = [f"{y}-{s}-{d}-{t}" for y, s, d, t in product(
            self.years, self.seasons, self.daytypes, self.dailytimebrackets)]
        t = len(timelabels)
        self.time_labels = dict(zip(range(t), timelabels))
        
        # timeslice = season x daytype x dailytimebracket
        # timeslice_df = self.input_data.get("TIMESLICE") # TODO: use this to validate combinations?

        return t
    
    def get_region_labels(self) -> Dict[int, str]:
        return self.region_labels
    def get_region_label(self, region_index: int) -> str:
        # TODO: handle out-of-bounds index
        return self.region_labels.get(region_index, "UNKNOWN")
    def get_time_labels(self) -> Dict[int, str]:
        return self.time_labels
    def get_time_label(self, time_index: int) -> str:
        # TODO: handle out-of-bounds index
        return self.time_labels.get(time_index, "UNKNOWN")

class PyPSAOutputTranslator(OutputTranslator):
    def translate(self) -> Dict[str, pd.DataFrame]:
        """
        Convert PyPSA results to standardized output DataFrames.
        """
        # Placeholder: implement actual translation logic
        return {"summary": pd.DataFrame({"result": ["example"]})}
