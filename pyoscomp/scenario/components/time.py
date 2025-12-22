# pyoscomp/scenario/components/time.py

"""
Time component for scenario building in PyPSA-OSeMOSYS Comparison Framework.
Note: This component handles the definition of the temporal resolution of the model.
Temporal resolution includes Years and Timeslices in OSeMOSYS terminology.
Timeslices are combinations of Seasons, DayTypes, and Daily Time Brackets.
Temporal resolution is referred to as Snapshots in PyPSA terminology.
Temporal resolution can be non-uniform, with different slices representing different numbers or fractions of hours.

# TODO: Investment period can have a different temporal resolution than operational period, but this is not currently implemented.
"""
import pandas as pd
import math
import os

from .base import ScenarioComponent

class TimeComponent(ScenarioComponent):
    def __init__(self, scenario_dir):
        super().__init__(scenario_dir)
        self.years = []
        # Constants for physical time validation
        self.HOURS_PER_YEAR = 8760
        self.HOURS_PER_DAY = 24
        self.DAYS_PER_YEAR = 365

    def process(self, years, seasons, daytypes, brackets):
        """
        Executes year and time structure processing.
        
        :return: list of tuples [(Year, Timeslice), ...] in chronological order.
        """
        # 1. Process Years
        self.process_years(years)
        
        # 2. Process Structure (returns ordered list of timeslice names)
        timeslices, slicehours = self.process_time_structure(seasons, daytypes, brackets)
        
        # 3. Generate Master List (Year -> Timeslice chronological order)
        # Iterate Year first, then Timeslices (e.g., YEAR1 TS1, YEAR1 TS2... YEAR2 TS1...)
        master_time_list = []
        for y in self.years:
            for ts in timeslices:
                master_time_list.append((y, ts))
        master_slice_hours = slicehours * len(self.years)
                
        return master_time_list, master_slice_hours

    def process_years(self, years_input):
        """
        Sets up the YEAR set.
        
        :param years_input: 
            list[int] (specific years e.g. [2020, 2025]) 
            OR tuple (start, end, step) e.g. (2020, 2050, 5)
        """
        if isinstance(years_input, (list, set)):
            self.years = sorted(list(years_input))
        elif isinstance(years_input, tuple) and len(years_input) == 3:
            start, end, step = years_input
            self.years = list(range(start, end + 1, step))
        else:
            raise ValueError("years_input must be a list of ints or a tuple (start, end, step).")

        self.write_csv("YEAR.csv", self.years)
        return self.years

    def process_time_structure(self, seasons: dict, daytypes: dict, brackets: dict):
        """
        Generates time structure calculating explicit duration in hours.
        Execute the logic to generate final CSVs.
        
        Recommended Inputs:
        :param seasons: dict {Name: Days} (e.g. Winter: 90) - Should sum to ~365
        :param daytypes: dict {Name: Weight} (e.g. Weekday: 5, Weekend: 2 | e.g. Peak: 1, OffPeak: 3)
        :param brackets: dict {Name: Hours} (e.g. Day: 16, Night: 8) - Should sum to ~24
        """
        if not self.years:
            raise ValueError("Years must be defined before defining time structure.")

        # 1. Convert everything to fractions
        s_fracs = self._normalize(seasons)
        d_fracs = self._normalize(daytypes)
        b_fracs = self._normalize(brackets)

        # 2. Write Sets
        self.write_csv("SEASON.csv", list(seasons.keys()))
        self.write_csv("DAYTYPE.csv", list(daytypes.keys()))
        self.write_csv("DAILYTIMEBRACKET.csv", list(brackets.keys()))

        # 3. Generate TIMESLICES (Cartesian Product)
        # Hierarchy: Season -> DayType -> Bracket
        # Naming Convention: Season_DayType_Bracket
        timeslice_data = []
        timeslice_hours = []
        
        # Store conversion data
        map_ls = [] # Slice -> Season
        map_ld = [] # Slice -> DayType
        map_lh = [] # Slice -> Bracket

        year_split_rows = []
        day_split_rows = []

        for s, s_val in s_fracs.items():
            for d, d_val in d_fracs.items():
                for b, b_val in b_fracs.items():
                    ts_name = f"{s}_{d}_{b}"
                    timeslice_data.append(ts_name)

                    # Standard Mapping
                    map_ls.append({"TIMESLICE": ts_name, "SEASON": s, "VALUE": 1})
                    map_ld.append({"TIMESLICE": ts_name, "DAYTYPE": d, "VALUE": 1})
                    map_lh.append({"TIMESLICE": ts_name, "DAILYTIMEBRACKET": b, "VALUE": 1})

                    # Calculations
                    season_hours = s_val * self.HOURS_PER_YEAR
                    daytype_hours = d_val * season_hours
                    slice_hours = b_val * daytype_hours
                    timeslice_hours.append(slice_hours)

                    # Calculate YearSplit (TimeSlice as a fraction of Year)
                    year_split_frac = slice_hours / self.HOURS_PER_YEAR
                    
                    for y in self.years:
                        year_split_rows.append({
                            "TIMESLICE": ts_name,
                            "YEAR": y,
                            "VALUE": round(year_split_frac, 9) # High precision required
                        })

                        # Calculate DayTypeSplit (DailyTimeBracket as a fraction of DayType)
                        # Should ideally correspond to Hours / 24
                        day_split_rows.append({
                            "DAILYTIMEBRACKET": b,
                            "YEAR": y,
                            "VALUE": round(b_val, 6)
                        })

        # 4. Validation
        if not math.isclose(sum(timeslice_hours), self.HOURS_PER_YEAR, abs_tol=0.1):
            print(f"WARNING: Total calculated time is {sum(timeslice_hours):.4f} hours per year. Please adjust your season/daytype/bracket definitions for better consistency.")

        # 5. Write Files
        self.write_csv("TIMESLICE.csv", timeslice_data)
        self.write_dataframe("Conversionls.csv", pd.DataFrame(map_ls))
        self.write_dataframe("Conversionld.csv", pd.DataFrame(map_ld))
        self.write_dataframe("Conversionlh.csv", pd.DataFrame(map_lh))
        self.write_dataframe("YearSplit.csv", pd.DataFrame(year_split_rows))
        self.write_dataframe("DaySplit.csv", pd.DataFrame(day_split_rows).drop_duplicates())

        # 6. DaysInDayType Calculation
        # Logic: 365 * SeasonFrac * DayTypeFrac
        didt_rows = []
        for s, s_val in s_fracs.items():
            for d, d_val in d_fracs.items():
                days = self.DAYS_PER_YEAR * s_val * d_val
                for y in self.years:
                    didt_rows.append({
                        "SEASON": s,
                        "DAYTYPE": d,
                        "YEAR": y,
                        "VALUE": round(days, 4)
                    })
        self.write_dataframe("DaysInDayType.csv", pd.DataFrame(didt_rows))


        return timeslice_data, timeslice_hours
    
    def _normalize(self, data: dict):
        """Normalizes inputs to sum to 1.0."""
        total = sum(data.values())
        if total == 0:
            return {k: 0 for k in data}
        return {k: v / total for k, v in data.items()}
    
    def visualize(self):
        """
        Creates a visualization of the timeslice structure.
        """
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches

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
        try:
            ys = pd.read_csv(os.path.join(self.scenario_dir, "YearSplit.csv"))
            try: 
                didt = pd.read_csv(os.path.join(self.scenario_dir, "DaysInDayType.csv"))
                didt['key'] = didt['SEASON'] + "_" + didt['DAYTYPE']
                days_lookup = didt.groupby('key')['VALUE'].mean().to_dict()
            except: days_lookup = {}
            
            cls = pd.read_csv(os.path.join(self.scenario_dir, "Conversionls.csv"))
            cld = pd.read_csv(os.path.join(self.scenario_dir, "Conversionld.csv"))
            clh = pd.read_csv(os.path.join(self.scenario_dir, "Conversionlh.csv"))
            
            slice_map = {}
            for _, row in cls.iterrows():
                slice_map.setdefault(row['TIMESLICE'], {})['Season'] = row['SEASON']
            for _, row in cld.iterrows():
                slice_map.setdefault(row['TIMESLICE'], {})['DayType'] = row['DAYTYPE']
            for _, row in clh.iterrows():
                slice_map.setdefault(row['TIMESLICE'], {})['DailyTimeBracket'] = row['DAILYTIMEBRACKET']

        except FileNotFoundError:
            print("Error: Required CSVs not found.")
            return

        rep_year = ys['YEAR'].min()
        ys = ys[ys['YEAR'] == rep_year]

        # --- Process Data ---
        data = []
        seasons = set()
        daytypes = set()
        timebrackets = set()

        for _, row in ys.iterrows():
            ts = row['TIMESLICE']
            duration = row['VALUE']
            meta = slice_map.get(ts, {})
            season = meta.get('Season', 'Unknown')
            daytype = meta.get('DayType', 'Unknown')
            timebracket = meta.get('DailyTimeBracket', 'Unknown')

            seasons.add(season)
            daytypes.add(daytype)
            timebrackets.add(timebracket)
            
            data.append({"ts": ts, "season": season, "daytype": daytype, "duration": duration, "timebracket": timebracket})

        seasons = sorted(list(seasons))
        sorted_daytypes = sorted(list(daytypes))
        sorted_timebrackets = sorted(list(timebrackets))
        
        dt_style_map = {dt: {'color': CB_PALETTE[i % 7]} for i, dt in enumerate(sorted_daytypes)}
        tb_style_map = {tb: {'hatch': HATCHES[i % 7]} for i, tb in enumerate(sorted_timebrackets)}

        season_totals = {}
        for item in data:
            season_totals[item['season']] = season_totals.get(item['season'], 0) + item['duration']

        # --- Plotting ---
        fig, ax = plt.subplots(figsize=(16, 8))
        season_cursors = {s: 0.0 for s in seasons}
        label_tracking = {} 

        bar_height = 0.6

        for item in data:
            s, d, h = item['season'], item['daytype'], item['timebracket']
            
            total_s_dur = season_totals.get(s, 1)
            rel_width = item['duration'] / total_s_dur
            x_start = season_cursors[s]
            y_center = seasons.index(s)
            
            rect = patches.Rectangle(
                (x_start, y_center - (bar_height/2)), rel_width, bar_height,
                facecolor=dt_style_map[d]['color'], hatch=tb_style_map[h]['hatch'],
                edgecolor='white', linewidth=1, alpha=0.9
            )
            ax.add_patch(rect)
            
            # Track for labeling
            if s not in label_tracking: label_tracking[s] = {}
            if d not in label_tracking[s]:
                label_tracking[s][d] = {'start': x_start, 'end': x_start + rel_width}
            else:
                label_tracking[s][d]['end'] = x_start + rel_width
            season_cursors[s] += rel_width

        # --- Annotations ---
        ax.set_yticks(range(len(seasons)))
        ax.set_yticklabels(seasons, fontsize=16)
        
        for s in seasons:
            y_pos = seasons.index(s)
            
            # Toggle for alternating Top/Bottom labels
            label_pos_top = True 
            
            # Sort keys by start time so labels flow left-to-right
            sorted_dts = sorted(label_tracking[s].keys(), key=lambda k: label_tracking[s][k]['start'])

            for dt in sorted_dts:
                coords = label_tracking[s][dt]
                width = coords['end'] - coords['start']
                center_x = coords['start'] + (width / 2)
                day_count = days_lookup.get(f"{s}_{dt}", 0)
                
                # Logic: Is it too small for inside text?
                # Threshold ~0.05 of total width
                if width > 0.05:
                    # LABEL INSIDE
                    ax.text(
                        center_x, y_pos,
                        f"{day_count:.0f} days",
                        ha='center', va='center', 
                        color='black', fontsize=16
                    )
                else:
                    # LABEL OUTSIDE (Alternating)
                    # Calculate Y offset
                    y_offset = (bar_height/2) + 0.15 if label_pos_top else -(bar_height/2) - 0.25
                    
                    label_text = f"{day_count:.1f} days"
                    ax.text(
                        center_x, y_pos + y_offset,
                        label_text,
                        ha='center', va='center',
                        color='black', fontsize=14
                    )
                    
                    # Flip the toggle for the next small block in this row
                    label_pos_top = not label_pos_top

        # --- Formatting ---
        ax.set_xlim(0, 1)
        ax.set_ylim(-0.6, len(seasons) - 0.4)
        
        ax.set_xlabel("Proportion of Season Time", fontsize=16, fontstyle='italic', labelpad=15)
        
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.tick_params(axis='y', length=0)
        
        legend_handles = [patches.Patch(facecolor=dt_style_map[dt]['color'], 
                          label=dt, edgecolor='black') for dt in sorted_daytypes]
            
        leg1 = ax.legend(handles=legend_handles, title="Day Types", loc='upper center', 
                         bbox_to_anchor=(0.5, -0.2), ncol=len(daytypes), frameon=False,
                         fontsize=14, title_fontsize=16)
        ax.add_artist(leg1)
        
        legend_handles = [patches.Patch(facecolor='white', hatch=tb_style_map[tb]['hatch'], 
                          label=tb, edgecolor='black') for tb in sorted_timebrackets]
        
        ax.legend(handles=legend_handles, title="Daily Time Brackets", loc='upper center',
                  bbox_to_anchor=(0.5, -0.4), ncol=len(timebrackets), frameon=False,
                  fontsize=14, title_fontsize=16)

        # Sum of YearSplit values * 8760
        total_fraction = ys['VALUE'].sum()
        total_hours = total_fraction * 8760

        ax.set_title(
            f"Scenario Time Structure\nTotal Duration: {total_hours:,.1f} Hours per Model Year", 
            fontsize=18, pad=20
        )

        plt.tight_layout()
        plt.show()