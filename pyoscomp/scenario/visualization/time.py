# pyoscomp/scenario/visualization/time.py

"""
Visualizations for the TimeComponent of a scenario.

Provides :class:`TimeVisualizer` with the following plots:

- ``plot_timeslice_structure`` – horizontal stacked-bar showing the
  hierarchical Season → DayType → DailyTimeBracket breakdown.
- ``plot_duration_pie`` – pie chart of timeslice durations for a
  single representative year.
- ``plot_daysplit_bar`` – bar chart of intra-day bracket hours.

All values are year-specific (leap-year aware) and displayed to two
decimal places for precise accounting.
"""

from typing import Dict, List, Optional, Tuple

import pandas as pd

from .base import (
    CB_PALETTE,
    HATCHES,
    ComponentVisualizer,
)
from ..components.time import TimeComponent
from ...constants import hours_in_year


class TimeVisualizer(ComponentVisualizer):
    """
    Visualizer for :class:`TimeComponent`.

    Parameters
    ----------
    component : TimeComponent
        A loaded (or loadable) time component instance.
    auto_load : bool, optional
        If ``True`` (default), call ``component.load()`` when the data
        frames appear empty.

    Example
    -------
    >>> time = TimeComponent("path/to/scenario")
    >>> time.load()
    >>> viz = TimeVisualizer(time)
    >>> viz.show()                        # primary plot
    >>> fig, ax = viz.plot_duration_pie(year = 2025)       # alternative view
    """

    def __init__(
        self,
        component: TimeComponent,
        auto_load: bool = True,
    ):
        super().__init__(component, auto_load)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        """Load the component if it appears empty and auto_load is on."""
        tc: TimeComponent = self.component
        if self._auto_load and tc.years_df.empty:
            tc.load()

    def _build_slice_map(self) -> Dict[str, Dict[str, str]]:
        """
        Build a {timeslice: {Season, DayType, DailyTimeBracket}} mapping.

        Returns
        -------
        dict
            Mapping from timeslice name to its component identifiers.
        """
        tc: TimeComponent = self.component
        slice_map: Dict[str, Dict[str, str]] = {}

        for _, row in tc.conversionls_df.iterrows():
            if row['VALUE'] == 1.0:
                slice_map.setdefault(
                    row['TIMESLICE'], {}
                )['Season'] = row['SEASON']
        for _, row in tc.conversionld_df.iterrows():
            if row['VALUE'] == 1.0:
                slice_map.setdefault(
                    row['TIMESLICE'], {}
                )['DayType'] = row['DAYTYPE']
        for _, row in tc.conversionlh_df.iterrows():
            if row['VALUE'] == 1.0:
                slice_map.setdefault(
                    row['TIMESLICE'], {}
                )['DailyTimeBracket'] = row['DAILYTIMEBRACKET']

        return slice_map

    def _days_lookup(
        self,
        year: Optional[int] = None,
    ) -> Dict[str, float]:
        """
        Build a {Season_DayType: days} lookup from DaysInDayType.

        Parameters
        ----------
        year : int, optional
            Model year to filter to.  If ``None``, values are averaged
            across all model years (legacy behaviour).

        Returns
        -------
        dict
            Keys are ``"Season_DayType"`` strings, values are day
            counts for the requested year.
        """
        tc: TimeComponent = self.component
        try:
            didt = tc.daysindaytype_df.copy()
            if year is not None:
                didt = didt[didt['YEAR'] == year]
            didt['key'] = didt['SEASON'] + "_" + didt['DAYTYPE']
            return didt.groupby('key')['VALUE'].mean().to_dict()
        except Exception:
            return {}

    def _prepare_data(
        self,
        year: Optional[int] = None,
    ) -> Tuple[
        pd.DataFrame,
        Dict[str, Dict[str, str]],
        List[dict],
        int,
    ]:
        """
        Common data preparation used by multiple plots.

        Parameters
        ----------
        year : int, optional
            Model year to use.  Defaults to the earliest year.

        Returns
        -------
        ys : pd.DataFrame
            YearSplit rows filtered to *year*.
        slice_map : dict
            Timeslice → component mapping.
        data : list of dict
            Per-timeslice records with keys ``ts``, ``season``,
            ``daytype``, ``timebracket``, ``duration``.
        rep_year : int
            The representative year used for filtering.
        """
        self._ensure_loaded()
        tc: TimeComponent = self.component

        ys = tc.yearsplit_df.copy()
        slice_map = self._build_slice_map()

        rep_year = year if year is not None else int(ys['YEAR'].min())
        ys = ys[ys['YEAR'] == rep_year]

        data: List[dict] = []
        for _, row in ys.iterrows():
            ts = row['TIMESLICE']
            meta = slice_map.get(ts, {})
            data.append({
                'ts': ts,
                'season': meta.get('Season', 'Unknown'),
                'daytype': meta.get('DayType', 'Unknown'),
                'timebracket': meta.get('DailyTimeBracket', 'Unknown'),
                'duration': row['VALUE'],
            })

        return ys, slice_map, data, rep_year

    # ==================================================================
    # Public plot methods
    # ==================================================================

    def plot_timeslice_structure(
        self,
        year: Optional[int] = None,
        figsize: Tuple[float, float] = (16, 8),
    ):
        """
        Horizontal stacked-bar chart of the timeslice hierarchy.

        Each row is a season.  Within a row, segments represent DayType ×
        DailyTimeBracket combinations.  Colour encodes DayType; hatch
        pattern encodes DailyTimeBracket.  Segment labels show the
        average number of days for each Season–DayType pair.

        Parameters
        ----------
        year : int, optional
            Model year whose YearSplit values are plotted.  Defaults to
            the earliest year in the component.
        figsize : tuple of float, optional
            Figure size ``(width, height)`` in inches.

        Returns
        -------
        fig : matplotlib.figure.Figure
        ax : matplotlib.axes.Axes
        """
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches

        self._apply_style()

        # 1. Prepare data
        ys, slice_map, data, rep_year = self._prepare_data(year)
        days_lookup = self._days_lookup(rep_year)

        # 2. Derive ordered sets
        seasons = sorted({d['season'] for d in data})
        sorted_daytypes = sorted({d['daytype'] for d in data})
        sorted_timebrackets = sorted({d['timebracket'] for d in data})

        dt_style = {
            dt: {'color': self._color_for_index(i)}
            for i, dt in enumerate(sorted_daytypes)
        }
        tb_style = {
            tb: {'hatch': self._hatch_for_index(i)}
            for i, tb in enumerate(sorted_timebrackets)
        }

        # 3. Season totals for normalising bar widths
        season_totals: Dict[str, float] = {}
        for item in data:
            season_totals[item['season']] = (
                season_totals.get(item['season'], 0) + item['duration']
            )

        # 4. Draw figure
        fig, ax = plt.subplots(figsize=figsize)
        season_cursors = {s: 0.0 for s in seasons}
        label_tracking: Dict[str, Dict[str, Dict[str, float]]] = {}
        bar_height = 0.6

        for item in data:
            s = item['season']
            d = item['daytype']
            h = item['timebracket']

            total_s_dur = season_totals.get(s, 1)
            rel_width = item['duration'] / total_s_dur
            x_start = season_cursors[s]
            y_center = seasons.index(s)

            rect = patches.Rectangle(
                (x_start, y_center - bar_height / 2),
                rel_width,
                bar_height,
                facecolor=dt_style[d]['color'],
                hatch=tb_style[h]['hatch'],
                edgecolor='white',
                linewidth=1,
                alpha=0.9,
            )
            ax.add_patch(rect)

            # Track daytype spans for labelling
            label_tracking.setdefault(s, {})
            if d not in label_tracking[s]:
                label_tracking[s][d] = {
                    'start': x_start,
                    'end': x_start + rel_width,
                }
            else:
                label_tracking[s][d]['end'] = x_start + rel_width
            season_cursors[s] += rel_width

        # 5. Annotations (day-count labels)
        ax.set_yticks(range(len(seasons)))
        ax.set_yticklabels(seasons, fontsize=16)

        for s in seasons:
            y_pos = seasons.index(s)
            label_pos_top = True
            sorted_dts = sorted(
                label_tracking[s].keys(),
                key=lambda k: label_tracking[s][k]['start'],
            )
            for dt in sorted_dts:
                coords = label_tracking[s][dt]
                width = coords['end'] - coords['start']
                center_x = coords['start'] + width / 2
                day_count = days_lookup.get(f"{s}_{dt}", 0)

                if width > 0.05:
                    ax.text(
                        center_x, y_pos,
                        f"{day_count:.2f} days",
                        ha='center', va='center',
                        color='black', fontsize=16,
                    )
                else:
                    y_off = (
                        (bar_height / 2 + 0.15) if label_pos_top
                        else -(bar_height / 2 + 0.25)
                    )
                    ax.text(
                        center_x, y_pos + y_off,
                        f"{day_count:.2f} days",
                        ha='center', va='center',
                        color='black', fontsize=14,
                    )
                    label_pos_top = not label_pos_top

        # 6. Formatting
        ax.set_xlim(0, 1)
        ax.set_ylim(-0.6, len(seasons) - 0.4)
        ax.set_xlabel(
            "Proportion of Season Time",
            fontsize=16, fontstyle='italic', labelpad=15,
        )
        self._strip_spines(ax, keep=['bottom'])
        ax.tick_params(axis='y', length=0)

        # Day-type colour legend
        dt_handles = [
            patches.Patch(
                facecolor=dt_style[dt]['color'],
                label=dt,
                edgecolor='black',
            )
            for dt in sorted_daytypes
        ]
        leg1 = ax.legend(
            handles=dt_handles,
            title="Day Types",
            loc='upper center',
            bbox_to_anchor=(0.5, -0.12),
            ncol=len(sorted_daytypes),
            frameon=False,
            fontsize=14,
            title_fontsize=16,
        )
        ax.add_artist(leg1)

        # Bracket hatch legend
        tb_handles = [
            patches.Patch(
                facecolor='white',
                hatch=tb_style[tb]['hatch'],
                label=tb,
                edgecolor='black',
            )
            for tb in sorted_timebrackets
        ]
        ax.legend(
            handles=tb_handles,
            title="Daily Time Brackets",
            loc='upper center',
            bbox_to_anchor=(0.5, -0.25),
            ncol=len(sorted_timebrackets),
            frameon=False,
            fontsize=14,
            title_fontsize=16,
        )

        # Title with total hours (year-specific accounting)
        year_hours = hours_in_year(rep_year)
        total_fraction = ys['VALUE'].sum()
        total_hours = total_fraction * year_hours
        ax.set_title(
            f"Scenario Time Structure  (Year {rep_year})\n"
            f"Accounted: {total_hours:,.2f} / {year_hours} Hours",
            fontsize=18,
            pad=20,
        )

        plt.tight_layout()
        return fig, ax

    # ------------------------------------------------------------------

    def plot_duration_pie(
        self,
        year: Optional[int] = None,
        figsize: Tuple[float, float] = (12, 10),
        pct_threshold: float = 2.0,
    ):
        """
        Pie chart of timeslice durations for a single year.

        Each wedge represents one timeslice.  Colour encodes DayType,
        hatch pattern encodes DailyTimeBracket (matching the stacked-bar
        chart).  Adjacent wedges belonging to the same season are grouped
        with a thick black outline, and a single external label shows the
        season name with its average day count.

        Wedges smaller than *pct_threshold* % have their percentage and
        outer labels suppressed to avoid clutter.

        Parameters
        ----------
        year : int, optional
            Model year.  Defaults to the earliest year.
        figsize : tuple of float, optional
            Figure size ``(width, height)`` in inches.
        pct_threshold : float, optional
            Minimum percentage for a wedge to display its label.
            Defaults to ``2.0``.

        Returns
        -------
        fig : matplotlib.figure.Figure
        ax : matplotlib.axes.Axes
        """
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        import numpy as np

        self._apply_style()

        # 1. Prepare data (sorted by season so same-season wedges are adjacent)
        ys, slice_map, data, rep_year = self._prepare_data(year)
        days_lookup = self._days_lookup(rep_year)
        data.sort(key=lambda d: (d['season'], d['daytype'], d['timebracket']))

        # 2. Style maps (consistent with plot_timeslice_structure)
        sorted_daytypes = sorted({d['daytype'] for d in data})
        sorted_timebrackets = sorted({d['timebracket'] for d in data})

        dt_style = {
            dt: {'color': self._color_for_index(i)}
            for i, dt in enumerate(sorted_daytypes)
        }
        tb_style = {
            tb: {'hatch': self._hatch_for_index(i)}
            for i, tb in enumerate(sorted_timebrackets)
        }

        sizes = [d['duration'] for d in data]
        colors = [dt_style[d['daytype']]['color'] for d in data]
        hatches = [tb_style[d['timebracket']]['hatch'] for d in data]

        total = sum(sizes)
        pcts = [(s / total) * 100 if total else 0 for s in sizes]

        # 3. Draw pie (no labels — we add them manually)
        fig, ax = plt.subplots(figsize=figsize)
        wedges, _ = ax.pie(
            sizes,
            colors=colors,
            startangle=90,
            wedgeprops={'edgecolor': 'white', 'linewidth': 0.8},
        )

        # 4. Apply hatch patterns
        for wedge, h in zip(wedges, hatches):
            wedge.set_hatch(h)

        # 5. Percentage labels inside (suppress < threshold)
        for wedge, pct in zip(wedges, pcts):
            if pct < pct_threshold:
                continue
            angle = (wedge.theta2 + wedge.theta1) / 2
            r = 0.75
            x = r * np.cos(np.radians(angle))
            y = r * np.sin(np.radians(angle))
            ax.text(
                x, y, f"{pct:.1f}%",
                ha='center', va='center',
                fontsize=12, fontweight='bold',
            )

        # 6. Thick black outlines grouping wedges by season
        seasons_seen: Dict[str, list] = {}
        for i, d in enumerate(data):
            seasons_seen.setdefault(d['season'], []).append(i)

        for season, indices in seasons_seen.items():
            for idx in indices:
                w = wedges[idx]
                w_copy = mpatches.Wedge(
                    center=w.center,
                    r=w.r,
                    theta1=wedges[indices[0]].theta1,
                    theta2=wedges[indices[-1]].theta2,
                    width=w.r,
                    fill=False,
                    edgecolor='black',
                    linewidth=2.5,
                )
            ax.add_patch(w_copy)

        # 7. External season labels (one per season)
        for season, indices in seasons_seen.items():
            theta1 = wedges[indices[0]].theta1
            theta2 = wedges[indices[-1]].theta2
            mid_angle = (theta1 + theta2) / 2

            # Total season days (sum across daytypes for this season)
            season_days = sum(
                days_lookup.get(f"{season}_{d}", 0)
                for d in sorted_daytypes
            )

            r_label = 1.15
            x = r_label * np.cos(np.radians(mid_angle))
            y = r_label * np.sin(np.radians(mid_angle))
            ha = 'left' if x >= 0 else 'right'
            ax.text(
                x, y,
                f"{season}\n({season_days:.2f} days)",
                ha=ha, va='center',
                fontsize=13, fontweight='bold',
            )

        # 8. Title (year-specific accounting)
        year_hours = hours_in_year(rep_year)
        total_hours = total * year_hours
        ax.set_title(
            f"Timeslice Duration Shares  (Year {rep_year})\n"
            f"Accounted: {total_hours:,.2f} / {year_hours} Hours",
            fontsize=18,
            pad=20,
        )

        # 9. Legends (same style as plot_timeslice_structure)
        dt_handles = [
            mpatches.Patch(
                facecolor=dt_style[dt]['color'],
                label=dt,
                edgecolor='black',
            )
            for dt in sorted_daytypes
        ]
        leg1 = ax.legend(
            handles=dt_handles,
            title="Day Types",
            loc='upper center',
            bbox_to_anchor=(0.5, -0.02),
            ncol=len(sorted_daytypes),
            frameon=False,
            fontsize=14,
            title_fontsize=16,
        )
        ax.add_artist(leg1)

        tb_handles = [
            mpatches.Patch(
                facecolor='white',
                hatch=tb_style[tb]['hatch'],
                label=tb,
                edgecolor='black',
            )
            for tb in sorted_timebrackets
        ]
        ax.legend(
            handles=tb_handles,
            title="Daily Time Brackets",
            loc='upper center',
            bbox_to_anchor=(0.5, -0.10),
            ncol=len(sorted_timebrackets),
            frameon=False,
            fontsize=14,
            title_fontsize=16,
        )

        plt.tight_layout()
        return fig, ax

    # ------------------------------------------------------------------

    def plot_daysplit_bar(
        self,
        year: Optional[int] = None,
        figsize: Tuple[float, float] = (10, 6),
    ):
        """
        Bar chart of DaySplit fractions (daily time bracket weights).

        Shows how a single day is subdivided into time brackets, making
        it easy to verify the intra-day resolution at a glance.

        Parameters
        ----------
        year : int, optional
            Model year.  Defaults to the earliest year.
        figsize : tuple of float, optional
            Figure size ``(width, height)`` in inches.

        Returns
        -------
        fig : matplotlib.figure.Figure
        ax : matplotlib.axes.Axes
        """
        import matplotlib.pyplot as plt

        self._apply_style()
        self._ensure_loaded()
        tc: TimeComponent = self.component

        ds = tc.daysplit_df.copy()
        rep_year = year if year is not None else int(ds['YEAR'].min())
        ds = ds[ds['YEAR'] == rep_year]

        brackets = ds['DAILYTIMEBRACKET'].tolist()
        fractions = ds['VALUE'].tolist()
        hours_per_day = 24
        hours = [f * hours_per_day for f in fractions]

        colors = [
            self._color_for_index(i) for i in range(len(brackets))
        ]

        fig, ax = plt.subplots(figsize=figsize)
        bars = ax.bar(brackets, hours, color=colors, edgecolor='black')

        # Value labels on bars
        total_bar_hours = sum(hours)
        for bar, frac in zip(bars, fractions):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.2,
                f"{frac:.4f}\n({bar.get_height():.2f} h)",
                ha='center', va='bottom', fontsize=11,
            )

        ax.set_ylabel("Hours", fontsize=14)
        ax.set_xlabel("Daily Time Bracket", fontsize=14)
        ax.set_title(
            f"DaySplit: Intra-Day Resolution  (Year {rep_year})\n"
            f"Accounted: {total_bar_hours:.2f} / {hours_per_day} Hours per Day",
            fontsize=18, pad=15,
        )
        self._strip_spines(ax, keep=['bottom', 'left'])

        plt.tight_layout()
        return fig, ax

    # ==================================================================
    # Convenience entry point
    # ==================================================================

    def show(self, **kwargs) -> None:
        """
        Display the primary visualisation (timeslice structure chart).

        Parameters
        ----------
        **kwargs
            Forwarded to :meth:`plot_timeslice_structure`.
        """
        import matplotlib.pyplot as plt

        self.plot_timeslice_structure(**kwargs)
        plt.show()
