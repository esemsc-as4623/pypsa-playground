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
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
import datetime
from itertools import product

class PyPSAInputTranslator(InputTranslator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.network = pypsa.Network()
        self.network.add("Carrier", "AC", color="lightblue") # TODO: make configurable

    def translate(self):
        """
        Convert generic scenario input to PyPSA network data format.
        Returns a PyPSA Network object.
        """
        # create buses based on regions
        self.network.add("Bus", self._create_buses())

        # create snapshots based on YEAR, SEASON, DAYTYPE, DAILYTIMEBRACKET
        self.network.set_snapshots(range(self._create_snapshots()))

        # add load (demand) profile
        for bus in self.network.buses.index:
            self.network.add("Load", bus + " load", bus=bus,
                  p_set=self._add_demand(bus))
    
    def _create_buses(self) -> np.ndarray:
        """
        Helper method to create one bus per OSeMOSYS region.
        Returns an array of region names
        """
        regions_df = self.input_data.get("REGION")
        
        if regions_df is None:
            return 0
        
        elif regions_df.empty:
            # if no regions listed, assume single region model
            regions = np.array(["DEFAULT_REGION"])

        else:
            regions = regions_df.values.flatten()
        
        return regions
    
    def _create_snapshots(self) -> np.ndarray:
        """
        Helper method to determine number of snapshots from TIMESLICE data.
        Returns an array of timeslices
        """
        # first check for explicit TIMESLICE definition
        timeslice_df = self.input_data.get("TIMESLICE")
        
        if timeslice_df is not None and not timeslice_df.empty:
            return timeslice_df.values.flatten()
        
        # otherwise, build timeslices from YEAR, SEASON, DAYTYPE, DAILYTIMEBRACKET
        year_df = self.input_data.get("YEAR")
        season_df = self.input_data.get("SEASON")
        daytype_df = self.input_data.get("DAYTYPE")
        dailytimebracket_df = self.input_data.get("DAILYTIMEBRACKET")

        if year_df is None or year_df.empty:
            # assume single year if none specified
            years = np.array([datetime.datetime.now().year])
        else:
            years = year_df.values.flatten()

        if season_df is None or season_df.empty:
            # assume single season if none specified
            seasons = np.array(["ANNUAL"])
        else:
            seasons = season_df.values.flatten()

        if daytype_df is None or daytype_df.empty:
            # assume single daytype if none specified
            daytypes = np.array(["ALLDAYS"])
        else:
            daytypes = daytype_df.values.flatten()

        if dailytimebracket_df is None or dailytimebracket_df.empty:
            # assume single dailytimebracket if none specified
            dailytimebrackets = np.array(["ALLHOURS"])
        else:
            dailytimebrackets = dailytimebracket_df.values.flatten()

        # store mapping of time indices to time labels
        timelabels = np.array([f"{y}-{s}-{d}-{t}" for y, s, d, t in product(
            years, seasons, daytypes, dailytimebrackets)])
        
        return timelabels
    
    def _add_demand(self, aggregate: bool = True):
        """
        Helper method to add demand profile to self.network.
        """
        annual_df = self.input_data.get("SpecifiedAnnualDemand")
        if annual_df is None or annual_df.empty:
            # TODO: error handling
            return None
        profile_df = self.input_data.get("SpecifiedDemandProfile")
        if profile_df is None or profile_df.empty:
            # if no profile provided, assume flat profile
            profile_df = pd.DataFrame({
                "REGION": annual_df["REGION"],
                "YEAR": annual_df["YEAR"],
                "TIMESLICE": self.network.snapshots,
                "VALUE": 1.0 / len(self.network.snapshots) # TODO: divide by number of timeslices per year
            })

        timeslices = self.network.snapshots

        if aggregate:
            # loop over regions (buses)
            for region in self.network.buses.index:
                demand = np.zeros(len(timeslices))
                region_annual = annual_df[annual_df["REGION"] == region]
                
                # for each year
                for _, annual_row in region_annual.iterrows():
                    year = annual_row["YEAR"]
                    value = annual_row["VALUE"]

                    # get profile by timeslice
                    region_profile = profile_df[
                        (profile_df["REGION"] == region) &
                        (profile_df["YEAR"] == year)
                    ]

                    # for each timeslice
                    for _, profile_row in region_profile.iterrows():
                        timeslice = profile_row["TIMESLICE"]
                        profile_value = profile_row["VALUE"]

                        # add timeslice_proportion * annual_value to demand array
                        if timeslice in timeslices:
                            idx = list(timeslices).index(timeslice)
                            demand[idx] += value * profile_value

                # add load to network
                self.network.add("Load", region + " load", bus=region, p_set=demand)
                
        else:
            # TODO: incorporate fuel-specific demand
            pass

        additional_df = self.input_data.get("AccumulatedAnnualDemand")
        if additional_df is not None and not additional_df.empty:
            # TODO: deal with additional non-profiled demand
            pass

    def _add_supply(self, generator: str):
        """
        Helper method to add supply profile to self.network.
        """
        pass

class PyPSAOutputTranslator(OutputTranslator):
    def translate(self) -> Dict[str, pd.DataFrame]:
        """
        Convert PyPSA results to standardized output DataFrames.
        """
        # Placeholder: implement actual translation logic
        return {"summary": pd.DataFrame({"result": ["example"]})}
