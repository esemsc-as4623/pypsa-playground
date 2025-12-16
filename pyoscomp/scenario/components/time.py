import pandas as pd
from .base import ScenarioComponent

class TimeComponent(ScenarioComponent):
    def __init__(self, scenario_dir):
        super().__init__(scenario_dir)
        self.years = []
        # Store definitions to calculate derived parameters later
        self.seasons = {} 
        self.daytypes = {}
        self.brackets = {}

    def process(self, **kwargs):
        self.process_years(kwargs.get("years"))
        self.process_time_structure(
            kwargs.get("seasons", {"Yearly": 1}),
            kwargs.get("daytypes", {"Day": 1}),
            kwargs.get("brackets", {"Avg": 1})
        )

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
        Generates a complex time structure with specific weights and custom conversion factors.
        
        :param seasons_config: dict {Name: Fraction_of_Year} (e.g., Winter: 0.25)
        :param daytypes_config: dict {Name: Fraction_of_Season} (e.g., PeakDay: 0.01)
        :param brackets_config: dict {Name: Fraction_of_Day} (e.g., EveningPeak: 0.10)
        """
        if not self.years:
            raise ValueError("Years must be defined before defining time structure.")

        # 1. Normalize Inputs to ensure they sum to 1.0 (Safety check)
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
        
        # Store conversion data
        map_ls = [] # Slice -> Season
        map_ld = [] # Slice -> DayType
        map_lh = [] # Slice -> Bracket

        # Calculate YearSplit and DaySplit
        year_split_rows = []
        day_split_rows = []
        
        for s, s_val in s_fracs.items():
            for d, d_val in d_fracs.items():
                for b, b_val in b_fracs.items():
                    ts_name = f"{s}_{d}_{b}"
                    timeslice_data.append(ts_name)

                    # Create Mapping (Conversion) records
                    # Format: (Timeslice, Parent, Value)
                    # We write 1 for match. OSeMOSYS implies 0 otherwise (usually sparse).
                    map_ls.append({"TIMESLICE": ts_name, "SEASON": s, "VALUE": 1})
                    map_ld.append({"TIMESLICE": ts_name, "DAYTYPE": d, "VALUE": 1})
                    map_lh.append({"TIMESLICE": ts_name, "DAILYTIMEBRACKET": b, "VALUE": 1})

                    # Calculate YearSplit (The fraction of the year this slice represents)
                    # Fraction = SeasonFrac * DayTypeFrac * BracketFrac
                    total_frac = s_val * d_val * b_val
                    
                    # Apply to every modeled year
                    for y in self.years:
                        year_split_rows.append({
                            "TIMESLICE": ts_name,
                            "YEAR": y,
                            "VALUE": round(total_frac, 6)
                        })

                # Calculate DaySplit (Fraction of Day)
                # Note: This is usually just the bracket fraction, defined per year
                for b, b_val in b_fracs.items():
                    for y in self.years:
                        day_split_rows.append({
                            "DAILYTIMEBRACKET": b,
                            "YEAR": y,
                            "VALUE": round(b_val, 6)
                        })

        # 4. Write Sets and Maps
        self.write_csv("TIMESLICE.csv", timeslice_data)
        self.write_dataframe("Conversionls.csv", pd.DataFrame(map_ls))
        self.write_dataframe("Conversionld.csv", pd.DataFrame(map_ld))
        self.write_dataframe("Conversionlh.csv", pd.DataFrame(map_lh))
        self.write_dataframe("YearSplit.csv", pd.DataFrame(year_split_rows))
        self.write_dataframe("DaySplit.csv", pd.DataFrame(day_split_rows).drop_duplicates())

        # 5. DaysInDayType (The number of days a specific DayType occurs in a Season)
        # Logic: 365 * Fraction_Season * Fraction_DayType
        didt_rows = []
        for s, s_val in s_fracs.items():
            for d, d_val in d_fracs.items():
                days = 365.0 * s_val * d_val
                for y in self.years:
                    didt_rows.append({
                        "SEASON": s,
                        "DAYTYPE": d,
                        "YEAR": y,
                        "VALUE": round(days, 4)
                    })
        self.write_dataframe("DaysInDayType.csv", pd.DataFrame(didt_rows))

    def _normalize(self, data: dict):
        total = sum(data.values())
        return {k: v / total for k, v in data.items()} if total > 0 else data
    
    def visualize_timeslices(self):
        """
        Creates a publication-ready visualization of the timeslice structure.
        Features:
        - Broken Bar Chart logic
        - Colorblind-friendly palette + Textures
        - Annotations for duration (Days) and Intensity (Stress)
        """
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches
        import pandas as pd

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
            ys = pd.read_csv(f"{self.scenario_dir}/YearSplit.csv")
            try: 
                didt = pd.read_csv(f"{self.scenario_dir}/DaysInDayType.csv")
                didt['key'] = didt['SEASON'] + "_" + didt['DAYTYPE']
                days_lookup = didt.groupby('key')['VALUE'].mean().to_dict()
            except: days_lookup = {}
            
            cls = pd.read_csv(f"{self.scenario_dir}/Conversionls.csv")
            cld = pd.read_csv(f"{self.scenario_dir}/Conversionld.csv")
            
            slice_map = {}
            for _, row in cls.iterrows():
                slice_map.setdefault(row['TIMESLICE'], {})['Season'] = row['SEASON']
            for _, row in cld.iterrows():
                slice_map.setdefault(row['TIMESLICE'], {})['DayType'] = row['DAYTYPE']

        except FileNotFoundError:
            print("Error: Required CSVs not found.")
            return

        rep_year = ys['YEAR'].min()
        ys = ys[ys['YEAR'] == rep_year]

        # --- Process Data ---
        data = []
        seasons = []
        daytypes = set()

        for _, row in ys.iterrows():
            ts = row['TIMESLICE']
            duration = row['VALUE']
            meta = slice_map.get(ts, {})
            season = meta.get('Season', 'Unknown')
            daytype = meta.get('DayType', 'Unknown')

            if season not in seasons: seasons.append(season)
            daytypes.add(daytype)
            
            data.append({"ts": ts, "season": season, "daytype": daytype, "duration": duration})

        sorted_daytypes = sorted(list(daytypes))
        dt_style_map = {dt: {'color': CB_PALETTE[i % 7], 'hatch': HATCHES[i % 7]} 
                        for i, dt in enumerate(sorted_daytypes)}

        season_totals = {}
        for item in data:
            season_totals[item['season']] = season_totals.get(item['season'], 0) + item['duration']

        # --- Plotting ---
        fig, ax = plt.subplots(figsize=(16, 8))
        season_cursors = {s: 0.0 for s in seasons}
        label_tracking = {} 

        bar_height = 0.6

        for item in data:
            s, d = item['season'], item['daytype']
            
            total_s_dur = season_totals.get(s, 1)
            rel_width = item['duration'] / total_s_dur
            x_start = season_cursors[s]
            y_center = seasons.index(s)
            
            rect = patches.Rectangle(
                (x_start, y_center - (bar_height/2)), rel_width, bar_height,
                facecolor=dt_style_map[d]['color'], hatch=dt_style_map[d]['hatch'],
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
        
        # Italic, Larger Axis Label
        ax.set_xlabel("Proportion of Season Time", fontsize=16, fontstyle='italic', labelpad=15)
        
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.tick_params(axis='y', length=0)
        
        # Larger Legend
        legend_handles = [patches.Patch(facecolor=dt_style_map[dt]['color'], 
                          hatch=dt_style_map[dt]['hatch'], label=dt, edgecolor='black') 
                          for dt in sorted_daytypes]
            
        ax.legend(handles=legend_handles, title="Day Types", loc='upper center', 
                  bbox_to_anchor=(0.5, -0.15), ncol=len(daytypes), frameon=False,
                  fontsize=14, title_fontsize=16)

        plt.tight_layout()
        plt.show()