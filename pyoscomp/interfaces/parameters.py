# pyoscomp/interfaces/parameters.py

"""
OSeMOSYS Parameter group definitions for the ScenarioData interface.

This module defines immutable dataclasses for each parameter category,
organized by owning component per the component_mapping.md specification.

Each parameter group:
- Stores related OSeMOSYS parameters as pandas DataFrames
- Provides validation methods to check references and constraints
- Is immutable (frozen dataclass) to prevent accidental modification
"""

import math
import pandas as pd
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..constants import TOL

if TYPE_CHECKING:
    from .sets import OSeMOSYSSets


def _empty_df() -> pd.DataFrame:
    """Factory for creating empty DataFrames (used for optional parameters)."""
    return pd.DataFrame()


@dataclass(frozen=True)
class TimeParameters:
    """
    Time-related OSeMOSYS parameters owned by TimeComponent.
    
    Attributes
    ----------
    year_split : pd.DataFrame
        YearSplit[l,y] - Fraction of year per timeslice.
        Columns: TIMESLICE, YEAR, VALUE
    day_split : pd.DataFrame
        DaySplit[lh,y] - Fraction of day per daily time bracket.
        Columns: DAILYTIMEBRACKET, YEAR, VALUE
    conversion_ls : pd.DataFrame
        Conversionls[l,ls] - Binary mapping TIMESLICE→SEASON.
        Columns: TIMESLICE, SEASON, VALUE
    conversion_ld : pd.DataFrame
        Conversionld[l,ld] - Binary mapping TIMESLICE→DAYTYPE.
        Columns: TIMESLICE, DAYTYPE, VALUE
    conversion_lh : pd.DataFrame
        Conversionlh[l,lh] - Binary mapping TIMESLICE→DAILYTIMEBRACKET.
        Columns: TIMESLICE, DAILYTIMEBRACKET, VALUE
    days_in_daytype : pd.DataFrame
        DaysInDayType[ls,ld,y] - Days per daytype per season per year.
        Columns: SEASON, DAYTYPE, YEAR, VALUE
    
    Notes
    -----
    - YearSplit must sum to 1.0 for each year
    - DaySplit must sum to 1.0 for each year
    - Conversion tables contain binary (0 or 1) mappings
    """
    year_split: pd.DataFrame = field(default_factory=_empty_df)
    day_split: pd.DataFrame = field(default_factory=_empty_df)
    conversion_ls: pd.DataFrame = field(default_factory=_empty_df)
    conversion_ld: pd.DataFrame = field(default_factory=_empty_df)
    conversion_lh: pd.DataFrame = field(default_factory=_empty_df)
    days_in_daytype: pd.DataFrame = field(default_factory=_empty_df)
    
    # Mapping to CSV filenames
    CSV_MAPPING = {
        'year_split': 'YearSplit.csv',
        'day_split': 'DaySplit.csv',
        'conversion_ls': 'Conversionls.csv',
        'conversion_ld': 'Conversionld.csv',
        'conversion_lh': 'Conversionlh.csv',
        'days_in_daytype': 'DaysInDayType.csv',
    }
    
    def validate(self, sets: 'OSeMOSYSSets') -> None:
        """
        Validate temporal consistency and coverage.
        
        Checks:
        - YearSplit sums to 1.0 for each year
        - DaySplit sums to 1.0 for each year
        - All referenced timeslices exist in sets.timeslices
        
        Raises
        ------
        ValueError
            If validation fails.
        """
        # Check YearSplit sums to 1.0 per year
        if not self.year_split.empty:
            for year in sets.years:
                year_data = self.year_split[self.year_split['YEAR'] == year]
                if not year_data.empty:
                    total = year_data['VALUE'].sum()
                    if not math.isclose(total, 1.0, abs_tol=TOL):
                        raise ValueError(f"YearSplit for {year} sums to {total:.6f}, not 1.0")
            
            # Check timeslice references
            ts_refs = set(self.year_split['TIMESLICE'].unique())
            sets.validate_membership(ts_refs, 'timeslices', 'in YearSplit')
        
        # Check DaySplit sums to 1.0 per year
        if not self.day_split.empty:
            for year in sets.years:
                day_data = self.day_split[self.day_split['YEAR'] == year]
                if not day_data.empty:
                    total = day_data['VALUE'].sum()
                    if not math.isclose(total, 1.0, abs_tol=TOL):
                        raise ValueError(f"DaySplit for {year} sums to {total:.6f}, not 1.0")
            
            # Check bracket references
            bracket_refs = set(self.day_split['DAILYTIMEBRACKET'].unique())
            sets.validate_membership(bracket_refs, 'dailytimebrackets', 'in DaySplit')


@dataclass(frozen=True)
class DemandParameters:
    """
    Demand-related OSeMOSYS parameters owned by DemandComponent.
    
    Attributes
    ----------
    specified_annual_demand : pd.DataFrame
        SpecifiedAnnualDemand[r,f,y] - Annual demand volume (energy units).
        Columns: REGION, FUEL, YEAR, VALUE
    specified_demand_profile : pd.DataFrame
        SpecifiedDemandProfile[r,f,l,y] - Fraction of annual demand per timeslice.
        Columns: REGION, FUEL, TIMESLICE, YEAR, VALUE
    accumulated_annual_demand : pd.DataFrame
        AccumulatedAnnualDemand[r,f,y] - Flexible demand (any time during year).
        Columns: REGION, FUEL, YEAR, VALUE
    
    Notes
    -----
    - SpecifiedDemandProfile must sum to 1.0 for each (region, fuel, year) combination
    - Demand fuels must exist in the FUEL set
    """
    specified_annual_demand: pd.DataFrame = field(default_factory=_empty_df)
    specified_demand_profile: pd.DataFrame = field(default_factory=_empty_df)
    accumulated_annual_demand: pd.DataFrame = field(default_factory=_empty_df)
    
    CSV_MAPPING = {
        'specified_annual_demand': 'SpecifiedAnnualDemand.csv',
        'specified_demand_profile': 'SpecifiedDemandProfile.csv',
        'accumulated_annual_demand': 'AccumulatedAnnualDemand.csv',
    }
    
    def validate(self, sets: 'OSeMOSYSSets') -> None:
        """
        Validate demand references and profile sums.
        
        Raises
        ------
        ValueError
            If fuels/regions/years not in sets, or profiles don't sum to 1.0.
        """
        # Validate SpecifiedAnnualDemand references
        if not self.specified_annual_demand.empty:
            fuels = set(self.specified_annual_demand['FUEL'].unique())
            sets.validate_membership(fuels, 'fuels', 'in SpecifiedAnnualDemand')
            
            regions = set(self.specified_annual_demand['REGION'].unique())
            sets.validate_membership(regions, 'regions', 'in SpecifiedAnnualDemand')
            
            years = set(self.specified_annual_demand['YEAR'].unique())
            sets.validate_membership(years, 'years', 'in SpecifiedAnnualDemand')
        
        # Validate SpecifiedDemandProfile sums to 1.0
        if not self.specified_demand_profile.empty:
            grouped = self.specified_demand_profile.groupby(['REGION', 'FUEL', 'YEAR'])['VALUE'].sum()
            for (region, fuel, year), total in grouped.items():
                if not math.isclose(total, 1.0, abs_tol=TOL):
                    raise ValueError(
                        f"SpecifiedDemandProfile for ({region}, {fuel}, {year}) "
                        f"sums to {total:.6f}, not 1.0"
                    )


@dataclass(frozen=True)
class SupplyParameters:
    """
    Supply-related parameters owned by SupplyComponent.
    
    Attributes
    ----------
    residual_capacity : pd.DataFrame
        ResidualCapacity[r,t,y] - Pre-installed capacity (power units).
        Columns: REGION, TECHNOLOGY, YEAR, VALUE
    
    Notes
    -----
    - ResidualCapacity represents existing infrastructure
    - Technologies must exist in the TECHNOLOGY set
    """
    residual_capacity: pd.DataFrame = field(default_factory=_empty_df)
    
    CSV_MAPPING = {
        'residual_capacity': 'ResidualCapacity.csv',
    }
    
    def validate(self, sets: 'OSeMOSYSSets') -> None:
        """
        Validate supply parameter references.
        
        Raises
        ------
        ValueError
            If referenced technologies/regions/years not in sets.
        """
        if not self.residual_capacity.empty:
            techs = set(self.residual_capacity['TECHNOLOGY'].unique())
            sets.validate_membership(techs, 'technologies', 'in ResidualCapacity')
            
            regions = set(self.residual_capacity['REGION'].unique())
            sets.validate_membership(regions, 'regions', 'in ResidualCapacity')


@dataclass(frozen=True)
class EconomicsParameters:
    """
    Economics parameters owned by EconomicsComponent.
    
    Attributes
    ----------
    discount_rate : pd.DataFrame
        DiscountRate[r] - Regional discount rate for NPV calculations.
        Columns: REGION, VALUE
    discount_rate_idv : pd.DataFrame
        DiscountRateIdv[r,t] - Technology-specific discount rate (optional).
        Columns: REGION, TECHNOLOGY, VALUE
    capital_cost : pd.DataFrame
        CapitalCost[r,t,y] - Capital investment cost per unit capacity.
        Columns: REGION, TECHNOLOGY, YEAR, VALUE
    variable_cost : pd.DataFrame
        VariableCost[r,t,m,y] - Operating cost per unit activity.
        Columns: REGION, TECHNOLOGY, MODE_OF_OPERATION, YEAR, VALUE
    fixed_cost : pd.DataFrame
        FixedCost[r,t,y] - Annual fixed O&M cost per unit capacity.
        Columns: REGION, TECHNOLOGY, YEAR, VALUE
    
    Notes
    -----
    - Discount rates should be in range [0, 1]
    - Costs should be non-negative
    """
    discount_rate: pd.DataFrame = field(default_factory=_empty_df)
    discount_rate_idv: pd.DataFrame = field(default_factory=_empty_df)
    capital_cost: pd.DataFrame = field(default_factory=_empty_df)
    variable_cost: pd.DataFrame = field(default_factory=_empty_df)
    fixed_cost: pd.DataFrame = field(default_factory=_empty_df)
    
    CSV_MAPPING = {
        'discount_rate': 'DiscountRate.csv',
        'discount_rate_idv': 'DiscountRateIdv.csv',
        'capital_cost': 'CapitalCost.csv',
        'variable_cost': 'VariableCost.csv',
        'fixed_cost': 'FixedCost.csv',
    }
    
    def validate(self, sets: 'OSeMOSYSSets') -> None:
        """
        Validate cost parameter references and value constraints.
        
        Raises
        ------
        ValueError
            If references invalid or costs negative.
        """
        # Validate DiscountRate
        if not self.discount_rate.empty:
            regions = set(self.discount_rate['REGION'].unique())
            sets.validate_membership(regions, 'regions', 'in DiscountRate')
            
            # Check rate bounds
            if (self.discount_rate['VALUE'] < 0).any() or (self.discount_rate['VALUE'] > 1).any():
                raise ValueError("DiscountRate must be in range [0, 1]")
        
        # Validate CapitalCost
        if not self.capital_cost.empty:
            techs = set(self.capital_cost['TECHNOLOGY'].unique())
            sets.validate_membership(techs, 'technologies', 'in CapitalCost')
            
            if (self.capital_cost['VALUE'] < 0).any():
                raise ValueError("CapitalCost cannot be negative")
        
        # Validate VariableCost
        if not self.variable_cost.empty:
            techs = set(self.variable_cost['TECHNOLOGY'].unique())
            sets.validate_membership(techs, 'technologies', 'in VariableCost')
            
            modes = set(self.variable_cost['MODE_OF_OPERATION'].unique())
            sets.validate_membership(modes, 'modes', 'in VariableCost')


@dataclass(frozen=True)
class PerformanceParameters:
    """
    Performance parameters (owned by SupplyComponent, facade in PerformanceComponent).
    
    Attributes
    ----------
    operational_life : pd.DataFrame
        OperationalLife[r,t] - Asset lifetime in years.
        Columns: REGION, TECHNOLOGY, VALUE
    capacity_to_activity_unit : pd.DataFrame
        CapacityToActivityUnit[r,t] - Conversion factor (default 8760).
        Columns: REGION, TECHNOLOGY, VALUE
    input_activity_ratio : pd.DataFrame
        InputActivityRatio[r,t,f,m,y] - Input fuel per unit output.
        Columns: REGION, TECHNOLOGY, FUEL, MODE_OF_OPERATION, YEAR, VALUE
    output_activity_ratio : pd.DataFrame
        OutputActivityRatio[r,t,f,m,y] - Output per unit activity.
        Columns: REGION, TECHNOLOGY, FUEL, MODE_OF_OPERATION, YEAR, VALUE
    capacity_factor : pd.DataFrame
        CapacityFactor[r,t,l,y] - Max capacity utilization per timeslice.
        Columns: REGION, TECHNOLOGY, TIMESLICE, YEAR, VALUE
    availability_factor : pd.DataFrame
        AvailabilityFactor[r,t,y] - Annual availability (0-1).
        Columns: REGION, TECHNOLOGY, YEAR, VALUE
    
    Notes
    -----
    - CapacityFactor and AvailabilityFactor should be in range [0, 1]
    - OperationalLife should be positive integer
    """
    operational_life: pd.DataFrame = field(default_factory=_empty_df)
    capacity_to_activity_unit: pd.DataFrame = field(default_factory=_empty_df)
    input_activity_ratio: pd.DataFrame = field(default_factory=_empty_df)
    output_activity_ratio: pd.DataFrame = field(default_factory=_empty_df)
    capacity_factor: pd.DataFrame = field(default_factory=_empty_df)
    availability_factor: pd.DataFrame = field(default_factory=_empty_df)
    
    CSV_MAPPING = {
        'operational_life': 'OperationalLife.csv',
        'capacity_to_activity_unit': 'CapacityToActivityUnit.csv',
        'input_activity_ratio': 'InputActivityRatio.csv',
        'output_activity_ratio': 'OutputActivityRatio.csv',
        'capacity_factor': 'CapacityFactor.csv',
        'availability_factor': 'AvailabilityFactor.csv',
    }
    
    def validate(self, sets: 'OSeMOSYSSets') -> None:
        """
        Validate efficiency and factor references.
        
        Raises
        ------
        ValueError
            If references invalid or factors out of bounds.
        """
        # Validate OperationalLife
        if not self.operational_life.empty:
            techs = set(self.operational_life['TECHNOLOGY'].unique())
            sets.validate_membership(techs, 'technologies', 'in OperationalLife')
            
            if (self.operational_life['VALUE'] <= 0).any():
                raise ValueError("OperationalLife must be positive")
        
        # Validate InputActivityRatio
        if not self.input_activity_ratio.empty:
            techs = set(self.input_activity_ratio['TECHNOLOGY'].unique())
            sets.validate_membership(techs, 'technologies', 'in InputActivityRatio')
            
            fuels = set(self.input_activity_ratio['FUEL'].unique())
            sets.validate_membership(fuels, 'fuels', 'in InputActivityRatio')
            
            modes = set(self.input_activity_ratio['MODE_OF_OPERATION'].unique())
            sets.validate_membership(modes, 'modes', 'in InputActivityRatio')
        
        # Validate OutputActivityRatio
        if not self.output_activity_ratio.empty:
            techs = set(self.output_activity_ratio['TECHNOLOGY'].unique())
            sets.validate_membership(techs, 'technologies', 'in OutputActivityRatio')
            
            fuels = set(self.output_activity_ratio['FUEL'].unique())
            sets.validate_membership(fuels, 'fuels', 'in OutputActivityRatio')
        
        # Validate CapacityFactor bounds
        if not self.capacity_factor.empty:
            vals = self.capacity_factor['VALUE']
            if (vals < 0).any() or (vals > 1).any():
                raise ValueError("CapacityFactor must be in range [0, 1]")
        
        # Validate AvailabilityFactor bounds
        if not self.availability_factor.empty:
            vals = self.availability_factor['VALUE']
            if (vals < 0).any() or (vals > 1).any():
                raise ValueError("AvailabilityFactor must be in range [0, 1]")