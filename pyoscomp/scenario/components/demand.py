import pandas as pd
import numpy as np
import os

from .base import ScenarioComponent

class DemandComponent(ScenarioComponent):
    def __init__(self, scenario_dir):
        super().__init__(scenario_dir)
        # Storage
        self.annual_demand_data = []      # List of dicts
        self.profile_demand_data = []     # List of dicts
        self.accumulated_demand_data = [] # List of dicts
        
        # Tracking
        self.defined_fuels = set()        # (Region, Fuel)
        self.profile_assignments = {}     # (Region, Fuel) -> Profile Name/Type

    # ==========================================================================
    # 1. USER INPUT METHODS
    # ==========================================================================

    def add_annual_demand(self, region, fuel, model_years, trajectory: dict,
                          trend_function=None, interpolation: str='step'):
        """
        Define annual demand volume with validation and extrapolation.
        """
        self.defined_fuels.add((region, fuel))

        # --- VALIDATION: Non-Negative Check ---
        # CAGR and Energy models generally fail with negative demand
        for y, val in trajectory.items():
            if val < 0:
                raise ValueError(f"Demand cannot be negative. Found {val} in {y} for {region}-{fuel}")

        # --- PATH A: Function Based ---
        if trend_function:
            for y in model_years:
                val = trajectory.get(y, trend_function(y))
                if val < 0: raise ValueError(f"Trend function produced negative demand for {y}")
                
                self.annual_demand_data.append({
                    "REGION": region, "FUEL": fuel, "YEAR": y, "VALUE": round(val, 4)
                })

        # --- PATH B: Trajectory Based ---
        else:
            sorted_years = sorted(trajectory.keys())
            if not sorted_years: return
            
            # Interpolate
            for i in range(len(sorted_years) - 1):
                y_start = sorted_years[i]
                y_end = sorted_years[i+1]
                val_start = trajectory[y_start]
                val_end = trajectory[y_end]
                years_range = list(range(y_start, y_end))
                
                if interpolation == 'step':
                    values = [val_start] * len(years_range)
                elif interpolation == 'cagr':
                    if val_start == 0:
                         # Handle 0 start for CAGR (mathematically undefined, fallback to linear or 0)
                         values = np.linspace(val_start, val_end, len(years_range) + 1)[:-1]
                    else:
                        steps = y_end - y_start
                        r = (val_end / val_start) ** (1 / steps) - 1
                        values = [val_start * ((1 + r) ** n) for n in range(len(years_range))]
                else: # Linear
                    values = np.linspace(val_start, val_end, len(years_range) + 1)[:-1]

                for y, val in zip(years_range, values):
                    self.annual_demand_data.append({
                        "REGION": region, "FUEL": fuel, "YEAR": y, "VALUE": round(val, 4)
                    })

            # Final Point
            last_yr = sorted_years[-1]
            last_val = trajectory[last_yr]
            self.annual_demand_data.append({
                "REGION": region, "FUEL": fuel, "YEAR": last_yr, "VALUE": round(last_val, 4)
            })

            # Extrapolate
            remaining_years = [y for y in model_years if y > last_yr]
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
                    # Validate Extrapolation didn't go negative
                    if val < 0: val = 0 
                    self.annual_demand_data.append({
                        "REGION": region, "FUEL": fuel, "YEAR": y, "VALUE": round(val, 4)
                    })

    def add_flexible_demand(self, region, fuel, year, value):
        self.accumulated_demand_data.append({
            "REGION": region, "FUEL": fuel, "YEAR": year, "VALUE": value
        })

    def set_profile(self, region, fuel, timeslice_weights=None, 
                    season_weights=None, day_weights=None, hourly_weights=None):
        if timeslice_weights:
            self.profile_assignments[(region, fuel)] = {
                "type": "custom", "custom": timeslice_weights
            }
            return

        if season_weights or day_weights or hourly_weights:
            self.profile_assignments[(region, fuel)] = {
                "type": "weighted",
                "season_w": season_weights, "day_w": day_weights, "hour_w": hourly_weights
            }
            return

        self.profile_assignments[(region, fuel)] = {"type": "flat"}

    # ==========================================================================
    # 2. PROCESSING
    # ==========================================================================

    def process(self, model_years):
        """
        Orchestrator: Loads Dependencies -> Calculates Logic -> Writes Output.
        """
        # 1. Load Dependency
        try:
            ys_path = os.path.join(self.scenario_dir, "YearSplit.csv")
            year_split_df = pd.read_csv(ys_path)
        except FileNotFoundError:
            print("WARNING: YearSplit.csv not found. Profiles will default to flat/1.0.")
            year_split_df = pd.DataFrame()

        # 2. Pure Logic Calculation
        self.profile_demand_data = self._generate_all_profiles(year_split_df, model_years)

        # 3. Write CSVs
        self._write_outputs(model_years)

    # ==========================================================================
    # 3. PURE LOGIC GENERATORS
    # ==========================================================================

    def _generate_all_profiles(self, year_split_df, model_years):
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
                raw_rows = self._calc_custom_profile(region, fuel, assignment["custom"], model_years)
            
            elif p_type == "weighted" and not year_split_df.empty:
                raw_rows = self._calc_weighted_profile(
                    region, fuel, year_split_df, model_years,
                    assignment.get("season_w"), assignment.get("day_w"), assignment.get("hour_w")
                )
            
            else: # Flat (Default)
                if not year_split_df.empty:
                    raw_rows = self._calc_flat_profile(region, fuel, year_split_df, model_years)
                else:
                    # Emergency fallback if no YearSplit
                    for y in model_years:
                        raw_rows.append({
                            "REGION": region, "FUEL": fuel, "TIMESLICE": "Yearly", 
                            "YEAR": y, "VALUE": 1.0
                        })

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
        if total == 0: return []

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
        """
        if not rows: return []
        
        df = pd.DataFrame(rows)
        
        # 1. Group by Year (Region/Fuel are constant in this batch)
        # We calculate the sum of VALUE
        sums = df.groupby('YEAR')['VALUE'].sum()
        
        # 2. Iterate through years to check and fix
        for year, total in sums.items():
            if not np.isclose(total, 1.0, atol=1e-9):
                residual = 1.0 - total
                
                # Identify the rows for this year
                mask = df['YEAR'] == year
                
                # Find the index of the largest value (to minimize relative distortion)
                # We use .idxmax() on the subset
                idx_to_fix = df.loc[mask, 'VALUE'].idxmax()
                
                # Apply fix
                df.at[idx_to_fix, 'VALUE'] += residual
                
                # Force rounding to clean up float artifacts
                df.loc[mask, 'VALUE'] = df.loc[mask, 'VALUE'].round(9)

        return df.to_dict('records')

    # ==========================================================================
    # 4. OUTPUT & VISUALIZATION
    # ==========================================================================

    def _write_outputs(self, model_years):
        # 1. Annual
        df_annual = pd.DataFrame(self.annual_demand_data)
        if not df_annual.empty:
            df_annual = df_annual[df_annual['YEAR'].isin(model_years)]
            df_annual = df_annual.sort_values(by=["REGION", "FUEL", "YEAR"])
            self.write_dataframe("SpecifiedAnnualDemand.csv", df_annual)
        else:
            self.write_dataframe("SpecifiedAnnualDemand.csv", 
                                 pd.DataFrame(columns=["REGION", "FUEL", "YEAR", "VALUE"]))

        # 2. Profile
        df_profile = pd.DataFrame(self.profile_demand_data)
        if not df_profile.empty:
            df_profile = df_profile[df_profile['YEAR'].isin(model_years)]
            # Check summation one last time (optional, as we fixed it logic)
            # self._validate_profiles(df_profile) 
            df_profile = df_profile.sort_values(by=["REGION", "FUEL", "TIMESLICE", "YEAR"])
            self.write_dataframe("SpecifiedDemandProfile.csv", df_profile)
        else:
            self.write_dataframe("SpecifiedDemandProfile.csv", 
                                 pd.DataFrame(columns=["REGION", "FUEL", "TIMESLICE", "YEAR", "VALUE"]))

        # 3. Accumulated
        df_accum = pd.DataFrame(self.accumulated_demand_data)
        if not df_accum.empty:
            df_accum = df_accum[df_accum['YEAR'].isin(model_years)]
            df_accum = df_accum.sort_values(by=["REGION", "FUEL", "YEAR"])
            self.write_dataframe("AccumulatedAnnualDemand.csv", df_accum)
        else:
            self.write_dataframe("AccumulatedAnnualDemand.csv", 
                                 pd.DataFrame(columns=["REGION", "FUEL", "YEAR", "VALUE"]))

    def visualize_demand(self, region, fuel):
        import matplotlib.pyplot as plt
        import numpy as np
        
        # --- 1. DATA PREPARATION ---
        if (region, fuel) not in self.defined_fuels:
            print(f"Error: No demand defined for {region} - {fuel}")
            return

        df_annual = pd.DataFrame(self.annual_demand_data)
        if df_annual.empty: return
        df_annual = df_annual[(df_annual['REGION'] == region) & (df_annual['FUEL'] == fuel)]
        
        try:
            ys_path = os.path.join(self.scenario_dir, "YearSplit.csv")
            year_split_df = pd.read_csv(ys_path)
            
            original_defined = self.defined_fuels
            self.defined_fuels = {(region, fuel)}
            
            years = sorted(df_annual['YEAR'].unique())
            profile_rows = self._generate_all_profiles(year_split_df, years)
            
            self.defined_fuels = original_defined
            df_profile = pd.DataFrame(profile_rows)
            
        except Exception as e:
            print(f"Visualization error: {e}")
            return

        merged = pd.merge(df_annual, df_profile, on='YEAR')
        merged['ABS_VALUE'] = merged['VALUE_x'] * merged['VALUE_y'] 
        
        # Pivot & Sort
        plot_data = merged.pivot(index='YEAR', columns='TIMESLICE', values='ABS_VALUE')
        plot_data = plot_data.reindex(sorted(plot_data.columns), axis=1)

        # --- 2. STYLING SETUP ---
        # Wong Palette (Colorblind friendly)
        CB_PALETTE = ['#E69F00', '#56B4E9', '#009E73', '#F0E442', '#0072B2', '#D55E00', '#CC79A7']
        # Textures for DayTypes
        HATCHES = ['', '///', '..', 'xxx', '++', 'OO']
        # Alphas for Brackets (1.0 = Solid, 0.5 = Faded)
        # We cycle logic: Bright, Dim, Bright, Dim...
        ALPHAS = [1.0, 0.55, 0.85, 0.4]

        timeslices = plot_data.columns
        unique_seasons = []
        unique_daytypes = []
        unique_brackets = []
        
        ts_meta = {} 
        
        for ts in timeslices:
            parts = ts.split('_')
            s = parts[0] if len(parts) > 0 else "Unknown"
            d = parts[1] if len(parts) > 1 else "Unknown"
            b = parts[2] if len(parts) > 2 else "Unknown"
            
            if s not in unique_seasons: unique_seasons.append(s)
            if d not in unique_daytypes: unique_daytypes.append(d)
            if b not in unique_brackets: unique_brackets.append(b)
            
            ts_meta[ts] = {'season': s, 'daytype': d, 'bracket': b}

        # Create Mappers
        season_color_map = {s: CB_PALETTE[i % len(CB_PALETTE)] for i, s in enumerate(unique_seasons)}
        daytype_hatch_map = {d: HATCHES[i % len(HATCHES)] for i, d in enumerate(unique_daytypes)}
        bracket_alpha_map = {b: ALPHAS[i % len(ALPHAS)] for i, b in enumerate(unique_brackets)}

        # --- 3. PLOTTING ---
        fig, ax = plt.subplots(figsize=(12, 7))
        
        bottoms = np.zeros(len(plot_data))
        years_x = plot_data.index.astype(str)

        for ts in timeslices:
            values = plot_data[ts].fillna(0).values
            meta = ts_meta[ts]
            
            color = season_color_map[meta['season']]
            hatch = daytype_hatch_map[meta['daytype']]
            alpha = bracket_alpha_map[meta['bracket']]
            
            # Plot bar segment
            # Note: We set the edge alpha to 1.0 (opaque) so the border remains crisp 
            # even if the fill is faded (alpha)
            bar = ax.bar(
                years_x, values, bottom=bottoms, 
                label=ts, color=color, hatch=hatch, alpha=alpha,
                edgecolor=(0,0,0,1), linewidth=0.5
            )
            
            bottoms += values

        # --- 4. FORMATTING ---
        ax.set_ylabel("Energy Demand (Model Units)")
        ax.set_xlabel("Year")
        ax.set_title(f"Demand Composition: {region} - {fuel}")
        
        # Legend
        if len(timeslices) > 10:
            ax.legend(title="Timeslice", bbox_to_anchor=(1.05, 1), loc='upper left')
        else:
            ax.legend(title="Timeslice", loc='best')

        plt.grid(axis='y', linestyle='--', alpha=0.3)
        plt.tight_layout()
        plt.show()