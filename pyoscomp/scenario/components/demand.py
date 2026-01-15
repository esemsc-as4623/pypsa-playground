# pyoscomp/scenario/components/demand.py

"""
Demand Component for scneario building in PyPSA-OSeMOSYS Comparison Framework.
Note: this component handles the definition of energy demand / load profiles in the model.
Demand is represented by AccumulatedAnnualDemand, SpecifiedAnnualDemand, and SpecifiedDemandProfile in OSeMOSYS terminology.
Demand is represented by Load and Generation (when sign is -1) in PyPSA terminology.
"""
import pandas as pd
import numpy as np

from .base import ScenarioComponent

class DemandComponent(ScenarioComponent):
    """
    Demand component for demand / load definitions and demand-side parameters.
    Handles OSeMOSYS demand parameters: annual demand volumes, demand profiles, and flexible demand.

    Prerequisites:
        - Time component must be initialized in the scenario (defines years and timeslices).
        - Topology component (regions, nodes) must be initialized.

    Raises descriptive errors if prerequisites are missing.

    Example usage::
        demand = DemandComponent(scenario_dir)
        demand.load() # Loads all demand parameter CSVs
        # ... modify DataFrames as needed ...
        demand.add_annual_demand(...)
        demand.set_subannual_profile(...)
        demand.add_flexible_demand(...)
        demand.process() # Recomputes demand parameter DataFrames
        demand.save() # Saves all demand parameter DataFrames to CSV

    CSV Format Expectations:
        - All CSVs must have columns as specified in each method's docstring.
        - See OSeMOSYS.md for parameter definitions.
    """
    def __init__(self, scenario_dir):
        super().__init__(scenario_dir)

        # Check prerequisites
        self.years, self.regions = self.check_prerequisites()
        self.time_axis = self.load_time_axis()

        # Demand parameters
        self.annual_demand_df = pd.DataFrame(columns=["REGION", "FUEL", "YEAR", "VALUE"])
        self.profile_demand_df = pd.DataFrame(columns=["REGION", "FUEL", "TIMESLICE", "YEAR", "VALUE"])
        self.accumulated_demand_df = pd.DataFrame(columns=["REGION", "FUEL", "YEAR", "VALUE"])

        # Tracking
        self.defined_fuels = set()        # (Region, Fuel)
        self.profile_assignments = {}     # (Region, Fuel, Year) -> Profile Name/Type
        
    # === Check Prerequisites ===
    def check_prerequisites(self):
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
        Load all demand parameter CSV files into DataFrames.
        Uses read_csv from base class. Updates DataFrames and defined_fuels.
        """
        # Annual
        df = self.read_csv("SpecifiedAnnualDemand.csv", ["REGION", "FUEL", "YEAR", "VALUE"])
        self.annual_demand_df = df
        self.defined_fuels = set(zip(df["REGION"], df["FUEL"]))

        # Profile
        df = self.read_csv("SpecifiedDemandProfile.csv", ["REGION", "FUEL", "TIMESLICE", "YEAR", "VALUE"])
        self.profile_demand_df = df

        # Accumulated
        df = self.read_csv("AccumulatedAnnualDemand.csv", ["REGION", "FUEL", "YEAR", "VALUE"])
        self.accumulated_demand_df = df

    def save(self):
        """
        Save all demand parameter DataFrames to CSV files in the scenario directory.
        Uses write_dataframe from base class.
        """
        # Annual
        df = self.annual_demand_df[["REGION", "FUEL", "YEAR", "VALUE"]].sort_values(by=["REGION", "FUEL", "YEAR"])
        self.write_dataframe("SpecifiedAnnualDemand.csv", df)

        # Profile
        df = self.profile_demand_df[["REGION", "FUEL", "TIMESLICE", "YEAR", "VALUE"]].sort_values(by=["REGION", "FUEL", "TIMESLICE", "YEAR"])
        self.write_dataframe("SpecifiedDemandProfile.csv", df)

        # Accumulated
        df = self.accumulated_demand_df[["REGION", "FUEL", "YEAR", "VALUE"]].sort_values(by=["REGION", "FUEL", "YEAR"])
        self.write_dataframe("AccumulatedAnnualDemand.csv", df)

    # === User Input Methods ===
    def add_annual_demand(self, region, fuel, trajectory: dict,
                          trend_function=None, interpolation: str='step'):
        """
        Define annual demand volume for a given region and fuel over specified model years.
        Trend function or interpolation method can be used to fill years missing in trajectory.
        If both trend_function and interpolation are provided, trend_function takes precedence.

        :param region: str, Region where the demand applies
        :param fuel: str, Name of the fuel/demand type
        :param trajectory: dict {year: value}, Known demand points
        :param trend_function: function(year) -> value, Optional function for demand values (used for years not in trajectory)
        :param interpolation: str, 'step', 'linear', or 'cagr' for interpolation method (default 'step'); also used to extrapolate beyond known points if needed to cover all model years.
        
        Example::
            demand.add_annual_demand('Region1', 'ELEC',
            trajectory={2020: 100, 2030: 120}, interpolation='linear')

            # OR
            def compound(year):
                return 1000*(1.05**(year-2025))
            demand.add_annual_demand('Region1', 'ELEC',
            trajectory={2020: 100, 2030: 120}, trend_function=compound)
        """
        # --- VALIDATION: Region, Trajectory, Interpolation
        if region not in self.regions:
            raise ValueError(f"Region '{region}' not defined in scenario. Set topology first.")
        self.defined_fuels.add((region, fuel))
        if len(trajectory) == 0:
            raise ValueError(f"No trajectory points provided for {region}-{fuel}.")
        for y, val in trajectory.items():
            if val < 0:
                raise ValueError(f"Demand cannot be negative. Found {val} in model year {y} for {region}-{fuel}")
        if interpolation not in ['step', 'linear', 'cagr']:
            print(f"Interpolation method '{interpolation}' for {region}-{fuel} not recognized. Using 'step' instead.") 
            interpolation = 'step'
        
        records = []
        # --- PATH A: Function Based ---
        if trend_function:
            for y in self.years:
                val = trajectory.get(y, trend_function(y))
                if val < 0:
                    raise ValueError(f"Trend function produced negative demand for {region}-{fuel} in model year {y}: {val}")
                records.append({"REGION": region, "FUEL": fuel, "YEAR": y, "VALUE": val})
        
        # --- PATH B: Interpolation Based ---
        else:
            sorted_years = sorted(trajectory.keys())
            if not sorted_years:
                raise ValueError(f"No trajectory points provided for {region}-{fuel}.")
            
            # Preceding Years
            first_yr = sorted_years[0]
            first_val = trajectory[first_yr]
            preceding_years = [y for y in self.years if y < first_yr]
            for y in preceding_years:
                records.append({
                    "REGION": region, "FUEL": fuel, "YEAR": y, "VALUE": first_val
                })

            # Interpolate
            for i in range(len(sorted_years) - 1):
                y_start, y_end = sorted_years[i], sorted_years[i+1]
                years_to_fill = [y for y in self.years if y_start <= y < y_end]
                val_start, val_end = trajectory[y_start], trajectory[y_end]
                
                if interpolation == 'linear':
                    values = np.linspace(val_start, val_end, len(years_to_fill) + 1)[:-1]
                elif interpolation == 'cagr':
                    if val_start == 0:
                         # Handle 0 start for CAGR (mathematically undefined, fallback to linear or 0)
                         values = np.linspace(val_start, val_end, len(years_to_fill) + 1)[:-1]
                    else:
                        steps = y_end - y_start
                        r = (val_end / val_start) ** (1 / steps) - 1
                        values = [val_start * ((1 + r) ** (y - y_start)) for y in years_to_fill]
                else: # Step
                    values = [val_start] * len(years_to_fill)
                    
                for y, val in zip(years_to_fill, values):
                    records.append({
                        "REGION": region, "FUEL": fuel, "YEAR": y, "VALUE": val
                    })

            # Final Point
            last_yr = sorted_years[-1]
            last_val = trajectory[last_yr]
            if last_yr in self.years:
                records.append({
                    "REGION": region, "FUEL": fuel, "YEAR": last_yr, "VALUE": last_val
                })

            # Extrapolate if needed
            remaining_years = [y for y in self.years if y > last_yr]
            if remaining_years:
                extrap_values = []
                if interpolation == 'step':
                    extrap_values = [last_val] * len(remaining_years)
                elif len(sorted_years) >= 2:
                    prev_yr = sorted_years[-2]
                    prev_val = trajectory[prev_yr]
                    y_diff = last_yr - prev_yr
                    
                    if interpolation == 'cagr':
                        if prev_val <= 0: # Fallback to linear slope
                            slope = (last_val - prev_val) / y_diff
                            extrap_values = [last_val + slope * (y - last_yr) for y in remaining_years]
                        else:
                            r = (last_val / prev_val) ** (1 / y_diff) - 1
                            extrap_values = [last_val * ((1 + r) ** (y - last_yr)) for y in remaining_years]
                    else: # Linear
                        slope = (last_val - prev_val) / y_diff
                        extrap_values = [last_val + slope * (y - last_yr) for y in remaining_years]
                else: # Step
                    extrap_values = [last_val] * len(remaining_years)

                for y, val in zip(remaining_years, extrap_values):
                    # Validate extrapolation didn't go negative
                    if val < 0:
                        val = 0
                    records.append({
                        "REGION": region, "FUEL": fuel, "YEAR": y, "VALUE": val
                    })
        
        self.annual_demand_df = self.add_to_dataframe(self.annual_demand_df, records,
                                                      key_columns=["REGION", "FUEL", "YEAR"])
        
    def add_flexible_demand(self, region, fuel, year, value):
        """
        Add a flexible (accumulated) demand entry for a given region, fuel, and year.

        :param region: str, Region where demand applies
        :param fuel: str, Name of the fuel/demand type
        :param year: int, Model year
        :param value: float, Flexible demand value

        Example::
            demand.add_flexible_demand('Region1', 'ELEC', 2025, 10.0)
        """
        if value < 0:
            raise ValueError(f"Flexible demand cannot be negative: {value} for {region}-{fuel} in year {year}")
        record = [{"REGION": region, "FUEL": fuel, "YEAR": year, "VALUE": value}]
        self.accumulated_demand_df = self.add_to_dataframe(self.accumulated_demand_df, record,
                                                           key_columns=["REGION", "FUEL", "YEAR"])

    def set_subannual_profile(self, region, fuel, year=None, timeslice_factor=None, 
                              season_factor=None, day_factor=None, time_factor=None):
        """
        Set the demand profile for a given region, fuel, and optionally year.
        Supports direct timeslice factors or hierarchical (season, day, time) factors.
        Factor dictionaries should map timeslice/season/daytype/dailytimebracket names to their respective factors.
        If both timeslice factors and hierarchical factors are provided, timeslice factors take precedence.
        If multiple factor dictionaries are provided, hierarchical weighting is used.
        Missing entries default to YearSplit.csv values, i.e. the proportion of the year that a timeslice represents.

        :param region: str, Region where demand applies
        :param fuel: str, Name of the fuel/demand type
        :param year: int, list[int] or None, Model year, if not specified applies to all years
        :param timeslice_factor: dict or None, {timeslice: factor}
        :param season_factor: dict or None, {season: factor}
        :param day_factor: dict or None, {daytype: factor}
        :param time_factor: dict or None, {dailytimebracket: factor}

        Example::
            demand.set_subannual_profile('Region1', 'ELEC', year=2040, timeslice_factor={'Winter_Weekday_Day': 0.6, ...})
            demand.set_subannual_profile('Region1', 'ELEC', year=[2028, 2032], season_factor={'Winter': 1.2, 'Summer': 0.8}, time_factor={'Day': 1.5, 'Night': 0.5})
        """
        # --- VALIDATION: Region, Fuel, Year ---
        if region not in self.regions:
            raise ValueError(f"Region '{region}' not defined in scenario. Set topology first.")
        if (region, fuel) not in self.defined_fuels:
            raise ValueError(f"Fuel '{fuel}' not registered in region '{region}'. Call add_annual_demand() first.")
        self.defined_fuels.add((region, fuel))
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
                timeslice_factor = self._apply_timeslice_factors(timeslice_factor, y)
            elif any(f is not None for f in [season_factor, day_factor, time_factor]):
                timeslice_factor = self._apply_hierarchical_factors(
                    season_factor or {}, day_factor or {}, time_factor or {}, y
                )
            else:
                print(f"Setting default (flat) profile for {region}, {fuel} in year {y}.")
                return
            # Normalize timeslice factors
            total = sum(timeslice_factor.values())
            if total <= 0:
                print(f"Warning: Timeslice factors for {region}, {fuel} in year {y} sum to {total}. Using flat profile.")
                self.profile_assignments[(region, fuel, y)] = {"type": "flat"}
            else:
                norm_weights = {k: v/total for k, v in timeslice_factor.items()}
                self.profile_assignments[(region, fuel, y)] = {"type": "custom", "weights": norm_weights}
        # Apply to all years if year is None
        if year is None:
            for y in self.years[1:]:
                self.profile_assignments[(region, fuel, y)] = self.profile_assignments[(region, fuel, years[0])]

    # === Processing ===
    def process(self):
        """
        Generate and update the full demand profile for each (region, fuel, year, timeslice) combination based on self.profile_assignments.
        Normalizes profiles so that the sum for each (region, fuel, year) is exactly 1.0.
        Updates self.profile_demand_df with the generated profiles.
        """
        for region, fuel in self.defined_fuels:
            for year in self.years:
                if (region, fuel, year) not in self.profile_assignments:
                    self.profile_assignments[(region, fuel, year)] = {"type": "flat"}
        all_rows = []
        for (region, fuel, year), assignment in self.profile_assignments.items():
            rows = self._generate_profile(region, fuel, year, assignment)
            all_rows.extend(rows)
        normalized_rows = self._normalize_profile_rows(all_rows)
        self.profile_demand_df = pd.DataFrame(normalized_rows)

    # === Internal Logic Helpers ===
    def _apply_timeslice_factors(self, factor_dict, year):
        """
        Applies timeslice factors using YearSplit.csv.
        If a timeslice is missing in factor_dict, it uses the original YearSplit proportion.
        If a timeslice is present, it multiplies the original YearSplit proportion by the provided factor.
        Returns a complete dict of timeslice factors.
        """
        result = {}
        for ts in self.time_axis["TIMESLICE"]:
            original = self.time_axis.loc[(self.time_axis["YEAR"] == year) & 
                                          (self.time_axis["TIMESLICE"] == ts), "VALUE"].values[0]
            result[ts] = original * factor_dict.get(ts, 1)
        return result
    
    def _apply_hierarchical_factors(self, season_factor, day_factor, time_factor, year):
        """
        Applies hierarchical factors to generate timeslice factors.
        If a season/day/time is missing in the respective factor dict, it uses the original YearSplit proportion.
        If a season/day/time is present, it multiplies the original YearSplit proportion by the provided factor.
        Returns a complete dict of timeslice factors.
        """
        # Compute adjusted factors for each dimension
        s_adj = {}
        for season in self.time_axis["Season"].unique():
            original = self.time_axis.loc[(self.time_axis["YEAR"] == year) & (self.time_axis["Season"] == season), "VALUE"].sum()
            s_adj[season] = original * season_factor.get(season, 1)
        d_adj = {}
        for day in self.time_axis["DayType"].unique():
            original = self.time_axis.loc[(self.time_axis["YEAR"] == year) & (self.time_axis["DayType"] == day), "VALUE"].sum()
            d_adj[day] = original * day_factor.get(day, 1)
        t_adj = {}
        for time in self.time_axis["DailyTimeBracket"].unique():
            original = self.time_axis.loc[(self.time_axis["YEAR"] == year) & (self.time_axis["DailyTimeBracket"] == time), "VALUE"].sum()
            t_adj[time] = original * time_factor.get(time, 1)

        result = {}
        for _, ts_row in self.time_axis.iterrows():
            ts = ts_row["TIMESLICE"]
            s, d, t = ts_row["Season"], ts_row["DayType"], ts_row["DailyTimeBracket"]
            result[ts] = s_adj[s] * d_adj[d] * t_adj[t]
        return result
        

    def _generate_profile(self, region, fuel, year, assignment):
        """
        Generate the demand profile rows for a specific (region, fuel, year) and assignment.
        Returns a list of dicts with keys: REGION, FUEL, TIMESLICE, YEAR, VALUE.
        Handles 'custom' and 'flat' assignment types. Defaults to 'flat' if type is unrecognized.
        """
        p_type = assignment.get("type", "flat")
        if p_type == "custom":
            weights = assignment["weights"]
            return [
                {"REGION": region, "FUEL": fuel, "TIMESLICE": ts, "YEAR": year, "VALUE": weights[ts]}
                for ts in weights
            ]
        else:  # Flat profile or fallback
            # Use the default yearsplit for the year
            ys = self.time_axis[self.time_axis["YEAR"] == year]
            return [
                {"REGION": region, "FUEL": fuel, "TIMESLICE": row["TIMESLICE"], "YEAR": year, "VALUE": row["VALUE"]}
                for _, row in ys.iterrows()
            ]

    def _normalize_profile_rows(self, rows):
        """
        Normalize the profile rows so that the sum of 'VALUE' for each (REGION, FUEL, YEAR) is exactly 1.0.
        Adjusts the largest timeslice to fix floating point errors.
        Returns a list of normalized dicts.
        """
        if not rows:
            return []
        df = pd.DataFrame(rows)
        group_cols = ["REGION", "FUEL", "YEAR"]
        sums = df.groupby(group_cols)['VALUE'].sum()
        for idx, total in sums.items():
            if not np.isclose(total, 1.0, atol=1e-9):
                residual = 1.0 - total
                mask = (df[group_cols[0]] == idx[0]) & (df[group_cols[1]] == idx[1]) & (df[group_cols[2]] == idx[2])
                idx_to_fix = df.loc[mask, 'VALUE'].idxmax()
                df.at[idx_to_fix, 'VALUE'] += residual
                df.loc[mask, 'VALUE'] = df.loc[mask, 'VALUE'].round(9)
        return df.to_dict('records')

    # === Visualization ===
    def visualize(self, region, fuel, legend=True, ax=None):
        """
        Creates a visualization of the demand composition by timeslice for a given region and fuel.
        """
        import matplotlib.pyplot as plt

        # --- Styles ---
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

        df_annual = self.annual_demand_df[
            (self.annual_demand_df['REGION'] == region) &
            (self.annual_demand_df['FUEL'] == fuel)
        ]
        df_profile = self.profile_demand_df[
            (self.profile_demand_df['REGION'] == region) &
            (self.profile_demand_df['FUEL'] == fuel)
        ]

        merged = pd.merge(df_annual, df_profile, on='YEAR')
        merged['ABS_VALUE'] = merged['VALUE_x'] * merged['VALUE_y']

        plot_data = merged.pivot(index='YEAR', columns='TIMESLICE', values='ABS_VALUE')
        plot_data = plot_data.reindex(sorted(plot_data.columns), axis=1)

        # --- Process Data ---
        data = []
        seasons = set()
        daytypes = set()
        timebrackets = set()

        for ts in plot_data.columns:
            row = self.time_axis.loc[self.time_axis["TIMESLICE"] == ts].iloc[0]
            season, daytype, timebracket = row["Season"], row["DayType"], row["DailyTimeBracket"]
            
            seasons.add(season)
            daytypes.add(daytype)
            timebrackets.add(timebracket)
            
            data.append({"ts": ts, "season": season, "daytype": daytype, "timebracket": timebracket})
        
        dt_style_map = {d: CB_PALETTE[i % len(CB_PALETTE)] for i, d in enumerate(sorted(list(daytypes)))}
        tb_style_map = {b: HATCHES[i % len(HATCHES)] for i, b in enumerate(sorted(list(timebrackets)))}

        # --- Plotting ---
        if ax is None:
            fig, ax = plt.subplots(figsize=(12, 7))
        bottoms = np.zeros(len(plot_data))
        years_x = plot_data.index.astype(str)

        legend_handles = {}
        for d in data:
            values = plot_data[d["ts"]].fillna(0).values
            color = dt_style_map[d['daytype']]
            hatch = tb_style_map[d['timebracket']]
            legend_key = f"{d['daytype']} | {d['timebracket']}"
            # Only add a handle for each (daytype, timebracket) combo once
            bar = ax.bar(
                years_x, values, bottom=bottoms, 
                label=None, color=color, hatch=hatch,
                edgecolor='white', linewidth=0.5
            )
            if legend_key not in legend_handles:
                legend_handles[legend_key] = bar[0]
            bottoms += values

        # --- Formatting ---
        ax.set_ylabel("Energy Demand (Model Units)")
        ax.set_title(f"Demand Composition: {region} - {fuel}")

        # Custom legend: only show daytype and timebracket
        if legend:
            handles = list(legend_handles.values())
            labels = list(legend_handles.keys())
            if len(handles) > 10:
                ax.legend(handles, labels, title="Daytype | Timebracket", bbox_to_anchor=(1.05, 1), loc='upper left')
            else:
                ax.legend(handles, labels, title="Daytype | Timebracket", loc='best')

        plt.grid(axis='y', linestyle='--', alpha=0.3)
        plt.tight_layout()
        plt.show()

    def visualize_all(self):
        """
        Creates one stacked area plot per region, with all fuel types stacked for each region.
        Years are on the x-axis, demand is on the y-axis, and each area represents a fuel.
        """
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches

        # --- Styles ---
        COLOR = ['darkslategrey']
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
        if self.annual_demand_df.empty:
            print("No annual demand data to visualize.")
            return
        
        regions = sorted(self.profile_demand_df['REGION'].unique())
        fuels = sorted(self.profile_demand_df['FUEL'].unique())
        n_regions = len(regions)

        ncols, nrows = 1, n_regions

        # Assign style map
        fuel_hatch_map = {fuel: HATCHES[i % len(HATCHES)] for i, fuel in enumerate(fuels)}
        
        # --- Plotting ---
        fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(12 * ncols, 7 * nrows))
        if n_regions == 1:
            axes = [axes]
        else:
            axes = axes.flatten()

        # Track global x/y limits
        global_ys, global_xs = [], []

        for idx, region in enumerate(regions):
            ax = axes[idx]
            region_df = self.profile_demand_df[self.profile_demand_df['REGION'] == region]

            # Sum over timeslices to get total demand per fuel per year
            grouped = region_df.groupby(['YEAR', 'FUEL'])['VALUE'].sum().unstack(fill_value=0)
            years = grouped.index.values
            fuel_names = grouped.columns.tolist()

            # If annual_demand_df exists, scale by annual demand for each (region, fuel, year)
            if not self.annual_demand_df.empty:
                for fuel in fuel_names:
                    for y in years:
                        mask = (
                            (self.annual_demand_df['REGION'] == region) &
                            (self.annual_demand_df['FUEL'] == fuel) &
                            (self.annual_demand_df['YEAR'] == y)
                        )
                        if not self.annual_demand_df[mask].empty:
                            grouped.at[y, fuel] *= self.annual_demand_df[mask]['VALUE'].values[0]
                        else:
                            grouped.at[y, fuel] = 0

            # Prepare data for stackplot
            y_arrays = [grouped[fuel].values for fuel in fuel_names]
            polys = ax.stackplot(years, y_arrays, labels=fuel_names, colors=COLOR)
            # Apply hatches to the stackplot polygons
            for poly, fuel in zip(polys, fuel_names):
                poly.set_hatch(fuel_hatch_map[fuel])
                poly.set_edgecolor('white')
                poly.set_linewidth(0.5)
            ax.set_title(f"Region: {region}")
            ax.set_ylabel("Total Demand (Model Units)")
            ax.grid(axis='y', linestyle='--', alpha=0.3)
            
            global_ys.append(ax.get_ylim())
            global_xs.append(ax.get_xlim())

            if idx == n_regions - 1:
                ax.set_xlabel("Year")
        
        # --- Formatting ---
        # Set shared axis limits
        y_min = min([y[0] for y in global_ys])
        y_max = max([y[1] for y in global_ys])
        x_min = min([x[0] for x in global_xs])
        x_max = max([x[1] for x in global_xs])
        for ax in axes:
            ax.set_ylim(y_min, y_max)
            ax.set_xlim(x_min, x_max)
        
        # Hide any unused subplots
        for j in range(idx + 1, len(axes)):
            fig.delaxes(axes[j])
        
        # Add a global legend for all fuels at the top
        fuel_handles = [
            mpatches.Patch(facecolor='white', edgecolor='k', label=fuel, hatch=fuel_hatch_map[fuel])
            for fuel in fuels
        ]
        fig.legend(
            handles=fuel_handles,
            title="Fuel", labels=fuels,
            loc='upper center', bbox_to_anchor=(0.5, 1.05),
            ncol=min(len(fuel_handles), 5), frameon=False, handleheight=2.0, handlelength=3.0
        )
        plt.tight_layout()
        plt.show()