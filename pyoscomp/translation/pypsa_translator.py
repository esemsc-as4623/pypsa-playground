# pyoscomp/translation/pypsa_translator.py

"""
PyPSA translation module for the PyOSComp framework.

This module translates OSeMOSYS-structured ScenarioData into a PyPSA Network
object suitable for optimization. It handles mapping of regions to buses,
timeslices to snapshots, technologies to generators, and economics integration
including annualized capital costs and investment period weightings.

Key translation decisions:
- OSeMOSYS CapacityFactor[r,t,l,y] × AvailabilityFactor[r,t,y] → PyPSA p_max_pu
- OSeMOSYS CapitalCost annualized via pypsa.common.annuity() for multi-period
- OSeMOSYS ResidualCapacity → PyPSA p_nom (existing capacity)
- OSeMOSYS InputActivityRatio → PyPSA efficiency (1/IAR for single-mode)
- OSeMOSYS VariableCost → PyPSA marginal_cost (same units assumed)
"""

from .base import InputTranslator, OutputTranslator

import logging
import pypsa
from pypsa.common import annuity
from typing import Dict, Optional
import pandas as pd
import numpy as np

from ..constants import hours_in_year, TOL

logger = logging.getLogger(__name__)


class PyPSAInputTranslator(InputTranslator):
    """
    Translate ScenarioData to a PyPSA Network object.

    Creates a fully configured PyPSA network from OSeMOSYS-structured
    scenario data, mapping regions to buses, timeslices to snapshots,
    technologies to generators, and storage to StorageUnits.

    Attributes
    ----------
    scenario_data : ScenarioData
        The source scenario data (from base class).
    network : pypsa.Network
        The PyPSA network being constructed.
    _data_dict : Dict[str, pd.DataFrame]
        Cached dictionary representation of scenario_data.

    Examples
    --------
    >>> from pyoscomp.interfaces import ScenarioData
    >>> data = ScenarioData.from_directory('/path/to/scenario')
    >>> translator = PyPSAInputTranslator(data)
    >>> network = translator.translate()
    >>> network.optimize(solver_name='glpk',
    ...     multi_investment_periods=True)
    """

    def __init__(self, scenario_data):
        """
        Initialize the translator with scenario data.

        Parameters
        ----------
        scenario_data : ScenarioData
            The scenario data to translate.
        """
        super().__init__(scenario_data)
        self.network = pypsa.Network()
        # Cache dict representation for methods that need it
        self._data_dict = None
        self._snapshot_result = None

    @property
    def data_dict(self) -> Dict[str, pd.DataFrame]:
        """Lazy-load dictionary representation of scenario data."""
        if self._data_dict is None:
            self._data_dict = self.scenario_data.to_dict()
        return self._data_dict

    def translate(self) -> pypsa.Network:
        """
        Convert ScenarioData to a PyPSA Network object.

        Orchestrates the full translation pipeline: buses, carriers,
        time structure, investment periods, demand, and supply.

        Returns
        -------
        pypsa.Network
            Fully configured PyPSA network ready for optimization.

        Raises
        ------
        ValueError
            If required sets (REGION, YEAR, TIMESLICE) are missing.
        """
        # 1. Add carriers from FUEL set
        self._add_carriers()

        # 2. Create buses (regions)
        regions = self._create_buses()
        self.network.add("Bus", regions, carrier="AC")

        # 3. Set flat snapshots & per-timeslice weightings
        self._setup_time_structure()

        # 4. Set investment periods (converts snapshots to MultiIndex)
        self._setup_investment_periods()

        # 5. Apply exact per-(year, timeslice) weightings
        self._finalize_snapshot_weightings()

        # 6. Add loads (demand)
        self._add_demand()

        # 7. Add generators (supply + performance + economics)
        self._add_generators()

        # 8. Add storage units (StorageComponent → PyPSA StorageUnit)
        self._add_storage()

        return self.network

    # ------------------------------------------------------------------
    # Carriers
    # ------------------------------------------------------------------

    def _add_carriers(self) -> None:
        """
        Register OSeMOSYS fuels as PyPSA carriers.

        Each entry in the FUEL set becomes a PyPSA Carrier. An ``AC``
        carrier is always added as the default electrical carrier.
        """
        self.network.add("Carrier", "AC", color="lightblue")
        for fuel in sorted(self.scenario_data.sets.fuels):
            if fuel not in self.network.carriers.index:
                self.network.add("Carrier", fuel)

    # ------------------------------------------------------------------
    # Buses
    # ------------------------------------------------------------------

    def _create_buses(self) -> np.ndarray:
        """
        Create one bus per OSeMOSYS region.

        Returns
        -------
        np.ndarray
            Array of region names to use as bus identifiers.
        """
        regions = self.scenario_data.sets.regions

        if not regions:
            logger.warning(
                "No regions defined, using default 'REGION1'"
            )
            return np.array(["REGION1"])

        return np.array(sorted(regions))

    # ------------------------------------------------------------------
    # Investment periods
    # ------------------------------------------------------------------

    def _setup_investment_periods(self) -> None:
        """
        Configure multi-year investment periods and discount weightings.

        OSeMOSYS DiscountRate[r] is used to build the
        ``investment_period_weightings`` DataFrame that PyPSA requires
        for multi-investment-period optimisation.

        The ``years`` column gives the duration each period represents
        (computed from inter-year gaps), and the ``objective`` column
        gives the present-value discount factor ``1/(1+r)^(y-y0)``.
        """
        years = sorted(self.scenario_data.sets.years)

        if len(years) <= 1:
            # Single-period model; set_investment_periods still needed
            self.network.set_investment_periods(years)
            return

        self.network.set_investment_periods(years)

        # Derive discount rate (take first region's rate, default 5 %)
        discount_rate = self._get_discount_rate()

        # Period durations (years between consecutive periods).
        # np.diff with prepend=years[0] gives 0 for the first period — wrong.
        # Instead, use the gap between consecutive years and replicate the last
        # gap for the final period (or 1 for a single-year model).
        if len(years) > 1:
            gaps = [years[i + 1] - years[i] for i in range(len(years) - 1)]
            durations = gaps + [gaps[-1]]
        else:
            durations = [1]

        ipw = pd.DataFrame(index=years)
        ipw["years"] = durations
        ipw["objective"] = [
            1.0 / ((1.0 + discount_rate) ** (y - years[0]))
            for y in years
        ]
        self.network.investment_period_weightings = ipw

    def _get_discount_rate(self) -> float:
        """
        Extract a scalar discount rate from ScenarioData.

        Uses the first region's DiscountRate value. Falls back to 0.05
        if no discount rate is specified.

        Returns
        -------
        float
            Discount rate in [0, 1].
        """
        dr_df = self.scenario_data.economics.discount_rate
        if dr_df is not None and not dr_df.empty:
            return float(dr_df["VALUE"].iloc[0])
        logger.warning(
            "No DiscountRate found; using default 0.05"
        )
        return 0.05

    # ------------------------------------------------------------------
    # Time structure
    # ------------------------------------------------------------------

    def _setup_time_structure(self) -> None:
        """
        Set network snapshots and per-timeslice weightings.

        Uses the robust time translation from
        ``pyoscomp.translation.time.to_snapshots``, which converts
        OSeMOSYS YearSplit fractions into hour-based weightings for
        PyPSA.

        OSeMOSYS Logic
            YearSplit[l,y] = fraction of year (0–1), sum to 1.0
        PyPSA Logic
            weighting[t] = duration in hours, sum to 8760/8784 per year

        Important
        ---------
        Snapshots are set as a **flat** index of timeslice names here.
        ``_setup_investment_periods()`` (called next) invokes
        ``network.set_investment_periods()`` which lets PyPSA itself
        tile the flat snapshots into a proper ``(period, timestep)``
        MultiIndex.

        After the MultiIndex is created, ``_finalize_snapshot_weightings``
        writes the exact per-(year, timeslice) hour durations.

        Notes
        -----
        The timeslice labels are *year-agnostic categorical names*
        (e.g. ``ALLSEASONS_ALLDAYS_ALLTIMES``), **not** real datetime
        timestamps.  PyPSA snapshot weightings carry the duration
        information that the optimizer actually uses, so the lack of
        exact datetime alignment does not affect results.
        """
        from pyoscomp.translation.time import to_snapshots

        result = to_snapshots(self.scenario_data)
        self._snapshot_result = result  # kept for _finalize

        # Validate coverage
        if not result.validate_coverage():
            for year in sorted(self.scenario_data.sets.years):
                year_mask = (
                    result.snapshots.get_level_values("period") == year
                )
                total_hours = result.weightings[year_mask].sum()
                expected = hours_in_year(year)
                if abs(total_hours - expected) > TOL:
                    logger.warning(
                        f"Year {year}: weightings sum to "
                        f"{total_hours:.2f}h, expected {expected:.0f}h "
                        f"(diff={total_hours - expected:.2f}h)"
                    )

        # --- Set FLAT snapshots (timeslice names only) ---------------
        flat_index = pd.Index(
            result.timeslice_names, name="timestep"
        )
        self.network.set_snapshots(flat_index)

        # Temporary per-timeslice weightings (first year's hours).
        # These are overwritten by _finalize_snapshot_weightings()
        # once the MultiIndex exists.
        first_year = result.years[0]
        mask = (
            result.snapshots.get_level_values("period") == first_year
        )
        flat_wt = result.weightings[mask].values
        self.network.snapshot_weightings["objective"] = flat_wt
        self.network.snapshot_weightings["generators"] = flat_wt
        self.network.snapshot_weightings["stores"] = flat_wt

    def _finalize_snapshot_weightings(self) -> None:
        """
        Write exact per-(year, timeslice) hour durations.

        Called after ``_setup_investment_periods`` has turned the flat
        snapshot index into a ``(period, timestep)`` MultiIndex.  This
        ensures every snapshot gets its year-specific weighting (which
        matters when ``YearSplit`` differs across years or for leap
        years).
        """
        result = getattr(self, "_snapshot_result", None)
        if result is None:
            return

        wt = result.weightings.reindex(self.network.snapshots)
        self.network.snapshot_weightings["objective"] = wt.values
        self.network.snapshot_weightings["generators"] = wt.values
        self.network.snapshot_weightings["stores"] = wt.values

    # ------------------------------------------------------------------
    # Demand → Loads
    # ------------------------------------------------------------------

    def _add_demand(self) -> None:
        """
        Add demand as PyPSA Load components.

        OSeMOSYS
            SpecifiedAnnualDemand[r,f,y] — total energy per year
            SpecifiedDemandProfile[r,f,l,y] — fraction per timeslice

        PyPSA
            Load.p_set — power (MW) per snapshot

        Formula
            Power = (AnnualDemand × ProfileFraction) / DurationHours
        """
        annual_df = self.scenario_data.demand.specified_annual_demand
        profile_df = self.scenario_data.demand.specified_demand_profile

        if annual_df is None or annual_df.empty:
            logger.warning(
                "No SpecifiedAnnualDemand found, skipping demand"
            )
            return

        # Prepare weights for power calculation
        weights = self.network.snapshot_weightings["generators"]

        # Handle case where no profile exists — flat profile
        if profile_df is None or profile_df.empty:
            logger.warning(
                "No SpecifiedDemandProfile found. "
                "Assuming flat demand."
            )
            n_slices = len(self.scenario_data.sets.timeslices)
            profile_records = []
            for _, row in annual_df.iterrows():
                for ts in sorted(self.scenario_data.sets.timeslices):
                    profile_records.append({
                        "REGION": row["REGION"],
                        "FUEL": row["FUEL"],
                        "TIMESLICE": ts,
                        "YEAR": row["YEAR"],
                        "VALUE": 1.0 / n_slices,
                    })
            profile_df = pd.DataFrame(profile_records)

        # Index for fast lookup
        annual_idx = annual_df.set_index(
            ["REGION", "FUEL", "YEAR"]
        )["VALUE"]
        profile_idx = profile_df.set_index(
            ["REGION", "FUEL", "TIMESLICE", "YEAR"]
        )["VALUE"]

        demand_fuels = annual_df["FUEL"].unique()

        for region in self.network.buses.index:
            for fuel in demand_fuels:
                load_name = f"{region}_{fuel}_load"
                power_series = pd.Series(
                    index=self.network.snapshots, dtype=float
                )

                for year, timeslice in self.network.snapshots:
                    try:
                        annual = annual_idx.loc[
                            (region, fuel, year)
                        ]
                        profile = profile_idx.loc[
                            (region, fuel, timeslice, year)
                        ]
                        hours = weights.loc[(year, timeslice)]

                        if hours > 0:
                            power = (annual * profile) / hours
                        else:
                            power = 0.0
                        power_series.loc[
                            (year, timeslice)
                        ] = power
                    except KeyError:
                        power_series.loc[
                            (year, timeslice)
                        ] = 0.0

                if power_series.sum() > 0:
                    self.network.add(
                        "Load",
                        name=load_name,
                        bus=region,
                        p_set=power_series,
                    )

    # ------------------------------------------------------------------
    # Supply → Generators
    # ------------------------------------------------------------------

    def _add_generators(self) -> None:
        """
        Add generators from supply, performance, and economics data.

        Translation mapping (per technology per region):

        +---------------------------------+------------------------------+
        | OSeMOSYS                        | PyPSA Generator              |
        +=================================+==============================+
        | ResidualCapacity[r,t,y]         | p_nom (first year value)     |
        | TotalAnnualMaxCapacity[r,t,y]   | p_nom_max                    |
        | TotalAnnualMinCapacity[r,t,y]   | p_nom_min                    |
        | CapitalCost[r,t,y] (annualized) | capital_cost                 |
        |   + FixedCost[r,t,y]            |                              |
        | VariableCost[r,t,m,y]           | marginal_cost                |
        | InputActivityRatio              | efficiency = 1/IAR           |
        | OutputActivityRatio fuel        | carrier (output fuel)        |
        | CapacityFactor × Availability   | p_max_pu (time-varying)      |
        | OperationalLife[r,t]            | lifetime                     |
        +---------------------------------+------------------------------+

        Notes
        -----
        - ``p_max_pu`` is built as the product of OSeMOSYS
          CapacityFactor[r,t,l,y] and AvailabilityFactor[r,t,y].
          CapacityFactor varies per timeslice; AvailabilityFactor is
          annual.  This product is the per-snapshot upper bound on
          generation as a fraction of installed capacity.
        - Capital cost is annualized using ``pypsa.common.annuity()``
          to match PyPSA's multi-investment-period objective, which
          expects an annual cost stream rather than a lump-sum.
          OSeMOSYS uses lump-sum CapitalCost with salvage-value
          accounting, so results will differ (see Reflection).
        - FixedCost is added on top of the annualized capital cost
          because PyPSA does not have a separate fixed-O&M field.
        """
        technologies = sorted(self.scenario_data.sets.technologies)
        if not technologies:
            logger.info("No technologies defined, skipping supply")
            return

        # Collect charge/discharge technologies used by storage — they are
        # folded into StorageUnit objects by _add_storage() and must not
        # also be added as generators.
        storage_techs: set = set()
        stor = self.scenario_data.storage
        if stor is not None:
            for df in (stor.technology_to_storage, stor.technology_from_storage):
                if df is not None and not df.empty and "TECHNOLOGY" in df.columns:
                    storage_techs.update(df["TECHNOLOGY"].tolist())

        years = sorted(self.scenario_data.sets.years)
        discount_rate = self._get_discount_rate()

        # Pre-index parameter DataFrames for fast lookup
        residual = self._index_df(
            self.scenario_data.supply.residual_capacity,
            ["REGION", "TECHNOLOGY", "YEAR"],
        )
        op_life = self._index_df(
            self.scenario_data.supply.operational_life,
            ["REGION", "TECHNOLOGY"],
        )
        cap_cost = self._index_df(
            self.scenario_data.economics.capital_cost,
            ["REGION", "TECHNOLOGY", "YEAR"],
        )
        fixed_cost = self._index_df(
            self.scenario_data.economics.fixed_cost,
            ["REGION", "TECHNOLOGY", "YEAR"],
        )
        var_cost = self._index_df(
            self.scenario_data.economics.variable_cost,
            ["REGION", "TECHNOLOGY", "MODE_OF_OPERATION", "YEAR"],
        )
        iar = self._index_df(
            self.scenario_data.performance.input_activity_ratio,
            ["REGION", "TECHNOLOGY", "FUEL",
             "MODE_OF_OPERATION", "YEAR"],
        )
        oar = self._index_df(
            self.scenario_data.performance.output_activity_ratio,
            ["REGION", "TECHNOLOGY", "FUEL",
             "MODE_OF_OPERATION", "YEAR"],
        )
        cap_factor = self._index_df(
            self.scenario_data.performance.capacity_factor,
            ["REGION", "TECHNOLOGY", "TIMESLICE", "YEAR"],
        )
        avail_factor = self._index_df(
            self.scenario_data.performance.availability_factor,
            ["REGION", "TECHNOLOGY", "YEAR"],
        )
        max_cap = self._index_df(
            self.scenario_data.performance.total_annual_max_capacity,
            ["REGION", "TECHNOLOGY", "YEAR"],
        )
        min_cap = self._index_df(
            self.scenario_data.performance.total_annual_min_capacity,
            ["REGION", "TECHNOLOGY", "YEAR"],
        )

        # Build p_max_pu DataFrame (index=snapshots, columns=tech names)
        p_max_pu = pd.DataFrame(
            index=self.network.snapshots, dtype=float
        )

        for region in self.network.buses.index:
            for tech in technologies:
                if tech in storage_techs:
                    logger.debug(
                        f"Skipping {tech} as generator — it is a storage "
                        f"charge/discharge technology handled by _add_storage()"
                    )
                    continue

                # --- Operational Life ---
                lifetime = self._safe_lookup(
                    op_life, (region, tech), default=25.0
                )

                # --- Residual Capacity (first year) ---
                first_year = years[0]
                p_nom = self._safe_lookup(
                    residual, (region, tech, first_year),
                    default=0.0,
                )

                # --- Capacity limits (use first year values) ---
                p_nom_max = self._safe_lookup(
                    max_cap, (region, tech, first_year),
                    default=np.inf,
                )
                # OSeMOSYS default of -1 means no upper limit
                if p_nom_max < 0:
                    p_nom_max = np.inf

                p_nom_min = self._safe_lookup(
                    min_cap, (region, tech, first_year),
                    default=0.0,
                )

                # --- Economics ---
                cc = self._safe_lookup(
                    cap_cost, (region, tech, first_year),
                    default=0.0,
                )
                fc = self._safe_lookup(
                    fixed_cost, (region, tech, first_year),
                    default=0.0,
                )
                # Annualize capital cost for PyPSA multi-period
                annualized_cc = (
                    cc * annuity(discount_rate, lifetime) + fc
                )

                # Warn if cost parameters vary across years (learning curves
                # are not propagated — PyPSA always uses the first-year value).
                self._warn_if_year_varying(
                    cap_cost, (region, tech), first_year, years, "CapitalCost"
                )
                self._warn_if_year_varying(
                    fixed_cost, (region, tech), first_year, years, "FixedCost"
                )
                self._warn_if_year_varying(
                    max_cap, (region, tech), first_year, years,
                    "TotalAnnualMaxCapacity"
                )

                # Variable cost — prefer MODE1 as canonical operational mode
                modes = sorted(self.scenario_data.sets.modes)
                mode = "MODE1" if "MODE1" in modes else (modes[0] if modes else "MODE1")
                mc = self._safe_lookup(
                    var_cost, (region, tech, mode, first_year),
                    default=0.0,
                )
                self._warn_if_year_varying(
                    var_cost, (region, tech, mode), first_year, years,
                    "VariableCost"
                )

                # --- Efficiency from InputActivityRatio ---
                # efficiency = 1 / IAR (for output fuel, first mode)
                efficiency = self._compute_efficiency(
                    iar, region, tech, mode, first_year
                )

                # --- Output carrier ---
                carrier = self._get_output_carrier(
                    oar, region, tech, mode, first_year
                )

                # --- p_max_pu: CapacityFactor × AvailabilityFactor ---
                p_max_pu_series = self._build_p_max_pu(
                    cap_factor, avail_factor,
                    region, tech, years,
                )
                gen_name = f"{tech}" if len(
                    self.network.buses
                ) == 1 else f"{tech}_{region}"
                p_max_pu[gen_name] = p_max_pu_series

                # --- Add generator ---
                self.network.add(
                    "Generator",
                    gen_name,
                    bus=region,
                    carrier=carrier,
                    p_nom=p_nom,
                    p_nom_extendable=True,
                    p_nom_max=p_nom_max,
                    p_nom_min=p_nom_min,
                    capital_cost=annualized_cc,
                    marginal_cost=mc,
                    efficiency=efficiency,
                    lifetime=lifetime,
                    build_year=first_year,
                )

        # Apply time-varying availability
        self.network.generators_t.p_max_pu = p_max_pu

    # ------------------------------------------------------------------
    # Storage → StorageUnits
    # ------------------------------------------------------------------

    def _add_storage(self) -> None:
        """
        Add storage units from StorageParameters.

        Translation mapping (per storage per region):

        +---------------------------------------+------------------------------+
        | OSeMOSYS                              | PyPSA StorageUnit            |
        +=======================================+==============================+
        | StorageEnergyRatio[r,s]               | max_hours                    |
        | MinStorageCharge[r,s,y]               | min_stor (first year)        |
        | OperationalLifeStorage[r,s]           | lifetime                     |
        | CapitalCostStorage[r,s,y]*max_hours   | capital_cost (combined,      |
        |   * annuity + CapitalCost[discharge]  |   per MW of discharge cap.)  |
        |   * annuity + FixedCost[discharge]    |                              |
        |   + CapitalCost[charge] * annuity     |                              |
        |   + FixedCost[charge]                 |                              |
        | 1 / IAR[charge_tech]                  | efficiency_store             |
        | OAR[discharge_tech]                   | efficiency_dispatch          |
        | VariableCost[discharge_tech]          | marginal_cost                |
        | ResidualStorageCapacity[r,s,y]        | e_nom (existing energy MWh)  |
        |   / StorageEnergyRatio                |   → p_nom (existing MW)      |
        +---------------------------------------+------------------------------+

        Structural note
        ---------------
        OSeMOSYS uses three components (charge tech, storage, discharge tech)
        with separate costs and lifetimes.  PyPSA uses a single ``StorageUnit``
        with a combined capital cost.  Total NPV is preserved but cost
        attribution differs (documented structural disagreement).
        """
        storage_params = self.scenario_data.storage
        storages = sorted(self.scenario_data.sets.storages)

        if not storages:
            logger.info("No storage defined, skipping storage")
            return

        years = sorted(self.scenario_data.sets.years)
        first_year = years[0]
        discount_rate = self._get_discount_rate()
        modes = sorted(self.scenario_data.sets.modes)
        mode = modes[0] if modes else "MODE1"

        # Pre-index storage parameters
        cap_cost_stor = self._index_df(
            storage_params.capital_cost_storage,
            ["REGION", "STORAGE", "YEAR"],
        )
        op_life_stor = self._index_df(
            storage_params.operational_life_storage,
            ["REGION", "STORAGE"],
        )
        residual_stor = self._index_df(
            storage_params.residual_storage_capacity,
            ["REGION", "STORAGE", "YEAR"],
        )
        min_charge = self._index_df(
            storage_params.min_storage_charge,
            ["REGION", "STORAGE", "YEAR"],
        )
        energy_ratio = self._index_df(
            storage_params.energy_ratio,
            ["REGION", "STORAGE"],
        )

        # Pre-index technology parameters (reuse supply/economics data)
        op_life = self._index_df(
            self.scenario_data.supply.operational_life,
            ["REGION", "TECHNOLOGY"],
        )
        cap_cost = self._index_df(
            self.scenario_data.economics.capital_cost,
            ["REGION", "TECHNOLOGY", "YEAR"],
        )
        fixed_cost = self._index_df(
            self.scenario_data.economics.fixed_cost,
            ["REGION", "TECHNOLOGY", "YEAR"],
        )
        var_cost = self._index_df(
            self.scenario_data.economics.variable_cost,
            ["REGION", "TECHNOLOGY", "MODE_OF_OPERATION", "YEAR"],
        )
        iar_df = self.scenario_data.performance.input_activity_ratio
        oar_df = self.scenario_data.performance.output_activity_ratio

        for region in self.network.buses.index:
            for storage_name in storages:
                charge_tech = self._find_storage_charge_tech(
                    storage_params.technology_to_storage,
                    region,
                    storage_name,
                    mode,
                )
                discharge_tech = self._find_storage_discharge_tech(
                    storage_params.technology_from_storage,
                    region,
                    storage_name,
                    mode,
                )

                if discharge_tech is None:
                    logger.warning(
                        f"No discharge technology found for storage "
                        f"{storage_name} in region {region}, skipping"
                    )
                    continue

                # --- max_hours (energy capacity ratio) ---
                max_hours = self._safe_lookup(
                    energy_ratio, (region, storage_name), default=4.0
                )

                # --- Lifetime ---
                life_stor = self._safe_lookup(
                    op_life_stor, (region, storage_name), default=25.0
                )
                life_discharge = self._safe_lookup(
                    op_life, (region, discharge_tech), default=25.0
                )

                # --- Existing capacity (from residual storage capacity) ---
                e_nom = self._safe_lookup(
                    residual_stor, (region, storage_name, first_year), default=0.0
                )
                p_nom = e_nom / max_hours if max_hours > 0 else 0.0

                # --- Minimum state of charge ---
                min_stor = self._safe_lookup(
                    min_charge, (region, storage_name, first_year), default=0.0
                )

                # --- Combined annualized capital cost (per MW discharge) ---
                # Energy reservoir: CapitalCostStorage[MWh] × max_hours → per MW
                cc_stor = self._safe_lookup(
                    cap_cost_stor, (region, storage_name, first_year), default=0.0
                )
                ann_stor = cc_stor * max_hours * annuity(discount_rate, life_stor)

                # Discharge technology
                cc_dis = self._safe_lookup(
                    cap_cost, (region, discharge_tech, first_year), default=0.0
                )
                fc_dis = self._safe_lookup(
                    fixed_cost, (region, discharge_tech, first_year), default=0.0
                )
                ann_discharge = cc_dis * annuity(discount_rate, life_discharge) + fc_dis

                # Charge technology (if present)
                ann_charge = 0.0
                if charge_tech is not None:
                    life_charge = self._safe_lookup(
                        op_life, (region, charge_tech), default=25.0
                    )
                    cc_chg = self._safe_lookup(
                        cap_cost, (region, charge_tech, first_year), default=0.0
                    )
                    fc_chg = self._safe_lookup(
                        fixed_cost, (region, charge_tech, first_year), default=0.0
                    )
                    ann_charge = cc_chg * annuity(discount_rate, life_charge) + fc_chg

                combined_capital_cost = ann_stor + ann_discharge + ann_charge

                # --- Marginal cost from discharge technology ---
                mc = self._safe_lookup(
                    var_cost, (region, discharge_tech, mode, first_year), default=0.0
                )

                # --- Efficiency: 1/IAR for charge, OAR for discharge ---
                efficiency_store = 1.0
                if charge_tech is not None and iar_df is not None and not iar_df.empty:
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
                            efficiency_store = 1.0 / iar_val

                efficiency_dispatch = 1.0
                if oar_df is not None and not oar_df.empty:
                    mask = (
                        (oar_df["REGION"] == region)
                        & (oar_df["TECHNOLOGY"] == discharge_tech)
                        & (oar_df["MODE_OF_OPERATION"] == mode)
                        & (oar_df["YEAR"] == first_year)
                    )
                    oar_rows = oar_df[mask]
                    if not oar_rows.empty:
                        efficiency_dispatch = float(oar_rows["VALUE"].iloc[0])

                # --- StorageUnit name (mirrors generator naming convention) ---
                su_name = (
                    storage_name
                    if len(self.network.buses) == 1
                    else f"{storage_name}_{region}"
                )

                self.network.add(
                    "StorageUnit",
                    su_name,
                    bus=region,
                    carrier="AC",
                    p_nom=p_nom,
                    p_nom_extendable=True,
                    max_hours=max_hours,
                    efficiency_store=efficiency_store,
                    efficiency_dispatch=efficiency_dispatch,
                    capital_cost=combined_capital_cost,
                    marginal_cost=mc,
                    lifetime=life_stor,
                    build_year=first_year,
                    min_stor=min_stor,
                    cyclic_state_of_charge=True,
                )

    # ------------------------------------------------------------------
    # Helpers: find charge / discharge technologies for a storage asset
    # ------------------------------------------------------------------

    @staticmethod
    def _find_storage_charge_tech(
        technology_to_storage: Optional[pd.DataFrame],
        region: str,
        storage_name: str,
        mode: str,
    ) -> Optional[str]:
        """Return the charge technology for a storage asset, or None."""
        if technology_to_storage is None or technology_to_storage.empty:
            return None
        mask = (
            (technology_to_storage["REGION"] == region)
            & (technology_to_storage["STORAGE"] == storage_name)
            & (technology_to_storage["MODE_OF_OPERATION"] == mode)
        )
        rows = technology_to_storage[mask]
        return str(rows["TECHNOLOGY"].iloc[0]) if not rows.empty else None

    @staticmethod
    def _find_storage_discharge_tech(
        technology_from_storage: Optional[pd.DataFrame],
        region: str,
        storage_name: str,
        mode: str,
    ) -> Optional[str]:
        """Return the discharge technology for a storage asset, or None."""
        if technology_from_storage is None or technology_from_storage.empty:
            return None
        mask = (
            (technology_from_storage["REGION"] == region)
            & (technology_from_storage["STORAGE"] == storage_name)
            & (technology_from_storage["MODE_OF_OPERATION"] == mode)
        )
        rows = technology_from_storage[mask]
        return str(rows["TECHNOLOGY"].iloc[0]) if not rows.empty else None

    # ------------------------------------------------------------------
    # Helper: build p_max_pu series
    # ------------------------------------------------------------------

    def _build_p_max_pu(
        self,
        cap_factor_idx: Optional[pd.Series],
        avail_factor_idx: Optional[pd.Series],
        region: str,
        tech: str,
        years: list,
    ) -> pd.Series:
        """
        Build per-snapshot p_max_pu from CapacityFactor × AvailabilityFactor.

        Parameters
        ----------
        cap_factor_idx : pd.Series or None
            Indexed CapacityFactor[r,t,l,y].
        avail_factor_idx : pd.Series or None
            Indexed AvailabilityFactor[r,t,y].
        region : str
            Region name.
        tech : str
            Technology name.
        years : list
            Model years.

        Returns
        -------
        pd.Series
            Per-snapshot availability fraction, index aligned with
            network snapshots.
        """
        series = pd.Series(
            1.0, index=self.network.snapshots, dtype=float
        )

        for year, timeslice in self.network.snapshots:
            cf = self._safe_lookup(
                cap_factor_idx,
                (region, tech, timeslice, year),
                default=1.0,
            )
            af = self._safe_lookup(
                avail_factor_idx,
                (region, tech, year),
                default=1.0,
            )
            series.loc[(year, timeslice)] = cf * af

        return series

    # ------------------------------------------------------------------
    # Helper: compute efficiency from IAR
    # ------------------------------------------------------------------

    def _compute_efficiency(
        self,
        iar_idx: Optional[pd.Series],
        region: str,
        tech: str,
        mode: str,
        year: int,
    ) -> float:
        """
        Derive PyPSA efficiency from OSeMOSYS InputActivityRatio.

        In OSeMOSYS the input-to-output relationship is:
            InputActivityRatio = fuel_in / activity
        For a simple conversion technology:
            efficiency = 1 / InputActivityRatio

        Parameters
        ----------
        iar_idx : pd.Series or None
            Indexed InputActivityRatio.
        region, tech, mode : str
            Identifiers.
        year : int
            Model year.

        Returns
        -------
        float
            Efficiency in (0, 1].  Returns 1.0 if IAR is unavailable.
        """
        if iar_idx is None:
            return 1.0

        # Use the pre-indexed Series directly — avoids O(n) full-DataFrame scan.
        # iar_idx is indexed by (REGION, TECHNOLOGY, FUEL, MODE_OF_OPERATION, YEAR).
        # We slice on all dimensions except FUEL (pick the first available fuel).
        try:
            subset = iar_idx.loc[(region, tech, slice(None), mode, year)]
            if isinstance(subset, pd.Series) and not subset.empty:
                iar_val = float(subset.iloc[0])
            else:
                iar_val = float(subset)
            return 1.0 / iar_val if iar_val > 0 else 1.0
        except KeyError:
            return 1.0

    # ------------------------------------------------------------------
    # Helper: get output carrier
    # ------------------------------------------------------------------

    def _get_output_carrier(
        self,
        oar_idx: Optional[pd.Series],
        region: str,
        tech: str,
        mode: str,
        year: int,
    ) -> str:
        """
        Determine main output carrier from OutputActivityRatio.

        Parameters
        ----------
        oar_idx : pd.Series or None
            Indexed OutputActivityRatio.
        region, tech, mode : str
            Identifiers.
        year : int
            Model year.

        Returns
        -------
        str
            Fuel name used as PyPSA ``carrier`` attribute.
            Defaults to ``'AC'`` if no OAR is found.
        """
        oar_df = self.scenario_data.performance.output_activity_ratio
        if oar_df is None or oar_df.empty:
            return "AC"

        mask = (
            (oar_df["REGION"] == region)
            & (oar_df["TECHNOLOGY"] == tech)
            & (oar_df["MODE_OF_OPERATION"] == mode)
            & (oar_df["YEAR"] == year)
        )
        rows = oar_df[mask]
        if rows.empty:
            return "AC"
        return str(rows["FUEL"].iloc[0])

    # ------------------------------------------------------------------
    # Helper: safe index lookup
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_lookup(
        indexed: Optional[pd.Series],
        key,
        default: float = 0.0,
    ) -> float:
        """
        Look up a value in an indexed Series, returning *default* on miss.

        Parameters
        ----------
        indexed : pd.Series or None
            Series indexed by the relevant columns.
        key : tuple or scalar
            Index key to look up.
        default : float
            Value to return if key is missing or indexed is None.

        Returns
        -------
        float
        """
        if indexed is None:
            return default
        try:
            return float(indexed.loc[key])
        except (KeyError, TypeError):
            return default

    def _warn_if_year_varying(
        self,
        indexed: Optional[pd.Series],
        key_prefix: tuple,
        first_year: int,
        years: list,
        param_name: str,
    ) -> None:
        """Emit a warning if a cost/capacity parameter varies across years.

        Checks whether the value for *key_prefix* + (first_year,) differs from
        any later year.  Emits a logger warning when it does, because the
        translator uses only the first-year value and learning curves are
        therefore invisible to PyPSA.

        Parameters
        ----------
        indexed : pd.Series or None
            Series indexed by (..., YEAR) for the parameter.
        key_prefix : tuple
            All index dimensions *except* YEAR, e.g. (region, tech).
        first_year : int
        years : list[int]
        param_name : str
            Human-readable parameter name for the warning message.
        """
        if indexed is None or len(years) < 2:
            return
        try:
            first_val = float(indexed.loc[(*key_prefix, first_year)])
        except (KeyError, TypeError):
            return  # parameter not defined for this tech — nothing to warn
        for y in years[1:]:
            try:
                val = float(indexed.loc[(*key_prefix, y)])
            except (KeyError, TypeError):
                continue
            if abs(val - first_val) > 1e-9:
                logger.warning(
                    "%s varies across years for %s (using %s value of %.4g; "
                    "year %s value %.4g not propagated to PyPSA)",
                    param_name,
                    key_prefix,
                    first_year,
                    first_val,
                    y,
                    val,
                )
                return  # one warning per tech is enough

    @staticmethod
    def _index_df(
        df: Optional[pd.DataFrame],
        columns: list,
    ) -> Optional[pd.Series]:
        """
        Index a DataFrame by the given columns, returning a Series.

        Parameters
        ----------
        df : pd.DataFrame or None
            Source DataFrame with a ``VALUE`` column.
        columns : list[str]
            Column names to set as index.

        Returns
        -------
        pd.Series or None
            Indexed ``VALUE`` column, or None if df is empty/None.
        """
        if df is None or df.empty:
            return None
        return df.set_index(columns)["VALUE"]


class PyPSAOutputTranslator(OutputTranslator):
    """
    Translate PyPSA optimisation results to a harmonized ``ModelResults``.

    The translator inspects the solved ``pypsa.Network`` and extracts:

    * **Topology** — buses → nodes; lines/links → edges.
    * **Supply** — ``p_nom_opt`` (installed), ``p_nom_opt - p_nom``
      (new capacity), grouped by bus × carrier × investment period.
    * **Objective** — ``network.objective``.

    Parameters
    ----------
    model_output : pypsa.Network
        A PyPSA Network that has been solved (i.e. ``network.optimize()``
        or ``network.lopf()`` has been called).

    Examples
    --------
    >>> translator = PyPSAOutputTranslator(network)
    >>> results = translator.translate()
    >>> results.supply.installed_capacity
       REGION  TECHNOLOGY  YEAR     VALUE
    0  REGION1    GAS_CCGT  2026  0.012684
    """

    # ------------------------------------------------------------------ #
    # public API
    # ------------------------------------------------------------------ #

    def translate(self) -> "ModelResults":
        """
        Convert PyPSA results to a ``ModelResults`` container.

        Returns
        -------
        ModelResults
            Harmonized, frozen result object.

        Raises
        ------
        ValueError
            If the network has not been solved.
        """
        from ..interfaces.results import (
            DispatchResult,
            EconomicsResult,
            ModelResults,
            StorageResult,
            TopologyResult,
            SupplyResult,
            TradeResult,
        )

        network: pypsa.Network = self.model_output

        # 1. Build TopologyResult from buses + lines/links
        topology = self._extract_topology(network)

        # 2. Build SupplyResult from generators
        supply = self._extract_supply(network)

        # 3. Objective value
        objective_raw = getattr(network, "objective", 0.0)
        objective = float(objective_raw) if objective_raw is not None else 0.0

        # 4. Additional harmonized domains
        dispatch = self._extract_dispatch(network)
        storage = self._extract_storage(network)
        economics = self._extract_economics(network)
        trade = self._extract_trade(network)

        # 5. Metadata
        metadata: Dict[str, object] = {
            "solver_name": getattr(network, "solver_name", None),
        }

        result = ModelResults(
            model_name="PyPSA",
            topology=topology,
            supply=supply,
            dispatch=dispatch,
            storage=storage,
            economics=economics,
            trade=trade,
            objective=objective,
            metadata=metadata,
        )
        result.validate()
        return result

    # ------------------------------------------------------------------ #
    # private helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _extract_topology(
        network: "pypsa.Network",
    ) -> "TopologyResult":
        """
        Build a ``TopologyResult`` from network buses, lines, and links.

        Parameters
        ----------
        network : pypsa.Network
            Solved PyPSA network.

        Returns
        -------
        TopologyResult
        """
        from ..interfaces.results import TopologyResult

        # --- nodes (buses) ---
        buses = network.buses
        nodes = pd.DataFrame({"NAME": buses.index.tolist()})
        if "carrier" in buses.columns:
            nodes["CARRIER"] = buses["carrier"].values

        # --- edges (lines + links) ---
        edge_frames = []
        for component, cap_col in [
            ("lines", "s_nom_opt"),
            ("links", "p_nom_opt"),
        ]:
            df = getattr(network, component)
            if df.empty:
                continue
            cap = (
                df[cap_col].values
                if cap_col in df.columns
                else np.zeros(len(df))
            )
            edge_df = pd.DataFrame(
                {
                    "FROM": df["bus0"].values,
                    "TO": df["bus1"].values,
                    "CAPACITY": cap,
                }
            )
            if "carrier" in df.columns:
                edge_df["CARRIER"] = df["carrier"].values
            edge_frames.append(edge_df)

        edges = (
            pd.concat(edge_frames, ignore_index=True)
            if edge_frames
            else pd.DataFrame(
                columns=["FROM", "TO", "CAPACITY"]
            )
        )

        return TopologyResult(nodes=nodes, edges=edges)

    @staticmethod
    def _extract_supply(
        network: "pypsa.Network",
    ) -> "SupplyResult":
        """
        Build a ``SupplyResult`` from generator optimal capacities.

        For multi-investment-period models, capacity is reported per
        investment period.  For single-period models, the year is taken
        from the first snapshot.

        Parameters
        ----------
        network : pypsa.Network
            Solved PyPSA network.

        Returns
        -------
        SupplyResult
        """
        from ..interfaces.results import SupplyResult

        gens = network.generators

        # Determine investment periods or fall back to snapshot year
        if hasattr(network, "investment_periods") and len(
            network.investment_periods
        ):
            years = list(network.investment_periods)
            if len(years) > 1:
                logger.warning(
                    "Multi-investment-period model detected: _extract_supply "
                    "reports the same p_nom_opt for all periods. Per-period "
                    "capacity extraction is not yet implemented."
                )
        else:
            years = [network.snapshots[0].year]

        # --- installed capacity (p_nom_opt) ---
        rows_installed = []
        rows_new = []

        for gen_name, gen in gens.iterrows():
            bus = gen["bus"]
            # Extract technology name from generator name.
            # Naming convention: "{TECHNOLOGY}_{REGION}" (set in
            # PyPSAInputTranslator._add_generators).  Strip the
            # region suffix to recover the original technology name.
            suffix = f"_{bus}"
            if gen_name.endswith(suffix):
                technology = gen_name[: -len(suffix)]
            else:
                technology = gen_name
            p_nom = gen.get("p_nom", 0.0)
            p_nom_opt = gen.get("p_nom_opt", p_nom)

            for year in years:
                rows_installed.append(
                    {
                        "REGION": bus,
                        "TECHNOLOGY": technology,
                        "YEAR": int(year),
                        "VALUE": float(p_nom_opt),
                    }
                )
                new_cap = max(0.0, float(p_nom_opt) - float(p_nom))
                rows_new.append(
                    {
                        "REGION": bus,
                        "TECHNOLOGY": technology,
                        "YEAR": int(year),
                        "VALUE": new_cap,
                    }
                )

        installed = pd.DataFrame(rows_installed)
        new = pd.DataFrame(rows_new)

        # Aggregate by (REGION, TECHNOLOGY, YEAR) when multiple
        # generators map to the same carrier in the same bus
        if not installed.empty:
            installed = (
                installed.groupby(
                    ["REGION", "TECHNOLOGY", "YEAR"], as_index=False
                )
                .agg({"VALUE": "sum"})
            )
        if not new.empty:
            new = (
                new.groupby(
                    ["REGION", "TECHNOLOGY", "YEAR"], as_index=False
                )
                .agg({"VALUE": "sum"})
            )

        return SupplyResult(
            installed_capacity=installed, new_capacity=new
        )

    @staticmethod
    def _snapshot_year_and_timeslice(snapshot) -> tuple[int, str]:
        """Convert a PyPSA snapshot index value to (YEAR, TIMESLICE)."""
        if isinstance(snapshot, tuple) and len(snapshot) >= 2:
            return int(snapshot[0]), str(snapshot[1])

        ts = pd.Timestamp(snapshot)
        return int(ts.year), ts.isoformat()

    @staticmethod
    def _extract_dispatch(network: "pypsa.Network") -> "DispatchResult":
        """Build DispatchResult from generator dispatch time series."""
        from ..interfaces.results import DispatchResult

        cols = [
            "REGION",
            "TIMESLICE",
            "TECHNOLOGY",
            "FUEL",
            "YEAR",
            "VALUE",
        ]
        production_rows = []

        if not network.generators_t.p.empty:
            for snapshot in network.generators_t.p.index:
                year, timeslice = PyPSAOutputTranslator._snapshot_year_and_timeslice(
                    snapshot
                )
                row = network.generators_t.p.loc[snapshot]
                for gen_name, value in row.items():
                    if float(value) <= 0.0:
                        continue
                    gen = network.generators.loc[gen_name]
                    region = str(gen["bus"])
                    suffix = f"_{region}"
                    technology = (
                        gen_name[: -len(suffix)]
                        if str(gen_name).endswith(suffix)
                        else str(gen_name)
                    )
                    fuel = str(gen.get("carrier", "ELECTRICITY"))
                    production_rows.append(
                        {
                            "REGION": region,
                            "TIMESLICE": timeslice,
                            "TECHNOLOGY": technology,
                            "FUEL": fuel,
                            "YEAR": year,
                            "VALUE": float(value),
                        }
                    )

        production = pd.DataFrame(production_rows, columns=cols)
        if not production.empty:
            production = production.groupby(cols[:-1], as_index=False)["VALUE"].sum()

        # Curtailment: available energy minus actual dispatch, per snapshot.
        # Available = p_max_pu × p_nom_opt × weighting (MWh)
        # Curtailed  = max(0, available − dispatched)
        curtail_cols = ["REGION", "TIMESLICE", "TECHNOLOGY", "YEAR", "VALUE"]
        curtailment_rows = []
        if (
            not network.generators_t.p.empty
            and not network.generators_t.p_max_pu.empty
            and not network.generators.empty
        ):
            weights = network.snapshot_weightings.get(
                "generators", pd.Series(dtype=float)
            )
            p_actual = network.generators_t.p
            p_max_pu = network.generators_t.p_max_pu

            for snapshot in p_actual.index:
                year, timeslice = PyPSAOutputTranslator._snapshot_year_and_timeslice(
                    snapshot
                )
                w = float(weights.get(snapshot, 1.0)) if not weights.empty else 1.0
                for gen_name in p_actual.columns:
                    gen = network.generators.loc[gen_name]
                    p_nom_opt = float(gen.get("p_nom_opt", gen.get("p_nom", 0.0)))
                    max_pu = (
                        float(p_max_pu.loc[snapshot, gen_name])
                        if gen_name in p_max_pu.columns
                        else 1.0
                    )
                    available = p_nom_opt * max_pu * w
                    dispatched = float(p_actual.loc[snapshot, gen_name]) * w
                    curtailed = max(0.0, available - dispatched)
                    if curtailed > 1e-8:
                        region = str(gen["bus"])
                        suffix = f"_{region}"
                        technology = (
                            gen_name[: -len(suffix)]
                            if str(gen_name).endswith(suffix)
                            else str(gen_name)
                        )
                        curtailment_rows.append(
                            {
                                "REGION": region,
                                "TIMESLICE": timeslice,
                                "TECHNOLOGY": technology,
                                "YEAR": year,
                                "VALUE": curtailed,
                            }
                        )

        curtailment = pd.DataFrame(curtailment_rows, columns=curtail_cols)
        if not curtailment.empty:
            curtailment = curtailment.groupby(
                curtail_cols[:-1], as_index=False
            )["VALUE"].sum()

        return DispatchResult(
            production=production,
            use=pd.DataFrame(columns=cols),
            curtailment=curtailment,
            unmet_demand=pd.DataFrame(
                columns=["REGION", "TIMESLICE", "FUEL", "YEAR", "VALUE"]
            ),
        )

    @staticmethod
    def _extract_storage(network: "pypsa.Network") -> "StorageResult":
        """Build StorageResult from storage unit and store time series."""
        from ..interfaces.results import StorageResult

        ts_cols = [
            "REGION",
            "TIMESLICE",
            "STORAGE_TECHNOLOGY",
            "YEAR",
            "VALUE",
        ]
        annual_cols = ["REGION", "STORAGE_TECHNOLOGY", "YEAR", "VALUE"]

        charge_rows = []
        discharge_rows = []
        soc_rows = []

        if hasattr(network, "storage_units_t") and not network.storage_units.empty:
            p_df = network.storage_units_t.p
            soc_df = network.storage_units_t.state_of_charge
            for snapshot in p_df.index:
                year, timeslice = PyPSAOutputTranslator._snapshot_year_and_timeslice(
                    snapshot
                )
                for name, p_value in p_df.loc[snapshot].items():
                    meta = network.storage_units.loc[name]
                    region = str(meta["bus"])
                    tech = str(name)
                    if float(p_value) < 0.0:
                        charge_rows.append(
                            {
                                "REGION": region,
                                "TIMESLICE": timeslice,
                                "STORAGE_TECHNOLOGY": tech,
                                "YEAR": year,
                                "VALUE": float(-p_value),
                            }
                        )
                    elif float(p_value) > 0.0:
                        discharge_rows.append(
                            {
                                "REGION": region,
                                "TIMESLICE": timeslice,
                                "STORAGE_TECHNOLOGY": tech,
                                "YEAR": year,
                                "VALUE": float(p_value),
                            }
                        )

                    if not soc_df.empty and name in soc_df.columns:
                        soc_rows.append(
                            {
                                "REGION": region,
                                "TIMESLICE": timeslice,
                                "STORAGE_TECHNOLOGY": tech,
                                "YEAR": year,
                                "VALUE": float(soc_df.loc[snapshot, name]),
                            }
                        )

        charge = pd.DataFrame(charge_rows, columns=ts_cols)
        discharge = pd.DataFrame(discharge_rows, columns=ts_cols)
        soc = pd.DataFrame(soc_rows, columns=ts_cols)
        if not charge.empty:
            charge = charge.groupby(ts_cols[:-1], as_index=False)["VALUE"].sum()
        if not discharge.empty:
            discharge = discharge.groupby(
                ts_cols[:-1], as_index=False
            )["VALUE"].sum()
        if not soc.empty:
            soc = soc.groupby(ts_cols[:-1], as_index=False)["VALUE"].sum()

        throughput = pd.DataFrame(columns=annual_cols)
        if not charge.empty or not discharge.empty:
            both = pd.concat([charge, discharge], ignore_index=True)
            throughput = both.groupby(
                ["REGION", "STORAGE_TECHNOLOGY", "YEAR"],
                as_index=False,
            )["VALUE"].sum()

        # Installed capacity tables (power MW and energy MWh), per investment period.
        if hasattr(network, "investment_periods") and len(network.investment_periods):
            cap_years = list(network.investment_periods)
        elif len(network.snapshots) > 0:
            first_snap = network.snapshots[0]
            cap_years = [int(first_snap[0]) if isinstance(first_snap, tuple) else int(pd.Timestamp(first_snap).year)]
        else:
            cap_years = []

        installed_mw_rows = []
        installed_mwh_rows = []
        cap_rows = []  # for equivalent cycles calculation
        for name, row in network.storage_units.iterrows():
            region = str(row["bus"])
            p_nom_opt = float(row.get("p_nom_opt", row.get("p_nom", 0.0)))
            max_hours = float(row.get("max_hours", 0.0))
            e_nom_opt = p_nom_opt * max_hours
            for y in cap_years:
                installed_mw_rows.append(
                    {"REGION": region, "STORAGE_TECHNOLOGY": str(name), "YEAR": int(y), "VALUE": p_nom_opt}
                )
                installed_mwh_rows.append(
                    {"REGION": region, "STORAGE_TECHNOLOGY": str(name), "YEAR": int(y), "VALUE": e_nom_opt}
                )
            if e_nom_opt > 0:
                cap_rows.append(
                    {"REGION": region, "STORAGE_TECHNOLOGY": str(name), "ENERGY_CAPACITY": e_nom_opt}
                )

        installed_capacity = pd.DataFrame(installed_mw_rows, columns=annual_cols)
        installed_energy_capacity = pd.DataFrame(installed_mwh_rows, columns=annual_cols)

        # Equivalent full cycles proxy: throughput / (2 * energy_capacity).
        cycles = pd.DataFrame(columns=annual_cols)
        if not throughput.empty and cap_rows:
            cap_df = pd.DataFrame(cap_rows)
            cycles = throughput.merge(cap_df, on=["REGION", "STORAGE_TECHNOLOGY"], how="left")
            cycles["VALUE"] = cycles["VALUE"] / (
                2.0 * cycles["ENERGY_CAPACITY"].replace(0, np.nan)
            )
            cycles = cycles.drop(columns=["ENERGY_CAPACITY"]).fillna(0.0)

        return StorageResult(
            charge=charge,
            discharge=discharge,
            state_of_charge=soc,
            throughput=throughput,
            equivalent_cycles=cycles,
            installed_capacity=installed_capacity,
            installed_energy_capacity=installed_energy_capacity,
        )

    @staticmethod
    def _extract_economics(network: "pypsa.Network") -> "EconomicsResult":
        """Build a conservative EconomicsResult from PyPSA objective outputs."""
        from ..interfaces.results import EconomicsResult

        years = []
        if hasattr(network, "investment_periods") and len(network.investment_periods):
            years = [int(y) for y in network.investment_periods]
        elif len(network.snapshots):
            first_snapshot = network.snapshots[0]
            if isinstance(first_snapshot, tuple):
                years = [int(first_snapshot[0])]
            else:
                years = [int(pd.Timestamp(first_snapshot).year)]

        if not years:
            return EconomicsResult()

        regions = network.buses.index.tolist()
        region = str(regions[0]) if regions else "REGION1"
        objective_raw = getattr(network, "objective", 0.0)
        objective = float(objective_raw) if objective_raw is not None else 0.0

        total = pd.DataFrame(
            {
                "REGION": [region],
                "YEAR": [int(years[0])],
                "VALUE": [objective],
            }
        )

        return EconomicsResult(
            total_system_cost=total,
        )

    @staticmethod
    def _extract_trade(network: "pypsa.Network") -> "TradeResult":
        """Build TradeResult from inter-bus link flows when available."""
        from ..interfaces.results import TradeResult

        cols = ["REGION", "TO_REGION", "TIMESLICE", "FUEL", "YEAR", "VALUE"]
        rows = []

        if hasattr(network, "links_t") and not network.links.empty:
            p0 = network.links_t.p0
            if not p0.empty:
                for snapshot in p0.index:
                    year, timeslice = (
                        PyPSAOutputTranslator._snapshot_year_and_timeslice(snapshot)
                    )
                    for link_name, value in p0.loc[snapshot].items():
                        link = network.links.loc[link_name]
                        bus0 = str(link.get("bus0", ""))
                        bus1 = str(link.get("bus1", ""))
                        if bus0 == bus1:
                            continue
                        flow = float(value)
                        if flow >= 0.0:
                            source = bus0
                            sink = bus1
                            magnitude = flow
                        else:
                            source = bus1
                            sink = bus0
                            magnitude = -flow
                        if magnitude <= 0.0:
                            continue
                        rows.append(
                            {
                                "REGION": source,
                                "TO_REGION": sink,
                                "TIMESLICE": timeslice,
                                "FUEL": str(link.get("carrier", "ELECTRICITY")),
                                "YEAR": year,
                                "VALUE": magnitude,
                            }
                        )

        flows = pd.DataFrame(rows, columns=cols)
        if not flows.empty:
            flows = flows.groupby(cols[:-1], as_index=False)["VALUE"].sum()

        return TradeResult(flows=flows)