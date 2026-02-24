# pyoscomp/scenario/visualization/demand.py

"""
Visualizations for the DemandComponent of a scenario.

Provides :class:`DemandVisualizer` with the following plots:

- ``plot_demand_composition`` – stacked bar chart of demand by timeslice
  for a single (region, fuel) pair, with flexible demand overlay.
- ``plot_demand_overview`` – one stacked-area subplot per region, all
  fuels stacked

Colour encodes DayType, hatch encodes DailyTimeBracket (consistent
with :class:`TimeVisualizer`).  Flexible demand
(AccumulatedAnnualDemand) is shown in grey with reversed hatching
in the overview and as a separate grey bar in the composition view.
"""

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .base import (
    CB_PALETTE,
    HATCHES,
    ComponentVisualizer,
)
from ..components.demand import DemandComponent


class DemandVisualizer(ComponentVisualizer):
    """
    Visualizer for :class:`DemandComponent`.

    Parameters
    ----------
    component : DemandComponent
        A loaded (or loadable) demand component instance.
    auto_load : bool, optional
        If ``True`` (default), call ``component.load()`` when the data
        frames appear empty.

    Example
    -------
    >>> demand = DemandComponent("path/to/scenario")
    >>> demand.load()
    >>> viz = DemandVisualizer(demand)
    >>> viz.show()
    >>> viz.plot_demand_composition(region="North", fuel="Electricity")
    """

    def __init__(
        self,
        component: DemandComponent,
        auto_load: bool = True,
    ):
        super().__init__(component, auto_load)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        """Load the component if it appears empty and auto_load is on."""
        dc: DemandComponent = self.component
        if self._auto_load and dc.annual_demand_df.empty:
            dc.load()

    def _time_axis(self) -> pd.DataFrame:
        """
        Access the demand component's internal time axis.

        Returns
        -------
        pd.DataFrame
            Columns: TIMESLICE, YEAR, VALUE, Season, DayType,
            DailyTimeBracket.
        """
        dc: DemandComponent = self.component
        return dc._time_axis

    def _style_maps(
        self,
        daytypes: List[str],
        timebrackets: List[str],
    ) -> Tuple[Dict[str, str], Dict[str, str]]:
        """
        Build colour (DayType) and hatch (DailyTimeBracket) style maps.

        Consistent with :class:`TimeVisualizer` ordering.
        """
        dt_style = {
            dt: self._color_for_index(i)
            for i, dt in enumerate(sorted(daytypes))
        }
        tb_style = {
            tb: self._hatch_for_index(i)
            for i, tb in enumerate(sorted(timebrackets))
        }
        return dt_style, tb_style

    # ==================================================================
    # Public plot methods
    # ==================================================================

    def plot_demand_composition(
        self,
        region: str,
        fuel: str,
        legend: bool = True,
        ax=None,
        figsize: Tuple[float, float] = (12, 7),
    ):
        """
        Stacked bar chart of demand composition by timeslice.

        Each bar (year) is decomposed into timeslice segments coloured by
        DayType and hatched by DailyTimeBracket. Flexible demand
        (AccumulatedAnnualDemand), if present, is stacked on top in grey.

        Parameters
        ----------
        region : str
            Region identifier.
        fuel : str
            Fuel/demand identifier.
        legend : bool, optional
            Whether to show legend (default ``True``).
        ax : matplotlib.axes.Axes, optional
            Axes to draw on. If ``None``, a new figure is created.
        figsize : tuple of float, optional
            Figure size ``(width, height)`` in inches (used only when
            *ax* is ``None``).

        Returns
        -------
        fig : matplotlib.figure.Figure
        ax : matplotlib.axes.Axes
        """
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches

        self._apply_style()
        self._ensure_loaded()
        dc: DemandComponent = self.component

        # --- Filter data ---
        df_annual = dc.annual_demand_df[
            (dc.annual_demand_df['REGION'] == region)
            & (dc.annual_demand_df['FUEL'] == fuel)
        ]
        df_profile = dc.profile_demand_df[
            (dc.profile_demand_df['REGION'] == region)
            & (dc.profile_demand_df['FUEL'] == fuel)
        ]

        if df_annual.empty or df_profile.empty:
            raise ValueError(
                f"No demand data for region='{region}', fuel='{fuel}'"
            )

        # Absolute timeslice demand = annual * profile
        merged = pd.merge(df_annual, df_profile, on='YEAR')
        merged['ABS_VALUE'] = merged['VALUE_x'] * merged['VALUE_y']

        plot_data = merged.pivot(
            index='YEAR', columns='TIMESLICE', values='ABS_VALUE',
        )
        plot_data = plot_data.reindex(sorted(plot_data.columns), axis=1)

        # --- Flexible demand ---
        df_flex = dc.accumulated_demand_df[
            (dc.accumulated_demand_df['REGION'] == region)
            & (dc.accumulated_demand_df['FUEL'] == fuel)
        ]
        has_flex = not df_flex.empty

        # --- Timeslice metadata ---
        time_axis = self._time_axis()
        ts_meta: Dict[str, Dict[str, str]] = {}
        daytypes_set: set = set()
        timebrackets_set: set = set()

        for ts in plot_data.columns:
            row = time_axis.loc[time_axis['TIMESLICE'] == ts].iloc[0]
            season = row['Season']
            daytype = row['DayType']
            timebracket = row['DailyTimeBracket']
            daytypes_set.add(daytype)
            timebrackets_set.add(timebracket)
            ts_meta[ts] = {
                'season': season,
                'daytype': daytype,
                'timebracket': timebracket,
            }

        dt_color, tb_hatch = self._style_maps(
            list(daytypes_set), list(timebrackets_set),
        )

        # --- Plotting ---
        created_fig = ax is None
        if created_fig:
            fig, ax = plt.subplots(figsize=figsize)
        else:
            fig = ax.figure

        bottoms = np.zeros(len(plot_data))
        years_x = plot_data.index.astype(str)

        legend_handles: Dict[str, object] = {}
        for ts in plot_data.columns:
            values = plot_data[ts].fillna(0).values
            meta = ts_meta[ts]
            color = dt_color[meta['daytype']]
            hatch = tb_hatch[meta['timebracket']]
            legend_key = f"{meta['daytype']} | {meta['timebracket']}"

            bar = ax.bar(
                years_x, values, bottom=bottoms,
                color=color, hatch=hatch,
                edgecolor='white', linewidth=0.5,
            )
            if legend_key not in legend_handles:
                legend_handles[legend_key] = bar[0]
            bottoms += values

        # Flexible demand on top in grey
        if has_flex:
            flex_vals = np.zeros(len(plot_data))
            for i, yr in enumerate(plot_data.index):
                match = df_flex[df_flex['YEAR'] == yr]
                if not match.empty:
                    flex_vals[i] = match['VALUE'].values[0]

            bar_flex = ax.bar(
                years_x, flex_vals, bottom=bottoms,
                color='#AAAAAA', edgecolor='white', linewidth=0.5,
                label='Flexible Demand',
            )
            legend_handles['Flexible'] = bar_flex[0]

        # --- Formatting ---
        ax.set_ylabel("Energy Demand (Model Units)", fontsize=14)
        ax.set_xlabel("Year", fontsize=14)
        ax.set_title(
            f"Demand Composition: {region} — {fuel}",
            fontsize=18, pad=15,
        )
        ax.grid(axis='y', linestyle='--', alpha=0.3)
        self._strip_spines(ax, keep=['bottom', 'left'])

        if legend:
            handles = list(legend_handles.values())
            labels = list(legend_handles.keys())
            if len(handles) > 10:
                ax.legend(
                    handles, labels,
                    title="Daytype | Timebracket",
                    bbox_to_anchor=(1.05, 1), loc='upper left',
                    fontsize=10, title_fontsize=12,
                )
            else:
                ax.legend(
                    handles, labels,
                    title="Daytype | Timebracket",
                    loc='best',
                    fontsize=10, title_fontsize=12,
                )

        plt.tight_layout()
        return fig, ax

    # ------------------------------------------------------------------

    def plot_demand_overview(
        self,
        figsize_per_row: Tuple[float, float] = (12, 7),
    ):
        """
        One stacked-area subplot per region with all fuels stacked.

        Fuels are distinguished by hatch pattern on a dark-slate base
        colour.  Flexible demand (AccumulatedAnnualDemand), if present,
        is stacked on top using reversed hatching.

        All subplots share x- and y-axis limits for easy comparison.

        Parameters
        ----------
        figsize_per_row : tuple of float, optional
            ``(width, height)`` for each subplot row.

        Returns
        -------
        fig : matplotlib.figure.Figure
        axes : list of matplotlib.axes.Axes
        """
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches

        self._apply_style()
        self._ensure_loaded()
        dc: DemandComponent = self.component

        if dc.annual_demand_df.empty:
            raise ValueError("No annual demand data to visualize.")

        fill_color = 'darkslategrey'

        regions = sorted(dc.profile_demand_df['REGION'].unique())
        fuels = sorted(dc.profile_demand_df['FUEL'].unique())
        n_regions = len(regions)

        fuel_hatch = {
            fuel: self._hatch_for_index(i)
            for i, fuel in enumerate(fuels)
        }

        fig_w, fig_h = figsize_per_row
        fig, axes = plt.subplots(
            nrows=n_regions, ncols=1,
            figsize=(fig_w, fig_h * n_regions),
            squeeze=False,
        )
        axes = [ax for row in axes for ax in row]

        # Combine specified and flexible annual demand
        annual_demand_combined = dc.annual_demand_df.copy()
        if not dc.accumulated_demand_df.empty:
            for _, flex_row in dc.accumulated_demand_df.iterrows():
                region, fuel, year = flex_row['REGION'], flex_row['FUEL'], flex_row['YEAR']
                flex_val = flex_row['VALUE']
                mask = (
                    (annual_demand_combined['REGION'] == region)
                    & (annual_demand_combined['FUEL'] == fuel)
                    & (annual_demand_combined['YEAR'] == year)
                )
                if mask.any():
                    annual_demand_combined.loc[mask, 'VALUE'] += flex_val
                else:
                    # No existing annual demand; add flexible as a new row
                    annual_demand_combined = pd.concat([
                        annual_demand_combined,
                        pd.DataFrame([{
                            'REGION': region,
                            'FUEL': fuel,
                            'YEAR': year,
                            'VALUE': flex_val
                        }])
                    ], ignore_index=True)

        global_ys: List[Tuple[float, float]] = []
        global_xs: List[Tuple[float, float]] = []

        for idx, region in enumerate(regions):
            ax = axes[idx]

            # Profile demand grouped per (year, fuel) → total
            region_profile = dc.profile_demand_df[
                dc.profile_demand_df['REGION'] == region
            ]
            grouped = (
                region_profile
                .groupby(['YEAR', 'FUEL'])['VALUE']
                .sum()
                .unstack(fill_value=0)
            )
            years = grouped.index.values
            fuel_names = grouped.columns.tolist()

            # Scale by combined annual demand (specified + flexible)
            for fuel in fuel_names:
                for y in years:
                    mask = (
                        (annual_demand_combined['REGION'] == region)
                        & (annual_demand_combined['FUEL'] == fuel)
                        & (annual_demand_combined['YEAR'] == y)
                    )
                    matches = annual_demand_combined.loc[mask, 'VALUE']
                    if not matches.empty:
                        grouped.at[y, fuel] *= matches.values[0]
                    else:
                        grouped.at[y, fuel] = 0

            # Stacked area (specified + flexible demand combined)
            y_arrays = [grouped[fuel].values for fuel in fuel_names]
            polys = ax.stackplot(
                years, y_arrays, labels=fuel_names, colors=[fill_color],
            )
            for poly, fuel in zip(polys, fuel_names):
                poly.set_hatch(fuel_hatch[fuel])
                poly.set_edgecolor('white')
                poly.set_linewidth(0.5)

            ax.set_title(f"Region: {region}", fontsize=16)
            ax.set_ylabel("Total Demand (Model Units)", fontsize=14)
            ax.grid(axis='y', linestyle='--', alpha=0.3)
            self._strip_spines(ax, keep=['bottom', 'left'])

            global_ys.append(ax.get_ylim())
            global_xs.append(ax.get_xlim())

            if idx == n_regions - 1:
                ax.set_xlabel("Year", fontsize=14)

        # --- Shared limits ---
        y_min = min(yl[0] for yl in global_ys)
        y_max = max(yl[1] for yl in global_ys)
        x_min = min(xl[0] for xl in global_xs)
        x_max = max(xl[1] for xl in global_xs)
        for ax in axes:
            ax.set_ylim(y_min, y_max)
            ax.set_xlim(x_min, x_max)

        # Hide unused subplots (shouldn't happen, but defensive)
        for j in range(n_regions, len(axes)):
            fig.delaxes(axes[j])

        # --- Global fuel legend ---
        fuel_handles = [
            mpatches.Patch(
                facecolor='white', edgecolor='k',
                label=fuel, hatch=fuel_hatch[fuel],
            )
            for fuel in fuels
        ]
        fig.legend(
            handles=fuel_handles,
            title="Fuel",
            loc='upper center',
            bbox_to_anchor=(0.5, 1.03),
            ncol=min(len(fuel_handles), 5),
            frameon=False,
            handleheight=2.0,
            handlelength=3.0,
            fontsize=14,
            title_fontsize=16,
        )

        plt.tight_layout()
        return fig, axes

    # ==================================================================
    # Convenience entry point
    # ==================================================================

    def show(self, **kwargs) -> None:
        """
        Display the primary visualisation (demand overview).

        Parameters
        ----------
        **kwargs
            Forwarded to :meth:`plot_demand_overview`.
        """
        import matplotlib.pyplot as plt

        self.plot_demand_overview(**kwargs)
        plt.show()
