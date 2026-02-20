# pyoscomp/translation/pypsa_translator.py

from .base import InputTranslator, OutputTranslator

import logging
import pypsa
from typing import Dict
import pandas as pd
import numpy as np

from ..constants import hours_in_year, TOL
from .time import SnapshotResult

logger = logging.getLogger(__name__)


class PyPSAInputTranslator(InputTranslator):
    """
    Translates ScenarioData to a PyPSA Network object.
    
    This translator creates a PyPSA network from OSeMOSYS-structured scenario data,
    mapping regions to buses, timeslices to snapshots, and technologies to generators.
    
    Attributes
    ----------
    scenario_data : ScenarioData
        The source scenario data (from base class).
    network : pypsa.Network
        The PyPSA network being constructed.
    _data_dict : Dict[str, pd.DataFrame]
        Cached dictionary representation of scenario_data for convenience.
    
    Example
    -------
    >>> from pyoscomp.interfaces import ScenarioData
    >>> data = ScenarioData.from_directory('/path/to/scenario')
    >>> translator = PyPSAInputTranslator(data)
    >>> network = translator.translate()
    """
    
    def __init__(self, scenario_data):
        """
        Initialize the translator with scenario data.
        
        Parameters
        ----------
        scenario_data : ScenarioData
            The scenario data to translate.
        """
        super().__init__(scenario_data)
        self.network = pypsa.Network()
        self.network.add("Carrier", "AC", color="lightblue")
        # Cache dict representation for methods that need it
        self._data_dict = None

    @property
    def data_dict(self) -> Dict[str, pd.DataFrame]:
        """Lazy-load dictionary representation of scenario data."""
        if self._data_dict is None:
            self._data_dict = self.scenario_data.to_dict()
        return self._data_dict

    def translate(self) -> pypsa.Network:
        """
        Convert ScenarioData to a PyPSA Network object.
        
        Returns
        -------
        pypsa.Network
            Fully configured PyPSA network ready for optimization.
        
        Raises
        ------
        ValueError
            If required sets (REGION, YEAR, TIMESLICE) are missing.
        """
        # 1. Create Buses (Regions)
        regions = self._create_buses()
        self.network.add("Bus", regions)

        # 2. Create Snapshots & Weightings (Time)
        snapshot_results = self._setup_time_structure()
        snapshot_results.apply_to_network(self.network)

        # 3. Add Loads (Demand)
        self._add_demand()
        
        # 4. Add Generators (Supply) - if supply data exists
        self._add_supply()
        
        return self.network
    
    def _create_buses(self) -> np.ndarray:
        """
        Create one bus per OSeMOSYS region.
        
        Returns
        -------
        np.ndarray
            Array of region names to use as bus identifiers.
        """
        regions = self.scenario_data.sets.regions
        
        if not regions:
            # Fallback for simple single-node models
            logger.warning("No regions defined, using default 'REGION1'")
            return np.array(["REGION1"])
        
        return np.array(sorted(regions))
    
    def _setup_time_structure(self) -> SnapshotResult:
        """
        Set network snapshots and weightings.
        
        Uses the robust time translation logic from pyoscomp.translation.time module.
        This creates a SnapshotResult and applies it to the network, handling:
        - Multiple investment periods (years)
        - Leap year handling via hours_in_year()
        - Proper validation of temporal coverage
        
        OSeMOSYS Logic: YearSplit[l,y] = Fraction of year (0 to 1), sum to 1.0
        PyPSA Logic: weighting[t] = Duration in hours, sum to 8760/8784 per year
        """
        from pyoscomp.translation.time import to_snapshots

        result = to_snapshots(self.scenario_data)

        # 1. Create MultiIndex snapshots (period, timestep)
        snapshots = result.snapshots

        # 2. Create weightings from YearSplit (fraction → hours)
        weightings = result.weightings
        weightings = weightings.reindex(snapshots)  # Ensure alignment

        # 3. Create SnapshotResult for validation
        snapshot_result = SnapshotResult(
            years=self.scenario_data.sets.years,
            snapshots=snapshots,
            weightings=weightings,
            timeslice_names=self.scenario_data.sets.timeslices
        )
        
        # 4. Validate coverage (weightings sum to correct hours per year)
        if not snapshot_result.validate_coverage():
            # Log warning but continue - the model may still work
            for year in self.scenario_data.sets.years:
                year_mask = snapshots.get_level_values('period') == year
                total_hours = weightings[year_mask].sum()
                expected = hours_in_year(year)
                if abs(total_hours - expected) > TOL:
                    logger.warning(
                        f"Year {year}: weightings sum to {total_hours:.2f}h, "
                        f"expected {expected:.0f}h (diff={total_hours - expected:.2f}h)"
                    )

        # 5. Apply to network
        snapshot_result.apply_to_network(self.network)

    def _add_demand(self) -> None:
        """
        Add demand as loads to the network.
        
        OSeMOSYS: 
          - SpecifiedAnnualDemand (energy units/year)
          - SpecifiedDemandProfile (fraction of demand in this slice)
        
        PyPSA:
          - Load p_set (power units)
        
        Formula: Power = (AnnualDemand × ProfileFraction) / DurationHours
        """
        annual_df = self.scenario_data.demand.specified_annual_demand
        profile_df = self.scenario_data.demand.specified_demand_profile
        
        if annual_df is None or annual_df.empty:
            logger.warning("No SpecifiedAnnualDemand found, skipping demand")
            return

        # Prepare weights for power calculation
        weights = self.network.snapshot_weightings['generators']

        # Handle case where no profile exists
        if profile_df is None or profile_df.empty:
            logger.warning("No SpecifiedDemandProfile found. Assuming flat demand.")
            # Create flat profile
            n_slices = len(self.scenario_data.sets.timeslices)
            profile_df = annual_df.copy()
            profile_records = []
            for _, row in annual_df.iterrows():
                for ts in self.scenario_data.sets.timeslices:
                    profile_records.append({
                        'REGION': row['REGION'],
                        'FUEL': row['FUEL'],
                        'TIMESLICE': ts,
                        'YEAR': row['YEAR'],
                        'VALUE': 1.0 / n_slices
                    })
            profile_df = pd.DataFrame(profile_records)

        # Pivot Annual Data: Index=[REGION, FUEL, YEAR], Value=annual demand
        annual_indexed = annual_df.set_index(['REGION', 'FUEL', 'YEAR'])['VALUE']

        # Pivot Profile Data: Index=[REGION, FUEL, YEAR, TIMESLICE], Value=fraction
        profile_indexed = profile_df.set_index(['REGION', 'FUEL', 'TIMESLICE', 'YEAR'])['VALUE']
        
        # Get unique demand fuels
        demand_fuels = annual_df['FUEL'].unique()
        
        # Iterate through regions and fuels to add loads
        for region in self.network.buses.index:
            for fuel in demand_fuels:
                load_name = f"{region}_{fuel}_load"
                
                # Build power series for this load
                power_series = pd.Series(index=self.network.snapshots, dtype=float)
                
                for (year, timeslice) in self.network.snapshots:
                    try:
                        annual = annual_indexed.loc[(region, fuel, year)]
                        profile = profile_indexed.loc[(region, fuel, timeslice, year)]
                        hours = weights.loc[(year, timeslice)]
                        
                        # Energy (MWh) = Annual × Profile fraction
                        # Power (MW) = Energy / Hours
                        if hours > 0:
                            power = (annual * profile) / hours
                        else:
                            power = 0.0
                        power_series.loc[(year, timeslice)] = power
                    except KeyError:
                        power_series.loc[(year, timeslice)] = 0.0
                
                if power_series.sum() > 0:
                    self.network.add(
                        "Load", 
                        name=load_name, 
                        bus=region, 
                        p_set=power_series
                    )

    def _add_supply(self) -> None:
        """
        Add generators based on supply data.
        
        Maps OSeMOSYS technologies to PyPSA generators with:
        - ResidualCapacity → p_nom
        - CapacityFactor → p_max_pu
        - VariableCost → marginal_cost
        - CapitalCost + OperationalLife → capital_cost (annualized)
        
        Note: Full implementation requires economics and performance data.
        Currently a placeholder that logs a warning.
        """
        technologies = self.scenario_data.sets.technologies
        
        if not technologies:
            logger.info("No technologies defined, skipping supply")
            return
            
        # TODO: Implement full supply translation using:
        # - self.scenario_data.supply.residual_capacity
        # - self.scenario_data.performance.capacity_factor
        # - self.scenario_data.economics.capital_cost
        # - etc.
        logger.warning("Supply translation not yet fully implemented")


class PyPSAOutputTranslator(OutputTranslator):
    """
    Translates PyPSA optimization results to standardized output DataFrames.
    """
    
    def translate(self) -> Dict[str, pd.DataFrame]:
        """
        Convert PyPSA results to standardized output DataFrames.
        
        Returns
        -------
        Dict[str, pd.DataFrame]
            Dictionary of result DataFrames keyed by result type.
        """
        results = {}
        
        # Extract generation results
        if not self.model_output.generators_t.p.empty:
            results["Generation"] = self.model_output.generators_t.p.copy()
        
        # Extract optimal capacities
        if hasattr(self.model_output.generators, 'p_nom_opt'):
            results["OptimalCapacity"] = self.model_output.generators[['p_nom_opt']].copy()
        
        # Extract objective value
        results["Objective"] = pd.DataFrame({
            'VALUE': [self.model_output.objective]
        })
            
        return results