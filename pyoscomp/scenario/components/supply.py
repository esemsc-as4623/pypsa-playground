# pyoscomp/scenario/components/supply.py

"""
Supply Component for scenario building in PyPSA-OSeMOSYS Comparison Framework.
Note: this component handles technology / generator definitions and supply-side parameters.
Supply is provided by a TECHNOLOGY in OSeMOSYS terminology, and by a Generator in PyPSA terminology.
"""
import pandas as pd
import numpy as np

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
        years = self.read_csv("YEAR.csv", ["VALUE"])["VALUE"].tolist()
        if not years:
            raise AttributeError("Time component is not defined for this scenario.")

        # Check Topology Component
        regions = self.read_csv("REGION.csv", ["VALUE"])["VALUE"].tolist()
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
    def add_technology(self, region, technology, operational_life: int, 
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
        if region not in self.regions:
            raise ValueError(f"Region '{region}' not defined in scenario. Set topology first.")
        self.defined_tech.add((region, technology))

        # --- VALIDATION: Operational Life Provided, Non-negative ---
        if operational_life <= 0:
            raise ValueError(f"Operational life cannot be negative for technology '{technology}' in region '{region}'.")
        
        record1 = [{"REGION": region, "TECHNOLOGY": technology, "VALUE": operational_life}]
        record2 = [{"REGION": region, "TECHNOLOGY": technology, "VALUE": capacity_to_activity_unit}]
        
        self.operational_life = self.add_to_dataframe(
            self.operational_life, record1, key_columns=["REGION", "TECHNOLOGY"]
        )
        self.capacity_to_activity_unit = self.add_to_dataframe(
            self.capacity_to_activity_unit, record2, key_columns=["REGION", "TECHNOLOGY"]
        )
    
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
        # --- VALIDATION: Region, Technology, Year, Fuel, Efficiency ---
        if region not in self.regions:
            raise ValueError(f"Region '{region}' not defined in scenario. Set topology first.")
        if (region, technology) not in self.defined_tech:
            raise ValueError(f"Technology '{technology}' not registered in region '{region}'. Call add_technology() first.")
        self.defined_tech.add((region, technology))
        if isinstance(year, int) and year not in self.years:
            raise ValueError(f"Year {year} not defined in scenario years.")
        if isinstance(year, list) and not all(y in self.years for y in year):
            raise ValueError(f"One or more years in {year} not defined in scenario years.")
        if input_fuel == output_fuel:
            raise ValueError("Input and output fuel must be different.")
        if isinstance(efficiency, dict):
            for y, val in efficiency.items():
                if not (0 < val <= 1):
                    raise ValueError(f"Efficiency for year {y} must be in (0, 1].")
        else:
            if not (0 < efficiency <= 1):
                raise ValueError("Efficiency must be in (0, 1].")
        
        if isinstance(year, int):
            years = [year]
        if isinstance(year, list):
            years = year
        if year is None:
            years = self.years
        
        # Map year to efficiency
        # Implicitly uses step interpolation
        if isinstance(efficiency, dict):
            eff_years = sorted(efficiency.keys())
            eff_map = {}
            for y in self.years:
                prev_years = [ey for ey in eff_years if ey <= y]
                if prev_years:
                    last_year = max(prev_years)
                    eff_map[y] = efficiency[last_year]
                else:
                    first_year = min(eff_years)
                    eff_map[y] = efficiency[first_year]
        else:
            eff_map = {y: efficiency for y in self.years}
        
        # Compute input/output activity ratios
        input_records, output_records = [], []
        for y in years:
            eff = eff_map[y]
            input_ratio, output_ratio = self._apply_efficiency_to_ratios(eff, mode=mode)
            input_records.append({
                "REGION": region, "TECHNOLOGY": technology, "FUEL": input_fuel, 
                "MODE_OF_OPERATION": mode, "YEAR": y, "VALUE": input_ratio})
            output_records.append({
                "REGION": region, "TECHNOLOGY": technology, "FUEL": output_fuel, 
                "MODE_OF_OPERATION": mode, "YEAR": y, "VALUE": output_ratio})
        
        self.input_activity_ratio = self.add_to_dataframe(self.input_activity_ratio, input_records,
                                                          key_columns=["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR"])
        self.output_activity_ratio = self.add_to_dataframe(self.output_activity_ratio, output_records,
                                                           key_columns=["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR"])
        self.defined_fuels.add(input_fuel)
        self.defined_fuels.add(output_fuel)

        if (region, technology) not in self.mode_definitions:
            self.mode_definitions[(region, technology)] = []
        if mode not in self.mode_definitions[(region, technology)]:
            self.mode_definitions[(region, technology)].append(mode)

    def set_multimode_technology(self, region, technology, modes_config):
        """
        Define a technology with multiple operating modes (e.g., CHP, fuel-switching, variable efficiency).
        
        :param region: str, Region where technology operates
        :param technology: str, Technology identifier
        :param modes_config: dict, Configuration for each mode
                            {mode_name: {
                                'inputs': {fuel: ratio, ...},
                                'outputs': {fuel: ratio, ...},
                                'years': list or None  # Optional: apply only to specific years
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
            
            # Technology with mode available only in later years
            supply.set_multimode_technology('Region1', 'FLEX_TECH', {
                'MODE_OLD': {
                    'inputs': {'FUEL_A': 1.5},
                    'outputs': {'ELEC': 1.0},
                    'years': [2020, 2025, 2030]  # Only available in these years
                },
                'MODE_NEW': {
                    'inputs': {'FUEL_B': 1.2},
                    'outputs': {'ELEC': 1.0},
                    'years': [2030, 2035, 2040]  # New mode from 2030
                }
            })
        """
        # --- VALIDATION: Region, Technology, Mode ---
        if region not in self.regions:
            raise ValueError(f"Region '{region}' not defined in scenario. Set topology first.")
        if (region, technology) not in self.defined_tech:
            raise ValueError(f"Technology '{technology}' not registered in region '{region}'. Call add_technology() first.")
        self._validate_mode_configuration(modes_config)

        if (region, technology) not in self.mode_definitions:
            self.mode_definitions[(region, technology)] = []
        
        input_records, output_records = [], []

        for mode, config in modes_config.items():
            if mode not in self.mode_definitions[(region, technology)]:
                self.mode_definitions[(region, technology)].append(mode)
            
            inputs = config.get('inputs', {})
            outputs = config.get('outputs', {})
            mode_years = config.get('years', None)
            
            # Determine which years this mode applies to
            if mode_years is None:
                years_to_apply = self.years
            else:
                # Validate years
                if not all(y in self.years for y in mode_years):
                    invalid = [y for y in mode_years if y not in self.years]
                    raise ValueError(f"Mode '{mode}' specifies invalid years: {invalid}. Valid years: {self.years}")
                years_to_apply = mode_years
            
            # Create records for each year
            for y in years_to_apply:
                # Input ratios
                for fuel, ratio in inputs.items():
                    input_records.append({
                        "REGION": region, "TECHNOLOGY": technology, "FUEL": fuel, 
                        "MODE_OF_OPERATION": mode, "YEAR": y, "VALUE": ratio
                    })
                    self.defined_fuels.add(fuel)
                
                # Output ratios
                for fuel, ratio in outputs.items():
                    output_records.append({
                        "REGION": region, "TECHNOLOGY": technology, "FUEL": fuel, 
                        "MODE_OF_OPERATION": mode, "YEAR": y, "VALUE": ratio
                    })
                    self.defined_fuels.add(fuel)
        
        self.input_activity_ratio = self.add_to_dataframe(
            self.input_activity_ratio, input_records,
            key_columns=["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR"]
        )
        self.output_activity_ratio = self.add_to_dataframe(
            self.output_activity_ratio, output_records,
            key_columns=["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR"]
        )

    def set_resource_technology(self, region, technology, output_fuel):
        """
        Define a resource extraction/harvesting technology (e.g., renewables, mining).
        These technologies typically have no input fuel, just produce from a resource.
        
        :param region: str, Region where technology operates
        :param technology: str, Technology identifier
        :param output_fuel: str, Fuel produced
        
        Example::
            # Define wind onshore resource technology
            supply.set_resource_technology('Region1', 'WIND_ONSHORE', output_fuel='ELEC')
        """
        # --- VALIDATION: Region, Technology, Mode ---
        if region not in self.regions:
            raise ValueError(f"Region '{region}' not defined in scenario. Set topology first.")
        if (region, technology) not in self.defined_tech:
            raise ValueError(f"Technology '{technology}' not registered in region '{region}'. Call add_technology() first.")
        self.defined_fuels.add(output_fuel)
        if (region, technology) not in self.mode_definitions:
            self.mode_definitions[(region, technology)] = ['MODE1']
        elif 'MODE1' not in self.mode_definitions[(region, technology)]:
            self.mode_definitions[(region, technology)].append('MODE1')
        
        # Output activity ratios always 1.0 for resource technologies
        output_records = []
        for y in self.years:
            output_records.append({
                "REGION": region, "TECHNOLOGY": technology, 
                "FUEL": output_fuel, "MODE_OF_OPERATION": 'MODE1', 
                "YEAR": y, "VALUE": 1.0
            })
        self.output_activity_ratio = self.add_to_dataframe(
            self.output_activity_ratio, output_records,
            key_columns=["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR"]
        )

    def set_capacity_factor(self, region, technology, year=None,
                            timeslice_factor=None, season_factor=None, 
                            day_factor=None, time_factor=None):
        """
        Set capacity factor profile for a technology across timeslices.
        Capacity factor represents the fraction of installed capacity that can operate.
        Supports direct timeslice factors or hierarchical (season, day, time) factors.
        Factor dictionaries should map timeslice/season/daytype/dailytimebracket names to their respective factors.
        If both timeslice factors and hierarchical factors are provided, timeslice factors take precedence.
        If multiple factor dictionaries are provided, hierarchical weighting is used.
        Missing entries default to 1.0, i.e. no adjustment.

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
        # --- VALIDATION: Region, Technology, Year ---
        if region not in self.regions:
            raise ValueError(f"Region '{region}' not defined in scenario. Set topology first.")
        if (region, technology) not in self.defined_tech:
            raise ValueError(f"Technology '{technology}' not registered in region '{region}'. Call add_technology() first.")
        self.defined_tech.add((region, technology))
        if isinstance(year, int) and year not in self.years:
            raise ValueError(f"Year {year} not defined in scenario years.")
        if isinstance(year, list) and not all(y in self.years for y in year):
            raise ValueError(f"One or more years in {year} not defined in scenario years.")
        
        # Determine which years to apply to
        if isinstance(year, int):
            years = [year]
        elif isinstance(year, list):
            years = year
        else:
            years = self.years  # Apply to ALL years, not just first
        
        # Create comprehensive timeslice factor dict ONCE (efficiency optimization)
        if timeslice_factor is not None:
            cf_dict = self._apply_timeslice_factors(timeslice_factor, default=1.0)
        elif any(f is not None for f in [season_factor, day_factor, time_factor]):
            cf_dict = self._apply_hierarchical_factors(
                season_factor or {}, day_factor or {}, time_factor or {}, default=1.0
            )
        else:
            cf_dict = self._apply_timeslice_factors({}, default=1.0)
        
        # Apply to all specified years
        for y in years:
            self.capacity_factor_assignments[(region, technology, y)] = {
                "type": "custom", "weights": cf_dict
            }

    def set_availability_factor(self, region, technology, availability):
        """
        Set annual availability factor for a technology (maintenance, forced outages).
        This is different from capacity factor - it represents planned/unplanned downtime.
        
        :param region: str, Region where technology operates
        :param technology: str, Technology identifier
        :param availability: float or dict, Annual availability (0-1)
                            If float: constant across all years
                            If dict: {year: availability} for time-varying
        
        Example::
            # Nuclear plant with 90% availability (10% maintenance/outages)
            supply.set_availability_factor('Region1', 'NUCLEAR', availability=0.90)
            
            # Coal plant with improving availability due to better maintenance
            supply.set_availability_factor('Region1', 'COAL_PP',
                                           availability={2020: 0.85, 2030: 0.88, 2040: 0.90})
        """
        # --- VALIDATION: Region, Technology, Year, Availability ---
        if region not in self.regions:
            raise ValueError(f"Region '{region}' not defined in scenario. Set topology first.")
        if (region, technology) not in self.defined_tech:
            raise ValueError(f"Technology '{technology}' not registered in region '{region}'. Call add_technology() first.")
        self.defined_tech.add((region, technology))
        if isinstance(availability, dict):
            for y, val in availability.items():
                if not (0 <= val <= 1):
                    raise ValueError(f"Resource availability for year {y} must be in [0, 1].")
        elif isinstance(availability, (int, float)):
            if not (0 <= availability <= 1):
                raise ValueError("Resource availability must be in [0, 1].")

        # Map year to availability factor
        # Implicitly uses step interpolation
        if isinstance(availability, dict):
            avail_years = sorted(availability.keys())
            avail_map = {}
            for y in self.years:
                prev_years = [ay for ay in avail_years if ay <= y]
                if prev_years:
                    last_year = max(prev_years)
                    avail_map[y] = availability[last_year]
                else:
                    first_year = min(avail_years)
                    avail_map[y] = availability[first_year]
        else:
            avail_map = {y: availability for y in self.years}

        # Availability factor
        records = []
        for y in self.years:
            records.append({"REGION": region, "TECHNOLOGY": technology, "YEAR": y, "VALUE": avail_map[y]})
        self.availability_factor = self.add_to_dataframe(self.availability_factor, records,
                                                            key_columns=["REGION", "TECHNOLOGY", "YEAR"])
        
    def set_residual_capacity(self, region, technology, capacity_trajectory: dict,
                              interpolation='step'):
        """
        Define existing/legacy capacity for a given region and technology (capacity built before model start) over specified model years.
        
        :param region: str, Region where capacity exists
        :param technology: str, Technology identifier
        :param capacity_trajectory: dict, {year: capacity_MW/GW} known capacity points
        :param interpolation: str, 'step' or 'linear', for interpolation between points
        
        Example::
            # Existing coal capacity being phased out
            supply.set_residual_capacity('Region1', 'COAL_OLD',
                                         capacity_trajectory={2020: 15, 2030: 8, 2040: 2, 2050: 0},
                                         interpolation='linear')
            
            # Nuclear fleet with scheduled retirements
            supply.set_residual_capacity('Region1', 'NUCLEAR_GEN2',
                                         capacity_trajectory={2020: 10, 2030: 10, 2040: 5},
                                         interpolation='step')
        """
        # --- VALIDATION: Region, Technology, Trajectory, Interpolation ---
        if region not in self.regions:
            raise ValueError(f"Region '{region}' not defined in scenario. Set topology first.")
        if (region, technology) not in self.defined_tech:
            raise ValueError(f"Technology '{technology}' not registered in region '{region}'. Call add_technology() first.")
        self.defined_tech.add((region, technology))
        if len(capacity_trajectory) == 0:
            raise ValueError(f"No capacity trajectory points provided for {region}-{technology}.")
        for y, val in capacity_trajectory.items():
            if val < 0:
                raise ValueError(f"Residual capacity cannot be negative. Found {val} in model year {y} for {region}-{technology}.")
        if interpolation not in ['step', 'linear']:
            print(f"Interpolation method '{interpolation}' for {region}-{technology} not recognized. Using 'step' instead.")
            interpolation = 'step'

        records = []
        sorted_years = sorted(capacity_trajectory.keys())
        # Preceding Years
        first_yr = sorted_years[0]
        first_val = capacity_trajectory[first_yr]
        preceding_years = [y for y in self.years if y < first_yr]
        for y in preceding_years:
            records.append({
                "REGION": region, "TECHNOLOGY": technology, "YEAR": y, "VALUE": first_val
            })
        
        # Interpolate
        sorted_years = sorted(capacity_trajectory.keys())
        for i in range(len(sorted_years) - 1):
            y_start, y_end = sorted_years[i], sorted_years[i+1]
            years_to_fill = [y for y in self.years if y_start <= y < y_end]
            val_start, val_end = capacity_trajectory[y_start], capacity_trajectory[y_end]
            
            if interpolation == 'linear':
                values = np.linspace(val_start, val_end, len(years_to_fill) + 1)[:-1]
            else: # Step
                values = [val_start] * len(years_to_fill)

            for y, val in zip(years_to_fill, values):
                records.append({
                    "REGION": region, "TECHNOLOGY": technology, "YEAR": y, "VALUE": val
                })
        
        # Final Point
        last_yr = sorted_years[-1]
        last_val = capacity_trajectory[last_yr]
        if last_yr in self.years:
            records.append({
                "REGION": region, "TECHNOLOGY": technology, "YEAR": last_yr, "VALUE": last_val
            })

        # Extrapolate if needed
        remaining_years = [y for y in self.years if y > last_yr]
        if remaining_years:
            extrap_values = []
            if interpolation == 'step':
                extrap_values = [last_val] * len(remaining_years)
            elif len(sorted_years) >= 2:
                prev_yr = sorted_years[-2]
                prev_val = capacity_trajectory[prev_yr]
                y_diff = last_yr - prev_yr

                if interpolation == 'linear':
                    slope = (last_val - prev_val) / y_diff
                    extrap_values = [last_val + slope * (y - last_yr) for y in remaining_years]
            else: # Step
                extrap_values = [last_val] * len(remaining_years)

            for y, val in zip(remaining_years, extrap_values):
                # Validate extrapolation didn't go negative
                if val < 0:
                    val = 0
                records.append({
                    "REGION": region, "TECHNOLOGY": technology, "YEAR": y, "VALUE": val
                })

        self.residual_capacity = self.add_to_dataframe(self.residual_capacity, records,
                                                       key_columns=["REGION", "TECHNOLOGY", "YEAR"])
            
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
    def process(self):
        """
        Generate and update all supply parameter DataFrames based on user-defined configurations.
        This method:
        0. Validates consistency of activity ratios
        1. Processes capacity factor assignments into full timeslice profiles
        2. Ensures all defined region-technology-year combinations have capacity factors
        3. Ensures all defined region-technology-year combinations have availability factors
        4. Updates all DataFrames for CSV output
        
        Should be called after all user input methods and before save().
        """
        self._validate_activity_ratio_consistency()

        # Generate capacity factor profiles
        all_cf_rows = []
        for (region, technology, year), assignment in self.capacity_factor_assignments.items():
            for ts, value in assignment["weights"].items():
                all_cf_rows.append({
                    "REGION": region, "TECHNOLOGY": technology, "TIMESLICE": ts, "YEAR": year, "VALUE": value
                })
        
        # Ensure all technologies have capacity factors (default to 1.0)
        for region, technology in self.defined_tech:
            for year in self.years:
                if (region, technology, year) not in self.capacity_factor_assignments:
                    for ts in self.time_axis["TIMESLICE"].unique():
                        all_cf_rows.append({
                            "REGION": region, "TECHNOLOGY": technology, "TIMESLICE": ts, "YEAR": year, "VALUE": 1.0
                        })
        self.capacity_factor = self.add_to_dataframe(self.capacity_factor, all_cf_rows,
                                                     key_columns=["REGION", "TECHNOLOGY", "TIMESLICE", "YEAR"])
        
        # Ensure all technologies have availability factors (default to 1.0)
        all_af_rows = []
        for region, technology in self.defined_tech:
            for year in self.years:
                if not ((self.availability_factor["REGION"] == region) & 
                    (self.availability_factor["TECHNOLOGY"] == technology) & 
                    (self.availability_factor["YEAR"] == year)).any():
                    all_af_rows.append({
                        "REGION": region, "TECHNOLOGY": technology, "YEAR": year, "VALUE": 1.0
                    })
        self.availability_factor = self.add_to_dataframe(self.availability_factor, all_af_rows,
                                                         key_columns=["REGION", "TECHNOLOGY", "YEAR"])

    # === Internal Logic Helpers ===
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
        if not (0 < efficiency <= 1):
            raise ValueError(f"Efficiency must be in (0, 1], got {efficiency}.")
        input_ratio = 1.0 / efficiency
        output_ratio = 1.0
        return input_ratio, output_ratio
    
    def _apply_timeslice_factors(self, factor_dict, default=1.0):
        """
        Applies timeslice factors.
        If a timeslice is missing in factor_dict, it uses the default.
        If a timeslice is present, it uses the provided factor.
        Returns a complete dict of timeslice factors.
        """
        result = {}
        for ts in self.time_axis["TIMESLICE"]:
            val = factor_dict.get(ts, default)
            if not 0 <= val <= 1:
                raise ValueError(f"Capacity factor for timeslice '{ts}' must be in [0,1], got {val}.")
            result[ts] = val
        return result
    
    def _apply_hierarchical_factors(self, season_factor, day_factor, time_factor, default=1.0):
        """
        Applies hierarchical factors to generate timeslice factors.
        If a season/day/time is missing in the respective factor dict, it uses the default.
        If a season/day/time is present, it uses the provided factor.
        Returns a complete dict of timeslice factors.
        """
        # Compute adjusted factors for each dimension
        s_adj = {season: season_factor.get(season, default) for season in self.time_axis["Season"].unique()}
        d_adj = {day: day_factor.get(day, default) for day in self.time_axis["DayType"].unique()}
        t_adj = {time: time_factor.get(time, default) for time in self.time_axis["DailyTimeBracket"].unique()}
        
        result = {}
        for _, ts_row in self.time_axis.iterrows():
            ts = ts_row["TIMESLICE"]
            s, d, t = ts_row["Season"], ts_row["DayType"], ts_row["DailyTimeBracket"]
            val = s_adj[s] * d_adj[d] * t_adj[t]

            # Clamp to [0,1]
            val = max(0.0, min(1.0, val))
            result[ts] = val
        return result

    def _validate_mode_configuration(self, modes_config):
        """
        Validate that multi-mode configuration is properly structured.
        Checks:
        - All modes have 'inputs' and 'outputs'
        - Ratios are positive
        - At least one output fuel is specified
        """
        if not isinstance(modes_config, dict):
            raise ValueError("modes_config must be a dictionary of mode configurations.")
        for mode, config in modes_config.items():
            if not isinstance(config, dict):
                raise ValueError(f"Configuration for mode '{mode}' must be a dictionary.")
            if 'inputs' not in config or 'outputs' not in config:
                raise ValueError(f"Mode '{mode}' must have both 'inputs' and 'outputs' keys.")
            if not isinstance(config['inputs'], dict) or not isinstance(config['outputs'], dict):
                raise ValueError(f"'inputs' and 'outputs' for mode '{mode}' must be dictionaries.")
            # At least one output fuel
            if not config['outputs']:
                raise ValueError(f"Mode '{mode}' must specify at least one output fuel.")
            # All ratios must be positive
            for fuel, ratio in list(config['inputs'].items()) + list(config['outputs'].items()):
                if not (isinstance(ratio, (int, float)) and ratio > 0):
                    raise ValueError(f"Ratio for fuel '{fuel}' in mode '{mode}' must be a positive number.")

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
        
        Raises ValueError if inconsistencies found.
        Should be called in process() before saving.
        """
        errors = []
        
        # Check 1: Every technology must have at least one output
        if self.output_activity_ratio.empty:
            errors.append("No output activity ratios defined for any technology.")
            raise ValueError("\n".join(errors))
        
        techs_with_outputs = set(
            zip(self.output_activity_ratio['REGION'], 
                self.output_activity_ratio['TECHNOLOGY'])
        )
        
        for region, technology in self.defined_tech:
            if (region, technology) not in techs_with_outputs:
                errors.append(
                    f"Technology '{technology}' in region '{region}' has no output activity ratios defined."
                )
        
        # Check 2: Every input mode must have corresponding outputs
        if not self.input_activity_ratio.empty:
            for region, technology in self.defined_tech:
                input_modes = self.input_activity_ratio[
                    (self.input_activity_ratio['REGION'] == region) & 
                    (self.input_activity_ratio['TECHNOLOGY'] == technology)
                ]['MODE_OF_OPERATION'].unique()
                
                output_modes = self.output_activity_ratio[
                    (self.output_activity_ratio['REGION'] == region) & 
                    (self.output_activity_ratio['TECHNOLOGY'] == technology)
                ]['MODE_OF_OPERATION'].unique()
                
                # Every input mode must have outputs
                for mode in input_modes:
                    if mode not in output_modes:
                        errors.append(
                            f"Technology '{technology}' in region '{region}' has mode '{mode}' "
                            f"with inputs but no outputs."
                        )
        
        # Check 3: Validate ratio values are positive
        if not self.input_activity_ratio.empty and (self.input_activity_ratio['VALUE'] <= 0).any():
            negative_inputs = self.input_activity_ratio[self.input_activity_ratio['VALUE'] <= 0]
            for _, row in negative_inputs.iterrows():
                errors.append(
                    f"Non-positive input activity ratio: {row['TECHNOLOGY']} in {row['REGION']}, "
                    f"fuel {row['FUEL']}, mode {row['MODE_OF_OPERATION']}, year {row['YEAR']}: {row['VALUE']}"
                )
        
        if not self.output_activity_ratio.empty and (self.output_activity_ratio['VALUE'] <= 0).any():
            negative_outputs = self.output_activity_ratio[self.output_activity_ratio['VALUE'] <= 0]
            for _, row in negative_outputs.iterrows():
                errors.append(
                    f"Non-positive output activity ratio: {row['TECHNOLOGY']} in {row['REGION']}, "
                    f"fuel {row['FUEL']}, mode {row['MODE_OF_OPERATION']}, year {row['YEAR']}: {row['VALUE']}"
                )
        
        # Raise aggregated errors
        if errors:
            error_msg = "Activity ratio consistency validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            raise ValueError(error_msg)
        
        return True
    
    # === Visualization ===
    def visualize_technologies(self):
        pass
        
    def visualize_capacity_mix(self):
        """
        Visualize the technology capacity mix for all regions.
        Creates a stacked bar chart showing capacity composition of legacy infrastructure over time.
        """
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        import numpy as np

        # --- Styles ---
        CB_PALETTE = ['#56B4E9', '#D55E00', '#009E73', '#F0E442', '#0072B2', '#CC79A7', '#E69F00'][::-1]
        HATCHES = ['', '//', '..', 'xx', '++', '**', 'OO']
        plt.rcParams.update({
            'font.size': 14, 
            'text.color': 'black',
            'axes.labelcolor': 'black',
            'xtick.color': 'black',
            'ytick.color': 'black',
            'font.family': 'sans-serif'
        })
        
        # --- Load Data ---
        self.load()
        regions = sorted(self.residual_capacity['REGION'].unique())
        n_regions = len(regions)
        years = self.years

        all_techs = sorted(self.residual_capacity['TECHNOLOGY'].unique())
        all_fuels = sorted(self.output_activity_ratio['FUEL'].unique())

        # --- Process Data ---
        tech_to_fuel = {}
        for tech in all_techs:
            fuels = self.output_activity_ratio[self.output_activity_ratio['TECHNOLOGY'] == tech]['FUEL']
            if not fuels.empty:
                tech_to_fuel[tech] = fuels.value_counts().idxmax()
            else:
                tech_to_fuel[tech] = 'Unknown'

        tech_to_color = {tech: CB_PALETTE[i % len(CB_PALETTE)] for i, tech in enumerate(all_techs)}
        fuel_to_hatch = {fuel: HATCHES[i % len(HATCHES)] for i, fuel in enumerate(all_fuels)}

        # --- Plotting ---
        fig, axes = plt.subplots(nrows=n_regions, ncols=1, figsize=(12, 4.5 * n_regions), sharey=True)
        if n_regions == 1:
            axes = [axes]
        
        for idx, region in enumerate(regions):
            ax = axes[idx]
            df_capacity = self.residual_capacity[self.residual_capacity['REGION'] == region].copy()
            df_capacity['PRIMARY OUTPUT FUEL'] = df_capacity['TECHNOLOGY'].map(tech_to_fuel)
            df_pivot = df_capacity.pivot_table(
                index='YEAR', columns='TECHNOLOGY', values='VALUE', aggfunc='sum', fill_value=0
            ).reindex(index=years, columns=all_techs, fill_value=0)

            bottom = np.zeros(len(df_pivot))
            for i, tech in enumerate(all_techs):
                hatch = fuel_to_hatch.get(tech_to_fuel[tech], '')
                bar = ax.bar(
                    df_pivot.index,
                    df_pivot[tech],
                    bottom=bottom,
                    color=tech_to_color[tech],
                    label=tech,
                    hatch=hatch,
                    edgecolor='black'
                )
                bottom += df_pivot[tech].values

            ax.set_ylabel("Installed Capacity (Model Units)")
            ax.set_title(f"Region: {region}")
            ax.set_xticks(df_pivot.index)
            ax.set_xticklabels(df_pivot.index, rotation=0)
            ax.grid(axis='y', linestyle='--', alpha=0.5)
            if idx == n_regions - 1:
                ax.set_xlabel("Year")
            else:
                ax.set_xlabel("")

        # --- Formatting ---
        tech_handles = [
            mpatches.Patch(facecolor=tech_to_color[tech], edgecolor='black', label=tech)
            for tech in all_techs
        ]
        fuel_handles = [
            mpatches.Patch(facecolor='white', edgecolor='black', label=fuel, hatch=fuel_to_hatch[fuel])
            for fuel in all_fuels
        ]
        handles = tech_handles + fuel_handles
        labels = [h.get_label() for h in handles]
        fig.legend(
            handles, labels,
            title="Technology (color) / Output Fuel (hatch)",
            loc='upper center', bbox_to_anchor=(0.5, 1.04),
            ncol=min(len(handles), 5), frameon=False, handleheight=2.0, handlelength=3.0
        )

        plt.tight_layout(rect=[0, 0, 1, 0.97])
        plt.show()

    def visualize_potential(self, region, fuel, legend=True):
        """
        Visualize generation/activity profile across timeslices for technologies.
        Shows how capacity factors and availability affect generation patterns.
        
        :param region: str, Region to visualize
        :param fuel: str, Output fuel to filter technologies
        :param legend: bool, Show legend
        :param ax: matplotlib axis object or None
        
        Creates visualization showing:
        - Installed capacity
        - Available capacity (after availability factor)
        - Actual generation potential (after capacity factor)
        """
        import matplotlib.pyplot as plt

        # --- Styles ---
        COLOR = ['darkslategrey']
        CB_PALETTE = ['#56B4E9', '#D55E00', '#009E73', '#F0E442', '#0072B2', '#CC79A7', '#E69F00']
        HATCHES = ['', '//', '..', 'xx', '++', '**', 'OO']
        plt.rcParams.update({
            'font.size': 14, 
            'text.color': 'black',
            'axes.labelcolor': 'black',
            'xtick.color': 'black',
            'ytick.color': 'black',
            'font.family': 'sans-serif'
        })

        # --- Load Data ---
        self.load()

        techs = self.output_activity_ratio[
            (self.output_activity_ratio['REGION'] == region) &
            (self.output_activity_ratio['FUEL'] == fuel)
        ]['TECHNOLOGY'].unique()

        residual_techs = self.residual_capacity[
            (self.residual_capacity['REGION'] == region) &
            (self.residual_capacity['TECHNOLOGY'].isin(techs))
        ]['TECHNOLOGY'].unique()
        techs_sorted = list(residual_techs) + [t for t in techs if t not in residual_techs]
        n_techs = len(techs_sorted)
        if n_techs == 0:
            print(f"No technologies producing '{fuel}' in region '{region}'.")
            return
        
        # --- Process Data ---
        data = []
        seasons = set()
        daytypes = set()
        timebrackets = set()

        for ts in self.time_axis['TIMESLICE'].unique():
            row = self.time_axis.loc[self.time_axis['TIMESLICE'] == ts].iloc[0]
            season, daytype, timebracket = row['Season'], row['DayType'], row['DailyTimeBracket']

            seasons.add(season)
            daytypes.add(daytype)
            timebrackets.add(timebracket)

            data.append({"ts": ts, "season": season, "daytype": daytype, "timebracket": timebracket})

        dt_style_map = {d: CB_PALETTE[i % len(CB_PALETTE)] for i, d in enumerate(sorted(daytypes))}
        tb_hatch_map = {b: HATCHES[i % len(HATCHES)] for i, b in enumerate(sorted(timebrackets))}

        fig, axes = plt.subplots(nrows=n_techs, ncols=1, figsize=(12, 7 * n_techs),
                                 sharex=True, sharey=True)
        if n_techs == 1:
            ax = [axes]
        else:
            ax = axes.flatten()
        
        # --- Plotting ---
        for t, tech in enumerate(techs_sorted):
            df_res = self.residual_capacity[
                (self.residual_capacity['REGION'] == region) &
                (self.residual_capacity['TECHNOLOGY'] == tech)
            ]
            df_avail = self.availability_factor[
                (self.availability_factor['REGION'] == region) &
                (self.availability_factor['TECHNOLOGY'] == tech)
            ]
            df_cap = self.capacity_factor[
                (self.capacity_factor['REGION'] == region) &
                (self.capacity_factor['TECHNOLOGY'] == tech)
            ]
            merged = pd.merge(df_avail, df_cap, on='YEAR')
            merged['AVAIL x CAP'] = merged['VALUE_x'] * merged['VALUE_y']

            plot_data = merged.pivot(index='YEAR', columns='TIMESLICE', values='VALUE_y') # AVAIL x CAP
            plot_data = plot_data.reindex(sorted(plot_data.columns), axis=1)

            bottoms = df_res.set_index('YEAR')['VALUE'].reindex(plot_data.index, fill_value=0).values
            years_x = plot_data.index.astype(str)
            # Add residual capacity
            ax[t].bar(years_x, bottoms, color=COLOR[0], edgecolor='white', linewidth=0.5, alpha=0.1)

            legend_handles = {}
            for d in data:
                values = plot_data[d['ts']].fillna(0).values
                color = dt_style_map[d['daytype']]
                hatch = tb_hatch_map[d['timebracket']]
                legend_key = f"{d['daytype']} | {d['timebracket']}"
                # Only add a handle for each (daytype, timebracket) combo once
                bar = ax[t].bar(
                    years_x, values, bottom=bottoms,
                    label=None, color=color, hatch=hatch,
                    edgecolor='white', linewidth=0.5
                )
                if legend_key not in legend_handles:
                    legend_handles[legend_key] = bar[0]
                bottoms += values
            
            # --- Formatting ---
            ax[t].set_ylabel(f"{tech} Generation Potential (Model Units)")
            ax[t].set_title(f"Generation Profile: {region} - {tech} ({fuel})")

            # Custom legend: only show daytype and timebracket
            if legend:
                handles = list(legend_handles.values())
                labels = list(legend_handles.keys())
                if len(handles) > 10:
                    ax[t].legend(handles, labels, title="Daytype | Timebracket", bbox_to_anchor=(1.05, 1), loc='upper left')
                else:
                    ax[t].legend(handles, labels, title="Daytype | Timebracket", loc='best')

        plt.grid(axis='y', linestyle='--', alpha=0.3)
        plt.tight_layout()
        plt.show()

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