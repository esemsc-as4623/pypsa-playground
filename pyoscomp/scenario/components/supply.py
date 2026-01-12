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

    # === Prerequisite Check === # TODO: modularize instead of copying from demand.py
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
        
        # Append to DataFrame
        df_new1 = pd.DataFrame([{"REGION": region, "TECHNOLOGY": technology, "VALUE": operational_life}])
        df_new2 = pd.DataFrame([{"REGION": region, "TECHNOLOGY": technology, "VALUE": capacity_to_activity_unit}])
        for attr_name, df_new in [("capacity_to_activity_unit", df_new2), ("operational_life", df_new1)]:
            current_df = getattr(self, attr_name)
            if current_df.empty:
                setattr(self, attr_name, df_new)
            else:
                # Merge on REGION, TECHNOLOGY
                combined = pd.concat([current_df, df_new], ignore_index=True)
                # Keep the last occurrence (i.e. new data overwrites old)
                merged_df = combined.drop_duplicates(subset=["REGION", "TECHNOLOGY"], keep='last').reset_index(drop=True)
                setattr(self, attr_name, merged_df)
    
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
        if isinstance(efficiency, dict):
            eff_map = {y: efficiency.get(y, list(efficiency.values())[0]) for y in years}
        else:
            eff_map = {y: efficiency for y in years}
        
        # Compute input/output activity ratios
        input_records, output_records = [], []
        for y in years:
            eff = eff_map[y]
            input_ratio, output_ratio = self._apply_efficiency_to_ratios(eff, mode=mode)
            input_records.append({"REGION": region, "TECHNOLOGY": technology, "FUEL": input_fuel, "MODE_OF_OPERATION": mode, "YEAR": y, "VALUE": input_ratio})
            output_records.append({"REGION": region, "TECHNOLOGY": technology, "FUEL": output_fuel, "MODE_OF_OPERATION": mode, "YEAR": y, "VALUE": output_ratio})
        
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
        # --- VALIDATION: Region, Technology, Mode ---
        if region not in self.regions:
            raise ValueError(f"Region '{region}' not defined in scenario. Set topology first.")
        if (region, technology) not in self.defined_tech:
            raise ValueError(f"Technology '{technology}' not registered in region '{region}'. Call add_technology() first.")
        self.defined_tech.add((region, technology))
        self._validate_mode_configuration(modes_config)

        if (region, technology) not in self.mode_definitions:
            self.mode_definitions[(region, technology)] = []
        input_records, output_records = [], []

        for mode, config in modes_config.items():
            if mode not in self.mode_definitions[(region, technology)]:
                self.mode_definitions[(region, technology)].append(mode)
            inputs, outputs = config.get('inputs', {}), config.get('outputs', {})
            
            for y in self.years:
                # Inputs
                for fuel, ratio in inputs.items():
                    input_records.append({"REGION": region, "TECHNOLOGY": technology, "FUEL": fuel, "MODE_OF_OPERATION": mode, "YEAR": y, "VALUE": ratio})
                    self.defined_fuels.add(fuel)
                # Outputs
                for fuel, ratio in outputs.items():
                    output_records.append({"REGION": region, "TECHNOLOGY": technology, "FUEL": fuel, "MODE_OF_OPERATION": mode, "YEAR": y, "VALUE": ratio})
                    self.defined_fuels.add(fuel)
        # Merge records
        self.input_activity_ratio = self.add_to_dataframe(self.input_activity_ratio, input_records,
                                                          key_columns=["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR"])
        self.output_activity_ratio = self.add_to_dataframe(self.output_activity_ratio, output_records,
                                                           key_columns=["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR"])

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
        # --- VALIDATION: Region, Technology, Availability ---
        if region not in self.regions:
            raise ValueError(f"Region '{region}' not defined in scenario. Set topology first.")
        if (region, technology) not in self.defined_tech:
            raise ValueError(f"Technology '{technology}' not registered in region '{region}'. Call add_technology() first.")
        if isinstance(resource_availability, dict):
            for y, val in resource_availability.items():
                if not (0 <= val <= 1):
                    raise ValueError(f"Resource availability for year {y} must be in [0, 1].")
        elif isinstance(resource_availability, (int, float)):
            if not (0 <= resource_availability <= 1):
                raise ValueError("Resource availability must be in [0, 1].")
        self.defined_tech.add((region, technology))
        self.defined_fuels.add(output_fuel)

        # Map year to resource availability factor
        if resource_availability is None:
            avail_map = {y: 1.0 for y in self.years}
        elif isinstance(resource_availability, dict):
            avail_map = {y: resource_availability.get(y, list(resource_availability.values())[0]) for y in self.years}
        else:
            avail_map = {y: resource_availability for y in self.years}

        # Output activity ratios always 1.0 for resource technologies
        output_records = []
        for y in self.years:
            output_records.append({"REGION": region, "TECHNOLOGY": technology, "FUEL": output_fuel, "MODE_OF_OPERATION": 'MODE1', "YEAR": y, "VALUE": 1.0})
        self.output_activity_ratio = self.add_to_dataframe(self.output_activity_ratio, output_records,
                                                           key_columns=["REGION", "TECHNOLOGY", "FUEL", "MODE_OF_OPERATION", "YEAR"])
        self.defined_fuels.add(output_fuel)

        # Availability factor
        avail_records = []
        for y in self.years:
            avail_records.append({"REGION": region, "TECHNOLOGY": technology, "YEAR": y, "VALUE": avail_map[y]})
        self.availability_factor = self.add_to_dataframe(self.availability_factor, avail_records,
                                                         key_columns=["REGION", "TECHNOLOGY", "YEAR"])

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
        
        if isinstance(year, int):
            years = [year]
        elif isinstance(year, list):
            years = year
        else:
            years = [self.years[0]]

        for y in years:
            # Create comprehensive timeslice factor dict
            if timeslice_factor is not None:
                timeslice_factor = self._apply_timeslice_factors(timeslice_factor, default=1.0)
            elif any(f is not None for f in [season_factor, day_factor, time_factor]):
                timeslice_factor = self._apply_hierarchical_factors(
                    season_factor or {}, day_factor or {}, time_factor or {}, default=1.0
                )
            else: # Default to 1.0 for all timeslices
                timeslice_factor = self._apply_timeslice_factors({}, default=1.0)
            self.capacity_factor_assignments[(region, technology, y)] = {"type": "custom", "weights": timeslice_factor}
        # Apply to all years if year is None
        if year is None:
            for y in self.years[1:]:
                self.capacity_factor_assignments[(region, technology, y)] = self.capacity_factor_assignments[(region, technology, years[0])]

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
        # --- VALIDATION: Region, Technology, Year, Availability ---
        if region not in self.regions:
            raise ValueError(f"Region '{region}' not defined in scenario. Set topology first.")
        if (region, technology) not in self.defined_tech:
            raise ValueError(f"Technology '{technology}' not registered in region '{region}'. Call add_technology() first.")
        self.defined_tech.add((region, technology))
        if isinstance(year, int) and year not in self.years:
            raise ValueError(f"Year {year} not defined in scenario years.")
        if isinstance(year, list) and not all(y in self.years for y in year):
            raise ValueError(f"One or more years in {year} not defined in scenario years.")
        if isinstance(availability, dict):
            for y, val in availability.items():
                if not (0 <= val <= 1):
                    raise ValueError(f"Resource availability for year {y} must be in [0, 1].")
        elif isinstance(availability, (int, float)):
            if not (0 <= availability <= 1):
                raise ValueError("Resource availability must be in [0, 1].")

        if isinstance(year, int):
            years = [year]
        elif isinstance(year, list):
            years = year
        else:
            years = self.years

        # Map year to availability factor
        if isinstance(availability, dict):
            avail_map = {y: availability.get(y, list(availability.values())[0]) for y in years}
        else:
            avail_map = {y: availability for y in years}

        # Availability factor
        records = []
        for y in years:
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
        
    # def set_emission_activity(self, region, technology, emission, rate, 
    #                           mode='MODE1', year=None):
    #     """
    #     Define emission rate per unit of activity for a technology.
        
    #     :param region: str, Region where technology operates
    #     :param technology: str, Technology identifier
    #     :param emission: str, Emission type (e.g., 'CO2', 'NOx', 'SOx')
    #     :param rate: float or dict, Emission per unit activity (e.g., tCO2/PJ)
    #                 If float: constant emission rate
    #                 If dict: {year: rate} for time-varying rates
    #     :param mode: str, Mode of operation (default 'MODE1')
    #     :param year: int, list[int], or None. Overrides dict if specified
        
    #     Example::
    #         # Coal plant CO2 emissions
    #         supply.set_emission_activity('Region1', 'COAL_PP', 'CO2', rate=94.6)  # tCO2/TJ
            
    #         # Gas plant with improving emissions (CCS retrofit)
    #         supply.set_emission_activity('Region1', 'GAS_CCGT_CCS', 'CO2',
    #                                     rate={2020: 56.1, 2030: 11.2, 2040: 5.6})
    #     """
    #     # --- VALIDATION: Region, Technology, Year, Emission Rate ---
    #     if region not in self.regions:
    #         raise ValueError(f"Region '{region}' not defined in scenario. Set topology first.")
    #     if (region, technology) not in self.defined_tech:
    #         raise ValueError(f"Technology '{technology}' not registered in region '{region}'. Call add_technology() first.")
    #     self.defined_tech.add((region, technology))
    #     if isinstance(year, int) and year not in self.years:
    #         raise ValueError(f"Year {year} not defined in scenario years.")
    #     if isinstance(year, list) and not all(y in self.years for y in year):
    #         raise ValueError(f"One or more years in {year} not defined in scenario years.")
    #     if isinstance(rate, dict):
    #         for y, val in rate.items():
    #             if val < 0:
    #                 raise ValueError(f"Emission rate cannot be negative. Found {val} in year {y}.")
    #     elif isinstance(rate, (int, float)):
    #         if rate < 0:
    #             raise ValueError("Emission rate cannot be negative.")
    #     else:
    #         raise ValueError("Emission rate must be a float or dict of {year: value}.")
        
    #     if isinstance(year, int):
    #         years = [year]
    #     elif isinstance(year, list):
    #         years = year
    #     else:
    #         if isinstance(rate, dict):
    #             years = sorted(set(rate.keys()) & set(self.years))
    #         else:
    #             years = self.years
        
    #     # Map year to emission rate
    #     if isinstance(rate, dict):
    #         rate_map = {y: rate.get(y, list(rate.values())[0]) for y in years}
    #     else:
    #         rate_map = {y: rate for y in years}

    #     records = []
    #     for y in years:
    #         records.append({
    #             "REGION": region, "TECHNOLOGY": technology, "EMISSION": emission, "MODE_OF_OPERATION": mode, "YEAR": y, "VALUE": rate_map[y]
    #         })

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
        s_adj = {}
        for season in self.time_axis["SEASON"].unique():
            s_adj[season] = season_factor.get(season, default)
        d_adj = {}
        for day in self.time_axis["DAYTYPE"].unique():
            d_adj[day] = day_factor.get(day, default)
        t_adj = {}
        for time in self.time_axis["DAILYTIMEBRACKET"].unique():
            t_adj[time] = time_factor.get(time, default)
        
        result = {}
        for _, ts_row in self.time_axis.iterrows():
            ts = ts_row["TIMESLICE"]
            s, d, t = ts_row["SEASON"], ts_row["DAYTYPE"], ts_row["DAILYTIMEBRACKET"]
            val = s_adj[s] * d_adj[d] * t_adj[t]
            if not 0 <= val <= 1:
                raise ValueError(f"Capacity factor for timeslice '{ts}' must be in [0,1], got {val}.")
            result[ts] = val
        return result

    def _interpolate_capacity_trajectory(self, trajectory, years, method='step'):
        """
        Interpolate capacity values for all model years based on known points.
        
        :param trajectory: dict, {year: value} known points
        :param years: list, All model years
        :param method: str, 'step', 'linear', or 'retire'
        :return: dict, {year: value} for all years
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
        """
        pass

    def _get_technology_summary(self, region, technology):
        """
        Generate a summary dict of all parameters for a technology.
        Useful for debugging and validation.
        
        :return: dict with keys for each parameter type
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