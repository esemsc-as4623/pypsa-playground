# Simple Energy System Scenario: OSeMOSYS to PyPSA Mapping

This document outlines a simple energy system scenario and provides a mapping between the required OSeMOSYS input files and the equivalent PyPSA component initializations.

## Scenario Overview

- **Region:** A single region, `REGION1`.
- **Year:** A single year of analysis, `2025`.
- **Time Slices:** Two representative time slices: `PEAK` and `OFFPEAK`.
- **Demand:** A demand for electricity (`ELEC`).
- **Technologies:**
    - `GAS_CCGT`: A baseload combined-cycle gas turbine.
    - `GAS_TURBINE`: A peaking gas turbine.
- **Fuel:** Both technologies consume natural gas (`GAS`).

## Mapping Table

| OSeMOSYS Input File | PyPSA Component & Attribute | Dummy Data / Initialization Parameters |
| :--- | :--- | :--- |
| **Sets** | **PyPSA Network Setup** | |
| `YEAR.csv` | `n.set_investment_periods([2025])` | A single year for the optimization. |
| `REGION.csv` | `n.add("Bus", "REGION1", carrier="AC")` | A single bus representing the region's electricity grid. |
| `TECHNOLOGY.csv` | `n.add("Generator", "GAS_CCGT", ...)`<br>`n.add("Generator", "GAS_TURBINE", ...)` | Two generator components are added to the network. |
| `FUEL.csv` | `n.add("Carrier", "GAS")`<br>`n.add("Carrier", "AC")` | Carriers for gas and electricity. The electricity carrier is implicitly handled by the bus. |
| `TIMESLICE.csv` | `n.set_snapshots(["PEAK", "OFFPEAK"])` | Two snapshots representing the time slices. |
| `MODE_OF_OPERATION.csv` | (Implicit) | PyPSA generators have a single mode of operation by default. |
| **Parameters** | **PyPSA Component Attributes** | |
| `SpecifiedAnnualDemand.csv` & `SpecifiedDemandProfile.csv` | `n.add("Load", "demand", bus="REGION1", p_set={"PEAK": 1000, "OFFPEAK": 500})` | A load component attached to the bus with a time series for demand. For example, 1000 MW during peak and 500 MW during off-peak. |
| `YearSplit.csv` | `n.snapshot_weightings` | `objective`: `{"PEAK": 2000, "OFFPEAK": 6760}`. Represents the number of hours in each time slice. |
| `InputActivityRatio.csv` & `OutputActivityRatio.csv` | `n.generators.efficiency` | `GAS_CCGT`: `0.5` (50% efficient)<br>`GAS_TURBINE`: `0.35` (35% efficient). This is equivalent to OSeMOSYS's input/output ratios. |
| `CapitalCost.csv` | `n.generators.capital_cost` | `GAS_CCGT`: `1000` (€/MW)<br>`GAS_TURBINE`: `600` (€/MW). Cost to build new capacity. |
| `VariableCost.csv` | `n.generators.marginal_cost` | `GAS_CCGT`: `50` (€/MWh)<br>`GAS_TURBINE`: `80` (€/MWh). This includes fuel and other variable costs. |
| `FixedCost.csv` | (Not directly available) | PyPSA does not have a separate `FixedCost` parameter in the same way as OSeMOSYS. It can be annualized and included in `capital_cost`. |
| `OperationalLife.csv` | `n.generators.lifetime` | `GAS_CCGT`: `30`<br>`GAS_TURBINE`: `25`. The technical lifetime in years. |
| `ResidualCapacity.csv` | `n.generators.p_nom` | `GAS_CCGT`: `800`<br>`GAS_TURBINE`: `300`. Existing capacity at the start of the simulation. |
| `TotalAnnualMaxCapacityInvestment.csv` | `n.generators.p_nom_extendable = True`<br>`n.generators.p_nom_max` | To allow investment, set `p_nom_extendable` to `True`. `p_nom_max` can be used to set an upper limit on total capacity (existing + new). |
| `DiscountRate.csv` | `n.investment_period_weightings` | The discount rate is applied to the `objective` column of the investment period weightings. |
| `CapacityFactor.csv` | `n.generators_t.p_max_pu` | A time series defining the availability of the generator. For this simple case, we can assume it's always 1 (fully available). |
| `AvailabilityFactor.csv` | (Implicit in `p_max_pu`) | In PyPSA, planned and unplanned outages are typically factored into the `p_max_pu` time series. |
