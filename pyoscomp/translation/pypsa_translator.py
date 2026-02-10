from .base import InputTranslator, OutputTranslator

import logging
from pathlib import Path
import pypsa
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from itertools import product

logger = logging.getLogger(__name__)

class PyPSAInputTranslator(InputTranslator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.network = pypsa.Network()
        self.network.add("Carrier", "AC", color="lightblue") 

    def translate(self):
        """
        Convert generic scenario input to PyPSA network data format.
        Returns a PyPSA Network object.
        """
        regions = self.scenario_data.sets.regions
        years = self.scenario_data.sets.years
        year_split = self.scenario_data.time.year_split
        demand = self.scenario_data.demand.specified_annual_demand
        # ... clean, typed access

        # 1. Create Buses (Regions)
        regions = self._create_buses()
        self.network.add("Bus", regions)

        # 2. Create Snapshots & Weightings (Time)
        self._setup_time_structure()

        # 3. Add Loads (Demand)
        self._add_demand()
        
        return self.network
    
    def _create_buses(self) -> np.ndarray:
        """
        Helper method to create one bus per OSeMOSYS region.
        """
        regions_df = self.input_data.get("REGION")
        
        if regions_df is None or regions_df.empty:
            # Fallback for simple single-node models
            return np.array(["Region1"])
        
        return regions_df["VALUE"].values.flatten()
    
    def _create_snapshots(self):
        """
        Sets network snapshots and snapshot_weightings based on TIMESLICE, YEAR, and YearSplit.
        
        OSeMOSYS Logic: YearSplit[t,y] = Fraction of year (0 to 1)
        PyPSA Logic: weighting[t] = Duration in hours
        """
        timeslice_df = self.input_data.get("TIMESLICE")
        year_df = self.input_data.get("YEAR")
        year_split = self.input_data.get("YearSplit")

        if timeslice_df is None or year_df is None:
            raise ValueError("TIMESLICE and YEAR must be defined in input data.")

        years = year_df["VALUE"].values
        timeslices = timeslice_df["VALUE"].values

        # 1. Create a MultiIndex for (Year, Timeslice)
        snapshot_index = pd.MultiIndex.from_product(
            [years, timeslices], 
            names=["year", "timeslice"]
        )
        self.network.set_snapshots(snapshot_index)

        # 2. Calculate Weightings (Hours)
        # Default to 1 hour if YearSplit is missing (dangerous, but prevents crash)
        duration_hours = pd.Series(1.0, index=snapshot_index)

        if year_split is not None and not year_split.empty:
            # Map OSeMOSYS 'YearSplit' to the snapshot index
            # OSeMOSYS columns: ["TIMESLICE", "YEAR", "VALUE"]
            
            ys = year_split.copy()
            ys = ys.rename(columns={"VALUE": "fraction"})
            
            # Create matching index for easy mapping
            ys = ys.set_index(["YEAR", "TIMESLICE"])
            
            # Reindex to map the YearSplit data to the Cartesian product of snapshots
            # Any missing combinations get 0 hours
            aligned_fractions = ys["fraction"].reindex(snapshot_index).fillna(0)
            
            # Convert fraction of year to hours (8760 hours/year)
            duration_hours = aligned_fractions * 8760.0

        # 3. Assign to PyPSA specific columns
        # PyPSA expects a DataFrame with 'objective', 'stores', 'generators'
        self.network.snapshot_weightings = pd.DataFrame(
            {
                "objective": duration_hours,
                "stores": duration_hours,
                "generators": duration_hours
            },
            index=self.network.snapshots
        )

    def _add_demand(self):
        """
        Vectorized addition of demand profiles.
        
        OSeMOSYS: 
          - SpecifiedAnnualDemand (MWh/year)
          - SpecifiedDemandProfile (Fraction of demand in this slice)
        
        PyPSA:
          - Load p_set (MW)
        
        Formula: Power (MW) = (AnnualDemand * ProfileFraction) / (DurationHours)
        """
        annual_df = self.input_data.get("SpecifiedAnnualDemand")
        profile_df = self.input_data.get("SpecifiedDemandProfile")
        
        if annual_df is None or annual_df.empty:
            return

        # Prepare Annual Data
        # Index: [REGION, YEAR]
        annual_piv = annual_df.pivot(index=["REGION", "YEAR"], columns=[], values="VALUE")

        # Prepare Profile Data
        if profile_df is None or profile_df.empty:
            # If no profile, assume flat profile (1/N) logic handled implicitly or raise warning
            logger.warning("No SpecifiedDemandProfile found. Assuming flat demand.")
            # Create a dummy flat profile logic here if needed
            return

        # Pivot Profile to: Index=[REGION, YEAR], Columns=[TIMESLICE]
        # This gives us the fraction for every slice
        profile_piv = profile_df.pivot(index=["REGION", "YEAR"], columns="TIMESLICE", values="VALUE")
        
        # Ensure we have data for all Regions/Years
        # Multiply Annual Total (MWh) by Profile Fraction -> Energy per slice (MWh)
        energy_per_slice = profile_piv.multiply(annual_piv, axis=0)
        
        # Now convert Energy (MWh) to Power (MW)
        # Divide by the duration of each snapshot
        # Snapshot weightings are indexed by (Year, Timeslice)
        weights = self.network.snapshot_weightings
        
        # Iterate through regions to add them to the network
        for region in self.network.buses.index:
            if region not in energy_per_slice.index.get_level_values("REGION"):
                continue

            # Extract data for this region: Index becomes [YEAR], cols are [TIMESLICE]
            region_energy = energy_per_slice.loc[region] 
            
            # Stack to get Series with index (YEAR, TIMESLICE) matching snapshots
            region_energy_stacked = region_energy.stack()
            region_energy_stacked.index.names = ["year", "timeslice"]
            
            # Align with network snapshots (filling missing data with 0)
            aligned_energy = region_energy_stacked.reindex(self.network.snapshots).fillna(0)
            
            # Calculate Power: MW = MWh / Hours
            # Avoid division by zero
            aligned_power = aligned_energy / weights.replace(0, 1)
            
            # Handle cases where weight is 0 (should imply 0 power)
            aligned_power = aligned_power.where(weights > 0, 0)

            self.network.add("Load", 
                             name=f"{region}_load", 
                             bus=region, 
                             p_set=aligned_power)

    def _add_supply(self, generator: str):
        """
        Helper method to add supply profile to self.network.
        """
        # Similar vectorized logic would go here for Capacity, AvailabilityFactor, etc.
        pass

class PyPSAOutputTranslator(OutputTranslator):
    def translate(self) -> Dict[str, pd.DataFrame]:
        """
        Convert PyPSA results to standardized output DataFrames.
        """
        results = {}
        
        # Example: Generation per carrier
        if not self.model_output.generators_t.p.empty:
            gen = self.model_output.generators_t.p
            # Logic to unstack/melt back to OSeMOSYS format
            results["Generation"] = gen 
            
        return results