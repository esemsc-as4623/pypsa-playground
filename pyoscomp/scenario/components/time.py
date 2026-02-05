# pyoscomp/scenario/components/time.py

"""
Time component for scenario building in PyPSA-OSeMOSYS Comparison Framework.
Note: This component handles the definition of the temporal resolution of the model.
Temporal resolution includes Years and Timeslices in OSeMOSYS terminology.
Timeslices are combinations of Seasons, DayTypes, and Daily Time Brackets.
Temporal resolution is referred to as Snapshots in PyPSA terminology.
Temporal resolution can be non-uniform, with different slices representing different numbers or fractions of hours.

# NOTE: OSeMOSYS assumes 365 days per year.
"""
import pandas as pd
import math
import os
from decimal import Decimal, getcontext

from .base import ScenarioComponent

# Set decimal precision for exact arithmetic
getcontext().prec = 28

class TimeComponent(ScenarioComponent):
    """
    Time component for timeslice/snapshot definitions and temporal parameters.
    Handles OSeMOSYS time parameters: years, timeslices, seasons, daytypes, daily time brackets, and conversion tables.

    Prerequisites:
        - None

    Example usage::
        time = TimeComponent(scenario_dir)
        # Define a custom OSeMOSYS-aligned time structure
        years = [2020, 2025, 2030]
        seasons = {"Winter": 90, "Summer": 90, "Shoulder": 185}  # days in each season, should sum to 365
        daytypes = {"Weekday": 5, "Weekend": 2}  # relative weights (e.g., 5 weekdays, 2 weekend days per week)
        brackets = {"Day": 16, "Night": 8}  # hours in each bracket, should sum to 24

        time.add_time_structure(years, seasons, daytypes, brackets)
        time.save()  # Saves all time parameter DataFrames to CSV

        # To load and inspect the generated time structure later:
        time.load()  # Loads all time parameter CSVs
        # ... modify DataFrames as needed ...
        time.save()  # Saves any changes

    CSV Format Expectations:
        - All CSVs must have columns as specified in each method's docstring.
        - See OSeMOSYS.md for parameter definitions.
    """
    def __init__(self, scenario_dir):
        super().__init__(scenario_dir)

        # Operational time parameters
        self.years_df = pd.DataFrame(columns=["VALUE"])
        self.timeslices_df = pd.DataFrame(columns=["VALUE"])
        self.seasons_df = pd.DataFrame(columns=["VALUE"])
        self.daytypes_df = pd.DataFrame(columns=["VALUE"])
        self.brackets_df = pd.DataFrame(columns=["VALUE"])

        self.conversionls_df = pd.DataFrame(columns=["TIMESLICE", "SEASON", "VALUE"])
        self.conversionld_df = pd.DataFrame(columns=["TIMESLICE", "DAYTYPE", "VALUE"])
        self.conversionlh_df = pd.DataFrame(columns=["TIMESLICE", "DAILYTIMEBRACKET", "VALUE"])
        self.yearsplit_df = pd.DataFrame(columns=["TIMESLICE", "YEAR", "VALUE"])
        self.daysplit_df = pd.DataFrame(columns=["DAILYTIMEBRACKET", "YEAR", "VALUE"])
        self.daysindaytype_df = pd.DataFrame(columns=["SEASON", "DAYTYPE", "VALUE"])

        # Tracking
        self.master_time_list = []  # List of tuples (Year, Timeslice)
        self.master_time_hours = []  # List of doubles (Hours per Timeslice)
        self.timeslice_name_map = {}  # Dict TIMESLICE -> (Season, DayType, DailyTimeBracket)

        # Constants for physical time validation
        self.HOURS_PER_YEAR = 8760
        self.HOURS_PER_DAY = 24
        self.DAYS_PER_YEAR = 365

        # Constant for validation
        self.TOL = 1e-6

    # === Load and Save Methods ===
    def load(self):
        """
        Load all time parameter CSV files into DataFrames.
        Uses read_csv from base class.
        :raises FileNotFoundError: if any required file is missing.
        :raises ValueError: if any file has missing or incorrect columns.
        """
        self.years_df = self.read_csv("YEAR.csv")
        self.timeslices_df = self.read_csv("TIMESLICE.csv")
        self.seasons_df = self.read_csv("SEASON.csv")
        self.daytypes_df = self.read_csv("DAYTYPE.csv")
        self.brackets_df = self.read_csv("DAILYTIMEBRACKET.csv")

        self.conversionls_df = self.read_csv("Conversionls.csv")
        self.conversionld_df = self.read_csv("Conversionld.csv")
        self.conversionlh_df = self.read_csv("Conversionlh.csv")
        self.yearsplit_df = self.read_csv("YearSplit.csv")
        self.daysplit_df = self.read_csv("DaySplit.csv")
        self.daysindaytype_df = self.read_csv("DaysInDayType.csv")

    def save(self):
        """
        Save all time parameter DataFrames to CSV files in the scenario directory.
        Uses write_csv and write_dataframe from base class.
        """
        self.write_dataframe("YEAR.csv", self.years_df)
        self.write_dataframe("TIMESLICE.csv", self.timeslices_df)
        self.write_dataframe("SEASON.csv", self.seasons_df)
        self.write_dataframe("DAYTYPE.csv", self.daytypes_df)
        self.write_dataframe("DAILYTIMEBRACKET.csv", self.brackets_df)

        self.write_dataframe("Conversionls.csv", self.conversionls_df)
        self.write_dataframe("Conversionld.csv", self.conversionld_df)
        self.write_dataframe("Conversionlh.csv", self.conversionlh_df)
        self.write_dataframe("YearSplit.csv", self.yearsplit_df)
        self.write_dataframe("DaySplit.csv", self.daysplit_df)
        self.write_dataframe("DaysInDayType.csv", self.daysindaytype_df)

    # === User Input Methods ===
    def add_time_structure(self, years, seasons, daytypes, brackets):
        """
        Sets up the time structure for the scenario, updating DataFrames and class attributes, and persists outputs via save().

        :param years: list[int] or tuple (start, end, step)
        :param seasons: dict {Name: Days}
        :param daytypes: dict {Name: Weight}
        :param brackets: dict {Name: Hours}
        """
        processed_years = self._process_years(years)
        self.years_df = pd.DataFrame({"VALUE": processed_years})
        timeslices, slicehours = self._process_time_structure(processed_years, seasons, daytypes, brackets)

        self.timeslices_df = pd.DataFrame({"VALUE": timeslices})
        self.seasons_df = pd.DataFrame({"VALUE": list(seasons.keys())})
        self.daytypes_df = pd.DataFrame({"VALUE": list(daytypes.keys())})
        self.brackets_df = pd.DataFrame({"VALUE": list(brackets.keys())})

        # 3. Generate Master List (Year -> Timeslice chronological order)
        self.master_time_list = [(y, ts) for y in years for ts in timeslices]
        self.master_time_hours = slicehours * len(years)

    # === Internal Logic Helpers ===
    def _process_years(self, years_input):
        """
        Sets up the YEAR set.
        
        :param years_input: 
            list[int] (specific years e.g. [2020, 2025]) 
            OR tuple (start, end, step) e.g. (2020, 2050, 5)
        :return: list[int] The list of years
        """
        if isinstance(years_input, (list, set)):
            years = sorted(list(years_input))
        elif isinstance(years_input, tuple) and len(years_input) == 3:
            start, end, step = years_input
            years = list(range(start, end + 1, step))
        else:
            raise ValueError("years_input must be a list of ints or a tuple (start, end, step).")
        return years

    def _process_time_structure(self, years, seasons: dict, daytypes: dict, brackets: dict):
        """
        Generates time structure calculating explicit duration in hours.
        Execute the logic to generate final CSVs.
        
        Recommended Inputs:
        :param years: list[int] (e.g. [2020, 2025, 2030])
        :param seasons: dict {Name: Days} (e.g. Winter: 90) - Should sum to ~365
        :param daytypes: dict {Name: Weight} (e.g. Weekday: 5, Weekend: 2 | e.g. Peak: 1, OffPeak: 3)
        :param brackets: dict {Name: Hours} (e.g. Day: 16, Night: 8) - Should sum to ~24
        """
        # --- User input validation ---
        # Check for empty dimensions
        if not seasons or not daytypes or not brackets:
            raise ValueError("Seasons, daytypes, and brackets must all be non-empty.")
        if sum(seasons.values()) == 0 or sum(daytypes.values()) == 0 or sum(brackets.values()) == 0:
            raise ValueError("Season, daytype, and bracket weights must all be non-zero.")

        # Warn if user input is far from expected
        if abs(sum(seasons.values()) - self.DAYS_PER_YEAR) > 1e-3:
            print(f"WARNING: Sum of season days is {sum(seasons.values())}, expected {self.DAYS_PER_YEAR}.\n"
                  "Season values will be normalized to sum to 1.0. This means the relative proportions are preserved, "
                  "but the absolute mapping to calendar days may be lost. If you want physical accuracy, ensure your input sums to 365.")
        if abs(sum(brackets.values()) - self.HOURS_PER_DAY) > 1e-3:
            print(f"WARNING: Sum of bracket hours is {sum(brackets.values())}, expected {self.HOURS_PER_DAY}.\n"
                  "Bracket values will be normalized to sum to 1.0. This means the relative proportions are preserved, "
                  "but the absolute mapping to hours in a day may be lost. If you want physical accuracy, ensure your input sums to 24.")

        # 1. Convert everything to fractions
        s_fracs = self._normalize(seasons)
        d_fracs = self._normalize(daytypes)
        b_fracs = self._normalize(brackets)

        # 2. Update DataFrames
        self.seasons_df = pd.DataFrame({"SEASON": list(seasons.keys())})
        self.daytypes_df = pd.DataFrame({"DAYTYPE": list(daytypes.keys())})
        self.brackets_df = pd.DataFrame({"DAILYTIMEBRACKET": list(brackets.keys())})

        # 3. Generate TIMESLICES (Cartesian Product)
        # Hierarchy: Season -> DayType -> Bracket
        # Naming Convention: Season_DayType_DailyTimeBracket
        timeslice_data = []
        timeslice_hours = []
        
        # Store conversion data
        map_ls = [] # Slice -> Season
        map_ld = [] # Slice -> DayType
        map_lh = [] # Slice -> DailyTimeBracket

        year_split_rows = []
        day_split_rows = []

        for s, s_val in s_fracs.items():
            for d, d_val in d_fracs.items():
                for b, b_val in b_fracs.items():
                    ts_name = f"{self._sanitize(s)}_{self._sanitize(d)}_{self._sanitize(b)}"
                    self.timeslice_name_map[ts_name] = (s, d, b)
                    timeslice_data.append(ts_name)

                    # Standard Mapping
                    map_ls.append({"TIMESLICE": ts_name, "SEASON": s, "VALUE": 1})
                    map_ld.append({"TIMESLICE": ts_name, "DAYTYPE": d, "VALUE": 1})
                    map_lh.append({"TIMESLICE": ts_name, "DAILYTIMEBRACKET": b, "VALUE": 1})

                    # Calculations using Decimal for exact arithmetic
                    season_hours = Decimal(str(s_val)) * Decimal(str(self.HOURS_PER_YEAR))
                    daytype_hours = Decimal(str(d_val)) * season_hours
                    slice_hours = Decimal(str(b_val)) * daytype_hours
                    timeslice_hours.append(float(slice_hours))

                    # Calculate YearSplit (TimeSlice as a fraction of Year) using Decimal
                    year_split_frac = slice_hours / Decimal(str(self.HOURS_PER_YEAR))
                    for y in years:
                        year_split_rows.append({"TIMESLICE": ts_name, "YEAR": y, "VALUE": float(year_split_frac)})
                        # Calculate DayTypeSplit (DailyTimeBracket as a fraction of DayType)
                        day_split_rows.append({"DAILYTIMEBRACKET": b, "YEAR": y, "VALUE": float(Decimal(str(b_val)))})

        # 4. Validation and normalization for timeslice hours (YearSplit)
        total_hours = sum(timeslice_hours)
        if not math.isclose(total_hours, self.HOURS_PER_YEAR, abs_tol=self.TOL):
            print(f"WARNING: Total calculated time is {total_hours:.4f} hours per year. Expected {self.HOURS_PER_YEAR}.\nPlease adjust your season/daytype/dailytimebracket definitions for better consistency.")

        # 5. Update class attributes
        self.timeslices_df = pd.DataFrame({"TIMESLICE": timeslice_data})
        self.conversionls_df = pd.DataFrame(map_ls)
        self.conversionld_df = pd.DataFrame(map_ld)
        self.conversionlh_df = pd.DataFrame(map_lh)
        self.yearsplit_df = pd.DataFrame(year_split_rows)
        self.daysplit_df = pd.DataFrame(day_split_rows).drop_duplicates()

        # 6. Validation for YearSplit: enforce sum to 1.0 for each year
        for y in years:
            year_sum = self.yearsplit_df[self.yearsplit_df['YEAR'] == y]['VALUE'].sum()
            if not math.isclose(year_sum, 1.0, abs_tol=self.TOL):
                print(f"WARNING: YearSplit for year {y} sums to {year_sum}, expected 1.0.")

        # 7. Validation for DaySplit: enforce sum to 1.0 for each year
        for y in years:
            day_sum = self.daysplit_df[self.daysplit_df['YEAR'] == y]['VALUE'].sum()
            if not math.isclose(day_sum, 1.0, abs_tol=self.TOL):
                print(f"WARNING: DaySplit for year {y} sums to {day_sum}, expected 1.0.")

        # 8. DaysInDayType Calculation
        # Logic: 365 * SeasonFrac * DayTypeFrac
        didt_rows = []
        for s, s_val in s_fracs.items():
            for d, d_val in d_fracs.items():
                didt_rows.append({"SEASON": s, "DAYTYPE": d, "VALUE": self.DAYS_PER_YEAR * s_val * d_val})
        self.daysindaytype_df = pd.DataFrame(didt_rows)

        return timeslice_data, timeslice_hours
    
    def _normalize(self, data: dict):
        """
        Normalizes inputs to sum to 1.0 using Decimal for exact arithmetic.
        """
        # Convert to Decimal for exact arithmetic
        decimal_data = {k: Decimal(str(v)) for k, v in data.items()}
        total = sum(decimal_data.values())
        
        if total == 0:
            return {k: 0 for k in data}
        
        # Perform exact division and convert back to float
        normalized = {k: float(v / total) for k, v in decimal_data.items()}
        return normalized

    def _sanitize(self, name):
        """
        Replace underscores in user-provided names with double underscores to avoid ambiguity.
        """
        return name.replace("_", "__")
    
    def _unsanitize(self, name):
        """
        Revert double underscores back to single underscores.
        """
        return name.replace("__", "_")
    
    def _get_timeslice_components(self, timeslice_name):
        """
        Given a TIMESLICE name, returns its components (SEASON, DAYTYPE, DAILYTIMEBRACKET).
        """
        return self.timeslice_name_map.get(timeslice_name, (None, None, None))
    
    # === Static Methods ===
    @staticmethod
    def load_time_axis(scenario):
        """
        Loads and returns all time axis DataFrames and a slice_map for use in other components.
        Returns:
            dict: {
                'yearsplit': DataFrame,
                'slice_map': dict (TIMESLICE -> {'Season', 'DayType', 'DailyTimeBracket'})
            }
        """
        # Load DataFrames
        yearsplit = pd.read_csv(os.path.join(scenario.scenario_dir, "YearSplit.csv"))
        conversionls = pd.read_csv(os.path.join(scenario.scenario_dir, "Conversionls.csv"))
        conversionld = pd.read_csv(os.path.join(scenario.scenario_dir, "Conversionld.csv"))
        conversionlh = pd.read_csv(os.path.join(scenario.scenario_dir, "Conversionlh.csv"))

        # Build slice_map
        slice_map = {}
        for _, row in conversionls.iterrows():
            slice_map.setdefault(row['TIMESLICE'], {})['Season'] = row['SEASON']
        for _, row in conversionld.iterrows():
            slice_map.setdefault(row['TIMESLICE'], {})['DayType'] = row['DAYTYPE']
        for _, row in conversionlh.iterrows():
            slice_map.setdefault(row['TIMESLICE'], {})['DailyTimeBracket'] = row['DAILYTIMEBRACKET']

        return {
            'yearsplit': yearsplit,
            'slice_map': slice_map
        }
    
    # === Visualization ===
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
        self.load()
        ys = self.yearsplit_df.copy()
        try:
            didt = self.daysindaytype_df.copy()
            didt['key'] = didt['SEASON'] + "_" + didt['DAYTYPE']
            days_lookup = didt.groupby('key')['VALUE'].mean().to_dict()
        except Exception:
            days_lookup = {}

        cls = self.conversionls_df.copy()
        cld = self.conversionld_df.copy()
        clh = self.conversionlh_df.copy()

        slice_map = {}
        for _, row in cls.iterrows():
            slice_map.setdefault(row['TIMESLICE'], {})['Season'] = row['SEASON']
        for _, row in cld.iterrows():
            slice_map.setdefault(row['TIMESLICE'], {})['DayType'] = row['DAYTYPE']
        for _, row in clh.iterrows():
            slice_map.setdefault(row['TIMESLICE'], {})['DailyTimeBracket'] = row['DAILYTIMEBRACKET']

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