"""
Harmonization checks for PyPSA-OSeMOSYS protocol compliance.

This module implements tolerance-based parity checks that can be applied
at two stages:

1. Input layer (`ScenarioData`) for cross-parameter consistency.
2. Translation layer (`ScenarioData` vs translated PyPSA network).

The checks are intentionally lightweight and deterministic so they can be
used in test suites and CI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
from pypsa.common import annuity


@dataclass(frozen=True)
class HarmonizationTolerances:
    """Tolerance configuration for harmonization protocol checks."""

    atol_rate: float = 1e-9
    atol_cost: float = 1e-6
    atol_lifetime: float = 1e-9
    atol_demand_energy: float = 1e-6
    atol_cf_stats: float = 1e-6
    atol_npv: float = 1e-3
    demand_corr_min: float = 0.99
    cf_corr_min: float = 0.99
    cf_percentiles: Tuple[float, float, float] = (0.05, 0.5, 0.95)
    require_single_region: bool = True


@dataclass(frozen=True)
class MetricResult:
    """Single harmonization metric result."""

    name: str
    passed: bool
    observed: float
    expected: float
    tolerance: float
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HarmonizationReport:
    """Collection of harmonization metrics for a specific scope."""

    scope: str
    metrics: List[MetricResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Return True if all metrics pass."""
        return all(metric.passed for metric in self.metrics)

    def add(self, metric: MetricResult) -> None:
        """Append a metric to the report."""
        self.metrics.append(metric)

    def get(self, metric_name: str) -> Optional[MetricResult]:
        """Get a metric by name, if present."""
        for metric in self.metrics:
            if metric.name == metric_name:
                return metric
        return None

    def to_frame(self) -> pd.DataFrame:
        """Convert report metrics to a tabular DataFrame."""
        rows = []
        for metric in self.metrics:
            rows.append(
                {
                    "scope": self.scope,
                    "name": metric.name,
                    "passed": metric.passed,
                    "observed": metric.observed,
                    "expected": metric.expected,
                    "tolerance": metric.tolerance,
                    "details": metric.details,
                }
            )
        return pd.DataFrame(rows)


def validate_input_harmonization(
    scenario_data,
    tolerances: Optional[HarmonizationTolerances] = None,
) -> HarmonizationReport:
    """
    Validate harmonization at the input (`ScenarioData`) level.

    Parameters
    ----------
    scenario_data : ScenarioData
        Validated scenario container.
    tolerances : HarmonizationTolerances, optional
        Numeric tolerances for protocol checks.

    Returns
    -------
    HarmonizationReport
        Input-layer harmonization diagnostics.
    """
    tol = tolerances or HarmonizationTolerances()
    report = HarmonizationReport(scope="input")

    # Discount rate consistency across regions.
    dr = scenario_data.economics.discount_rate
    if dr is None or dr.empty:
        report.add(
            MetricResult(
                name="discount_rate_exists",
                passed=False,
                observed=0.0,
                expected=1.0,
                tolerance=0.0,
                details={"reason": "DiscountRate is empty"},
            )
        )
    else:
        values = dr["VALUE"].astype(float).to_numpy()
        spread = float(np.max(np.abs(values - values[0])))
        report.add(
            MetricResult(
                name="discount_rate_uniform",
                passed=spread <= tol.atol_rate,
                observed=spread,
                expected=0.0,
                tolerance=tol.atol_rate,
            )
        )

    # Tech-specific discount rates should match region-level rate if provided.
    dr_idv = scenario_data.economics.discount_rate_idv
    if dr is not None and not dr.empty and dr_idv is not None and not dr_idv.empty:
        regional = dr.set_index("REGION")["VALUE"].to_dict()
        row_err = []
        for _, row in dr_idv.iterrows():
            region = row["REGION"]
            if region in regional:
                row_err.append(abs(float(row["VALUE"]) - float(regional[region])))
        observed = float(max(row_err)) if row_err else 0.0
        report.add(
            MetricResult(
                name="discount_rate_idv_consistent",
                passed=observed <= tol.atol_rate,
                observed=observed,
                expected=0.0,
                tolerance=tol.atol_rate,
            )
        )

    # Technology lifetime coverage: every technology must have at least one
    # OperationalLife entry (any region is sufficient).  Requiring all
    # region×tech pairs is too strict — a single-region scenario always has
    # full coverage, but a multi-region scenario may legitimately omit
    # technologies from some regions.
    life = scenario_data.supply.operational_life
    expected_techs = set(scenario_data.sets.technologies)
    if life is None or life.empty:
        missing_techs = expected_techs
        report.add(
            MetricResult(
                name="operational_life_coverage",
                passed=False,
                observed=float(len(missing_techs)),
                expected=0.0,
                tolerance=0.0,
                details={"missing_technologies": sorted(missing_techs)[:5]},
            )
        )
    else:
        covered_techs = set(life["TECHNOLOGY"])
        missing_techs = expected_techs - covered_techs
        report.add(
            MetricResult(
                name="operational_life_coverage",
                passed=(len(missing_techs) == 0),
                observed=float(len(missing_techs)),
                expected=0.0,
                tolerance=0.0,
                details={
                    "missing_technologies": sorted(missing_techs)[:5],
                },
            )
        )

    # Copper-plate / single-region condition for direct parity scenarios.
    n_regions = len(scenario_data.sets.regions)
    expected_regions = 1.0 if tol.require_single_region else float(n_regions)
    region_ok = (n_regions == 1) if tol.require_single_region else True
    report.add(
        MetricResult(
            name="topology_single_region",
            passed=region_ok,
            observed=float(n_regions),
            expected=expected_regions,
            tolerance=0.0,
        )
    )

    # Demand annual integral check: reconstructed annual demand should match.
    demand_energy_err = _max_demand_integral_error(scenario_data)
    report.add(
        MetricResult(
            name="demand_annual_integral",
            passed=demand_energy_err <= tol.atol_demand_energy,
            observed=demand_energy_err,
            expected=0.0,
            tolerance=tol.atol_demand_energy,
        )
    )

    # Wind capacity factor boundedness + weighted stats feasibility.
    wind_summary = _wind_cf_summary(scenario_data)
    report.add(
        MetricResult(
            name="wind_cf_bounds",
            passed=wind_summary["max_out_of_bounds"] <= 0.0,
            observed=wind_summary["max_out_of_bounds"],
            expected=0.0,
            tolerance=0.0,
            details=wind_summary,
        )
    )

    return report


def validate_pypsa_translation_harmonization(
    scenario_data,
    network,
    tolerances: Optional[HarmonizationTolerances] = None,
) -> HarmonizationReport:
    """
    Validate harmonization between input data and translated PyPSA network.

    Parameters
    ----------
    scenario_data : ScenarioData
        Input scenario container.
    network : pypsa.Network
        Translated PyPSA network.
    tolerances : HarmonizationTolerances, optional
        Numeric tolerances for protocol checks.

    Returns
    -------
    HarmonizationReport
        Translation-layer harmonization diagnostics.
    """
    tol = tolerances or HarmonizationTolerances()
    report = HarmonizationReport(scope="translation_pypsa")

    # Discount-rate parity through investment period objective weights.
    years = sorted(scenario_data.sets.years)
    dr = _scenario_discount_rate(scenario_data)
    if len(years) > 1 and hasattr(network, "investment_period_weightings"):
        ipw = network.investment_period_weightings
        expected = np.array(
            [1.0 / ((1.0 + dr) ** (y - years[0])) for y in years],
            dtype=float,
        )
        observed = ipw.loc[years, "objective"].to_numpy(dtype=float)
        max_err = float(np.max(np.abs(observed - expected)))
    else:
        max_err = 0.0
    report.add(
        MetricResult(
            name="discount_rate_translation",
            passed=max_err <= tol.atol_rate,
            observed=max_err,
            expected=0.0,
            tolerance=tol.atol_rate,
        )
    )

    # Topology parity: bus count should match REGION count.
    n_buses = len(network.buses.index)
    n_regions = len(scenario_data.sets.regions)
    report.add(
        MetricResult(
            name="topology_bus_region_count",
            passed=(n_buses == n_regions),
            observed=float(n_buses),
            expected=float(n_regions),
            tolerance=0.0,
        )
    )

    # Technology lifetime parity.
    life_err = _max_lifetime_error(scenario_data, network)
    report.add(
        MetricResult(
            name="lifetime_translation",
            passed=life_err <= tol.atol_lifetime,
            observed=life_err,
            expected=0.0,
            tolerance=tol.atol_lifetime,
        )
    )

    # Cost translation parity (annualized CAPEX + fixed O&M and variable O&M).
    cap_cost_err = _max_capital_cost_error(scenario_data, network)
    var_cost_err = _max_variable_cost_error(scenario_data, network)
    report.add(
        MetricResult(
            name="capital_fixed_cost_translation",
            passed=cap_cost_err <= tol.atol_cost,
            observed=cap_cost_err,
            expected=0.0,
            tolerance=tol.atol_cost,
        )
    )
    report.add(
        MetricResult(
            name="variable_cost_translation",
            passed=var_cost_err <= tol.atol_cost,
            observed=var_cost_err,
            expected=0.0,
            tolerance=tol.atol_cost,
        )
    )

    # Demand shape parity: compare expected translated profile to network loads.
    demand_corr, demand_energy_err = _demand_translation_metrics(
        scenario_data,
        network,
    )
    report.add(
        MetricResult(
            name="demand_shape_correlation",
            passed=demand_corr >= tol.demand_corr_min,
            observed=demand_corr,
            expected=tol.demand_corr_min,
            tolerance=0.0,
        )
    )
    report.add(
        MetricResult(
            name="demand_energy_translation",
            passed=demand_energy_err <= tol.atol_demand_energy,
            observed=demand_energy_err,
            expected=0.0,
            tolerance=tol.atol_demand_energy,
        )
    )

    # Wind CF translation parity from CapacityFactor*AvailabilityFactor.
    wind_corr, wind_stat_err = _wind_translation_metrics(
        scenario_data,
        network,
        tol.cf_percentiles,
    )
    report.add(
        MetricResult(
            name="wind_cf_correlation",
            passed=wind_corr >= tol.cf_corr_min,
            observed=wind_corr,
            expected=tol.cf_corr_min,
            tolerance=0.0,
        )
    )
    report.add(
        MetricResult(
            name="wind_cf_stats",
            passed=wind_stat_err <= tol.atol_cf_stats,
            observed=wind_stat_err,
            expected=0.0,
            tolerance=tol.atol_cf_stats,
        )
    )

    # Storage translation checks (only if storages are defined).
    n_storages = len(scenario_data.sets.storages)
    if n_storages > 0:
        n_sus = len(network.storage_units)
        report.add(
            MetricResult(
                name="storage_unit_count",
                passed=(n_sus == n_storages),
                observed=float(n_sus),
                expected=float(n_storages),
                tolerance=0.0,
                details={"reason": "one StorageUnit per STORAGE entry expected"},
            )
        )

        max_hours_err = _max_storage_max_hours_error(scenario_data, network)
        report.add(
            MetricResult(
                name="storage_max_hours_translation",
                passed=max_hours_err <= tol.atol_cost,
                observed=max_hours_err,
                expected=0.0,
                tolerance=tol.atol_cost,
            )
        )

        roundtrip_err = _max_storage_roundtrip_error(scenario_data, network)
        report.add(
            MetricResult(
                name="storage_roundtrip_efficiency",
                passed=roundtrip_err <= tol.atol_cost,
                observed=roundtrip_err,
                expected=0.0,
                tolerance=tol.atol_cost,
                details={"reason": "product of efficiency_store * efficiency_dispatch"},
            )
        )

    return report


def reconstruct_pypsa_npv(
    scenario_data,
    network,
) -> float:
    """
    Reconstruct PyPSA-side NPV using OSeMOSYS accounting equations.

    Notes
    -----
    This follows OSeMOSYS cost accounting for technology terms:

    - CC1/CC2 for discounted capital investment
    - OC1..OC4 for discounted operating costs (mid-year discounting)
    - SV1..SV4 for discounted salvage value

    Assumptions:

    - Depreciation method equivalent to OSeMOSYS method 1 is used.
    - Technology emissions penalties are excluded.
    - Storage costs use ``CapitalCostStorage × max_hours × annuity`` for the
      energy reservoir; charge/discharge tech costs are already folded into
      the PyPSA ``capital_cost`` by the input translator and are not
      double-counted here (only the storage energy reservoir is reconstructed).
    """
    return float(_reconstruct_pypsa_npv_components(scenario_data, network)["total"])


def _reconstruct_pypsa_npv_components(
    scenario_data,
    network,
) -> Dict[str, float]:
    """Return OSeMOSYS-style NPV components reconstructed from PyPSA."""
    years = sorted(scenario_data.sets.years)
    if not years:
        return {
            "capital_discounted": 0.0,
            "operating_discounted": 0.0,
            "salvage_discounted": 0.0,
            "total": 0.0,
        }

    year0 = years[0]
    year_end = years[-1]
    horizon_years = int(year_end - year0 + 1)

    cap_df = scenario_data.economics.capital_cost
    fix_df = scenario_data.economics.fixed_cost
    var_df = scenario_data.economics.variable_cost
    dr_df = scenario_data.economics.discount_rate
    dr_idv_df = scenario_data.economics.discount_rate_idv

    cap_idx = _safe_index(cap_df, ["REGION", "TECHNOLOGY", "YEAR"])
    fix_idx = _safe_index(fix_df, ["REGION", "TECHNOLOGY", "YEAR"])
    var_idx = _safe_index(
        var_df,
        ["REGION", "TECHNOLOGY", "MODE_OF_OPERATION", "YEAR"],
    )
    dr_idx = _safe_index(dr_df, ["REGION"])
    dr_idv_idx = _safe_index(dr_idv_df, ["REGION", "TECHNOLOGY"])

    life_df = scenario_data.supply.operational_life
    life_idx = _safe_index(life_df, ["REGION", "TECHNOLOGY"])

    modes = sorted(scenario_data.sets.modes)
    mode = modes[0] if modes else "MODE1"

    total_capex = 0.0
    total_opex = 0.0
    total_salvage = 0.0

    regions = sorted(scenario_data.sets.regions)
    single_region = len(regions) == 1
    weights = network.snapshot_weightings.get("generators", pd.Series(dtype=float))

    for gen_name, row in network.generators.iterrows():
        region, tech = _infer_region_tech(
            gen_name,
            regions,
            single_region=single_region,
        )

        build_year = int(row.get("build_year", year0))
        lifetime = float(
            _lookup(
                life_idx,
                (region, tech),
                default=float(row.get("lifetime", 25.0)),
            )
        )
        total_capacity = float(row.get("p_nom_opt", row.get("p_nom", 0.0)))
        existing_capacity = float(row.get("p_nom", 0.0))
        new_capacity = max(0.0, total_capacity - existing_capacity)

        rate = float(
            _lookup(
                dr_idx,
                (region,),
                default=_scenario_discount_rate(scenario_data),
            )
        )
        rate_idv = float(_lookup(dr_idv_idx, (region, tech), default=rate))

        capex_unit = float(_lookup(cap_idx, (region, tech, build_year), default=0.0))

        # CC1: CapitalInvestment = CapitalCost * NewCapacity * CRF * PvAnnuity
        capital_investment = (
            capex_unit
            * new_capacity
            * _capital_recovery_factor(rate_idv, lifetime)
            * _pv_annuity(rate, lifetime)
        )
        # CC2: DiscountedCapitalInvestment = CapitalInvestment / DiscountFactor
        total_capex += capital_investment / ((1.0 + rate) ** (build_year - year0))

        # OC1..OC4: annual operating cost discounted with mid-year factor.
        for y in years:
            fixed_unit = float(_lookup(fix_idx, (region, tech, y), default=0.0))
            var_unit = float(_lookup(var_idx, (region, tech, mode, y), default=0.0))

            annual_fixed = total_capacity * fixed_unit
            annual_energy = _generator_energy_in_year(network, gen_name, y, weights)
            annual_variable = annual_energy * var_unit
            annual_operating = annual_fixed + annual_variable

            total_opex += annual_operating / ((1.0 + rate) ** (y - year0 + 0.5))

        # SV1/SV2/SV3 and SV4: salvage value discounted to start year.
        if lifetime > 0 and (build_year + lifetime - 1) > year_end:
            salvage_factor = _salvage_fraction(
                rate,
                lifetime,
                build_year,
                year_end,
            )
            salvage_value = capital_investment * salvage_factor
            total_salvage += salvage_value / ((1.0 + rate) ** horizon_years)

    # Storage units (annualized costs already folded into capital_cost by the
    # input translator; reconstruct here via the same OSeMOSYS accounting).
    stor_cap_df = getattr(
        getattr(scenario_data, "storage", None), "capital_cost_storage", None
    )
    stor_life_df = getattr(
        getattr(scenario_data, "storage", None), "operational_life_storage", None
    )
    energy_ratio_df = getattr(
        getattr(scenario_data, "storage", None), "energy_ratio", None
    )
    stor_cap_idx = _safe_index(stor_cap_df, ["REGION", "STORAGE", "YEAR"])
    stor_life_idx = _safe_index(stor_life_df, ["REGION", "STORAGE"])
    er_idx = _safe_index(energy_ratio_df, ["REGION", "STORAGE"])

    for su_name, row in network.storage_units.iterrows():
        region, storage = _infer_region_tech(
            su_name, regions, single_region=single_region
        )
        build_year = int(row.get("build_year", year0))
        lifetime = float(
            _lookup(stor_life_idx, (region, storage), default=float(row.get("lifetime", 25.0)))
        )
        max_hours = float(row.get("max_hours", 0.0))
        total_p_nom = float(row.get("p_nom_opt", row.get("p_nom", 0.0)))
        existing_p_nom = float(row.get("p_nom", 0.0))
        new_p_nom = max(0.0, total_p_nom - existing_p_nom)

        rate = float(_lookup(dr_idx, (region,), default=_scenario_discount_rate(scenario_data)))
        stor_capex_per_mwh = float(_lookup(stor_cap_idx, (region, storage, build_year), default=0.0))

        # Capital investment for storage energy reservoir (converted to per-MW-discharge basis)
        capital_investment = (
            stor_capex_per_mwh
            * max_hours
            * new_p_nom
            * _capital_recovery_factor(rate, lifetime)
            * _pv_annuity(rate, lifetime)
        )
        total_capex += capital_investment / ((1.0 + rate) ** (build_year - year0))

        # Operating costs: use marginal_cost from network (variable) and fixed via storage_units
        for y in years:
            annual_fixed = total_p_nom * float(row.get("standing_loss", 0.0))
            annual_variable = float(
                _storage_unit_energy_dispatched(network, su_name, y, weights)
            ) * float(row.get("marginal_cost", 0.0))
            annual_operating = annual_fixed + annual_variable
            total_opex += annual_operating / ((1.0 + rate) ** (y - year0 + 0.5))

        # Salvage value
        if lifetime > 0 and (build_year + lifetime - 1) > year_end:
            salvage_factor = _salvage_fraction(rate, lifetime, build_year, year_end)
            salvage_value = capital_investment * salvage_factor
            total_salvage += salvage_value / ((1.0 + rate) ** horizon_years)

    total = total_capex + total_opex - total_salvage
    return {
        "capital_discounted": float(total_capex),
        "operating_discounted": float(total_opex),
        "salvage_discounted": float(total_salvage),
        "total": float(total),
    }


def compare_npv_to_osemosys(
    scenario_data,
    network,
    osemosys_results: Dict[str, pd.DataFrame],
    tolerances: Optional[HarmonizationTolerances] = None,
) -> MetricResult:
    """Compare reconstructed PyPSA NPV against OSeMOSYS TotalDiscountedCost."""
    tol = tolerances or HarmonizationTolerances()
    parts = _reconstruct_pypsa_npv_components(scenario_data, network)
    pypsa_npv = float(parts["total"])
    total_cost = 0.0
    if "TotalDiscountedCost" in osemosys_results:
        df = osemosys_results["TotalDiscountedCost"]
        if df is not None and not df.empty:
            total_cost = float(df["VALUE"].sum())
    err = abs(pypsa_npv - total_cost)
    return MetricResult(
        name="npv_parity",
        passed=err <= tol.atol_npv,
        observed=err,
        expected=0.0,
        tolerance=tol.atol_npv,
        details={
            "pypsa_npv": pypsa_npv,
            "osemosys_total_discounted_cost": total_cost,
            "pypsa_components": parts,
        },
    )


def _scenario_discount_rate(scenario_data) -> float:
    dr = scenario_data.economics.discount_rate
    if dr is None or dr.empty:
        return 0.05
    return float(dr["VALUE"].iloc[0])


def _capital_recovery_factor(rate: float, n_years: float) -> float:
    """Compute OSeMOSYS CapitalRecoveryFactor parameter value."""
    if n_years <= 0:
        return 0.0
    if abs(rate) < 1e-12:
        return 1.0 / n_years
    num = 1.0 - (1.0 + rate) ** (-1.0)
    den = 1.0 - (1.0 + rate) ** (-n_years)
    if abs(den) < 1e-12:
        return 0.0
    return num / den


def _pv_annuity(rate: float, n_years: float) -> float:
    """Compute OSeMOSYS PvAnnuity parameter value."""
    if n_years <= 0:
        return 0.0
    if abs(rate) < 1e-12:
        return float(n_years)
    return ((1.0 - (1.0 + rate) ** (-n_years)) * (1.0 + rate)) / rate


def _salvage_fraction(
    rate: float,
    lifetime: float,
    build_year: int,
    year_end: int,
) -> float:
    """Return OSeMOSYS salvage fraction for method-1 depreciation."""
    years_in_horizon = year_end - build_year + 1
    if lifetime <= 0:
        return 0.0
    if abs(rate) < 1e-12:
        return max(0.0, 1.0 - (years_in_horizon / lifetime))

    num = (1.0 + rate) ** years_in_horizon - 1.0
    den = (1.0 + rate) ** lifetime - 1.0
    if abs(den) < 1e-12:
        return 0.0
    return max(0.0, 1.0 - (num / den))


def _generator_energy_in_year(
    network,
    gen_name: str,
    year: int,
    weights: pd.Series,
) -> float:
    """Compute weighted annual generator output for a specific year."""
    if network.generators_t.p.empty or gen_name not in network.generators_t.p:
        return 0.0

    series = network.generators_t.p[gen_name]
    if isinstance(series.index, pd.MultiIndex):
        mask = series.index.get_level_values(0) == year
        if not np.any(mask):
            return 0.0
        year_series = series[mask]
        year_weights = weights.reindex(year_series.index).fillna(0.0)
        return float((year_series * year_weights).sum())

    year_weights = weights.reindex(series.index).fillna(0.0)
    return float((series * year_weights).sum())


def _safe_index(df: pd.DataFrame, cols: List[str]) -> Optional[pd.Series]:
    if df is None or df.empty:
        return None
    return df.set_index(cols)["VALUE"]


def _lookup(indexed: Optional[pd.Series], key, default: float) -> float:
    if indexed is None:
        return default
    try:
        value = indexed.loc[key]
        if isinstance(value, pd.Series):
            return float(value.iloc[0])
        return float(value)
    except KeyError:
        return default


def _infer_region_tech(
    gen_name: str,
    regions: List[str],
    single_region: bool,
) -> Tuple[str, str]:
    if single_region:
        return regions[0], gen_name
    for region in regions:
        prefix = f"{region}_"
        if gen_name.startswith(prefix):
            return region, gen_name[len(prefix):]
    return regions[0], gen_name


def _max_demand_integral_error(scenario_data) -> float:
    annual = scenario_data.demand.specified_annual_demand
    profile = scenario_data.demand.specified_demand_profile
    if annual is None or annual.empty:
        return 0.0
    if profile is None or profile.empty:
        return 0.0

    prof_sum = (
        profile.groupby(["REGION", "FUEL", "YEAR"], as_index=False)["VALUE"]
        .sum()
    )
    merged = annual.merge(
        prof_sum,
        on=["REGION", "FUEL", "YEAR"],
        suffixes=("_annual", "_profile"),
        how="left",
    )
    merged["VALUE_profile"] = merged["VALUE_profile"].fillna(0.0)
    err = (merged["VALUE_annual"] * (merged["VALUE_profile"] - 1.0)).abs()
    return float(err.max()) if not err.empty else 0.0


def _wind_cf_summary(scenario_data) -> Dict[str, float]:
    cf = scenario_data.performance.capacity_factor
    if cf is None or cf.empty:
        return {
            "n_rows": 0.0,
            "n_wind_rows": 0.0,
            "max_out_of_bounds": 0.0,
            "mean_cf": 0.0,
            "std_cf": 0.0,
        }

    mask = cf["TECHNOLOGY"].astype(str).str.contains("WIND", case=False)
    wind = cf[mask].copy()
    if wind.empty:
        return {
            "n_rows": float(len(cf)),
            "n_wind_rows": 0.0,
            "max_out_of_bounds": 0.0,
            "mean_cf": 0.0,
            "std_cf": 0.0,
        }

    vals = wind["VALUE"].astype(float)
    out_of_bounds = np.maximum(0.0, vals - 1.0) + np.maximum(0.0, -vals)
    return {
        "n_rows": float(len(cf)),
        "n_wind_rows": float(len(wind)),
        "max_out_of_bounds": float(out_of_bounds.max()),
        "mean_cf": float(vals.mean()),
        "std_cf": float(vals.std(ddof=0)),
    }


def _max_lifetime_error(scenario_data, network) -> float:
    life_idx = _safe_index(
        scenario_data.supply.operational_life,
        ["REGION", "TECHNOLOGY"],
    )
    if life_idx is None or network.generators.empty:
        return 0.0

    regions = sorted(scenario_data.sets.regions)
    single_region = len(regions) == 1
    max_err = 0.0
    for gen_name, row in network.generators.iterrows():
        region, tech = _infer_region_tech(gen_name, regions, single_region)
        exp = _lookup(life_idx, (region, tech), default=float(row.get("lifetime", 0.0)))
        obs = float(row.get("lifetime", 0.0))
        max_err = max(max_err, abs(obs - exp))
    return float(max_err)


def _max_capital_cost_error(scenario_data, network) -> float:
    if network.generators.empty:
        return 0.0

    years = sorted(scenario_data.sets.years)
    first_year = years[0]
    discount_rate = _scenario_discount_rate(scenario_data)

    cap_idx = _safe_index(
        scenario_data.economics.capital_cost,
        ["REGION", "TECHNOLOGY", "YEAR"],
    )
    fix_idx = _safe_index(
        scenario_data.economics.fixed_cost,
        ["REGION", "TECHNOLOGY", "YEAR"],
    )
    life_idx = _safe_index(
        scenario_data.supply.operational_life,
        ["REGION", "TECHNOLOGY"],
    )

    regions = sorted(scenario_data.sets.regions)
    single_region = len(regions) == 1

    max_err = 0.0
    for gen_name, row in network.generators.iterrows():
        region, tech = _infer_region_tech(gen_name, regions, single_region)
        life = _lookup(life_idx, (region, tech), default=float(row.get("lifetime", 25.0)))
        capex = _lookup(cap_idx, (region, tech, first_year), default=0.0)
        fixed = _lookup(fix_idx, (region, tech, first_year), default=0.0)
        expected = capex * annuity(discount_rate, life) + fixed
        observed = float(row.get("capital_cost", 0.0))
        max_err = max(max_err, abs(observed - expected))

    return float(max_err)


def _max_variable_cost_error(scenario_data, network) -> float:
    if network.generators.empty:
        return 0.0

    years = sorted(scenario_data.sets.years)
    first_year = years[0]
    modes = sorted(scenario_data.sets.modes)
    mode = modes[0] if modes else "MODE1"

    vc_idx = _safe_index(
        scenario_data.economics.variable_cost,
        ["REGION", "TECHNOLOGY", "MODE_OF_OPERATION", "YEAR"],
    )
    regions = sorted(scenario_data.sets.regions)
    single_region = len(regions) == 1

    max_err = 0.0
    for gen_name, row in network.generators.iterrows():
        region, tech = _infer_region_tech(gen_name, regions, single_region)
        expected = _lookup(vc_idx, (region, tech, mode, first_year), default=0.0)
        observed = float(row.get("marginal_cost", 0.0))
        max_err = max(max_err, abs(observed - expected))
    return float(max_err)


def _demand_translation_metrics(scenario_data, network) -> Tuple[float, float]:
    annual_df = scenario_data.demand.specified_annual_demand
    profile_df = scenario_data.demand.specified_demand_profile
    if (
        annual_df is None
        or annual_df.empty
        or profile_df is None
        or profile_df.empty
        or network.loads_t.p_set.empty
    ):
        return 1.0, 0.0

    weights = network.snapshot_weightings["generators"]
    expected = pd.Series(0.0, index=network.snapshots)

    annual_idx = annual_df.set_index(["REGION", "FUEL", "YEAR"])["VALUE"]
    profile_idx = profile_df.set_index(
        ["REGION", "FUEL", "TIMESLICE", "YEAR"]
    )["VALUE"]

    for (region, fuel, year), annual_value in annual_idx.items():
        for timeslice in scenario_data.sets.timeslices:
            frac = _lookup(
                profile_idx,
                (region, fuel, timeslice, year),
                default=0.0,
            )
            snap = (year, timeslice)
            if snap in expected.index:
                duration = float(weights.loc[snap])
                if duration > 0:
                    expected.loc[snap] += float(annual_value) * frac / duration

    actual = network.loads_t.p_set.sum(axis=1).reindex(network.snapshots).fillna(0.0)
    corr = _safe_corr(actual, expected)

    actual_energy = float((actual * weights).sum())
    expected_energy = float((expected * weights).sum())
    energy_err = abs(actual_energy - expected_energy)
    return corr, energy_err


def _wind_translation_metrics(
    scenario_data,
    network,
    percentiles: Iterable[float],
) -> Tuple[float, float]:
    cf_df = scenario_data.performance.capacity_factor
    af_df = scenario_data.performance.availability_factor
    if (
        cf_df is None
        or cf_df.empty
        or network.generators_t.p_max_pu.empty
    ):
        return 1.0, 0.0

    wind_techs = {
        tech for tech in scenario_data.sets.technologies
        if "WIND" in str(tech).upper()
    }
    if not wind_techs:
        return 1.0, 0.0

    regions = sorted(scenario_data.sets.regions)
    single_region = len(regions) == 1

    cf_idx = cf_df.set_index(["REGION", "TECHNOLOGY", "TIMESLICE", "YEAR"])["VALUE"]
    af_idx = _safe_index(af_df, ["REGION", "TECHNOLOGY", "YEAR"])

    expected = []
    observed = []
    for gen_name in network.generators.index:
        region, tech = _infer_region_tech(gen_name, regions, single_region)
        if tech not in wind_techs:
            continue
        series_obs = network.generators_t.p_max_pu[gen_name]
        for year, timeslice in series_obs.index:
            cf = _lookup(cf_idx, (region, tech, timeslice, year), default=1.0)
            af = _lookup(af_idx, (region, tech, year), default=1.0)
            expected.append(cf * af)
            observed.append(float(series_obs.loc[(year, timeslice)]))

    if not expected:
        return 1.0, 0.0

    exp_arr = np.array(expected, dtype=float)
    obs_arr = np.array(observed, dtype=float)

    corr = _safe_corr(pd.Series(obs_arr), pd.Series(exp_arr))

    stat_errs = [
        abs(float(obs_arr.mean()) - float(exp_arr.mean())),
        abs(float(obs_arr.std(ddof=0)) - float(exp_arr.std(ddof=0))),
    ]
    for q in percentiles:
        stat_errs.append(
            abs(
                float(np.percentile(obs_arr, q * 100.0))
                - float(np.percentile(exp_arr, q * 100.0))
            )
        )
    return corr, float(max(stat_errs))


def _storage_unit_energy_dispatched(
    network,
    su_name: str,
    year: int,
    weights: pd.Series,
) -> float:
    """Compute weighted annual discharge energy for a StorageUnit."""
    if network.storage_units_t.p.empty or su_name not in network.storage_units_t.p:
        return 0.0
    series = network.storage_units_t.p[su_name]
    # Positive p_value = discharging (convention in PyPSA StorageUnit)
    discharge = series.clip(lower=0.0)
    if isinstance(series.index, pd.MultiIndex):
        mask = series.index.get_level_values(0) == year
        if not np.any(mask):
            return 0.0
        year_series = discharge[mask]
        year_weights = weights.reindex(year_series.index).fillna(0.0)
        return float((year_series * year_weights).sum())
    year_weights = weights.reindex(discharge.index).fillna(0.0)
    return float((discharge * year_weights).sum())


def _max_storage_max_hours_error(scenario_data, network) -> float:
    """Max absolute error in max_hours vs StorageEnergyRatio."""
    energy_ratio_df = getattr(
        getattr(scenario_data, "storage", None), "energy_ratio", None
    )
    if energy_ratio_df is None or energy_ratio_df.empty or network.storage_units.empty:
        return 0.0
    er_idx = _safe_index(energy_ratio_df, ["REGION", "STORAGE"])
    regions = sorted(scenario_data.sets.regions)
    single_region = len(regions) == 1
    max_err = 0.0
    for su_name, row in network.storage_units.iterrows():
        region, storage = _infer_region_tech(su_name, regions, single_region)
        expected = _lookup(er_idx, (region, storage), default=float(row.get("max_hours", 0.0)))
        observed = float(row.get("max_hours", 0.0))
        max_err = max(max_err, abs(observed - expected))
    return float(max_err)


def _max_storage_roundtrip_error(scenario_data, network) -> float:
    """
    Max absolute error in round-trip efficiency vs expected from IAR/OAR.

    Expected round-trip = (1/IAR_charge) * OAR_discharge.
    PyPSA observed = efficiency_store * efficiency_dispatch.
    """
    if network.storage_units.empty:
        return 0.0
    stor_params = getattr(scenario_data, "storage", None)
    if stor_params is None:
        return 0.0
    t2s = stor_params.technology_to_storage
    f2s = stor_params.technology_from_storage
    if (t2s is None or t2s.empty) and (f2s is None or f2s.empty):
        return 0.0

    years = sorted(scenario_data.sets.years)
    first_year = years[0] if years else 0
    modes = sorted(scenario_data.sets.modes)
    mode = modes[0] if modes else "MODE1"
    iar_df = scenario_data.performance.input_activity_ratio
    oar_df = scenario_data.performance.output_activity_ratio
    regions = sorted(scenario_data.sets.regions)
    single_region = len(regions) == 1

    max_err = 0.0
    for su_name, row in network.storage_units.iterrows():
        region, storage = _infer_region_tech(su_name, regions, single_region)

        # Find charge/discharge techs
        charge_tech = None
        if t2s is not None and not t2s.empty:
            mask = (
                (t2s["REGION"] == region)
                & (t2s["STORAGE"] == storage)
                & (t2s["MODE_OF_OPERATION"] == mode)
            )
            rows = t2s[mask]
            if not rows.empty:
                charge_tech = str(rows["TECHNOLOGY"].iloc[0])

        discharge_tech = None
        if f2s is not None and not f2s.empty:
            mask = (
                (f2s["REGION"] == region)
                & (f2s["STORAGE"] == storage)
                & (f2s["MODE_OF_OPERATION"] == mode)
            )
            rows = f2s[mask]
            if not rows.empty:
                discharge_tech = str(rows["TECHNOLOGY"].iloc[0])

        # Expected efficiency from IAR/OAR
        eff_store_exp = 1.0
        if charge_tech and iar_df is not None and not iar_df.empty:
            mask = (
                (iar_df["REGION"] == region)
                & (iar_df["TECHNOLOGY"] == charge_tech)
                & (iar_df["MODE_OF_OPERATION"] == mode)
                & (iar_df["YEAR"] == first_year)
            )
            iar_rows = iar_df[mask]
            if not iar_rows.empty:
                iar_val = float(iar_rows["VALUE"].iloc[0])
                if iar_val > 0:
                    eff_store_exp = 1.0 / iar_val

        eff_dispatch_exp = 1.0
        if discharge_tech and oar_df is not None and not oar_df.empty:
            mask = (
                (oar_df["REGION"] == region)
                & (oar_df["TECHNOLOGY"] == discharge_tech)
                & (oar_df["MODE_OF_OPERATION"] == mode)
                & (oar_df["YEAR"] == first_year)
            )
            oar_rows = oar_df[mask]
            if not oar_rows.empty:
                eff_dispatch_exp = float(oar_rows["VALUE"].iloc[0])

        expected_rt = eff_store_exp * eff_dispatch_exp
        observed_rt = float(row.get("efficiency_store", 1.0)) * float(row.get("efficiency_dispatch", 1.0))
        max_err = max(max_err, abs(observed_rt - expected_rt))

    return float(max_err)


def _safe_corr(x: pd.Series, y: pd.Series) -> float:
    x_std = float(x.std(ddof=0))
    y_std = float(y.std(ddof=0))
    if x_std < 1e-15 and y_std < 1e-15:
        return 1.0 if np.allclose(x.to_numpy(), y.to_numpy()) else 0.0
    corr = x.corr(y)
    if corr is None or np.isnan(corr):
        return 0.0
    return float(corr)
