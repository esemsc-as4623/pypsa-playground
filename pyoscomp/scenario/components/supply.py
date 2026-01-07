# pyoscomp/scenario/components/supply.py

"""
Supply Component for scenario building in PyPSA-OSeMOSYS Comparison Framework.
Note: this component handles technology / generator definitions and supply-side parameters.
Supply is provided by a TECHNOLOGY in OSeMOSYS terminology, and by a Generator in PyPSA terminology.
"""
import pandas as pd

from .base import ScenarioComponent

class SupplyComponent(ScenarioComponent):
    """
    Supply component for technology / generator definitions and supply-side parameters.
    Handles OSeMOSYS supply parameters: technology metadata, capacity, activity ratios, and operational parameters.

    Prerequisites:
        - Time component must be initialized in the scenario (defines years and timeslices).
        - Topology component (regions, nodes) must be initialized.

    Raises descriptive errors if prerequisites are missing.
    
    Example usage::
        supply = SupplyComponent(scenario_dir)
        supply.load()  # Loads all supply parameter CSVs
        # ... modify DataFrames as needed ...
        supply.process() # Recomputs supply parameter DataFrames
        supply.save()  # Saves all supply parameter DataFrames to CSV
    
    CSV Format Expectations:
        - All CSVs must have columns as specified in each method's docstring.
        - See OSeMOSYS.md for parameter definitions.
    """
    
    def __init__(self, scenario_dir):
        super().__init__(scenario_dir)

        # Check prerequisites
        # TODO: modularize instead of copying from demand.py
        self.years, self.regions = self.check_prerequisites(time=True, topology=True)
        self.time_axis = self.load_time_axis()

        # Supply parameters
        self.capacity_to_activity_unit = pd.DataFrame(columns=["REGION", "TECHNOLOGY", "VALUE"])
        self.residual_capacity = pd.DataFrame(columns=["REGION", "TECHNOLOGY", "YEAR", "VALUE"])
        self.input_activity_ratio = pd.DataFrame(columns=["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR", "VALUE"])
        self.output_activity_ratio = pd.DataFrame(columns=["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR", "VALUE"])
        self.capacity_factor = pd.DataFrame(columns=["REGION", "TECHNOLOGY", "TIMESLICE", "YEAR", "VALUE"])
        self.availability_factor = pd.DataFrame(columns=["REGION", "TECHNOLOGY", "YEAR", "VALUE"])
        self.operational_life = pd.DataFrame(columns=["REGION", "TECHNOLOGY", "VALUE"])

        # Tracking
        self.defined_tech = set()                    # (Region, Technology)
        self.capacity_factor_assignments = {}        # (Region, Technology, Year) -> Profile Assignment
        self.mode_definitions = {}                   # (Region, Technology) -> [Mode1, Mode2, ...]
        self.defined_fuels = set()                   # Set of all fuels referenced in activity ratios

    # === Prerequisite Check ===
    def check_prerequisites(self, **kwargs):
        """
        Check that required components (Time, Topology) are initialized in the scenario.
        Raises an error if any prerequisite is missing.
        """
        # Check Time Component
        years = self.read_csv("YEAR.csv", ["YEAR"])["YEAR"].tolist()
        if not years:
            raise AttributeError("Time component is not defined for this scenario.")

        # Check Topology Component
        regions = self.read_csv("REGION.csv", ["REGION"])["REGION"].tolist()
        if not regions:
            raise AttributeError("Topology component is not defined for this scenario.")
        
        return years, regions
    
    def load_time_axis(self):
        """
        Load temporal resolution data from TimeComponent.
        Returns a DataFrame with TIMESLICE, YEAR, VALUE, Season, DayType, DailyTimeBracket columns.
        Raises an error if TimeComponent cannot be loaded.
        """
        try:
            from pyoscomp.scenario.components.time import TimeComponent
            time_data = TimeComponent.load_time_axis(self)

            df = time_data['yearsplit'].copy()
            slice_map = time_data['slice_map']

            df['Season'] = df['TIMESLICE'].map(lambda x: slice_map[x]['Season'])
            df['DayType'] = df['TIMESLICE'].map(lambda x: slice_map[x]['DayType'])
            df['DailyTimeBracket'] = df['TIMESLICE'].map(lambda x: slice_map[x]['DailyTimeBracket'])
            return df
        except Exception as e:
            raise AttributeError(f"Could not load time axis from TimeComponent: {e}")
    
    # === Load and Save Methods ===
    def load(self):
        """
        Load all supply parameter CSV files into DataFrames.
        Uses read_csv from base class. Updates DataFrames and defined_tech.
        """
        # Capacity to Activity
        df = self.read_csv("CapacityToActivityUnit.csv", ["REGION", "TECHNOLOGY", "VALUE"])
        self.capacity_to_activity_unit = df
        self.defined_tech = set(zip(df['REGION'], df['TECHNOLOGY']))

        # Capacity Factor
        df = self.read_csv("CapacityFactor.csv", ["REGION", "TECHNOLOGY", "TIMESLICE", "YEAR", "VALUE"])
        self.capacity_factor = df

        # Availability Factor
        df = self.read_csv("AvailabilityFactor.csv", ["REGION", "TECHNOLOGY", "YEAR", "VALUE"])
        self.availability_factor = df

        # Operational Life
        df = self.read_csv("OperationalLife.csv", ["REGION", "TECHNOLOGY", "VALUE"])
        self.operational_life = df

        # Residual Capacity
        df = self.read_csv("ResidualCapacity.csv", ["REGION", "TECHNOLOGY", "YEAR", "VALUE"])
        self.residual_capacity = df

        # Input Activity Ratio
        df = self.read_csv("InputActivityRatio.csv", ["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR", "VALUE"])
        self.input_activity_ratio = df

        # Output Activity Ratio
        df = self.read_csv("OutputActivityRatio.csv", ["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR", "VALUE"])
        self.output_activity_ratio = df

    def save(self):
        """
        Save all supply parameter DataFrames to CSV files in the scenario directory.
        Uses write_dataframe from base class.
        """
        # Capacity to Activity
        df = self.capacity_to_activity_unit[["REGION", "TECHNOLOGY", "VALUE"]].sort_values(by=["REGION", "TECHNOLOGY"])
        self.write_dataframe("CapacityToActivityUnit.csv", df)

        # Capacity Factor
        df = self.capacity_factor[["REGION", "TECHNOLOGY", "TIMESLICE", "YEAR", "VALUE"]].sort_values(by=["REGION", "TECHNOLOGY", "TIMESLICE", "YEAR"])
        self.write_dataframe("CapacityFactor.csv", df)

        # Availability Factor
        df = self.availability_factor[["REGION", "TECHNOLOGY", "YEAR", "VALUE"]].sort_values(by=["REGION", "TECHNOLOGY", "YEAR"])
        self.write_dataframe("AvailabilityFactor.csv", df)

        # Operational Life
        df = self.operational_life[["REGION", "TECHNOLOGY", "VALUE"]].sort_values(by=["REGION", "TECHNOLOGY"])
        self.write_dataframe("OperationalLife.csv", df)

        # Residual Capacity
        df = self.residual_capacity[["REGION", "TECHNOLOGY", "YEAR", "VALUE"]].sort_values(by=["REGION", "TECHNOLOGY", "YEAR"])
        self.write_dataframe("ResidualCapacity.csv", df)

        # Input Activity Ratio
        df = self.input_activity_ratio[["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR", "VALUE"]].sort_values(by=["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR"])
        self.write_dataframe("InputActivityRatio.csv", df)

        # Output Activity Ratio
        df = self.output_activity_ratio[["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR", "VALUE"]].sort_values(by=["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR"])
        self.write_dataframe("OutputActivityRatio.csv", df)

    # === User Input Methods ===
    def add_technology(self, region, technology, operational_life, 
                      capacity_to_activity_unit=31.536):
        """
        Register a new technology in the scenario with basic metadata.
        This is the entry point for defining any supply technology.
        
        :param region: str, Region where the technology is located
        :param technology: str, Name/identifier of the technology (e.g., 'COAL_PP', 'WIND_ONSHORE')
        :param operational_life: int, Operational lifetime in years
        :param capacity_to_activity_unit: float, Conversion factor from capacity to activity
                                          Default 31.536 converts GW to PJ/year (GW × 8760 hours × 3.6 MJ/kWh / 1000)
        
        Example::
            supply.add_technology('Region1', 'COAL_PP', operational_life=40, capacity_to_activity_unit=31.536)
            supply.add_technology('Region1', 'WIND_ONSHORE', operational_life=25)
        """
        pass

    def set_conversion_technology(self, region, technology, input_fuel, output_fuel,
                                  efficiency, mode='MODE1', year=None):
        """
        Define a simple conversion technology that converts one fuel to another.
        This is the most common type of technology (power plants, refineries, etc.).
        
        :param region: str, Region where technology operates
        :param technology: str, Technology identifier
        :param input_fuel: str, Input fuel consumed
        :param output_fuel: str, Output fuel produced
        :param efficiency: float or dict, Conversion efficiency (0-1). 
                          Can be float for constant efficiency or dict {year: efficiency} for time-varying
        :param mode: str, Mode of operation identifier (default 'MODE1')
        :param year: int, list[int], or None. If specified, applies only to those years
        
        Example::
            # Gas power plant with 55% efficiency
            supply.set_conversion_technology('Region1', 'GAS_CCGT', 
                                            input_fuel='GAS_NAT', 
                                            output_fuel='ELEC',
                                            efficiency=0.55)
            
            # Efficiency improving over time
            supply.set_conversion_technology('Region1', 'SOLAR_PV',
                                            input_fuel='SOLAR_RESOURCE',
                                            output_fuel='ELEC',
                                            efficiency={2020: 0.18, 2030: 0.22, 2040: 0.25})
        """
        pass

    def set_multimode_technology(self, region, technology, modes_config):
        """
        Define a technology with multiple operating modes (e.g., CHP, fuel-switching, variable efficiency).
        
        :param region: str, Region where technology operates
        :param technology: str, Technology identifier
        :param modes_config: dict, Configuration for each mode
                            {mode_name: {
                                'inputs': {fuel: ratio, ...},
                                'outputs': {fuel: ratio, ...},
                                'years': list or None
                            }}
        
        Example::
            # CHP plant with electricity-only and combined heat-power modes
            supply.set_multimode_technology('Region1', 'GAS_CHP', {
                'MODE1': {  # Electricity only
                    'inputs': {'GAS_NAT': 1.818},   # 55% efficiency
                    'outputs': {'ELEC': 1.0}
                },
                'MODE2': {  # CHP mode
                    'inputs': {'GAS_NAT': 1.25},    # 80% total efficiency
                    'outputs': {'ELEC': 0.5625, 'HEAT_DISTRICT': 0.4375}
                }
            })
            
            # Fuel-switching boiler
            supply.set_multimode_technology('Region1', 'BOILER_FLEX', {
                'MODE_GAS': {
                    'inputs': {'GAS_NAT': 1.11},
                    'outputs': {'HEAT_IND': 1.0}
                },
                'MODE_COAL': {
                    'inputs': {'COAL': 1.25},
                    'outputs': {'HEAT_IND': 1.0}
                }
            })
        """
        pass

    def set_resource_technology(self, region, technology, output_fuel, 
                               resource_availability=None):
        """
        Define a resource extraction/harvesting technology (e.g., renewables, mining).
        These technologies typically have no input fuel, just produce from a resource.
        
        :param region: str, Region where technology operates
        :param technology: str, Technology identifier
        :param output_fuel: str, Fuel produced
        :param resource_availability: float, dict, or None
                                     If float: constant availability factor
                                     If dict: {year: availability} for time-varying
                                     If None: defaults to 1.0 (always available)
        
        Example::
            # Wind turbine - no input fuel, produces electricity
            supply.set_resource_technology('Region1', 'WIND_ONSHORE', 
                                          output_fuel='ELEC',
                                          resource_availability=0.35)
            
            # Hydroelectric with varying availability
            supply.set_resource_technology('Region1', 'HYDRO_ROR',
                                          output_fuel='ELEC',
                                          resource_availability={2020: 0.45, 2030: 0.42, 2040: 0.40})
        """
        pass

    def set_capacity_factor(self, region, technology, year=None,
                           timeslice_factor=None, season_factor=None, 
                           day_factor=None, time_factor=None):
        """
        Set capacity factor profile for a technology across timeslices.
        Capacity factor represents the fraction of installed capacity that can operate.
        Supports direct timeslice factors or hierarchical (season, day, hour) factors.
        
        :param region: str, Region where technology operates
        :param technology: str, Technology identifier
        :param year: int, list[int], or None. If None, applies to all years
        :param timeslice_factor: dict or None, {timeslice: factor} for direct assignment
        :param season_factor: dict or None, {season: factor} for seasonal variation
        :param day_factor: dict or None, {daytype: factor} for weekday/weekend variation
        :param time_factor: dict or None, {dailytimebracket: factor} for time-of-day variation
        
        Example::
            # Solar PV with time-of-day variation
            supply.set_capacity_factor('Region1', 'SOLAR_PV', 
                                      time_factor={'Morning': 0.3, 'Midday': 1.0, 'Evening': 0.2, 'Night': 0.0})
            
            # Wind with seasonal variation
            supply.set_capacity_factor('Region1', 'WIND_OFFSHORE',
                                      season_factor={'Winter': 1.2, 'Spring': 0.9, 'Summer': 0.7, 'Fall': 1.1})
            
            # Combined seasonal and time-of-day
            supply.set_capacity_factor('Region1', 'WIND_ONSHORE',
                                      season_factor={'Winter': 1.1, 'Summer': 0.9},
                                      time_factor={'Day': 1.05, 'Night': 0.95})
        """
        pass

    def set_availability_factor(self, region, technology, availability, year=None):
        """
        Set annual availability factor for a technology (maintenance, forced outages).
        This is different from capacity factor - it represents planned/unplanned downtime.
        
        :param region: str, Region where technology operates
        :param technology: str, Technology identifier
        :param availability: float or dict, Annual availability (0-1)
                            If float: constant across all years
                            If dict: {year: availability} for time-varying
        :param year: int, list[int], or None. Overrides dict specification if provided
        
        Example::
            # Nuclear plant with 90% availability (10% maintenance/outages)
            supply.set_availability_factor('Region1', 'NUCLEAR', availability=0.90)
            
            # Coal plant with improving availability due to better maintenance
            supply.set_availability_factor('Region1', 'COAL_PP',
                                          availability={2020: 0.85, 2030: 0.88, 2040: 0.90})
        """
        pass

    def set_residual_capacity(self, region, technology, capacity_trajectory,
                            interpolation='step', retirement_profile=None):
        """
        Define existing/legacy capacity for a technology (capacity built before model start).
        
        :param region: str, Region where capacity exists
        :param technology: str, Technology identifier
        :param capacity_trajectory: dict, {year: capacity_MW/GW} known capacity points
        :param interpolation: str, 'step', 'linear', or 'retire' for interpolation between points
        :param retirement_profile: dict or None, {year: retirement_rate} for gradual retirement
                                  If None, capacity follows trajectory exactly
        
        Example::
            # Existing coal capacity being phased out
            supply.set_residual_capacity('Region1', 'COAL_OLD',
                                        capacity_trajectory={2020: 15, 2030: 8, 2040: 2, 2050: 0},
                                        interpolation='linear')
            
            # Nuclear fleet with scheduled retirements
            supply.set_residual_capacity('Region1', 'NUCLEAR_GEN2',
                                        capacity_trajectory={2020: 10, 2030: 10, 2040: 5},
                                        retirement_profile={2035: 0.5})  # 50% retire in 2035
        """
        pass

    def set_emission_activity(self, region, technology, emission, rate, 
                             mode='MODE1', year=None):
        """
        Define emission rate per unit of activity for a technology.
        
        :param region: str, Region where technology operates
        :param technology: str, Technology identifier
        :param emission: str, Emission type (e.g., 'CO2', 'NOx', 'SOx')
        :param rate: float or dict, Emission per unit activity (e.g., tCO2/PJ)
                    If float: constant emission rate
                    If dict: {year: rate} for time-varying rates
        :param mode: str, Mode of operation (default 'MODE1')
        :param year: int, list[int], or None. Overrides dict if specified
        
        Example::
            # Coal plant CO2 emissions
            supply.set_emission_activity('Region1', 'COAL_PP', 'CO2', rate=94.6)  # tCO2/TJ
            
            # Gas plant with improving emissions (CCS retrofit)
            supply.set_emission_activity('Region1', 'GAS_CCGT_CCS', 'CO2',
                                        rate={2020: 56.1, 2030: 11.2, 2040: 5.6})
        """
        pass

    def add_storage_linkage(self, region, technology, storage, mode='MODE1'):
        """
        Link a technology to a storage system (for charging/discharging).
        
        :param region: str, Region where linkage exists
        :param technology: str, Technology identifier (e.g., 'BATTERY_CHARGER', 'BATTERY_DISCHARGER')
        :param storage: str, Storage system identifier
        :param mode: str, Mode of operation
        
        Example::
            supply.add_storage_linkage('Region1', 'BATTERY_CHARGE', 'BATTERY_STORAGE')
            supply.add_storage_linkage('Region1', 'BATTERY_DISCHARGE', 'BATTERY_STORAGE')
        """
        pass

    def set_operating_constraints(self, region, technology, 
                                  min_utilization=None, ramp_rate=None,
                                  must_run=False):
        """
        Define operational constraints for a technology.
        
        :param region: str, Region where technology operates
        :param technology: str, Technology identifier
        :param min_utilization: float or None, Minimum capacity utilization when operating (0-1)
        :param ramp_rate: float or None, Maximum ramp rate per hour (fraction of capacity)
        :param must_run: bool, Whether technology must run in all timeslices
        
        Note: These map to TotalTechnologyAnnualActivityLowerLimit and related OSeMOSYS parameters.
        
        Example::
            # Nuclear must run at minimum 80% capacity
            supply.set_operating_constraints('Region1', 'NUCLEAR', 
                                            min_utilization=0.80, must_run=True)
            
            # Gas turbine with ramping limits
            supply.set_operating_constraints('Region1', 'GAS_OCGT',
                                            ramp_rate=0.50)  # 50% per hour
        """
        pass

    def copy_technology(self, source_region, source_technology, 
                       target_region, target_technology, scale_factor=1.0):
        """
        Copy all parameters from one technology to another (useful for similar technologies).
        
        :param source_region: str, Region of source technology
        :param source_technology: str, Source technology identifier
        :param target_region: str, Region for new technology
        :param target_technology: str, New technology identifier
        :param scale_factor: float, Scaling factor for all parameters (default 1.0)
        
        Example::
            # Create similar wind technology in another region
            supply.copy_technology('Region1', 'WIND_ONSHORE', 'Region2', 'WIND_ONSHORE')
            
            # Create upgraded version with 10% better efficiency
            supply.copy_technology('Region1', 'SOLAR_PV_2020', 'Region1', 'SOLAR_PV_2030',
                                  scale_factor=1.10)
        """
        pass

    # === Processing ===
    def process(self, **kwargs):
        """
        Generate and update all supply parameter DataFrames based on user-defined configurations.
        This method:
        1. Processes capacity factor assignments into full timeslice profiles
        2. Normalizes profiles where needed
        3. Validates consistency between parameters
        4. Updates all DataFrames for CSV output
        
        Should be called after all user input methods and before save().
        """
        pass

    # === Internal Logic Helpers ===
    def _validate_technology_exists(self, region, technology):
        """
        Check if technology has been registered via add_technology().
        Raises descriptive error if not found.
        """
        pass

    def _validate_fuel_exists(self, fuel):
        """
        Check if fuel has been defined (either in topology or via activity ratios).
        Raises descriptive error if fuel is unknown.
        """
        pass

    def _apply_efficiency_to_ratios(self, efficiency, mode='MODE1'):
        """
        Convert efficiency value to input/output activity ratios.
        For a technology with efficiency η:
        - Input ratio = 1/η (amount of input needed per unit output)
        - Output ratio = 1.0 (normalized)
        
        :param efficiency: float, Conversion efficiency (0-1)
        :param mode: str, Mode identifier
        :return: tuple (input_ratio, output_ratio)
        """
        pass

    def _interpolate_capacity_trajectory(self, trajectory, years, method='step'):
        """
        Interpolate capacity values for all model years based on known points.
        
        :param trajectory: dict, {year: value} known points
        :param years: list, All model years
        :param method: str, 'step', 'linear', or 'retire'
        :return: dict, {year: value} for all years
        """
        pass

    def _apply_capacity_factor_hierarchical(self, season_factor, day_factor, time_factor, year):
        """
        Apply hierarchical factors (season/day/time) to generate timeslice-specific capacity factors.
        Similar logic to demand profile generation but for capacity availability.
        
        :param season_factor: dict or None
        :param day_factor: dict or None
        :param time_factor: dict or None
        :param year: int
        :return: dict, {timeslice: capacity_factor}
        """
        pass

    def _apply_capacity_factor_timeslice(self, timeslice_factor, year):
        """
        Apply direct timeslice capacity factors.
        
        :param timeslice_factor: dict, {timeslice: factor}
        :param year: int
        :return: dict, {timeslice: capacity_factor}
        """
        pass

    def _generate_capacity_factor_profile(self, region, technology, year, assignment):
        """
        Generate capacity factor rows for a specific (region, technology, year).
        Returns list of dicts with keys: REGION, TECHNOLOGY, TIMESLICE, YEAR, VALUE.
        """
        pass

    def _validate_mode_configuration(self, modes_config):
        """
        Validate that multi-mode configuration is properly structured.
        Checks:
        - All modes have 'inputs' and 'outputs'
        - Ratios are positive
        - At least one output fuel is specified
        """
        pass

    def _expand_year_specification(self, year):
        """
        Convert year specification to list of years.
        - If None: returns all model years
        - If int: returns [year]
        - If list: returns list as-is
        Validates all years are in model year range.
        """
        pass

    def _merge_activity_ratios(self, existing_df, new_records):
        """
        Merge new activity ratio records into existing DataFrame.
        Handles duplicates by overwriting with new values.
        """
        pass

    def _compute_mode_activity_distribution(self, region, technology, modes):
        """
        Helper to track which modes are defined for a technology.
        Used during process() to ensure all mode-specific parameters are consistent.
        """
        pass

    def _validate_activity_ratio_consistency(self):
        """
        Validate that input and output activity ratios are consistent:
        - Every technology has at least one output
        - Technologies with inputs also have outputs (except demand/sink technologies)
        - Modes are consistently defined across input/output ratios
        """
        pass

    def _normalize_capacity_factors(self, capacity_factor_rows):
        """
        Ensure capacity factors are between 0 and 1.
        Log warnings for any suspicious values.
        """
        pass

    def _get_technology_summary(self, region, technology):
        """
        Generate a summary dict of all parameters for a technology.
        Useful for debugging and validation.
        
        :return: dict with keys for each parameter type
        """
        pass

    def _apply_retirement_profile(self, capacity_trajectory, retirement_profile, years):
        """
        Apply retirement profile to capacity trajectory.
        Retirement profile specifies years where capacity is retired.
        
        :param capacity_trajectory: dict, {year: capacity}
        :param retirement_profile: dict, {year: retirement_fraction}
        :param years: list, All model years
        :return: dict, {year: adjusted_capacity}
        """
        pass
    
    # === Visualization ===
    def visualize_capacity_mix(self, region, year=None, by_fuel=False, ax=None):
        """
        Visualize the technology capacity mix for a region.
        Can show either technology breakdown or group by output fuel.
        
        :param region: str, Region to visualize
        :param year: int, list[int], or None. Specific year(s) or all years if None
        :param by_fuel: bool, If True groups technologies by primary output fuel
        :param ax: matplotlib axis object or None
        
        Creates a stacked bar chart showing capacity composition over time.
        """
        pass

    def visualize_generation_profile(self, region, technology=None, year=None, ax=None):
        """
        Visualize generation/activity profile across timeslices for technologies.
        Shows how capacity factors and availability affect generation patterns.
        
        :param region: str, Region to visualize
        :param technology: str or None. Specific technology or all if None
        :param year: int or None. Specific year or latest if None
        :param ax: matplotlib axis object or None
        
        Creates visualization showing:
        - Installed capacity
        - Available capacity (after availability factor)
        - Actual generation potential (after capacity factor)
        """
        pass

    def visualize_conversion_efficiency(self, region, technologies=None, ax=None):
        """
        Visualize conversion efficiencies for technologies over time.
        Useful for comparing technology performance and efficiency improvements.
        
        :param region: str, Region to visualize
        :param technologies: list[str] or None. Technologies to compare
        :param ax: matplotlib axis object or None
        
        Creates line plot showing efficiency trends.
        """
        pass

    def visualize_fuel_balance(self, region, fuel, year, ax=None):
        """
        Visualize supply-side fuel balance for a specific fuel across timeslices.
        Shows which technologies are producing/consuming the fuel.
        
        :param region: str, Region to visualize
        :param fuel: str, Fuel to analyze
        :param year: int, Year to visualize
        :param ax: matplotlib axis object or None
        
        Creates stacked area plot showing:
        - Production by technology
        - Consumption by technology
        - Net balance
        """
        pass

    def visualize_all(self, output_dir=None):
        """
        Create comprehensive visualization suite for all regions and technologies.
        Generates multiple plots and optionally saves to output directory.
        
        :param output_dir: str or None. Directory to save plots. If None, displays interactively.
        
        Generates:
        - Capacity mix by region
        - Generation profiles by technology type
        - Efficiency comparisons
        - Fuel balance diagrams
        """
        pass