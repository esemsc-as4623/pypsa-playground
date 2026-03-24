"""Visualization utilities for input harmonization and divergence diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pypsa.common import annuity

from ..interfaces import DivergenceFlag, ModelResults, ScenarioData


class HarmonizationViolation(Exception):
    """Raised when a critical harmonization check fails."""


@dataclass(frozen=True)
class _CostRow:
    """Internal cost container for plotting and summary metrics."""

    name: str
    osemosys: float
    pypsa: float
    kind: str
    components: Dict[str, float]


class HarmonizationVisualizer:
    """Build harmonization and cross-model diagnostic figures."""

    def plot_time_structure(self, scenario_data: ScenarioData, network):
        """Plot OSeMOSYS YearSplit and PyPSA snapshot weights."""
        self._validate_year_split(scenario_data)

        year = self._first_year(scenario_data)
        ys, py = self._time_fractions_for_year(scenario_data, network, year)
        aligned = self._align_series(ys, py)
        discrepancy = (aligned["osemosys"] - aligned["pypsa"]).abs()

        fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
        x = np.arange(len(aligned))
        high = discrepancy > 0.001

        colors_left = np.where(high, "#d62728", "#4c72b0")
        colors_right = np.where(high, "#d62728", "#55a868")

        axes[0].bar(x, aligned["osemosys"].values, color=colors_left)
        axes[0].set_title(f"OSeMOSYS YearSplit ({year})")
        axes[0].set_ylabel("Fraction of year")
        axes[0].set_xticks(x)
        axes[0].set_xticklabels(aligned.index, rotation=45, ha="right")

        axes[1].bar(x, aligned["pypsa"].values, color=colors_right)
        axes[1].set_title(f"PyPSA Snapshot Weightings ({year})")
        axes[1].set_xticks(x)
        axes[1].set_xticklabels(aligned.index, rotation=45, ha="right")

        for ax in axes:
            ax.grid(axis="y", alpha=0.3)

        fig.suptitle(
            "Time Structure Harmonization - YearSplit vs Snapshot Weightings"
        )
        fig.tight_layout()
        return fig

    def plot_demand_profile(self, scenario_data: ScenarioData, network):
        """Plot OSeMOSYS and PyPSA annual demand allocation profiles."""
        year = self._first_year(scenario_data)

        osemosys_stack, osemosys_total = self._osemosys_demand_by_timeslice(
            scenario_data,
            years=[year],
        )
        pypsa_timeslice, pypsa_total = self._pypsa_demand_by_timeslice(
            network,
            years=[year],
        )

        index = sorted(set(osemosys_stack.index) | set(pypsa_timeslice.index))
        stack_plot = osemosys_stack.reindex(index, fill_value=0.0)
        py_plot = pypsa_timeslice.reindex(index, fill_value=0.0)

        fig, axes = plt.subplots(1, 2, figsize=(15, 5), sharey=True)

        if not stack_plot.empty:
            bottom = np.zeros(len(index), dtype=float)
            x = np.arange(len(index))
            for col in stack_plot.columns:
                vals = stack_plot[col].to_numpy(dtype=float)
                axes[0].bar(x, vals, bottom=bottom, label=col)
                bottom = bottom + vals
            axes[0].set_xticks(x)
            axes[0].set_xticklabels(index, rotation=45, ha="right")
            if len(stack_plot.columns) <= 8:
                axes[0].legend(loc="upper right", fontsize=8)
        else:
            axes[0].text(
                0.5,
                0.5,
                "No OSeMOSYS demand data",
                ha="center",
                va="center",
                transform=axes[0].transAxes,
            )

        x = np.arange(len(index))
        axes[1].bar(x, py_plot.values, color="#55a868")
        axes[1].set_xticks(x)
        axes[1].set_xticklabels(index, rotation=45, ha="right")

        ymax = max(
            float(stack_plot.sum(axis=1).max()) if not stack_plot.empty else 0.0,
            float(py_plot.max()) if not py_plot.empty else 0.0,
        )
        if ymax > 0:
            axes[0].set_ylim(0.0, ymax * 1.12)

        axes[0].set_title("OSeMOSYS demand by timeslice (MWh)")
        axes[1].set_title("PyPSA demand by snapshot (MWh)")
        axes[0].set_ylabel("Energy (MWh)")
        for ax in axes:
            ax.grid(axis="y", alpha=0.3)

        axes[0].text(
            0.02,
            0.95,
            f"Total: {osemosys_total / 1e6:.4f} TWh",
            transform=axes[0].transAxes,
            va="top",
        )
        axes[1].text(
            0.02,
            0.95,
            f"Total: {pypsa_total / 1e6:.4f} TWh",
            transform=axes[1].transAxes,
            va="top",
        )

        fig.suptitle("Demand Profile Harmonization")
        fig.tight_layout()
        return fig

    def plot_capacity_factor_profile(
        self,
        scenario_data: ScenarioData,
        network,
        technology: str,
    ):
        """Plot OSeMOSYS and PyPSA capacity-factor profile for one technology."""
        year = self._first_year(scenario_data)
        osemosys = self._osemosys_capacity_factor_series(
            scenario_data,
            technology,
            years=[year],
        )
        pypsa = self._pypsa_capacity_factor_series(network, technology, years=[year])

        aligned = self._align_series(osemosys, pypsa)
        x = np.arange(len(aligned))

        fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
        axes[0].step(x, aligned["osemosys"].values, where="mid", color="#4c72b0")
        axes[1].step(x, aligned["pypsa"].values, where="mid", color="#55a868")

        axes[0].set_title(f"OSeMOSYS CF x AF ({year})")
        axes[1].set_title(f"PyPSA p_max_pu ({year})")
        for ax in axes:
            ax.set_xticks(x)
            ax.set_xticklabels(aligned.index, rotation=45, ha="right")
            ax.set_ylim(0.0, min(1.05, max(1.0, float(aligned.max().max() * 1.1))))
            ax.grid(alpha=0.3)

        axes[0].set_ylabel("Capacity factor")
        axes[0].text(
            0.02,
            0.95,
            f"Mean: {aligned['osemosys'].mean():.4f}",
            transform=axes[0].transAxes,
            va="top",
        )
        axes[1].text(
            0.02,
            0.95,
            f"Mean: {aligned['pypsa'].mean():.4f}",
            transform=axes[1].transAxes,
            va="top",
        )

        fig.suptitle(f"Capacity Factor Profile - {technology}")
        fig.tight_layout()
        return fig

    def plot_capital_cost_comparison(self, scenario_data: ScenarioData, network):
        """Compare annualized OSeMOSYS CAPEX and translated PyPSA capital costs."""
        rows = self._collect_capital_cost_rows(scenario_data, network)

        fig, ax = plt.subplots(figsize=(12, max(4.0, len(rows) * 0.65 + 1.0)))
        if not rows:
            ax.text(0.5, 0.5, "No comparable technologies found", ha="center", va="center")
            ax.set_axis_off()
            fig.suptitle("Annualized Capital Cost Harmonization (EUR/MW/year)")
            fig.tight_layout()
            return fig

        y = np.arange(len(rows))
        h = 0.36

        for i, row in enumerate(rows):
            if row.kind == "storage":
                left = 0.0
                comp_colors = [
                    ("reservoir", "#4c72b0"),
                    ("charge", "#8172b2"),
                    ("discharge", "#64b5cd"),
                ]
                for comp, color in comp_colors:
                    val = float(row.components.get(comp, 0.0))
                    if val <= 0:
                        continue
                    label = f"OSeMOSYS {comp}" if i == 0 else None
                    ax.barh(i - h / 2, val, height=h, left=left, color=color, label=label)
                    left += val
            else:
                label = "OSeMOSYS annualized" if i == 0 else None
                ax.barh(i - h / 2, row.osemosys, height=h, color="#4c72b0", label=label)

            label = "PyPSA capital_cost" if i == 0 else None
            ax.barh(i + h / 2, row.pypsa, height=h, color="#55a868", label=label)

            rel = self._relative_diff(row.pypsa, row.osemosys) * 100.0
            x_text = max(row.osemosys, row.pypsa) * 1.02 if max(row.osemosys, row.pypsa) > 0 else 0.0
            ax.text(x_text, i, f"{rel:+.2f}%", va="center", fontsize=9)

        ax.set_yticks(y)
        ax.set_yticklabels([r.name for r in rows])
        ax.set_xlabel("Cost (EUR/MW/year)")
        ax.grid(axis="x", alpha=0.3)
        ax.legend(loc="best")
        fig.suptitle("Annualized Capital Cost Harmonization (EUR/MW/year)")
        fig.tight_layout()
        return fig

    def plot_translation_report(self, scenario_data: ScenarioData, network):
        """Create a 2x2 summary dashboard of translation fidelity metrics."""
        self._validate_year_split(scenario_data)

        max_time = self._max_time_weight_discrepancy(scenario_data, network)

        _, demand_total_ose = self._osemosys_demand_by_timeslice(scenario_data)
        _, demand_total_py = self._pypsa_demand_by_timeslice(network)
        demand_rel = abs(self._relative_diff(demand_total_py, demand_total_ose))

        max_cf = self._max_capacity_factor_discrepancy(scenario_data, network)
        max_cost = self._max_capital_cost_discrepancy(scenario_data, network)

        metrics = [
            (
                "Time Structure",
                max_time <= 0.001,
                f"max discrepancy: {max_time * 100:.3f}%",
            ),
            (
                "Demand",
                demand_rel <= 0.001,
                f"annual discrepancy: {demand_rel * 100:.3f}%",
            ),
            (
                "Capacity Factors",
                max_cf <= 0.005,
                f"max discrepancy: {max_cf * 100:.3f}%",
            ),
            (
                "Capital Costs",
                max_cost <= 0.01,
                f"max discrepancy: {max_cost * 100:.3f}%",
            ),
        ]

        fig, axes = plt.subplots(2, 2, figsize=(11, 8))
        for ax, (title, passed, detail) in zip(axes.flatten(), metrics):
            color = "#d9f2d9" if passed else "#f8d7da"
            ax.set_facecolor(color)
            ax.text(0.5, 0.65, title, ha="center", va="center", fontsize=12, fontweight="bold")
            ax.text(0.5, 0.45, "PASS" if passed else "FAIL", ha="center", va="center", fontsize=16)
            ax.text(0.5, 0.26, detail, ha="center", va="center", fontsize=10)
            ax.set_xticks([])
            ax.set_yticks([])

        fig.suptitle("Translation Harmonization Report")
        fig.tight_layout()
        return fig

    def plot_capacity_comparison(self, results_a: ModelResults, results_b: ModelResults):
        """Plot grouped installed-capacity comparison across two models."""
        merged = self._capacity_comparison_frame(results_a, results_b)

        fig, ax = plt.subplots(figsize=(12, max(4.5, len(merged) * 0.55 + 1.2)))
        if merged.empty:
            ax.text(0.5, 0.5, "No capacity results to compare", ha="center", va="center")
            ax.set_axis_off()
            fig.suptitle(
                f"Installed Capacity: {results_a.model_name} vs "
                f"{results_b.model_name}"
            )
            fig.tight_layout()
            return fig

        y = np.arange(len(merged))
        h = 0.36
        a_vals = merged[results_a.model_name].to_numpy(dtype=float)
        b_vals = merged[results_b.model_name].to_numpy(dtype=float)

        ax.barh(y - h / 2, a_vals, height=h, label=results_a.model_name, color="#4c72b0")
        ax.barh(y + h / 2, b_vals, height=h, label=results_b.model_name, color="#55a868")

        for i, row in merged.iterrows():
            rel = self._relative_diff(row[results_a.model_name], row[results_b.model_name]) * 100.0
            diff = row[results_a.model_name] - row[results_b.model_name]
            xt = max(row[results_a.model_name], row[results_b.model_name])
            ax.text(
                xt * 1.02 if xt > 0 else 0.0,
                i,
                f"DIFF={diff:.2f} MW ({rel:+.2f}%)",
                va="center",
                fontsize=8,
            )

        ax.set_yticks(y)
        ax.set_yticklabels(merged["LABEL"])
        ax.set_xlabel("Capacity (MW)")
        ax.grid(axis="x", alpha=0.3)
        ax.legend(loc="best")
        fig.suptitle(
            f"Installed Capacity: {results_a.model_name} vs "
            f"{results_b.model_name}"
        )
        fig.tight_layout()
        return fig

    def plot_dispatch_comparison(self, results_a: ModelResults, results_b: ModelResults):
        """Plot annual dispatch shares and volumes for two model outputs."""
        prod_a = self._annual_production_by_technology(results_a)
        prod_b = self._annual_production_by_technology(results_b)

        techs = sorted(set(prod_a.index) | set(prod_b.index))
        a_vals = prod_a.reindex(techs, fill_value=0.0)
        b_vals = prod_b.reindex(techs, fill_value=0.0)

        fig = plt.figure(figsize=(13, 8))
        gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.2])
        ax1 = fig.add_subplot(gs[0, 0])
        ax2 = fig.add_subplot(gs[0, 1])
        ax3 = fig.add_subplot(gs[1, :])

        self._plot_pie(ax1, a_vals, results_a.model_name)
        self._plot_pie(ax2, b_vals, results_b.model_name)

        x = np.arange(len(techs))
        w = 0.38
        ax3.bar(x - w / 2, a_vals.values, width=w, label=results_a.model_name, color="#4c72b0")
        ax3.bar(x + w / 2, b_vals.values, width=w, label=results_b.model_name, color="#55a868")
        ax3.set_xticks(x)
        ax3.set_xticklabels(techs, rotation=45, ha="right")
        ax3.set_ylabel("Annual production (MWh)")
        ax3.grid(axis="y", alpha=0.3)
        ax3.legend(loc="best")

        pypsa_result = self._pick_pypsa_results(results_a, results_b)
        curtail_note = "Curtailment rate: N/A"
        if pypsa_result is not None:
            curtail = float(pypsa_result.dispatch.curtailment.get("VALUE", pd.Series(dtype=float)).sum())
            prod = float(pypsa_result.dispatch.production.get("VALUE", pd.Series(dtype=float)).sum())
            rate = 0.0 if (prod + curtail) <= 0 else 100.0 * curtail / (prod + curtail)
            curtail_note = f"PyPSA curtailment rate: {rate:.2f}%"
        fig.text(0.5, 0.02, curtail_note, ha="center", fontsize=10)

        fig.suptitle("Annual Energy Dispatch Comparison")
        fig.tight_layout(rect=[0, 0.04, 1, 0.96])
        return fig

    def plot_cost_comparison(self, results_a: ModelResults, results_b: ModelResults):
        """Plot system cost decomposition for two model outputs."""
        comp_a = self._cost_components(results_a)
        comp_b = self._cost_components(results_b)

        fig, ax = plt.subplots(figsize=(10, 6))
        labels = [results_a.model_name, results_b.model_name]
        x = np.arange(2)

        keys = ["capex", "fixed_opex", "variable_opex", "salvage"]
        colors = {
            "capex": "#4c72b0",
            "fixed_opex": "#55a868",
            "variable_opex": "#c44e52",
            "salvage": "#8172b2",
        }

        bottoms = np.zeros(2, dtype=float)
        data = {
            "capex": np.array([comp_a["capex"], comp_b["capex"]], dtype=float),
            "fixed_opex": np.array([comp_a["fixed_opex"], comp_b["fixed_opex"]], dtype=float),
            "variable_opex": np.array([comp_a["variable_opex"], comp_b["variable_opex"]], dtype=float),
            "salvage": -np.array([comp_a["salvage"], comp_b["salvage"]], dtype=float),
        }

        for key in keys:
            vals = data[key]
            ax.bar(x, vals, bottom=bottoms, color=colors[key], label=key)
            bottoms = bottoms + vals

        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.set_ylabel("Cost")
        ax.grid(axis="y", alpha=0.3)
        ax.legend(loc="best")

        total_a = comp_a["total_system_cost"]
        total_b = comp_b["total_system_cost"]
        rel = self._relative_diff(total_a, total_b) * 100.0
        ax.text(0.5, 0.95, f"Relative total cost diff: {rel:+.2f}%", transform=ax.transAxes, ha="center", va="top")

        fig.text(
            0.5,
            0.01,
            "OSeMOSYS uses lump-sum + salvage value; PyPSA uses annualized costs. "
            "Objective values are not directly comparable.",
            ha="center",
            fontsize=9,
        )
        fig.suptitle("System Cost Decomposition")
        fig.tight_layout(rect=[0, 0.05, 1, 0.95])
        return fig

    def plot_divergence_summary(self, flags: List[DivergenceFlag]):
        """Plot divergence flags returned by divergence_analysis()."""
        fig, ax = plt.subplots(figsize=(11, max(4.0, len(flags) * 0.55 + 1.0)))
        if not flags:
            ax.text(0.5, 0.5, "No divergence flags", ha="center", va="center")
            ax.set_axis_off()
            fig.suptitle("Output Divergence Analysis")
            fig.tight_layout()
            return fig

        labels = [f.category for f in flags]
        values = [100.0 * float(f.max_rel_diff) for f in flags]
        colors = ["#ff7f0e" if f.structural else "#d62728" for f in flags]

        y = np.arange(len(flags))
        ax.barh(y, values, color=colors)
        ax.set_yticks(y)
        ax.set_yticklabels(labels)
        ax.set_xlabel("Relative difference (%)")
        ax.grid(axis="x", alpha=0.3)

        for i, flag in enumerate(flags):
            ax.text(values[i] * 1.01 if values[i] > 0 else 0.0, i, f"n={flag.n_mismatches}", va="center", fontsize=9)

        fig.suptitle("Output Divergence Analysis")
        fig.tight_layout()
        return fig

    @staticmethod
    def _snapshot_weight_frame(network) -> pd.DataFrame:
        """Return snapshot weights as YEAR/TIMESLICE rows."""
        weights = pd.Series(network.snapshot_weightings["generators"], index=network.snapshots)
        if isinstance(network.snapshots, pd.MultiIndex):
            frame = weights.reset_index()
            frame.columns = ["YEAR", "TIMESLICE", "WEIGHT"]
        else:
            frame = pd.DataFrame(
                {
                    "YEAR": [None] * len(weights),
                    "TIMESLICE": list(network.snapshots),
                    "WEIGHT": weights.values,
                }
            )
        return frame

    @staticmethod
    def _first_year(scenario_data: ScenarioData) -> int:
        """Return the smallest model year from ScenarioData."""
        return int(sorted(scenario_data.sets.years)[0])

    def _validate_year_split(self, scenario_data: ScenarioData) -> None:
        """Validate that YearSplit sums to one for each model year."""
        year_split = scenario_data.time.year_split
        if year_split.empty:
            raise HarmonizationViolation("YearSplit is empty")

        sums = year_split.groupby("YEAR")["VALUE"].sum()
        for year, total in sums.items():
            if abs(float(total) - 1.0) > 1e-4:
                raise HarmonizationViolation(
                    f"YearSplit for {year} sums to {total:.6f}, expected 1.0"
                )

    def _time_fractions_for_year(
        self,
        scenario_data: ScenarioData,
        network,
        year: int,
    ) -> Tuple[pd.Series, pd.Series]:
        """Return normalized OSeMOSYS and PyPSA time fractions for one year."""
        ys = (
            scenario_data.time.year_split
            .loc[scenario_data.time.year_split["YEAR"] == year]
            .groupby("TIMESLICE")["VALUE"]
            .sum()
            .sort_index()
        )
        ys = ys / ys.sum() if ys.sum() > 0 else ys

        weights = self._snapshot_weight_frame(network)
        if weights["YEAR"].notna().any():
            weights = weights[weights["YEAR"] == year]

        py = weights.groupby("TIMESLICE")["WEIGHT"].sum().sort_index()
        py = py / py.sum() if py.sum() > 0 else py
        return ys, py

    @staticmethod
    def _align_series(left: pd.Series, right: pd.Series) -> pd.DataFrame:
        """Align two named series on a shared index and fill missing values."""
        idx = sorted(set(left.index) | set(right.index))
        return pd.DataFrame(
            {
                "osemosys": left.reindex(idx, fill_value=0.0),
                "pypsa": right.reindex(idx, fill_value=0.0),
            },
            index=idx,
        )

    def _osemosys_demand_by_timeslice(
        self,
        scenario_data: ScenarioData,
        years: Optional[Sequence[int]] = None,
    ) -> Tuple[pd.DataFrame, float]:
        """Return OSeMOSYS timeslice demand stack and annual total."""
        annual = scenario_data.demand.specified_annual_demand
        profile = scenario_data.demand.specified_demand_profile

        if annual.empty or profile.empty:
            return pd.DataFrame(), 0.0

        if years is not None:
            annual = annual[annual["YEAR"].isin(years)]
            profile = profile[profile["YEAR"].isin(years)]

        merged = annual.merge(
            profile,
            on=["REGION", "FUEL", "YEAR"],
            suffixes=("_annual", "_profile"),
        )
        merged["ENERGY"] = merged["VALUE_annual"] * merged["VALUE_profile"]
        merged["STACK"] = merged["REGION"].astype(str) + "|" + merged["FUEL"].astype(str)

        stack = (
            merged.pivot_table(
                index="TIMESLICE",
                columns="STACK",
                values="ENERGY",
                aggfunc="sum",
                fill_value=0.0,
            )
            .sort_index()
        )
        total = float(merged["ENERGY"].sum())
        return stack, total

    def _pypsa_demand_by_timeslice(
        self,
        network,
        years: Optional[Sequence[int]] = None,
    ) -> Tuple[pd.Series, float]:
        """Return PyPSA timeslice demand energy and annual total."""
        if network.loads_t.p_set.empty:
            return pd.Series(dtype=float), 0.0

        weights = pd.Series(network.snapshot_weightings["generators"], index=network.snapshots)
        weighted = network.loads_t.p_set.mul(weights, axis=0)

        frame = weighted.copy()
        if isinstance(frame.index, pd.MultiIndex):
            if years is not None:
                frame = frame.loc[frame.index.get_level_values(0).isin(list(years))]
            grouped = frame.groupby(level=1).sum()
        else:
            grouped = frame

        by_timeslice = grouped.sum(axis=1).sort_index()
        return by_timeslice, float(by_timeslice.sum())

    def _osemosys_capacity_factor_series(
        self,
        scenario_data: ScenarioData,
        technology: str,
        years: Optional[Sequence[int]] = None,
    ) -> pd.Series:
        """Return OSeMOSYS CapacityFactor x AvailabilityFactor profile."""
        cf = scenario_data.performance.capacity_factor
        af = scenario_data.performance.availability_factor

        if cf.empty:
            raise ValueError("CapacityFactor data is empty")

        cf = cf[cf["TECHNOLOGY"] == technology]
        af = af[af["TECHNOLOGY"] == technology]
        if years is not None:
            cf = cf[cf["YEAR"].isin(years)]
            af = af[af["YEAR"].isin(years)]

        if cf.empty:
            raise ValueError(f"Technology {technology} not found in CapacityFactor")

        merged = cf.merge(
            af[["REGION", "TECHNOLOGY", "YEAR", "VALUE"]],
            on=["REGION", "TECHNOLOGY", "YEAR"],
            suffixes=("_cf", "_af"),
            how="left",
        )
        merged["VALUE"] = merged["VALUE_cf"] * merged["VALUE_af"].fillna(1.0)
        grouped = (
            merged.groupby(["YEAR", "TIMESLICE"])["VALUE"]
            .mean()
            .sort_index()
        )

        if years is not None and len(years) == 1:
            year = list(years)[0]
            out = grouped.loc[year]
            out.index = out.index.astype(str)
            return out

        out = grouped.copy()
        out.index = [f"{yr}:{ts}" for yr, ts in out.index]
        return out

    def _pypsa_capacity_factor_series(
        self,
        network,
        technology: str,
        years: Optional[Sequence[int]] = None,
    ) -> pd.Series:
        """Return PyPSA p_max_pu profile for technology name prefix."""
        candidates = [name for name in network.generators.index if str(name).startswith(technology)]
        if not candidates:
            candidates = [
                name for name in network.generators.index
                if f"_{technology}" in str(name)
            ]
        if not candidates:
            raise ValueError(f"No generator found for technology {technology}")

        data = network.generators_t.p_max_pu[candidates].mean(axis=1)

        if isinstance(data.index, pd.MultiIndex):
            if years is not None:
                data = data.loc[data.index.get_level_values(0).isin(list(years))]
            grouped = data.groupby(level=[0, 1]).mean().sort_index()
            if years is not None and len(years) == 1:
                year = list(years)[0]
                out = grouped.loc[year]
                out.index = out.index.astype(str)
                return out
            out = grouped.copy()
            out.index = [f"{yr}:{ts}" for yr, ts in out.index]
            return out

        return data.sort_index()

    def _collect_capital_cost_rows(
        self,
        scenario_data: ScenarioData,
        network,
    ) -> List[_CostRow]:
        """Build cost rows for generators and storage assets."""
        year = self._first_year(scenario_data)
        dr_df = scenario_data.economics.discount_rate
        discount_rate = float(dr_df["VALUE"].iloc[0]) if not dr_df.empty else 0.05

        cap_cost = scenario_data.economics.capital_cost
        op_life = scenario_data.supply.operational_life

        rows: List[_CostRow] = []

        for gen_name in network.generators.index:
            bus = str(network.generators.loc[gen_name, "bus"])
            tech = self._canonical_name(str(gen_name), bus)

            cc = self._lookup_region_tech_year(cap_cost, bus, tech, year)
            life = self._lookup_region_tech(op_life, bus, tech)
            if life <= 0:
                continue

            osemosys_val = cc * annuity(discount_rate, life)
            pypsa_val = float(network.generators.loc[gen_name, "capital_cost"])
            rows.append(
                _CostRow(
                    name=tech,
                    osemosys=osemosys_val,
                    pypsa=pypsa_val,
                    kind="generator",
                    components={"annualized": osemosys_val},
                )
            )

        storage_rows = self._collect_storage_cost_rows(
            scenario_data,
            network,
            year,
            discount_rate,
        )
        rows.extend(storage_rows)

        if not rows:
            return []

        frame = pd.DataFrame(
            {
                "name": [r.name for r in rows],
                "osemosys": [r.osemosys for r in rows],
                "pypsa": [r.pypsa for r in rows],
                "kind": [r.kind for r in rows],
                "components": [r.components for r in rows],
            }
        )

        grouped_rows: List[_CostRow] = []
        for name, grp in frame.groupby("name", sort=True):
            kind = "storage" if (grp["kind"] == "storage").any() else "generator"
            comps = {}
            if kind == "storage":
                for comp in ("reservoir", "charge", "discharge"):
                    comps[comp] = float(
                        sum(float(c.get(comp, 0.0)) for c in grp["components"])
                    )
            else:
                comps["annualized"] = float(sum(c.get("annualized", 0.0) for c in grp["components"]))

            grouped_rows.append(
                _CostRow(
                    name=name,
                    osemosys=float(grp["osemosys"].mean()),
                    pypsa=float(grp["pypsa"].mean()),
                    kind=kind,
                    components=comps,
                )
            )

        return sorted(grouped_rows, key=lambda r: (r.kind == "storage", r.name))

    def _collect_storage_cost_rows(
        self,
        scenario_data: ScenarioData,
        network,
        year: int,
        discount_rate: float,
    ) -> List[_CostRow]:
        """Build storage cost rows with reservoir/charge/discharge components."""
        storage = scenario_data.storage
        if storage is None or network.storage_units.empty:
            return []

        to_storage = storage.technology_to_storage
        from_storage = storage.technology_from_storage
        cap_cost = scenario_data.economics.capital_cost
        op_life = scenario_data.supply.operational_life

        rows: List[_CostRow] = []
        mode = "MODE1"
        if scenario_data.sets.modes:
            mode = sorted(scenario_data.sets.modes)[0]

        for su_name in network.storage_units.index:
            bus = str(network.storage_units.loc[su_name, "bus"])
            storage_name = self._canonical_name(str(su_name), bus)

            max_hours = self._lookup_region_storage(storage.energy_ratio, bus, storage_name)
            life_storage = self._lookup_region_storage(storage.operational_life_storage, bus, storage_name)
            cc_storage = self._lookup_region_storage_year(storage.capital_cost_storage, bus, storage_name, year)
            reservoir = cc_storage * max_hours * annuity(discount_rate, life_storage) if life_storage > 0 else 0.0

            charge_tech = self._lookup_storage_technology(to_storage, bus, storage_name, mode)
            discharge_tech = self._lookup_storage_technology(from_storage, bus, storage_name, mode)

            charge = 0.0
            if charge_tech is not None:
                life_charge = self._lookup_region_tech(op_life, bus, charge_tech)
                cc_charge = self._lookup_region_tech_year(cap_cost, bus, charge_tech, year)
                if life_charge > 0:
                    charge = cc_charge * annuity(discount_rate, life_charge)

            discharge = 0.0
            if discharge_tech is not None:
                life_dis = self._lookup_region_tech(op_life, bus, discharge_tech)
                cc_dis = self._lookup_region_tech_year(cap_cost, bus, discharge_tech, year)
                if life_dis > 0:
                    discharge = cc_dis * annuity(discount_rate, life_dis)

            osemosys_total = reservoir + charge + discharge
            pypsa_total = float(network.storage_units.loc[su_name, "capital_cost"])
            rows.append(
                _CostRow(
                    name=storage_name,
                    osemosys=osemosys_total,
                    pypsa=pypsa_total,
                    kind="storage",
                    components={
                        "reservoir": reservoir,
                        "charge": charge,
                        "discharge": discharge,
                    },
                )
            )

        return rows

    @staticmethod
    def _canonical_name(name: str, region: str) -> str:
        """Strip region prefix when names follow REGION_TECH pattern."""
        prefix = f"{region}_"
        if name.startswith(prefix):
            return name[len(prefix):]
        return name

    @staticmethod
    def _lookup_region_tech_year(df: pd.DataFrame, region: str, tech: str, year: int) -> float:
        """Lookup VALUE from REGION/TECHNOLOGY/YEAR with permissive fallback."""
        if df is None or df.empty:
            return 0.0
        mask = (
            (df["REGION"] == region)
            & (df["TECHNOLOGY"] == tech)
            & (df["YEAR"] == year)
        )
        rows = df[mask]
        if not rows.empty:
            return float(rows["VALUE"].iloc[0])

        rows = df[(df["TECHNOLOGY"] == tech) & (df["YEAR"] == year)]
        if not rows.empty:
            return float(rows["VALUE"].iloc[0])
        return 0.0

    @staticmethod
    def _lookup_region_tech(df: pd.DataFrame, region: str, tech: str) -> float:
        """Lookup VALUE from REGION/TECHNOLOGY with permissive fallback."""
        if df is None or df.empty:
            return 0.0
        rows = df[(df["REGION"] == region) & (df["TECHNOLOGY"] == tech)]
        if not rows.empty:
            return float(rows["VALUE"].iloc[0])

        rows = df[df["TECHNOLOGY"] == tech]
        if not rows.empty:
            return float(rows["VALUE"].iloc[0])
        return 0.0

    @staticmethod
    def _lookup_region_storage_year(df: pd.DataFrame, region: str, storage: str, year: int) -> float:
        """Lookup VALUE from REGION/STORAGE/YEAR with permissive fallback."""
        if df is None or df.empty:
            return 0.0
        rows = df[(df["REGION"] == region) & (df["STORAGE"] == storage) & (df["YEAR"] == year)]
        if not rows.empty:
            return float(rows["VALUE"].iloc[0])

        rows = df[(df["STORAGE"] == storage) & (df["YEAR"] == year)]
        if not rows.empty:
            return float(rows["VALUE"].iloc[0])
        return 0.0

    @staticmethod
    def _lookup_region_storage(df: pd.DataFrame, region: str, storage: str) -> float:
        """Lookup VALUE from REGION/STORAGE with permissive fallback."""
        if df is None or df.empty:
            return 0.0
        rows = df[(df["REGION"] == region) & (df["STORAGE"] == storage)]
        if not rows.empty:
            return float(rows["VALUE"].iloc[0])

        rows = df[df["STORAGE"] == storage]
        if not rows.empty:
            return float(rows["VALUE"].iloc[0])
        return 0.0

    @staticmethod
    def _lookup_storage_technology(
        df: pd.DataFrame,
        region: str,
        storage: str,
        mode: str,
    ) -> Optional[str]:
        """Lookup charge/discharge technology for a storage asset."""
        if df is None or df.empty:
            return None

        rows = df[
            (df["REGION"] == region)
            & (df["STORAGE"] == storage)
            & (df["MODE_OF_OPERATION"] == mode)
        ]
        if not rows.empty:
            return str(rows["TECHNOLOGY"].iloc[0])

        rows = df[(df["REGION"] == region) & (df["STORAGE"] == storage)]
        if not rows.empty:
            return str(rows["TECHNOLOGY"].iloc[0])
        return None

    def _max_time_weight_discrepancy(self, scenario_data: ScenarioData, network) -> float:
        """Compute max absolute discrepancy in normalized time weights."""
        max_diff = 0.0
        for year in sorted(scenario_data.sets.years):
            ys, py = self._time_fractions_for_year(scenario_data, network, year)
            aligned = self._align_series(ys, py)
            val = float((aligned["osemosys"] - aligned["pypsa"]).abs().max())
            max_diff = max(max_diff, val)
        return max_diff

    def _max_capacity_factor_discrepancy(self, scenario_data: ScenarioData, network) -> float:
        """Compute max CF discrepancy across all translatable technologies."""
        max_diff = 0.0
        for tech in sorted(scenario_data.sets.technologies):
            try:
                ose = self._osemosys_capacity_factor_series(scenario_data, tech)
                py = self._pypsa_capacity_factor_series(network, tech)
            except ValueError:
                continue
            aligned = self._align_series(ose, py)
            max_diff = max(max_diff, float((aligned["osemosys"] - aligned["pypsa"]).abs().max()))
        return max_diff

    def _max_capital_cost_discrepancy(self, scenario_data: ScenarioData, network) -> float:
        """Compute max relative discrepancy in annualized capital costs."""
        rows = self._collect_capital_cost_rows(scenario_data, network)
        if not rows:
            return 0.0
        return max(abs(self._relative_diff(row.pypsa, row.osemosys)) for row in rows)

    def _capacity_comparison_frame(
        self,
        results_a: ModelResults,
        results_b: ModelResults,
    ) -> pd.DataFrame:
        """Build merged capacity frame for generators and storage."""
        sup_a = self._prepare_supply_frame(results_a.supply.installed_capacity, "generation")
        sup_b = self._prepare_supply_frame(results_b.supply.installed_capacity, "generation")
        st_a = self._prepare_storage_frame(results_a.storage.installed_capacity)
        st_b = self._prepare_storage_frame(results_b.storage.installed_capacity)

        a_all = pd.concat([sup_a, st_a], ignore_index=True) if (not sup_a.empty or not st_a.empty) else pd.DataFrame()
        b_all = pd.concat([sup_b, st_b], ignore_index=True) if (not sup_b.empty or not st_b.empty) else pd.DataFrame()

        if a_all.empty and b_all.empty:
            return pd.DataFrame()

        merged = pd.merge(
            a_all,
            b_all,
            on=["REGION", "TECHNOLOGY", "TYPE"],
            how="outer",
            suffixes=(f"_{results_a.model_name}", f"_{results_b.model_name}"),
        ).fillna(0.0)

        merged[results_a.model_name] = merged[f"VALUE_{results_a.model_name}"]
        merged[results_b.model_name] = merged[f"VALUE_{results_b.model_name}"]

        merged["LABEL"] = merged["REGION"].astype(str) + " | " + merged["TECHNOLOGY"].astype(str)
        merged.loc[merged["TYPE"] == "storage", "LABEL"] = (
            merged.loc[merged["TYPE"] == "storage", "LABEL"] + " (storage)"
        )

        merged = merged.sort_values(by=["TYPE", "LABEL"], kind="stable")
        return merged[["LABEL", results_a.model_name, results_b.model_name]]

    @staticmethod
    def _prepare_supply_frame(df: pd.DataFrame, typ: str) -> pd.DataFrame:
        """Aggregate supply capacity to REGION/TECHNOLOGY rows."""
        if df is None or df.empty:
            return pd.DataFrame(columns=["REGION", "TECHNOLOGY", "TYPE", "VALUE"])
        grouped = (
            df.groupby(["REGION", "TECHNOLOGY"], as_index=False)["VALUE"]
            .sum()
            .assign(TYPE=typ)
        )
        return grouped[["REGION", "TECHNOLOGY", "TYPE", "VALUE"]]

    @staticmethod
    def _prepare_storage_frame(df: pd.DataFrame) -> pd.DataFrame:
        """Aggregate storage power capacity to REGION/TECHNOLOGY rows."""
        if df is None or df.empty:
            return pd.DataFrame(columns=["REGION", "TECHNOLOGY", "TYPE", "VALUE"])
        grouped = (
            df.groupby(["REGION", "STORAGE_TECHNOLOGY"], as_index=False)["VALUE"]
            .sum()
            .rename(columns={"STORAGE_TECHNOLOGY": "TECHNOLOGY"})
            .assign(TYPE="storage")
        )
        return grouped[["REGION", "TECHNOLOGY", "TYPE", "VALUE"]]

    @staticmethod
    def _annual_production_by_technology(results: ModelResults) -> pd.Series:
        """Aggregate annual production by technology."""
        prod = results.dispatch.production
        if prod is None or prod.empty:
            return pd.Series(dtype=float)
        return prod.groupby("TECHNOLOGY")["VALUE"].sum().sort_index()

    @staticmethod
    def _plot_pie(ax, values: pd.Series, title: str) -> None:
        """Plot a pie chart or no-data annotation."""
        total = float(values.sum())
        if total <= 0.0:
            ax.text(0.5, 0.5, "No production", ha="center", va="center")
            ax.set_title(title)
            return

        ax.pie(values.values, labels=values.index, autopct="%1.1f%%", startangle=90)
        ax.set_title(title)

    @staticmethod
    def _pick_pypsa_results(
        results_a: ModelResults,
        results_b: ModelResults,
    ) -> Optional[ModelResults]:
        """Return whichever result appears to be PyPSA output."""
        if "pypsa" in results_a.model_name.lower():
            return results_a
        if "pypsa" in results_b.model_name.lower():
            return results_b
        if not results_a.dispatch.curtailment.empty:
            return results_a
        if not results_b.dispatch.curtailment.empty:
            return results_b
        return None

    @staticmethod
    def _cost_components(results: ModelResults) -> Dict[str, float]:
        """Get aggregated cost components for cost-comparison plot."""
        econ = results.economics
        capex = float(econ.capex.get("VALUE", pd.Series(dtype=float)).sum())
        fixed_opex = float(econ.fixed_opex.get("VALUE", pd.Series(dtype=float)).sum())
        variable_opex = float(econ.variable_opex.get("VALUE", pd.Series(dtype=float)).sum())
        salvage = float(econ.salvage.get("VALUE", pd.Series(dtype=float)).sum())

        if econ.total_system_cost is not None and not econ.total_system_cost.empty:
            total = float(econ.total_system_cost["VALUE"].sum())
        else:
            total = capex + fixed_opex + variable_opex - salvage

        return {
            "capex": capex,
            "fixed_opex": fixed_opex,
            "variable_opex": variable_opex,
            "salvage": salvage,
            "total_system_cost": total,
        }

    @staticmethod
    def _relative_diff(a: float, b: float) -> float:
        """Relative difference against the larger magnitude denominator."""
        scale = max(abs(float(a)), abs(float(b)))
        if scale <= 0.0:
            return 0.0
        return (float(a) - float(b)) / scale
