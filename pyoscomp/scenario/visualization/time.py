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

from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

import pandas as pd

from .base import (
    CB_PALETTE,
    HATCHES,
    ComponentVisualizer,
)
from ..components.time import TimeComponent
from ...constants import ENDOFDAY, hours_in_year

if TYPE_CHECKING:
    from ...translation.time.results import SnapshotResult, TimesliceResult


class TimeVisualizer(ComponentVisualizer):
    """
    Visualizer for :class:`TimeComponent` or PyPSA Network snapshots.

    When initialized with a :class:`TimeComponent`, provides OSeMOSYS
    timeslice visualizations (pie charts, stacked bars, etc.).  When
    initialized with a ``pypsa.Network``, provides a snapshot timeline
    visualisation showing temporal coverage and spacing.

    Parameters
    ----------
    component : TimeComponent or pypsa.Network
        A loaded (or loadable) time component instance, **or** a PyPSA
        network whose snapshots have already been configured.
    auto_load : bool, optional
        If ``True`` (default), call ``component.load()`` when the data
        frames appear empty.  Ignored for PyPSA networks.

    Example
    -------
    OSeMOSYS timeslice visualization::

        >>> time = TimeComponent("path/to/scenario")
        >>> time.load()
        >>> viz = TimeVisualizer(time)
        >>> viz.show()

    PyPSA snapshot timeline::

        >>> import pypsa
        >>> n = pypsa.Network()
        >>> n.set_snapshots(pd.date_range("2025-01-01", periods=8760, freq="h"))
        >>> viz = TimeVisualizer(n)
        >>> viz.show()
    """

    def __init__(
        self,
        component,
        auto_load: bool = True,
    ):
        try:
            import pypsa
            is_network = isinstance(component, pypsa.Network)
        except ImportError:
            is_network = False

        if is_network:
            # Bypass ScenarioComponent init for PyPSA networks
            self.component = None
            self._auto_load = False
            self._network = component
        else:
            super().__init__(component, auto_load)
            self._network = None

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
        pct_threshold: float = 3.0,
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

    # ------------------------------------------------------------------
    # PyPSA snapshot helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_timedelta(td: pd.Timedelta) -> str:
        """
        Format a pandas Timedelta as a concise human-readable string.

        Chooses the most natural unit (months, days, or hours) based on
        the magnitude of the interval.

        Parameters
        ----------
        td : pd.Timedelta
            Time interval to format.

        Returns
        -------
        str
            Concise duration string, e.g. ``'6h'``, ``'3 days'``,
            ``'2 months'``.
        """
        total_seconds = td.total_seconds()
        if total_seconds >= 28 * 24 * 3600:
            months = total_seconds / (30.44 * 24 * 3600)
            if abs(months - round(months)) < 0.1:
                m = int(round(months))
                return f"{m} month{'s' if m != 1 else ''}"
            return f"{months:.1f} months"
        elif total_seconds >= 24 * 3600:
            days = total_seconds / (24 * 3600)
            if abs(days - round(days)) < 0.01:
                d = int(round(days))
                return f"{d} day{'s' if d != 1 else ''}"
            return f"{days:.1f} days"
        else:
            hours = total_seconds / 3600
            if abs(hours - round(hours)) < 0.01:
                return f"{int(round(hours))}h"
            return f"{hours:.1f}h"

    @staticmethod
    def _draw_zigzag(ax, x_start, x_end, y_center,
                     amplitude=0.18, n_teeth=12, **kwargs):
        """
        Draw a zigzag (triangular wave) polyline on *ax*.

        The line begins and ends at *y_center* so it connects
        seamlessly with adjacent straight segments.

        Parameters
        ----------
        ax : matplotlib.axes.Axes
        x_start, x_end : float
            Horizontal extent of the zigzag.
        y_center : float
            Baseline y value.
        amplitude : float
            Peak deviation above / below *y_center*.
        n_teeth : int
            Number of complete up-down teeth.
        **kwargs
            Forwarded to ``ax.plot()``.
        """
        import numpy as np

        pts = n_teeth * 2 + 1
        xs = np.linspace(x_start, x_end, pts)
        ys = np.full(pts, y_center, dtype=float)
        for i in range(1, pts - 1):
            ys[i] = y_center + amplitude * (1 if i % 2 == 1 else -1)
        kwargs.setdefault('color', 'black')
        kwargs.setdefault('linewidth', 2)
        kwargs.setdefault('zorder', 2)
        ax.plot(xs, ys, **kwargs)

    # ------------------------------------------------------------------

    def plot_snapshot_timeline(
        self,
        year: Optional[int] = None,
        figsize: Tuple[float, float] = (16, 5),
    ):
        """
        Horizontal timeline of PyPSA snapshots for a single year.

        The timeline is divided into **7 equal-width sections**:

        * Sections 0 – 4 → January – May (one month each).
        * Section 5 → zigzag representing the compressed Jun – Nov period.
        * Section 6 → December.

        Within each visible month section, snapshot markers are placed
        proportionally.  If a month contains more than
        ``MAX_MARKERS`` snapshots, only the first few and last few are
        drawn with a mini-zigzag indicating compression.

        Snapshot labels (first / last) appear **above** the timeline;
        year-boundary labels appear **below**.

        Parameters
        ----------
        year : int, optional
            Investment period (year) to plot.  Defaults to the earliest
            available year.
        figsize : tuple of float, optional
            Figure size ``(width, height)`` in inches.

        Returns
        -------
        fig : matplotlib.figure.Figure
        ax : matplotlib.axes.Axes

        Raises
        ------
        ValueError
            If the network has no snapshots for the requested year.
        """
        import matplotlib.pyplot as plt
        import numpy as np
        from datetime import datetime

        self._apply_style()
        network = self._network

        # ==============================================================
        # 1. Extract snapshots for the requested year
        # ==============================================================
        snapshots = network.snapshots
        is_multi = isinstance(snapshots, pd.MultiIndex)

        if is_multi:
            all_periods = snapshots.get_level_values("period")
            available_years = sorted(all_periods.unique())
            rep_year = year if year is not None else available_years[0]
            mask = (all_periods == rep_year)
            snap_times = pd.DatetimeIndex(
                snapshots.get_level_values("timestep")[mask]
            ).sort_values()
        else:
            snap_idx = pd.DatetimeIndex(snapshots)
            available_years = sorted(snap_idx.year.unique())
            rep_year = year if year is not None else available_years[0]
            mask = (snap_idx.year == rep_year)
            snap_times = snap_idx[mask].sort_values()

        n_snaps = len(snap_times)
        if n_snaps == 0:
            raise ValueError(
                f"No snapshots found for year {rep_year}. "
                f"Available years: {available_years}"
            )

        # Total weighted hours
        total_hours = float(
            network.snapshot_weightings["objective"].values[mask].sum()
        )
        year_hours = hours_in_year(rep_year)

        # ==============================================================
        # 2. Year boundaries (ENDOFDAY rounded to nearest second)
        # ==============================================================
        year_start = pd.Timestamp(datetime(rep_year, 1, 1, 0, 0, 0))
        year_end = pd.Timestamp(datetime(
            rep_year, 12, 31,
            ENDOFDAY.hour, ENDOFDAY.minute, ENDOFDAY.second,
        ))

        first_snap = snap_times[0]
        last_snap = snap_times[-1]

        # ==============================================================
        # 3. Compute spacings (regularity check)
        # ==============================================================
        if n_snaps > 1:
            deltas = snap_times[1:] - snap_times[:-1]
            is_regular = len(deltas.unique()) == 1
        else:
            deltas = pd.TimedeltaIndex([])
            is_regular = True

        # ==============================================================
        # 4. Section layout  (7 equal-width sections, x ∈ [0, 7])
        #    0=Jan  1=Feb  2=Mar  3=Apr  4=May  5=zigzag  6=Dec
        # ==============================================================
        visible_months = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 6: 12}
        sec_pad = 0.03  # inner padding within each section

        def _snap_to_x(ts: pd.Timestamp, sec_idx: int, month: int) -> float:
            """Map a timestamp to its x position within a section."""
            m_start = pd.Timestamp(datetime(rep_year, month, 1))
            m_end = (
                pd.Timestamp(datetime(rep_year, month + 1, 1))
                if month < 12
                else pd.Timestamp(datetime(rep_year + 1, 1, 1))
            )
            total_s = (m_end - m_start).total_seconds()
            frac = (
                (ts - m_start).total_seconds() / total_s
                if total_s > 0 else 0.5
            )
            frac = max(0.0, min(1.0, frac))
            return sec_idx + sec_pad + frac * (1 - 2 * sec_pad)

        # Group snapshots by visible-month section
        month_snaps: Dict[int, pd.DatetimeIndex] = {}
        for sec_idx, month in visible_months.items():
            month_snaps[sec_idx] = snap_times[snap_times.month == month]

        # ==============================================================
        # 5. Create figure
        # ==============================================================
        fig, ax = plt.subplots(figsize=figsize)
        y_line = 0.0

        # -- Projected x for first / last actual snapshots --------------
        def _project_snap(ts: pd.Timestamp) -> float:
            m = ts.month
            if 1 <= m <= 5:
                return _snap_to_x(ts, m - 1, m)
            elif m == 12:
                return _snap_to_x(ts, 6, 12)
            else:
                # In compressed zone (Jun-Nov)
                # Map linearly into zigzag section [5, 6]
                jun1 = pd.Timestamp(datetime(rep_year, 6, 1))
                dec1 = pd.Timestamp(datetime(rep_year, 12, 1))
                frac = (
                    (ts - jun1).total_seconds()
                    / (dec1 - jun1).total_seconds()
                )
                return 5.0 + max(0.0, min(1.0, frac))

        first_x = _project_snap(first_snap)
        last_x = _project_snap(last_snap)

        # ==============================================================
        # 6. Draw the main timeline
        # ==============================================================
        # Solid from sections 0-4
        ax.plot([0, 5], [y_line, y_line], '-', color='black',
                linewidth=2, zorder=2)
        # Zigzag for section 5 (Jun-Nov compression)
        self._draw_zigzag(ax, 5.0, 6.0, y_line,
                          amplitude=0.18, n_teeth=5)
        # Solid for section 6
        ax.plot([6, 7], [y_line, y_line], '-', color='black',
                linewidth=2, zorder=2)

        # Dotted overlay where no snapshots exist at boundaries
        if first_x > 0.05:
            ax.plot([0, first_x], [y_line, y_line], '-',
                    color='white', linewidth=5, zorder=3)
            ax.plot([0, first_x], [y_line, y_line], ':',
                    color='black', linewidth=1.5, zorder=4)
        if last_x < 6.95:
            ax.plot([last_x, 7], [y_line, y_line], '-',
                    color='white', linewidth=5, zorder=3)
            ax.plot([last_x, 7], [y_line, y_line], ':',
                    color='black', linewidth=1.5, zorder=4)

        # ==============================================================
        # 7. Year-boundary markers (tall black bars at x=0 and x=7)
        # ==============================================================
        bnd_h = 0.35
        for x_pos in [0.0, 7.0]:
            ax.plot(
                [x_pos, x_pos],
                [y_line - bnd_h, y_line + bnd_h],
                color='black', linewidth=2.5, zorder=6,
            )

        # ==============================================================
        # 8. Month-boundary markers (shorter gray bars)
        # ==============================================================
        month_bnd_h = 0.18
        month_boundaries = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        for x_pos in month_boundaries:
            ax.plot(
                [x_pos, x_pos],
                [y_line - month_bnd_h, y_line + month_bnd_h],
                color='gray', linewidth=1.5, zorder=5,
            )

        # ==============================================================
        # 9. Snapshot markers within visible month sections
        # ==============================================================
        mk_h = 0.22
        marker_color = self._color_for_index(4)  # '#0072B2'
        MAX_MARKERS = 15
        N_HEAD_MK = 5
        N_TAIL_MK = 2
        zz_mini_amp = 0.12

        for sec_idx, month in visible_months.items():
            snaps = month_snaps[sec_idx]
            n = len(snaps)
            if n == 0:
                continue

            if n <= MAX_MARKERS:
                for ts in snaps:
                    x = _snap_to_x(ts, sec_idx, month)
                    ax.plot(
                        [x, x], [y_line - mk_h, y_line + mk_h],
                        color=marker_color, linewidth=2, zorder=5,
                    )
            else:
                nh = min(N_HEAD_MK, n)
                nt = min(N_TAIL_MK, max(0, n - nh))
                for ts in snaps[:nh]:
                    x = _snap_to_x(ts, sec_idx, month)
                    ax.plot(
                        [x, x], [y_line - mk_h, y_line + mk_h],
                        color=marker_color, linewidth=2, zorder=5,
                    )
                for ts in snaps[-nt:]:
                    x = _snap_to_x(ts, sec_idx, month)
                    ax.plot(
                        [x, x], [y_line - mk_h, y_line + mk_h],
                        color=marker_color, linewidth=2, zorder=5,
                    )
                # Mini-zigzag for intra-month compression
                x_zz_l = _snap_to_x(snaps[nh - 1], sec_idx, month) + 0.02
                x_zz_r = _snap_to_x(snaps[n - nt], sec_idx, month) - 0.02
                if x_zz_r > x_zz_l + 0.04:
                    self._draw_zigzag(
                        ax, x_zz_l, x_zz_r, y_line,
                        amplitude=zz_mini_amp, n_teeth=6,
                        color='gray', linewidth=1.5, zorder=4,
                    )

        # ==============================================================
        # 10. Spacing labels (above the timeline)
        # ==============================================================
        spacing_color = '#D55E00'
        if n_snaps > 1 and is_regular:
            n_labels = 1
            # Find the first visible month with enough markers to label
            label_snaps = None
            for sec_idx in sorted(visible_months.keys()):
                s = month_snaps[sec_idx]
                if len(s) >= n_labels + 1:
                    label_snaps = s
                    label_sec = sec_idx
                    label_month = visible_months[sec_idx]
                    break

            if label_snaps is not None:
                for j in range(min(n_labels, len(label_snaps) - 1)):
                    td = label_snaps[j + 1] - label_snaps[j]
                    label = self._format_timedelta(td)
                    x1 = _snap_to_x(
                        label_snaps[j], label_sec, label_month,
                    )
                    x2 = _snap_to_x(
                        label_snaps[j + 1], label_sec, label_month,
                    )
                    xm = (x1 + x2) / 2
                    gap_w = x2 - x1

                    if gap_w > 0.15:
                        y_arr = y_line + mk_h + 0.25 + j * 0.35
                        ax.annotate(
                            '', xy=(x2, y_arr), xytext=(x1, y_arr),
                            arrowprops=dict(
                                arrowstyle='<->',
                                color=spacing_color, lw=1.5,
                            ),
                        )
                        ax.text(
                            xm, y_arr + 0.10, label,
                            ha='center', va='bottom', fontsize=12,
                            color=spacing_color, fontweight='bold',
                        )
                    else:
                        y_text = y_line + mk_h + 0.35 + j * 0.4
                        x_text = xm + 0.15
                        ax.annotate(
                            label,
                            xy=(xm, y_line + mk_h),
                            xytext=(x_text, y_text),
                            fontsize=12, color=spacing_color,
                            fontweight='bold', ha='left',
                            arrowprops=dict(
                                arrowstyle='->',
                                color=spacing_color, lw=1.2,
                                connectionstyle='arc3,rad=0.2',
                            ),
                        )

        # ==============================================================
        # 11. Labels
        # ==============================================================
        def _fmt(ts: pd.Timestamp) -> str:
            return (
                f"{ts.strftime('%Y-%m-%d')}\n"
                f"{ts.strftime('%H:%M:%S')}"
            )

        # Year boundaries → BELOW the timeline
        label_y_below = y_line - bnd_h - 0.20
        ax.text(
            0.0, label_y_below, _fmt(year_start),
            ha='center', va='top', fontsize=10,
        )
        ax.text(
            7.0, label_y_below, _fmt(year_end),
            ha='center', va='top', fontsize=10,
        )

        # Month boundaries → BELOW the timeline
        month_dates = {
            1.0: datetime(rep_year, 2, 1),
            2.0: datetime(rep_year, 3, 1),
            3.0: datetime(rep_year, 4, 1),
            4.0: datetime(rep_year, 5, 1),
            5.0: datetime(rep_year, 6, 1),
            6.0: datetime(rep_year, 12, 1),
        }
        for x_pos, month_dt in month_dates.items():
            month_ts = pd.Timestamp(month_dt)
            ax.text(
                x_pos, label_y_below, _fmt(month_ts),
                ha='center', va='top', fontsize=9, color='gray',
            )

        # First / last snapshot → ABOVE the timeline
        label_y_above = y_line + mk_h + 0.10
        ax.text(
            first_x, label_y_above, _fmt(first_snap),
            ha='center', va='bottom', fontsize=10,
            color=marker_color,
        )
        # Only draw last-snap label if it doesn't overlap the first
        if abs(last_x - first_x) > 0.4:
            ax.text(
                last_x, label_y_above, _fmt(last_snap),
                ha='center', va='bottom', fontsize=10,
                color=marker_color,
            )

        # ==============================================================
        # 12. Title (matches plot_timeslice_structure + snapshot count)
        # ==============================================================
        ax.set_title(
            f"Scenario Time Structure  (Year {rep_year})\n"
            f"Snapshots: {n_snaps}",
            fontsize=18, pad=20,
        )

        # ==============================================================
        # 13. Clean up axes
        # ==============================================================
        ax.set_xlim(-0.3, 7.3)
        ax.set_ylim(-1.5, 2.5)
        ax.axis('off')

        plt.tight_layout()
        return fig, ax

    # ------------------------------------------------------------------

    def plot_timeslice_snapshot_map(
        self,
        snap_result: 'SnapshotResult',
        year: Optional[int] = None,
        figsize: Tuple[float, float] = (16, 8),
    ):
        """
        Visualize the mapping from OSeMOSYS timeslices to PyPSA snapshots.

        Draws a three-level diagram for a single model year:

        - **Season strip** (top) — broad colour blocks showing each
          season's proportional share of the year.
        - **Timeslice bar** (middle) — individual segments for every
          timeslice, coloured by season and hatched by daily time
          bracket (consistent with ``plot_timeslice_structure``).
        - **Snapshot timeline** (bottom) — a horizontal line with
          season-coloured markers at each snapshot position, showing
          the flat sequential representation that PyPSA consumes.

        All three levels share the same proportional x-axis (fraction
        of the year) so duration comparisons are immediate.

        Parameters
        ----------
        snap_result : SnapshotResult
            Result container from ``to_snapshots()``, containing
            timeslice names, snapshot indices, and hour weightings.
        year : int, optional
            Investment period to plot.  Defaults to the earliest year
            in *snap_result*.
        figsize : tuple of float, optional
            Figure size ``(width, height)`` in inches.

        Returns
        -------
        fig : matplotlib.figure.Figure
        ax : matplotlib.axes.Axes

        Examples
        --------
        >>> snap_result = to_snapshots(scenario_data)
        >>> viz = TimeVisualizer(time_component)
        >>> fig, ax = viz.plot_timeslice_snapshot_map(snap_result)

        See Also
        --------
        plot_timeslice_structure : Hierarchical timeslice chart
        plot_snapshot_timeline : PyPSA snapshot timeline
        """
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches

        self._apply_style()

        # 1. Select year and extract data
        rep_year = (
            year if year is not None
            else snap_result.years[0]
        )
        expected_hours = hours_in_year(rep_year)
        ts_names = snap_result.timeslice_names
        is_multi = isinstance(
            snap_result.snapshots, pd.MultiIndex,
        )

        wt = {}
        for ts in ts_names:
            key = (rep_year, ts) if is_multi else ts
            wt[ts] = float(snap_result.weightings[key])
        total_hours = sum(wt.values())

        # 2. Parse timeslice names → (season, daytype, bracket)
        def _parse(name):
            parts = name.split('_')
            return (
                parts[0] if parts else '?',
                parts[1] if len(parts) > 1 else '?',
                '_'.join(parts[2:])
                if len(parts) > 2 else '?',
            )

        parsed = {ts: _parse(ts) for ts in ts_names}

        # Ordered unique hierarchy elements
        seasons = sorted(
            set(p[0] for p in parsed.values()),
        )
        daytypes = sorted(
            set(p[1] for p in parsed.values()),
        )
        brackets = sorted(
            set(p[2] for p in parsed.values()),
        )

        # Style maps
        season_colors = {
            s: self._color_for_index(i)
            for i, s in enumerate(seasons)
        }
        bracket_hatches = {
            b: self._hatch_for_index(i)
            for i, b in enumerate(brackets)
        }

        # Sort timeslices hierarchically
        ts_sorted = sorted(ts_names, key=lambda t: (
            seasons.index(parsed[t][0]),
            daytypes.index(parsed[t][1]),
            brackets.index(parsed[t][2]),
        ))

        # 3. Create figure
        fig, ax = plt.subplots(figsize=figsize)

        # Layout y-positions
        y_season = 2.0
        y_ts = 1.0
        y_snap = 0.0
        h_s = 0.22      # half-height of season strip
        h_ts = 0.25     # half-height of timeslice bar
        h_mk = 0.20     # half-height of snapshot markers

        # ==========================================================
        # 4. Season strip (top)
        # ==========================================================
        cursor = 0.0
        season_spans = {}
        for s in seasons:
            s_ts = [
                t for t in ts_sorted
                if parsed[t][0] == s
            ]
            s_hours = sum(wt[t] for t in s_ts)
            s_frac = s_hours / total_hours

            rect = mpatches.Rectangle(
                (cursor, y_season - h_s),
                s_frac, 2 * h_s,
                facecolor=season_colors[s],
                edgecolor='black', linewidth=1.0,
                alpha=0.9, zorder=3,
            )
            ax.add_patch(rect)

            # Label inside (only if wide enough)
            if s_frac > 0.06:
                ax.text(
                    cursor + s_frac / 2, y_season,
                    f"{s}\n({s_hours:,.0f} h)",
                    ha='center', va='center',
                    fontsize=10, fontweight='bold',
                    zorder=4,
                )

            season_spans[s] = (cursor, cursor + s_frac)
            cursor += s_frac

        # ==========================================================
        # 5. Timeslice bar (middle, hatched by bracket)
        # ==========================================================
        cursor = 0.0
        for ts in ts_sorted:
            frac = wt[ts] / total_hours
            season = parsed[ts][0]
            bracket = parsed[ts][2]

            rect = mpatches.Rectangle(
                (cursor, y_ts - h_ts),
                frac, 2 * h_ts,
                facecolor=season_colors[season],
                hatch=bracket_hatches[bracket],
                edgecolor='white', linewidth=0.3,
                alpha=0.85, zorder=3,
            )
            ax.add_patch(rect)
            cursor += frac

        # ==========================================================
        # 6. Snapshot timeline (bottom)
        # ==========================================================
        # Main horizontal line
        ax.plot(
            [0, 1], [y_snap, y_snap], '-',
            color='black', linewidth=2, zorder=2,
        )

        # Year boundary markers
        bnd_h = 0.30
        for x in [0.0, 1.0]:
            ax.plot(
                [x, x],
                [y_snap - bnd_h, y_snap + bnd_h],
                color='black', linewidth=2.5, zorder=6,
            )

        # Snapshot markers and coloured segments
        cursor = 0.0
        for ts in ts_sorted:
            frac = wt[ts] / total_hours
            color = season_colors[parsed[ts][0]]

            # Coloured segment on the timeline
            ax.plot(
                [cursor, cursor + frac],
                [y_snap, y_snap],
                color=color, linewidth=5, zorder=3,
                solid_capstyle='butt',
            )
            # Tick mark at segment start
            ax.plot(
                [cursor, cursor],
                [y_snap - h_mk, y_snap + h_mk],
                color=color, linewidth=1.2, zorder=5,
            )
            cursor += frac

        # ==========================================================
        # 7. Dashed connecting lines at season boundaries
        # ==========================================================
        for s, (xs, xe) in season_spans.items():
            color = season_colors[s]
            for x in [xs, xe]:
                ax.plot(
                    [x, x],
                    [y_season - h_s, y_snap + h_mk],
                    color=color, linewidth=0.7,
                    linestyle=':', alpha=0.4, zorder=1,
                )

        # ==========================================================
        # 8. Row labels
        # ==========================================================
        lx = -0.03
        ax.text(
            lx, y_season, 'Seasons',
            ha='right', va='center',
            fontsize=12, fontweight='bold',
        )
        ax.text(
            lx, y_ts, 'Timeslices',
            ha='right', va='center',
            fontsize=12, fontweight='bold',
        )
        ax.text(
            lx, y_snap, 'Snapshots',
            ha='right', va='center',
            fontsize=12, fontweight='bold',
        )

        # ==========================================================
        # 9. Title
        # ==========================================================
        ax.set_title(
            f"OSeMOSYS \u2192 PyPSA Time Mapping"
            f"  (Year {rep_year})\n"
            f"{len(seasons)} seasons \u00d7 "
            f"{len(daytypes)} day types \u00d7 "
            f"{len(brackets)} brackets = "
            f"{len(ts_names)} snapshots  \u00b7  "
            f"{total_hours:,.0f} / {expected_hours} h",
            fontsize=14, pad=20,
        )

        # ==========================================================
        # 10. Legends
        # ==========================================================
        s_handles = [
            mpatches.Patch(
                facecolor=season_colors[s],
                label=s, edgecolor='black',
            )
            for s in seasons
        ]
        leg1 = ax.legend(
            handles=s_handles,
            title='Seasons',
            loc='upper center',
            bbox_to_anchor=(0.5, -0.05),
            ncol=len(seasons),
            frameon=False,
            fontsize=12, title_fontsize=13,
        )
        ax.add_artist(leg1)

        b_handles = [
            mpatches.Patch(
                facecolor='white',
                hatch=bracket_hatches[b],
                label=b, edgecolor='black',
            )
            for b in brackets
        ]
        ax.legend(
            handles=b_handles,
            title='Daily Time Brackets',
            loc='upper center',
            bbox_to_anchor=(0.5, -0.15),
            ncol=len(brackets),
            frameon=False,
            fontsize=12, title_fontsize=13,
        )

        # ==========================================================
        # 11. Clean up
        # ==========================================================
        ax.set_xlim(-0.15, 1.03)
        ax.set_ylim(-0.8, 3.0)
        ax.axis('off')

        plt.tight_layout()
        return fig, ax

    # ------------------------------------------------------------------

    def plot_snapshot_timeslice_map(
        self,
        ts_result: 'TimesliceResult',
        year: Optional[int] = None,
        figsize: Tuple[float, float] = (16, 8),
    ):
        """
        Visualize the mapping from PyPSA snapshots to OSeMOSYS timeslices.

        Draws a three-level diagram for a single model year using the
        compressed-month layout from ``plot_snapshot_timeline()``:

        - **Snapshot timeline** (top) — markers at each snapshot position
          with time labels, solid lines for Jan–May and Dec, zigzag for
          the compressed Jun–Nov zone.
        - **Timeslice bar** (middle) — coloured/hatched segments for each
          timeslice aligned to visible month sections, with a matching
          zigzag for the compressed zone.  No time labels.
        - **Season strip** (bottom) — broad colour blocks showing each
          season's coverage across the visible sections.

        Parameters
        ----------
        ts_result : TimesliceResult
            Result container from ``to_timeslices()``, containing
            DayType, DailyTimeBracket, and Timeslice objects plus the
            snapshot-to-timeslice mapping.
        year : int, optional
            Model year to plot.  Defaults to the earliest year in
            *ts_result*.
        figsize : tuple of float, optional
            Figure size ``(width, height)`` in inches.

        Returns
        -------
        fig : matplotlib.figure.Figure
        ax : matplotlib.axes.Axes

        Examples
        --------
        >>> ts_result = to_timeslices(network.snapshots)
        >>> viz = TimeVisualizer(time_component)
        >>> fig, ax = viz.plot_snapshot_timeslice_map(ts_result)

        See Also
        --------
        plot_timeslice_snapshot_map : OSeMOSYS → PyPSA mapping
        plot_snapshot_timeline : PyPSA snapshot timeline
        """
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        import numpy as np
        from datetime import datetime, date, timedelta

        self._apply_style()

        # ==============================================================
        # 1. Select year and extract snapshot timestamps
        # ==============================================================
        rep_year = (
            year if year is not None else ts_result.years[0]
        )
        year_hours = hours_in_year(rep_year)

        all_snaps = sorted(ts_result.snapshot_to_timeslice.keys())
        snap_times = pd.DatetimeIndex(
            [s for s in all_snaps if s.year == rep_year]
        ).sort_values()
        n_snaps = len(snap_times)

        if n_snaps == 0:
            raise ValueError(
                f"No snapshots for year {rep_year}. "
                f"Available: {ts_result.years}"
            )

        year_start = pd.Timestamp(datetime(rep_year, 1, 1))
        year_end = pd.Timestamp(datetime(
            rep_year, 12, 31,
            ENDOFDAY.hour, ENDOFDAY.minute, ENDOFDAY.second,
        ))
        first_snap = snap_times[0]
        last_snap = snap_times[-1]

        # ==============================================================
        # 2. Section layout (7 sections, same as plot_snapshot_timeline)
        # ==============================================================
        visible_months = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 6: 12}
        sec_pad = 0.03

        def _snap_to_x(
            ts: pd.Timestamp, sec_idx: int, month: int,
        ) -> float:
            m_start = pd.Timestamp(datetime(rep_year, month, 1))
            m_end = (
                pd.Timestamp(datetime(rep_year, month + 1, 1))
                if month < 12
                else pd.Timestamp(datetime(rep_year + 1, 1, 1))
            )
            total_s = (m_end - m_start).total_seconds()
            frac = (
                (ts - m_start).total_seconds() / total_s
                if total_s > 0 else 0.5
            )
            frac = max(0.0, min(1.0, frac))
            return sec_idx + sec_pad + frac * (1 - 2 * sec_pad)

        def _project_snap(ts: pd.Timestamp) -> float:
            m = ts.month
            if 1 <= m <= 5:
                return _snap_to_x(ts, m - 1, m)
            elif m == 12:
                return _snap_to_x(ts, 6, 12)
            else:
                jun1 = pd.Timestamp(datetime(rep_year, 6, 1))
                dec1 = pd.Timestamp(datetime(rep_year, 12, 1))
                frac = (
                    (ts - jun1).total_seconds()
                    / (dec1 - jun1).total_seconds()
                )
                return 5.0 + max(0.0, min(1.0, frac))

        # Group snapshots by visible-month section
        month_snaps: Dict[int, pd.DatetimeIndex] = {}
        for sec_idx, month in visible_months.items():
            month_snaps[sec_idx] = snap_times[
                snap_times.month == month
            ]

        first_x = _project_snap(first_snap)
        last_x = _project_snap(last_snap)

        # ==============================================================
        # 3. Collect style data from TimesliceResult
        # ==============================================================
        seasons = sorted(ts_result.seasons)
        brackets_sorted = sorted(ts_result.dailytimebrackets)
        daytypes_sorted = sorted(ts_result.daytypes)

        season_colors = {
            s: self._color_for_index(i)
            for i, s in enumerate(seasons)
        }
        bracket_hatches = {
            b: self._hatch_for_index(i)
            for i, b in enumerate(brackets_sorted)
        }

        # ==============================================================
        # 4. Build per-month timeslice segments
        # ==============================================================
        # For each visible month, find overlapping (DayType, Bracket)
        # pairs and their fractional width within the section.

        def _days_overlap(dt, month: int) -> int:
            m_start = date(rep_year, month, 1)
            if month == 12:
                m_end = date(rep_year, 12, 31)
            else:
                m_end = (
                    date(rep_year, month + 1, 1) - timedelta(days=1)
                )
            dt_start, dt_end = dt.to_dates(rep_year)
            ov_start = max(m_start, dt_start)
            ov_end = min(m_end, dt_end)
            if ov_start > ov_end:
                return 0
            return (ov_end - ov_start).days + 1

        def _month_days(month: int) -> int:
            if month == 12:
                return (
                    date(rep_year, 12, 31)
                    - date(rep_year, 12, 1)
                ).days + 1
            return (
                date(rep_year, month + 1, 1)
                - date(rep_year, month, 1)
            ).days

        # Pre-compute segments per visible month section
        # Each segment: (frac_width, season, bracket_obj, daytype_obj)
        month_segments: Dict[int, list] = {}
        for sec_idx, month in visible_months.items():
            segs = []
            total_month_d = _month_days(month)
            for dt in daytypes_sorted:
                ov = _days_overlap(dt, month)
                if ov == 0:
                    continue
                day_frac = ov / total_month_d
                for b in brackets_sorted:
                    # Find the matching timeslice
                    ts_match = None
                    for ts in ts_result.timeslices:
                        if ts.daytype == dt and ts.dailytimebracket == b:
                            ts_match = ts
                            break
                    if ts_match is None:
                        continue
                    bracket_frac = b.duration_hours() / 24.0
                    frac_width = day_frac * bracket_frac
                    segs.append((
                        frac_width,
                        ts_match.season,
                        b,
                        dt,
                    ))
            month_segments[sec_idx] = segs

        # ==============================================================
        # 5. Create figure
        # ==============================================================
        fig, ax = plt.subplots(figsize=figsize)

        y_snap = 2.0       # snapshot timeline (top)
        y_ts = 0.8         # timeslice bar (middle)
        y_season = -0.3     # season strip (bottom)
        h_ts = 0.25        # timeslice bar half-height
        h_s = 0.18         # season strip half-height
        mk_h = 0.22        # snapshot marker half-height
        bnd_h = 0.35       # year-boundary half-height

        # ==============================================================
        # 6. Snapshot timeline (top) — solid + zigzag + markers
        # ==============================================================
        # Solid from sections 0-4
        ax.plot(
            [0, 5], [y_snap, y_snap], '-',
            color='black', linewidth=2, zorder=2,
        )
        # Zigzag for section 5
        self._draw_zigzag(
            ax, 5.0, 6.0, y_snap,
            amplitude=0.18, n_teeth=5,
        )
        # Solid for section 6
        ax.plot(
            [6, 7], [y_snap, y_snap], '-',
            color='black', linewidth=2, zorder=2,
        )

        # Dotted overlay outside snapshot coverage
        if first_x > 0.05:
            ax.plot(
                [0, first_x], [y_snap, y_snap], '-',
                color='white', linewidth=5, zorder=3,
            )
            ax.plot(
                [0, first_x], [y_snap, y_snap], ':',
                color='black', linewidth=1.5, zorder=4,
            )
        if last_x < 6.95:
            ax.plot(
                [last_x, 7], [y_snap, y_snap], '-',
                color='white', linewidth=5, zorder=3,
            )
            ax.plot(
                [last_x, 7], [y_snap, y_snap], ':',
                color='black', linewidth=1.5, zorder=4,
            )

        # Year-boundary bars
        for x_pos in [0.0, 7.0]:
            ax.plot(
                [x_pos, x_pos],
                [y_snap - bnd_h, y_snap + bnd_h],
                color='black', linewidth=2.5, zorder=6,
            )

        # Month-boundary bars
        month_bnd_h = 0.18
        for x_pos in [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]:
            ax.plot(
                [x_pos, x_pos],
                [y_snap - month_bnd_h, y_snap + month_bnd_h],
                color='gray', linewidth=1.5, zorder=5,
            )

        # Snapshot markers
        marker_color = self._color_for_index(4)
        MAX_MARKERS = 15
        N_HEAD_MK = 5
        N_TAIL_MK = 2

        for sec_idx, month in visible_months.items():
            snaps = month_snaps[sec_idx]
            n = len(snaps)
            if n == 0:
                continue
            if n <= MAX_MARKERS:
                for ts in snaps:
                    x = _snap_to_x(ts, sec_idx, month)
                    ax.plot(
                        [x, x],
                        [y_snap - mk_h, y_snap + mk_h],
                        color=marker_color, linewidth=2,
                        zorder=5,
                    )
            else:
                nh = min(N_HEAD_MK, n)
                nt = min(N_TAIL_MK, max(0, n - nh))
                for ts in snaps[:nh]:
                    x = _snap_to_x(ts, sec_idx, month)
                    ax.plot(
                        [x, x],
                        [y_snap - mk_h, y_snap + mk_h],
                        color=marker_color, linewidth=2,
                        zorder=5,
                    )
                for ts in snaps[-nt:]:
                    x = _snap_to_x(ts, sec_idx, month)
                    ax.plot(
                        [x, x],
                        [y_snap - mk_h, y_snap + mk_h],
                        color=marker_color, linewidth=2,
                        zorder=5,
                    )
                x_zz_l = (
                    _snap_to_x(snaps[nh - 1], sec_idx, month) + 0.02
                )
                x_zz_r = (
                    _snap_to_x(snaps[n - nt], sec_idx, month) - 0.02
                )
                if x_zz_r > x_zz_l + 0.04:
                    self._draw_zigzag(
                        ax, x_zz_l, x_zz_r, y_snap,
                        amplitude=0.12, n_teeth=6,
                        color='gray', linewidth=1.5, zorder=4,
                    )

        # ==============================================================
        # 7. Snapshot time labels (ABOVE timeline)
        # ==============================================================
        def _fmt(ts: pd.Timestamp) -> str:
            return (
                f"{ts.strftime('%Y-%m-%d')}\n"
                f"{ts.strftime('%H:%M:%S')}"
            )

        label_y_above = y_snap + mk_h + 0.10
        ax.text(
            first_x, label_y_above, _fmt(first_snap),
            ha='center', va='bottom', fontsize=10,
            color=marker_color,
        )
        if abs(last_x - first_x) > 0.4:
            ax.text(
                last_x, label_y_above, _fmt(last_snap),
                ha='center', va='bottom', fontsize=10,
                color=marker_color,
            )

        # Year-boundary labels BELOW snapshot timeline
        label_y_snap_below = y_snap - bnd_h - 0.12
        ax.text(
            0.0, label_y_snap_below, _fmt(year_start),
            ha='center', va='top', fontsize=9,
        )
        ax.text(
            7.0, label_y_snap_below, _fmt(year_end),
            ha='center', va='top', fontsize=9,
        )

        # Month-boundary labels
        month_dates = {
            1.0: datetime(rep_year, 2, 1),
            2.0: datetime(rep_year, 3, 1),
            3.0: datetime(rep_year, 4, 1),
            4.0: datetime(rep_year, 5, 1),
            5.0: datetime(rep_year, 6, 1),
            6.0: datetime(rep_year, 12, 1),
        }
        for x_pos, month_dt in month_dates.items():
            month_ts = pd.Timestamp(month_dt)
            ax.text(
                x_pos, label_y_snap_below, _fmt(month_ts),
                ha='center', va='top', fontsize=8,
                color='gray',
            )

        # ==============================================================
        # 8. Timeslice bar (middle) — coloured rectangles + zigzag
        # ==============================================================
        for sec_idx, month in visible_months.items():
            segs = month_segments.get(sec_idx, [])
            if not segs:
                continue
            total_frac = sum(s[0] for s in segs)
            cursor = float(sec_idx) + sec_pad
            usable = 1.0 - 2 * sec_pad
            for (frac_w, season, bracket, daytype) in segs:
                norm_w = (frac_w / total_frac) * usable if total_frac else 0
                rect = mpatches.Rectangle(
                    (cursor, y_ts - h_ts),
                    norm_w, 2 * h_ts,
                    facecolor=season_colors.get(season, '#cccccc'),
                    hatch=bracket_hatches.get(bracket, ''),
                    edgecolor='white', linewidth=0.3,
                    alpha=0.85, zorder=3,
                )
                ax.add_patch(rect)
                cursor += norm_w

        # Zigzag for compressed Jun-Nov zone
        self._draw_zigzag(
            ax, 5.0, 6.0, y_ts,
            amplitude=0.18, n_teeth=5,
        )

        # Section boundary lines on timeslice bar
        for x_pos in [0.0, 7.0]:
            ax.plot(
                [x_pos, x_pos],
                [y_ts - h_ts - 0.05, y_ts + h_ts + 0.05],
                color='black', linewidth=1.5, zorder=5,
            )
        for x_pos in [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]:
            ax.plot(
                [x_pos, x_pos],
                [y_ts - h_ts, y_ts + h_ts],
                color='gray', linewidth=0.8, zorder=4,
            )

        # ==============================================================
        # 9. Season strip (bottom) — colour blocks per visible section
        # ==============================================================
        # Determine which season(s) cover each section by looking at
        # which timeslice seasons appear in that month.
        for sec_idx, month in visible_months.items():
            segs = month_segments.get(sec_idx, [])
            if not segs:
                continue
            # Aggregate season fractions in this section
            season_fracs: Dict[str, float] = {}
            total_frac = sum(s[0] for s in segs)
            for (frac_w, season, _, _) in segs:
                season_fracs[season] = (
                    season_fracs.get(season, 0) + frac_w
                )
            cursor = float(sec_idx) + sec_pad
            usable = 1.0 - 2 * sec_pad
            for s_name in seasons:
                sf = season_fracs.get(s_name, 0)
                if sf == 0:
                    continue
                norm_w = (sf / total_frac) * usable
                rect = mpatches.Rectangle(
                    (cursor, y_season - h_s),
                    norm_w, 2 * h_s,
                    facecolor=season_colors[s_name],
                    edgecolor='black', linewidth=0.8,
                    alpha=0.9, zorder=3,
                )
                ax.add_patch(rect)
                # Label if wide enough
                if norm_w > 0.35:
                    ax.text(
                        cursor + norm_w / 2, y_season,
                        s_name,
                        ha='center', va='center',
                        fontsize=10, fontweight='bold',
                        zorder=4,
                    )
                cursor += norm_w

        # Season zigzag for compressed zone
        self._draw_zigzag(
            ax, 5.0, 6.0, y_season,
            amplitude=0.12, n_teeth=5,
            color='gray', linewidth=1.5, zorder=2,
        )

        # ==============================================================
        # 10. Row labels
        # ==============================================================
        lx = -0.15
        ax.text(
            lx, y_snap, 'Snapshots',
            ha='right', va='center',
            fontsize=12, fontweight='bold',
        )
        ax.text(
            lx, y_ts, 'Timeslices',
            ha='right', va='center',
            fontsize=12, fontweight='bold',
        )
        ax.text(
            lx, y_season, 'Seasons',
            ha='right', va='center',
            fontsize=12, fontweight='bold',
        )

        # ==============================================================
        # 11. Title
        # ==============================================================
        ax.set_title(
            f"PyPSA \u2192 OSeMOSYS Time Mapping"
            f"  (Year {rep_year})\n"
            f"{n_snaps} snapshots \u2192 "
            f"{len(ts_result.timeslices)} timeslices  "
            f"({len(ts_result.daytypes)} day types "
            f"\u00d7 {len(ts_result.dailytimebrackets)} brackets)",
            fontsize=14, pad=20,
        )

        # ==============================================================
        # 12. Legends — Seasons + DailyTimeBrackets (no DayTypes)
        # ==============================================================
        s_handles = [
            mpatches.Patch(
                facecolor=season_colors[s],
                label=s, edgecolor='black',
            )
            for s in seasons
        ]
        leg1 = ax.legend(
            handles=s_handles,
            title='Seasons',
            loc='upper center',
            bbox_to_anchor=(0.5, -0.02),
            ncol=max(len(seasons), 1),
            frameon=False,
            fontsize=12, title_fontsize=13,
        )
        ax.add_artist(leg1)

        b_handles = [
            mpatches.Patch(
                facecolor='white',
                hatch=bracket_hatches[b],
                label=b.name,
                edgecolor='black',
            )
            for b in brackets_sorted
        ]
        ax.legend(
            handles=b_handles,
            title='Daily Time Brackets',
            loc='upper center',
            bbox_to_anchor=(0.5, -0.10),
            ncol=len(brackets_sorted),
            frameon=False,
            fontsize=12, title_fontsize=13,
        )

        # ==============================================================
        # 13. Clean up
        # ==============================================================
        ax.set_xlim(-0.5, 7.3)
        ax.set_ylim(-1.2, 3.5)
        ax.axis('off')

        plt.tight_layout()
        return fig, ax

    # ==================================================================
    # Convenience entry point
    # ==================================================================

    def show(self, **kwargs) -> None:
        """
        Display the primary visualisation.

        For :class:`TimeComponent` inputs, shows the timeslice structure
        chart.  For PyPSA networks, shows the snapshot timeline.

        Parameters
        ----------
        **kwargs
            Forwarded to the appropriate plot method.
        """
        import matplotlib.pyplot as plt

        if self._network is not None:
            self.plot_snapshot_timeline(**kwargs)
        else:
            self.plot_timeslice_structure(**kwargs)
        plt.show()
