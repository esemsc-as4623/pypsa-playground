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
        self.yearsplit_df, self.years, self.regions = self.check_prerequisites()

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
        yearsplit = self.read_csv("YearSplit.csv", ["TIMESLICE", "YEAR", "VALUE"])
        years = self.read_csv("YEAR.csv", ["YEAR"])["YEAR"].tolist()
        if yearsplit.empty or not years:
            raise AttributeError("Time component is not defined for this scenario.")

        # Check Topology Component
        regions = self.read_csv("REGION.csv", ["REGION"])["REGION"].tolist()
        if not regions:
            raise AttributeError("Topology component is not defined for this scenario.")
        
        return yearsplit, years, regions

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
        if region not in self.regions:
            raise ValueError(f"Region '{region}' not defined in scenario. Set topology first.")
        self.defined_fuels.add((region, fuel))

        # --- VALIDATION: Trajectory Provided, Non-negative, Deduplicated ---
        if len(trajectory) == 0:
            raise ValueError(f"No trajectory points provided for {region}-{fuel}.")
        for y, val in trajectory.items():
            if val < 0:
                raise ValueError(f"Demand cannot be negative. Found {val} in model year {y} for {region}-{fuel}")
            
        # --- VALIDATION: Interpolation ---
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
                records.append({"REGION": region, "FUEL": fuel, "YEAR": y, "VALUE": round(val, 4)})
        
        # --- PATH B: Interpolation Based ---
        else:
            sorted_years = sorted(trajectory.keys())
            if not sorted_years:
                raise ValueError(f"No trajectory points provided for {region}-{fuel}.")
            
            # Interpolate
            for i in range(len(sorted_years) - 1):
                y_start = sorted_years[i]
                y_end = sorted_years[i+1]
                years_to_fill = [y for y in self.years if y_start <= y < y_end]
                val_start = trajectory[y_start]
                val_end = trajectory[y_end]
                
                if interpolation == 'step':
                    values = [val_start] * len(years_to_fill)
                elif interpolation == 'cagr':
                    if val_start == 0:
                         # Handle 0 start for CAGR (mathematically undefined, fallback to linear or 0)
                         values = np.linspace(val_start, val_end, len(years_to_fill) + 1)[:-1]
                    else:
                        steps = y_end - y_start
                        r = (val_end / val_start) ** (1 / steps) - 1
                        values = [val_start * ((1 + r) ** (y - y_start)) for y in years_to_fill]
                else: # Linear
                    values = np.linspace(val_start, val_end, len(years_to_fill) + 1)[:-1]

                for y, val in zip(years_to_fill, values):
                    records.append({
                        "REGION": region, "FUEL": fuel, "YEAR": y, "VALUE": round(val, 4)
                    })

            # Final Point
            last_yr = sorted_years[-1]
            last_val = trajectory[last_yr]
            records.append({
                "REGION": region, "FUEL": fuel, "YEAR": last_yr, "VALUE": round(last_val, 4)
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
                else:
                    extrap_values = [last_val] * len(remaining_years)

                for y, val in zip(remaining_years, extrap_values):
                    # Validate extrapolation didn't go negative
                    if val < 0:
                        val = 0
                    records.append({"REGION": region, "FUEL": fuel, "YEAR": y, "VALUE": round(val, 4)})
        
        # Append to DataFrame
        if not records:
            return
        df_new = pd.DataFrame(records)

        if self.annual_demand_df.empty:
            self.annual_demand_df = df_new
        else:
            # Merge on REGION, FUEL, YEAR, giving priority to new data
            combined = pd.concat([self.annual_demand_df, df_new], ignore_index=True)
            # Keep the last occurrence (i.e., new data overwrites old)
            self.annual_demand_df = combined.drop_duplicates(subset=["REGION", "FUEL", "YEAR"], keep="last").reset_index(drop=True)

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

        df_new = pd.DataFrame([{"REGION": region, "FUEL": fuel, "YEAR": year, "VALUE": value}])

        if self.accumulated_demand_df.empty:
            self.accumulated_demand_df = df_new
        else:
            # Merge on REGION, FUEL, YEAR, giving priority to new data
            combined = pd.concat([self.accumulated_demand_df, df_new], ignore_index=True)
            # Keep the last occurrence (i.e., new data overwrites old)
            self.accumulated_demand_df = combined.drop_duplicates(subset=["REGION", "FUEL", "YEAR"], keep="last").reset_index(drop=True)

    def set_subannual_profile(self, region, fuel, year=None, timeslice_factor=None, 
                              season_factor=None, day_factor=None, hourly_factor=None):
        """
        Set the demand profile for a given region, fuel, and optionally year.
        Supports direct timeslice factors or hierarchical (season, day, hour) factors.
        Factor dictionaries should map timeslice/season/daytype/dailytimebracket names to their respective factors.
        If both timeslice factors and is provided, it takes precendence.
        If multiple factor dictionaries are provided, hierarchical weighting is used.
        Missing entries default to YearSplit.csv values, i.e. the proportion of the year that a timeslice represents.

        :param region: str, Region where demand applies
        :param fuel: str, Name of the fuel/demand type
        :param year: int or None, Model year, if not specified applies to all years
        :param timeslice_factor: dict or None, {timeslice: factor}
        :param season_factor: dict or None, {season: factor}
        :param day_factor: dict or None, {daytype: factor}
        :param hourly_factor: dict or None, {dailytimebracket: factor}

        Example::
            demand.set_subannual_profile('Region1', 'ELEC', timeslice_factor={'Winter_Weekday_Day': 0.6, ...})
            demand.set_subannual_profile('Region1', 'ELEC', season_factor={'Winter': 1.2, 'Summer': 0.8}, hourly_factor={'Day': 1.5, 'Night': 0.5})
        """

        if timeslice_factor:
            # Validate timeslice factors and fill missing with YearSplit proportions
            timeslice_factor = self._check_timeslice_factors(timeslice_factor, year)
            total = sum(timeslice_factor.values())
            if total <= 0:
                print(f"Warning: Timeslice factors for {region}, {fuel} in year {year} sum to {total}. Using flat profile.")
                self.profile_assignments[(region, fuel)] = {"type": "flat"}
            else:
                norm_weights = {k: v/total for k, v in timeslice_factor.items()}
                self.profile_assignments[(region, fuel)] = {"type": "custom", "weights": norm_weights}
            return

        if season_factor or day_factor or hourly_factor:
            # Validate hierarchical factors and fill missing with YearSplit proportions

            self.profile_assignments[(region, fuel)] = {
                "type": "weighted",
                "season_w": season_factor, "day_w": day_factor, "hour_w": hourly_factor
            }
            return

        print(f"Setting flat profile for {region}, {fuel}.")
        self.profile_assignments[(region, fuel)] = {"type": "flat"}

    # === Processing ===
    def process(self):
        """
        Generate the full demand profile for each (region, fuel, year, timeslice) combination, normalized so that the sum matches the annual demand.
        """
        profile_rows = self._generate_all_profiles()
        self.profile_demand_df = pd.DataFrame(profile_rows)

    # === Internal Logic Helpers ===
    def _check_timeslice_factors(self, factor_dict, year):
        """
        Validates timeslice factors against YearSplit.csv.
        Fills missing timeslices with their YearSplit proportions.
        Returns a complete dict of timeslice factors.
        """
        pass

    def _generate_profile(self, region, fuel, year):
        """
        Generates the demand profile for a specific (region, fuel, year) combination.
        Returns a list of dictionaries with TIMESLICE and VALUE keys.

        :param region: str, Region where the demand applies
        :param fuel: str, Name of the fuel/demand type
        :param year: int, Model year
        """
        pass

    def _generate_all_profiles(self):
        """
        Iterates through defined fuels and calculates profile rows.
        Returns a list of dictionaries.
        """
        all_profile_rows = []

        for region, fuel in self.defined_fuels:
            assignment = self.profile_assignments.get((region, fuel), {"type": "flat"})
            p_type = assignment["type"]
            
            raw_rows = []

            # A. Strategy Pattern for Calculation
            if p_type == "custom":
                raw_rows = self._calc_custom_profile(region, fuel, assignment["weights"], self.years)
            
            elif p_type == "weighted":
                raw_rows = self._calc_weighted_profile(
                    region, fuel, self.yearsplit_df, self.years,
                    assignment.get("season_w"), assignment.get("day_w"), assignment.get("hour_w")
                )
            
            else: # Flat (Default)
                raw_rows = self._calc_flat_profile(region, fuel, self.yearsplit_df, self.years)

            # B. Normalization Step (Strict Summation to 1.0)
            cleaned_rows = self._normalize_and_fix_residuals(raw_rows)
            all_profile_rows.extend(cleaned_rows)
            
        return all_profile_rows

    def _calc_flat_profile(self, region, fuel, year_split_df, years):
        rows = []
        for y in years:
            ys_subset = year_split_df[year_split_df['YEAR'] == y]
            if ys_subset.empty:
                ys_subset = year_split_df[year_split_df['YEAR'] == year_split_df['YEAR'].min()]

            for _, row in ys_subset.iterrows():
                rows.append({
                    "REGION": region, "FUEL": fuel,
                    "TIMESLICE": row['TIMESLICE'], "YEAR": y,
                    "VALUE": row['VALUE'] 
                })
        return rows

    def _calc_custom_profile(self, region, fuel, profile_dict, years):
        rows = []
        total = sum(profile_dict.values())
        if total == 0:
            return []

        for y in years:
            for ts, val in profile_dict.items():
                rows.append({
                    "REGION": region, "FUEL": fuel,
                    "TIMESLICE": ts, "YEAR": y,
                    "VALUE": val / total
                })
        return rows

    def _calc_weighted_profile(self, region, fuel, year_split_df, years, s_w, d_w, h_w):
        rows = []
        s_w = s_w or {}
        d_w = d_w or {}
        h_w = h_w or {}

        # Representative year for shape
        rep_year = year_split_df['YEAR'].min()
        unique_slices = year_split_df[year_split_df['YEAR'] == rep_year][['TIMESLICE', 'VALUE']]
        
        slice_scores = {}
        total_score = 0
        
        for _, row in unique_slices.iterrows():
            ts = row['TIMESLICE']
            duration_frac = row['VALUE']
            
            parts = ts.split('_')
            s = parts[0] if len(parts) > 0 else "Unknown"
            d = parts[1] if len(parts) > 1 else "Unknown"
            h = parts[2] if len(parts) > 2 else "Unknown"
            
            weight = s_w.get(s, 1.0) * d_w.get(d, 1.0) * h_w.get(h, 1.0)
            score = weight * duration_frac
            slice_scores[ts] = score
            total_score += score

        for y in years:
            for ts, score in slice_scores.items():
                final_val = score / total_score if total_score > 0 else 0
                rows.append({
                    "REGION": region, "FUEL": fuel,
                    "TIMESLICE": ts, "YEAR": y,
                    "VALUE": final_val
                })
        return rows

    def _normalize_and_fix_residuals(self, rows):
        """
        Ensures the sum of profiles for every (Region, Fuel, Year) is EXACTLY 1.0.
        Fixes floating point errors (e.g., 0.9999999) by adjusting the largest slice.
        Prints a message if any correction is made.
        """
        if not rows:
            return []
        df = pd.DataFrame(rows)
        # Group by (REGION, FUEL, YEAR) for full generality
        group_cols = [col for col in ["REGION", "FUEL", "YEAR"] if col in df.columns]
        if not group_cols:
            return rows
        sums = df.groupby(group_cols)['VALUE'].sum()
        for idx, total in sums.items():
            if not np.isclose(total, 1.0, atol=1e-9):
                residual = 1.0 - total
                if isinstance(idx, tuple):
                    mask = (df[group_cols[0]] == idx[0]) & (df[group_cols[1]] == idx[1]) & (df[group_cols[2]] == idx[2])
                else:
                    mask = (df[group_cols[0]] == idx)
                idx_to_fix = df.loc[mask, 'VALUE'].idxmax()
                df.at[idx_to_fix, 'VALUE'] += residual
                df.loc[mask, 'VALUE'] = df.loc[mask, 'VALUE'].round(9)
                print(f"Auto-corrected demand profile for {idx}: sum was {total}, fixed residual {residual}.")
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
        if self.profile_demand_df.empty:
            print("No demand profile data to plot.")
            return
        if (region, fuel) not in self.defined_fuels:
            print(f"Error: No demand defined for {region} - {fuel}")
            return

        df_annual = self.annual_demand_df[(self.annual_demand_df['REGION'] == region) &
                                          (self.annual_demand_df['FUEL'] == fuel)]
        
        try:
            from pyoscomp.scenario.components.time import TimeComponent
            slice_map = TimeComponent.load_time_axis(self)['slice_map']
        except Exception as e:
            print(f"Could not load time axis: {e}")
            return
        
        # Filter profiles to only the selected region and fuel
        original_defined = self.defined_fuels
        self.defined_fuels = {(region, fuel)}
        profile_rows = self._generate_all_profiles()
        df_profile = pd.DataFrame(profile_rows)
        # Restore global defined fuels
        self.defined_fuels = original_defined

        # --- Process Data ---
        merged = pd.merge(df_annual, df_profile, on='YEAR')
        merged['ABS_VALUE'] = merged['VALUE_x'] * merged['VALUE_y']
        
        plot_data = merged.pivot(index='YEAR', columns='TIMESLICE', values='ABS_VALUE')
        plot_data = plot_data.reindex(sorted(plot_data.columns), axis=1)
        
        data = []
        seasons = set()
        daytypes = set()
        timebrackets = set()

        for ts in plot_data.columns:
            meta = slice_map.get(ts, {})
            season = meta.get('Season', 'Unknown')
            daytype = meta.get('DayType', 'Unknown')
            timebracket = meta.get('DailyTimeBracket', 'Unknown')
            
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
        ax.set_xlabel("Year")
        ax.tick_params(axis='x', labelrotation=45)
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

        # --- Styles ---
        CB_PALETTE = ['#56B4E9', '#D55E00', '#009E73', '#F0E442', '#0072B2', '#CC79A7', '#E69F00']
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
        if self.profile_demand_df.empty:
            print("No demand profile data to plot.")
            return
        
        # Get all unique regions and fuels
        regions = sorted(self.profile_demand_df['REGION'].unique())
        fuels = sorted(self.profile_demand_df['FUEL'].unique())
        n_regions = len(regions)

        ncols = 2 if n_regions > 1 else 1
        nrows = (n_regions + ncols - 1) // ncols

        # --- Plotting ---
        fig, axes = plt.subplots(nrows=nrows, ncols=ncols, figsize=(12 * ncols, 7 * nrows))
        if n_regions == 1:
            axes = [axes]
        else:
            axes = axes.flatten()

        # Prepare color cycle for all fuels (consistent across regions)
        fuel_color_map = {fuel: CB_PALETTE[i % len(CB_PALETTE)] for i, fuel in enumerate(fuels)}
        handles = []

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
            colors = [fuel_color_map[fuel] for fuel in fuel_names]
            polys = ax.stackplot(years, y_arrays, labels=fuel_names, colors=colors, alpha=0.8)
            ax.set_title(f"Region: {region}")
            ax.set_xlabel("Year")
            ax.set_ylabel("Total Demand (Model Units)")
            ax.grid(axis='y', linestyle='--', alpha=0.3)
            # Only collect handles for the first subplot (for global legend)
            if idx == 0:
                handles = [plt.Line2D([0], [0], color=fuel_color_map[fuel], lw=6) for fuel in fuel_names]

        # --- Formatting ---
        # Hide any unused subplots
        for j in range(idx + 1, len(axes)):
            fig.delaxes(axes[j])
        # Add a global legend for all fuels at the top
        if handles:
            fig.legend(handles, fuels, loc='upper center', bbox_to_anchor=(0.5, 1.05), ncol=min(len(fuels), 5), title="Fuel")
        plt.tight_layout(rect=[0, 0, 1, 0.97])
        plt.show()
        # Hide any unused subplots
        for j in range(idx + 1, len(axes)):
            fig.delaxes(axes[j])
        plt.tight_layout()
        plt.show()

    # TODO: complete compare_demand method
    @staticmethod
    def compare_demand(scenario1, scenario2, scale="annual", keys=None, rel_tol=1e-6):
        """
        Blueprint for comparing demand between two scenarios.

        Parameters
        ----------
        scenario1 : DemandComponent
            The first scenario instance (already loaded).
        scenario2 : DemandComponent
            The second scenario instance (already loaded).
        compare_type : str
            Type of comparison: "annual" for SpecifiedAnnualDemand, "profile" for SpecifiedDemandProfile,
            or "accumulated" for AccumulatedAnnualDemand.
        keys : list or None
            List of columns to use as join keys (e.g., ["REGION", "FUEL", "YEAR"] for annual,
            ["REGION", "FUEL", "YEAR", "TIMESLICE"] for profile).
            If None, use sensible defaults based on compare_type.
        rel_tol : float
            Relative tolerance for highlighting significant differences.

        Returns
        -------
        diff_df : pd.DataFrame
            DataFrame with columns for keys, values from both scenarios, absolute and relative differences.
            (e.g., REGION, FUEL, YEAR, VALUE_scenario1, VALUE_scenario2, ABS_DIFF, REL_DIFF)
        
        Notes
        -----
        - This method should not modify either scenario.
        - It should handle missing keys gracefully (e.g., fill with NaN or 0).
        - It should be able to highlight where differences exceed rel_tol.
        - Visualization or summary reporting can be added as a follow-up.
        - Example usage:
            diff = DemandComponent.compare_demand(scen1, scen2, scale="annual")
        """
        # 1. Select the appropriate DataFrame from each scenario based on compare_type
        #    (e.g., scenario1.annual_demand_df, scenario2.profile_demand_df, etc.)
        # 2. Determine join keys if not provided.
        # 3. Merge the two DataFrames on the join keys.
        # 4. Compute absolute and relative differences.
        # 5. Optionally, flag or filter rows where difference exceeds rel_tol.
        # 6. Return the resulting DataFrame for further analysis or visualization.
        pass  # Implementation to be added

# TODO: Validation and Error Handling
# a. Input Validation
# Check for missing or invalid regions, fuels, years, timeslices before adding or processing demand. Raise clear errors if any are missing or not defined in the scenario.
# Validate demand values: Ensure all demand values are non-negative and numeric. Warn or error on negative or NaN values.
# Profile normalization: When setting profiles, ensure the sum of weights (for timeslice, season, day, hour) is not zero and is normalized to 1.0. If not, auto-normalize and warn the user.
# b. Consistency Checks
# Annual vs. Profile Consistency: When both annual and profile demand are set, check that the sum of the profile for each (region, fuel, year) matches the annual demand. If not, either auto-scale or raise a warning.
# Timeslice completeness: Ensure that all timeslices for each year are covered in the profile. If not, fill missing timeslices with zero or raise an error.
# c. Edge Case Handling
# Partial years/timeslices: If a user provides demand for only a subset of years or timeslices, fill missing entries with zeros or provide a clear error.
# Zero demand: Handle zero-demand years/timeslices gracefully (do not drop them from output).
# Multiple profiles: If a user sets multiple profiles for the same (region, fuel, year), decide whether to overwrite, sum, or error, and document this behavior.