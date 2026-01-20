# OSeMOSYS Variables Table

I have carefully reviewed the OSeMOSYS guidance and compiled all variables. Below is the comprehensive table organized by category.

---

## 1. DEMAND VARIABLES

| Variable | Indices | Definition | Relationship to Other Variables/Parameters | Units |
|----------|---------|------------|-------------------------------------------|-------|
| **RateOfDemand** | [r,l,f,y] ≥0 | Intermediate variable representing the energy that would be demanded in time slice l if it lasted the whole year | RateOfDemand = SpecifiedAnnualDemand × SpecifiedDemandProfile / YearSplit | Energy per year |
| **Demand** | [r,l,f,y] ≥0 | Demand for one fuel in one time slice | Demand = RateOfDemand × YearSplit | Energy |

---

## 2. STORAGE VARIABLES

| Variable | Indices | Definition | Relationship to Other Variables/Parameters | Units |
|----------|---------|------------|-------------------------------------------|-------|
| **RateOfStorageCharge** | [r,s,ls,ld,lh,y] | Intermediate variable representing the commodity that would be charged to storage facility s in one time slice if the latter lasted the whole year | Function of RateOfActivity and TechnologyToStorage; linked via Conversionls, Conversionld, Conversionlh | Energy per year |
| **RateOfStorageDischarge** | [r,s,ls,ld,lh,y] | Intermediate variable representing the commodity that would be discharged from storage facility s in one time slice if the latter lasted the whole year | Function of RateOfActivity and TechnologyFromStorage; linked via Conversionls, Conversionld, Conversionlh | Energy per year |
| **NetChargeWithinYear** | [r,s,ls,ld,lh,y] | Net quantity of commodity charged to storage facility s in year y (can be negative) | NetChargeWithinYear = (RateOfStorageCharge - RateOfStorageDischarge) × YearSplit × Conversion factors | Energy |
| **NetChargeWithinDay** | [r,s,ls,ld,lh,y] | Net quantity of commodity charged to storage facility s in daytype ld (can be negative) | NetChargeWithinDay = (RateOfStorageCharge - RateOfStorageDischarge) × DaySplit | Energy |
| **StorageLevelYearStart** | [r,s,y] ≥0 | Level of stored commodity in storage facility s in the first time step of year y | For first year: = StorageLevelStart; Otherwise: = StorageLevelYearStart[y-1] + Σ NetChargeWithinYear[y-1] | Energy |
| **StorageLevelYearFinish** | [r,s,y] ≥0 | Level of stored commodity in storage facility s in the last time step of year y | For last year: = StorageLevelYearStart + Σ NetChargeWithinYear; Otherwise: = StorageLevelYearStart[y+1] | Energy |
| **StorageLevelSeasonStart** | [r,s,ls,y] ≥0 | Level of stored commodity in storage facility s in the first time step of season ls | For first season: = StorageLevelYearStart; Otherwise: = StorageLevelSeasonStart[ls-1] + Σ NetChargeWithinYear[ls-1] | Energy |
| **StorageLevelDayTypeStart** | [r,s,ls,ld,y] ≥0 | Level of stored commodity in storage facility s in the first time step of daytype ld | For first daytype: = StorageLevelSeasonStart; Otherwise: = StorageLevelDayTypeStart[ld-1] + Σ NetChargeWithinDay[ld-1] × DaysInDayType | Energy |
| **StorageLevelDayTypeFinish** | [r,s,ls,ld,y] ≥0 | Level of stored commodity in storage facility s in the last time step of daytype ld | Conditional based on position in season/daytype hierarchy; linked to StorageLevelYearFinish, StorageLevelSeasonStart, and NetChargeWithinDay | Energy |
| **StorageLowerLimit** | [r,s,y] ≥0 | Minimum allowed level of stored commodity in storage facility s | StorageLowerLimit = MinStorageCharge × StorageUpperLimit | Energy |
| **StorageUpperLimit** | [r,s,y] ≥0 | Maximum allowed level of stored commodity in storage facility s (total existing capacity) | StorageUpperLimit = AccumulatedNewStorageCapacity + ResidualStorageCapacity | Energy |
| **AccumulatedNewStorageCapacity** | [r,s,y] ≥0 | Cumulative capacity of newly installed storage from beginning of time domain to year y | AccumulatedNewStorageCapacity = Σ NewStorageCapacity[yy] for all yy where (y-yy) < OperationalLifeStorage and (y-yy) ≥ 0 | Energy |
| **NewStorageCapacity** | [r,s,y] ≥0 | Capacity of newly installed storage in year y | Decision variable; constrained by storage investment equations | Energy |
| **CapitalInvestmentStorage** | [r,s,y] ≥0 | Undiscounted investment in new capacity for storage facility s | CapitalInvestmentStorage = CapitalCostStorage × NewStorageCapacity | Monetary units |
| **DiscountedCapitalInvestmentStorage** | [r,s,y] ≥0 | Investment in new capacity for storage facility s, discounted to start year | DiscountedCapitalInvestmentStorage = CapitalInvestmentStorage / (1+DiscountRate)^(y-min(y)) | Monetary units |
| **SalvageValueStorage** | [r,s,y] ≥0 | Salvage value of storage facility s in year y | Function of CapitalInvestmentStorage, OperationalLifeStorage, DiscountRate, and DepreciationMethod | Monetary units |
| **DiscountedSalvageValueStorage** | [r,s,y] ≥0 | Salvage value of storage facility s, discounted to start year | DiscountedSalvageValueStorage = SalvageValueStorage / (1+DiscountRate)^(max(y)-min(y)+1) | Monetary units |
| **TotalDiscountedStorageCost** | [r,s,y] ≥0 | Net discounted cost for storage facility s in year y | TotalDiscountedStorageCost = DiscountedCapitalInvestmentStorage - DiscountedSalvageValueStorage | Monetary units |

---

## 3. CAPACITY VARIABLES

| Variable | Indices | Definition | Relationship to Other Variables/Parameters | Units |
|----------|---------|------------|-------------------------------------------|-------|
| **NumberOfNewTechnologyUnits** | [r,t,y] ≥0 (integer) | Number of newly installed units of technology t in year y | NewCapacity = CapacityOfOneTechnologyUnit × NumberOfNewTechnologyUnits (only when CapacityOfOneTechnologyUnit ≠ 0) | Dimensionless |
| **NewCapacity** | [r,t,y] ≥0 | Newly installed capacity of technology t in year y | Decision variable; constrained by TotalAnnualMinCapacityInvestment and TotalAnnualMaxCapacityInvestment | Power |
| **AccumulatedNewCapacity** | [r,t,y] ≥0 | Cumulative newly installed capacity of technology t from beginning of time domain to year y | AccumulatedNewCapacity = Σ NewCapacity[yy] for all yy where (y-yy) < OperationalLife and (y-yy) ≥ 0 | Power |
| **TotalCapacityAnnual** | [r,t,y] ≥0 | Total existing capacity of technology t in year y | TotalCapacityAnnual = AccumulatedNewCapacity + ResidualCapacity | Power |

---

## 4. ACTIVITY VARIABLES

| Variable | Indices | Definition | Relationship to Other Variables/Parameters | Units |
|----------|---------|------------|-------------------------------------------|-------|
| **RateOfActivity** | [r,l,t,m,y] ≥0 | Intermediate variable representing the activity of technology t in mode m and time slice l, if the latter lasted the whole year | Core decision variable; constrained by: RateOfTotalActivity ≤ TotalCapacityAnnual × CapacityFactor × CapacityToActivityUnit | Energy per year |
| **RateOfTotalActivity** | [r,t,l,y] ≥0 | Sum of RateOfActivity over all modes of operation | RateOfTotalActivity = Σ(m) RateOfActivity[r,l,t,m,y] | Energy per year |
| **TotalTechnologyAnnualActivity** | [r,t,y] ≥0 | Total annual activity of technology t | TotalTechnologyAnnualActivity = Σ(l) RateOfTotalActivity × YearSplit | Energy |
| **TotalAnnualTechnologyActivityByMode** | [r,t,m,y] ≥0 | Annual activity of technology t in mode of operation m | TotalAnnualTechnologyActivityByMode = Σ(l) RateOfActivity[r,l,t,m,y] × YearSplit | Energy |
| **TotalTechnologyModelPeriodActivity** | [r,t] | Sum of TotalTechnologyAnnualActivity over all years in the modelled period | TotalTechnologyModelPeriodActivity = Σ(y) TotalTechnologyAnnualActivity | Energy |
| **RateOfProductionByTechnologyByMode** | [r,l,t,m,f,y] ≥0 | Intermediate variable representing the quantity of fuel f that technology t would produce in mode m and time slice l, if the latter lasted the whole year | RateOfProductionByTechnologyByMode = RateOfActivity × OutputActivityRatio | Energy per year |
| **RateOfProductionByTechnology** | [r,l,t,f,y] ≥0 | Sum of RateOfProductionByTechnologyByMode over all modes of operation | RateOfProductionByTechnology = Σ(m) RateOfProductionByTechnologyByMode | Energy per year |
| **ProductionByTechnology** | [r,l,t,f,y] ≥0 | Production of fuel f by technology t in time slice l | ProductionByTechnology = RateOfProductionByTechnology × YearSplit | Energy |
| **ProductionByTechnologyAnnual** | [r,t,f,y] ≥0 | Annual production of fuel f by technology t | ProductionByTechnologyAnnual = Σ(l) ProductionByTechnology | Energy |
| **RateOfProduction** | [r,l,f,y] ≥0 | Sum of RateOfProductionByTechnology over all technologies | RateOfProduction = Σ(t) RateOfProductionByTechnology | Energy per year |
| **Production** | [r,l,f,y] ≥0 | Total production of fuel f in time slice l | Production = RateOfProduction × YearSplit; also Production = Σ(t) ProductionByTechnology | Energy |
| **RateOfUseByTechnologyByMode** | [r,l,t,m,f,y] ≥0 | Intermediate variable representing the quantity of fuel f that technology t would use in mode m and time slice l, if the latter lasted the whole year | RateOfUseByTechnologyByMode = RateOfActivity × InputActivityRatio | Energy per year |
| **RateOfUseByTechnology** | [r,l,t,f,y] ≥0 | Sum of RateOfUseByTechnologyByMode over all modes of operation | RateOfUseByTechnology = Σ(m) RateOfUseByTechnologyByMode | Energy per year |
| **UseByTechnology** | [r,l,t,f,y] ≥0 | Use of fuel f by technology t in time slice l | UseByTechnology = RateOfUseByTechnology × YearSplit | Energy |
| **UseByTechnologyAnnual** | [r,t,f,y] ≥0 | Annual use of fuel f by technology t | UseByTechnologyAnnual = Σ(l) RateOfUseByTechnology × YearSplit | Energy |
| **RateOfUse** | [r,l,f,y] ≥0 | Sum of RateOfUseByTechnology over all technologies | RateOfUse = Σ(t) RateOfUseByTechnology (from equation EBa6) | Energy per year |
| **Use** | [r,l,f,y] ≥0 | Total use of fuel f in time slice l | Use = RateOfUse × YearSplit; also Use = Σ(t) UseByTechnology | Energy |
| **Trade** | [r,rr,l,f,y] | Quantity of fuel f traded between region r and rr in time slice l (can be negative) | Trade[r,rr,l,f,y] = -Trade[rr,r,l,f,y] (antisymmetric); affects energy balance | Energy |
| **TradeAnnual** | [r,rr,f,y] | Annual quantity of fuel f traded between region r and rr | TradeAnnual = Σ(l) Trade | Energy |
| **ProductionAnnual** | [r,f,y] ≥0 | Total annual production of fuel f | ProductionAnnual = Σ(l) Production | Energy |
| **UseAnnual** | [r,f,y] ≥0 | Total annual use of fuel f | UseAnnual = Σ(l) Use | Energy |

---

## 5. COSTING VARIABLES

| Variable | Indices | Definition | Relationship to Other Variables/Parameters | Units |
|----------|---------|------------|-------------------------------------------|-------|
| **CapitalInvestment** | [r,t,y] ≥0 | Undiscounted investment in new capacity of technology t | CapitalInvestment = CapitalCost × NewCapacity | Monetary units |
| **DiscountedCapitalInvestment** | [r,t,y] ≥0 | Investment in new capacity of technology t, discounted to start year | DiscountedCapitalInvestment = CapitalInvestment / (1+DiscountRate)^(y-min(y)) | Monetary units |
| **SalvageValue** | [r,t,y] ≥0 | Salvage value of technology t in year y | Function of CapitalCost, NewCapacity, OperationalLife, DiscountRate, and DepreciationMethod; = 0 if technology life ends within model period | Monetary units |
| **DiscountedSalvageValue** | [r,t,y] ≥0 | Salvage value of technology t, discounted to start year | DiscountedSalvageValue = SalvageValue / (1+DiscountRate)^(1+max(y)-min(y)) | Monetary units |
| **AnnualVariableOperatingCost** | [r,t,y] ≥0 | Annual variable operating cost of technology t | AnnualVariableOperatingCost = Σ(m) TotalAnnualTechnologyActivityByMode × VariableCost | Monetary units |
| **AnnualFixedOperatingCost** | [r,t,y] ≥0 | Annual fixed operating cost of technology t | AnnualFixedOperatingCost = TotalCapacityAnnual × FixedCost | Monetary units |
| **OperatingCost** | [r,t,y] ≥0 | Undiscounted sum of annual variable and fixed operating costs of technology t | OperatingCost = AnnualFixedOperatingCost + AnnualVariableOperatingCost | Monetary units |
| **DiscountedOperatingCost** | [r,t,y] ≥0 | Annual operating cost of technology t, discounted to start year | DiscountedOperatingCost = OperatingCost / (1+DiscountRate)^(y-min(y)+0.5) | Monetary units |
| **TotalDiscountedCostByTechnology** | [r,t,y] ≥0 | Total discounted cost for technology t in year y | TotalDiscountedCostByTechnology = DiscountedOperatingCost + DiscountedCapitalInvestment + DiscountedTechnologyEmissionsPenalty - DiscountedSalvageValue | Monetary units |
| **TotalDiscountedCost** | [r,y] ≥0 | Sum of TotalDiscountedCostByTechnology over all technologies plus storage costs | TotalDiscountedCost = Σ(t) TotalDiscountedCostByTechnology + Σ(s) TotalDiscountedStorageCost | Monetary units |
| **ModelPeriodCostByRegion** | [r] ≥0 | Sum of TotalDiscountedCost over all modelled years | ModelPeriodCostByRegion = Σ(y) TotalDiscountedCost | Monetary units |

---

## 6. RESERVE MARGIN VARIABLES

| Variable | Indices | Definition | Relationship to Other Variables/Parameters | Units |
|----------|---------|------------|-------------------------------------------|-------|
| **TotalCapacityInReserveMargin** | [r,y] ≥0 | Total available capacity of technologies required to provide reserve margin, in activity units | TotalCapacityInReserveMargin = Σ(t) TotalCapacityAnnual × ReserveMarginTagTechnology × CapacityToActivityUnit | Energy per year |
| **DemandNeedingReserveMargin** | [r,l,y] ≥0 | Quantity of fuel produced that is assigned to a target of reserve margin | DemandNeedingReserveMargin = Σ(f) RateOfProduction × ReserveMarginTagFuel | Energy per year |
| **TotalREProductionAnnual** | [r,y] | Annual production by all technologies tagged as renewable | TotalREProductionAnnual = Σ(t,f) ProductionByTechnologyAnnual × RETagTechnology | Energy |
| **RETotalProductionOfTargetFuelAnnual** | [r,y] | Annual production of fuels tagged as renewable | RETotalProductionOfTargetFuelAnnual = Σ(l,f) RateOfProduction × YearSplit × RETagFuel | Energy |

---

## 7. EMISSIONS VARIABLES

| Variable | Indices | Definition | Relationship to Other Variables/Parameters | Units |
|----------|---------|------------|-------------------------------------------|-------|
| **AnnualTechnologyEmissionByMode** | [r,t,e,m,y] ≥0 | Annual emission of agent e by technology t in mode of operation m | AnnualTechnologyEmissionByMode = EmissionActivityRatio × TotalAnnualTechnologyActivityByMode | Quantity of emission |
| **AnnualTechnologyEmission** | [r,t,e,y] ≥0 | Sum of AnnualTechnologyEmissionByMode over all modes of operation | AnnualTechnologyEmission = Σ(m) AnnualTechnologyEmissionByMode | Quantity of emission |
| **AnnualTechnologyEmissionPenaltyByEmission** | [r,t,e,y] ≥0 | Undiscounted annual cost of emission e by technology t | AnnualTechnologyEmissionPenaltyByEmission = AnnualTechnologyEmission × EmissionsPenalty | Monetary units |
| **AnnualTechnologyEmissionsPenalty** | [r,t,y] ≥0 | Total undiscounted annual cost of all emissions generated by technology t | AnnualTechnologyEmissionsPenalty = Σ(e) AnnualTechnologyEmissionPenaltyByEmission | Monetary units |
| **DiscountedTechnologyEmissionsPenalty** | [r,t,y] ≥0 | Annual cost of emissions by technology t, discounted to start year | DiscountedTechnologyEmissionsPenalty = AnnualTechnologyEmissionsPenalty / (1+DiscountRate)^(y-min(y)+0.5) | Monetary units |
| **AnnualEmissions** | [r,e,y] ≥0 | Sum of AnnualTechnologyEmission over all technologies | AnnualEmissions = Σ(t) AnnualTechnologyEmission | Quantity of emission |
| **ModelPeriodEmissions** | [r,e] ≥0 | Total system emissions of agent e in the model period | ModelPeriodEmissions = Σ(y) AnnualEmissions + ModelPeriodExogenousEmission | Quantity of emission |

---

## VALIDATION SUMMARY

| Category | Count |
|----------|-------|
| Demand Variables | 2 |
| Storage Variables | 18 |
| Capacity Variables | 4 |
| Activity Variables | 21 |
| Costing Variables | 11 |
| Reserve Margin Variables | 4 |
| Emissions Variables | 7 |
| **TOTAL** | **67** |

### Notes on Validation:
1. **RateOfUse[r,l,f,y]** appears in equation EBa6 but is not explicitly listed in the original variable documentation table. It is included here for completeness based on its presence in the equations.
2. All indices follow OSeMOSYS conventions: r=region, l=timeslice, t=technology, m=mode, y=year, f=fuel, e=emission, s=storage, ls=season, ld=daytype, lh=dailytimebracket, rr=trading partner region.
3. Variables marked with "≥0" are constrained to be non-negative in the optimization.
4. The objective function minimizes: **Σ(r,y) TotalDiscountedCost[r,y]**

### Notes on Units:
Variable Cost Units in OSeMOSYS — General Case

The General Rule

**VariableCost units = [Monetary Units] / [Activity Unit]**

That's it. The units are always **cost per unit of activity**, where "activity unit" is whatever you've defined it to be in your model.


Understanding Activity Units

The **activity unit** in your model is implicitly defined by **CapacityToActivityUnit**, which has the relationship:

$$\text{CapacityToActivityUnit} = \frac{\text{[Activity Unit]}}{\text{[Capacity Unit]}}$$

This parameter answers: *"How many activity units does 1 capacity unit produce when running at full utilization for 1 year?"*

Deriving from the Equations

From **OC1_OperatingCostsVariable**:
```
AnnualVariableOperatingCost[r,t,y] = Σ(m) TotalAnnualTechnologyActivityByMode[r,t,m,y] × VariableCost[r,t,m,y]
```

Dimensional analysis:

| Variable | Units |
|----------|-------|
| AnnualVariableOperatingCost | [Money] |
| TotalAnnualTechnologyActivityByMode | [Activity] |
| VariableCost | **[Money] / [Activity]** |

Examples with Different Unit Choices

| Capacity Unit | Activity Unit | CapacityToActivityUnit | VariableCost Units |
|---------------|---------------|------------------------|-------------------|
| MW | MWh | 8,760 MWh/MW | $/MWh |
| GW | PJ | 31.536 PJ/GW | $/PJ |
| kW | kWh | 8,760 kWh/kW | $/kWh |
| MW | TJ | 31.536 TJ/MW | $/TJ |
| "1 power plant" | "1 plant-year" | 1 | $/plant-year |
| MW | GJ | 31,536 GJ/MW | $/GJ |


Key Insight

**You choose the activity unit. OSeMOSYS doesn't care what it physically represents.**

If you set:
- **CapacityToActivityUnit = 1**: Then 1 activity unit = output of 1 capacity unit running for 1 year
- **CapacityToActivityUnit = 8760**: Then 1 activity unit = output of 1 capacity unit running for 1 hour
- **CapacityToActivityUnit = 31.536**: Then 1 activity unit = 1 PJ (if capacity is in GW)

The VariableCost is simply **what it costs to produce one of those activity units**.

Practical Summary

$$\boxed{\text{VariableCost} = \frac{\text{[Monetary Unit]}}{\text{[Activity Unit]}}}$$

Where your choice of CapacityToActivityUnit implicitly defines what an "activity unit" means in physical terms.

### Notes on TotalDiscountedCost:

# Total Discounted Cost Calculation in OSeMOSYS

## Overview

The **objective function** minimizes the sum of TotalDiscountedCost across all regions and years:

$$\min \sum_{r \in REGION} \sum_{y \in YEAR} \text{TotalDiscountedCost}[r,y]$$

---

## Cost Hierarchy

```
TotalDiscountedCost[r,y]
├── Σ(t) TotalDiscountedCostByTechnology[r,t,y]
│   ├── (+) DiscountedCapitalInvestment[r,t,y]
│   ├── (+) DiscountedOperatingCost[r,t,y]
│   │   ├── AnnualFixedOperatingCost[r,t,y]
│   │   └── AnnualVariableOperatingCost[r,t,y]
│   ├── (+) DiscountedTechnologyEmissionsPenalty[r,t,y]
│   └── (−) DiscountedSalvageValue[r,t,y]
│
└── Σ(s) TotalDiscountedStorageCost[r,s,y]
    ├── (+) DiscountedCapitalInvestmentStorage[r,s,y]
    └── (−) DiscountedSalvageValueStorage[r,s,y]
```

Detailed Equations
1. Total Discounted Cost (Top Level)

**TDC2:**
$$\text{TotalDiscountedCost}[r,y] = \sum_{t} \text{TotalDiscountedCostByTechnology}[r,t,y] + \sum_{s} \text{TotalDiscountedStorageCost}[r,s,y]$$

**TDC1:**
$$\text{TotalDiscountedCostByTechnology}[r,t,y] = \text{DiscountedCapitalInvestment} + \text{DiscountedOperatingCost} + \text{DiscountedEmissionsPenalty} - \text{DiscountedSalvageValue}$$

2. Capital Investment

**CC1 — Undiscounted:**
$$\text{CapitalInvestment}[r,t,y] = \text{CapitalCost}[r,t,y] \times \text{NewCapacity}[r,t,y]$$

**CC2 — Discounted (beginning of year):**
$$\text{DiscountedCapitalInvestment}[r,t,y] = \frac{\text{CapitalInvestment}[r,t,y]}{(1 + r)^{(y - y_0)}}$$

Where:
- $r$ = DiscountRate
- $y_0$ = first year of model (min year)

3. Operating Costs

**OC1 — Variable:**
$$\text{AnnualVariableOperatingCost}[r,t,y] = \sum_{m} \text{TotalAnnualTechnologyActivityByMode}[r,t,m,y] \times \text{VariableCost}[r,t,m,y]$$

**OC2 — Fixed:**
$$\text{AnnualFixedOperatingCost}[r,t,y] = \text{TotalCapacityAnnual}[r,t,y] \times \text{FixedCost}[r,t,y]$$

**OC3 — Total Undiscounted:**
$$\text{OperatingCost}[r,t,y] = \text{AnnualFixedOperatingCost} + \text{AnnualVariableOperatingCost}$$

**OC4 — Discounted (mid-year):**
$$\text{DiscountedOperatingCost}[r,t,y] = \frac{\text{OperatingCost}[r,t,y]}{(1 + r)^{(y - y_0 + 0.5)}}$$

> **Note:** The `+0.5` represents **mid-year discounting** — operating costs are assumed to occur uniformly throughout the year, so they're discounted to the middle of the year.

4. Salvage Value

Salvage value recovers the remaining value of an asset whose operational life extends beyond the model horizon.

**SV3 — Life ends within model period:**
$$\text{SalvageValue}[r,t,y] = 0 \quad \text{if } (y + \text{OperationalLife} - 1) \leq y_{max}$$

**SV2 — Straight-line depreciation** (or sinking fund with r=0):
$$\text{SalvageValue}[r,t,y] = \text{CapitalCost} \times \text{NewCapacity} \times \left(1 - \frac{y_{max} - y + 1}{\text{OperationalLife}}\right)$$

**SV1 — Sinking fund depreciation** (with r > 0):
$$\text{SalvageValue}[r,t,y] = \text{CapitalCost} \times \text{NewCapacity} \times \left(1 - \frac{(1+r)^{(y_{max} - y + 1)} - 1}{(1+r)^{\text{OperationalLife}} - 1}\right)$$

**SV4 — Discounted to start year:**
$$\text{DiscountedSalvageValue}[r,t,y] = \frac{\text{SalvageValue}[r,t,y]}{(1 + r)^{(y_{max} - y_0 + 1)}}$$

> **Note:** Salvage value is discounted from the **end of the model period**, not from the year of investment.

5. Emissions Penalties

**E5 — Discounted (mid-year):**
$$\text{DiscountedTechnologyEmissionsPenalty}[r,t,y] = \frac{\text{AnnualTechnologyEmissionsPenalty}[r,t,y]}{(1 + r)^{(y - y_0 + 0.5)}}$$

Where:
$$\text{AnnualTechnologyEmissionsPenalty}[r,t,y] = \sum_{e} \text{AnnualTechnologyEmission}[r,t,e,y] \times \text{EmissionsPenalty}[r,e,y]$$

6. Storage Costs

**SI10:**
$$\text{TotalDiscountedStorageCost}[r,s,y] = \text{DiscountedCapitalInvestmentStorage}[r,s,y] - \text{DiscountedSalvageValueStorage}[r,s,y]$$

Discount Factor Summary

| Cost Component | Discount Factor | Timing Convention |
|----------------|-----------------|-------------------|
| Capital Investment | $(1+r)^{(y-y_0)}$ | Beginning of year |
| Operating Cost | $(1+r)^{(y-y_0+0.5)}$ | Mid-year |
| Emissions Penalty | $(1+r)^{(y-y_0+0.5)}$ | Mid-year |
| Salvage Value | $(1+r)^{(y_{max}-y_0+1)}$ | End of model period |

Numerical Example

**Setup:**
- Years: 2025, 2026, 2027 (so $y_0 = 2025$, $y_{max} = 2027$)
- DiscountRate = 0.05
- Technology installed in 2025: NewCapacity = 10 MW
- CapitalCost = $1000/MW
- VariableCost = $20/MWh
- FixedCost = $50/MW/year
- OperationalLife = 30 years
- Annual Activity = 50,000 MWh

**Year 2025 Calculations:**

| Component | Undiscounted | Discount Factor | Discounted |
|-----------|-------------|-----------------|------------|
| Capital Investment | $10,000 | $(1.05)^0 = 1.000$ | $10,000 |
| Variable Operating | $1,000,000 | $(1.05)^{0.5} = 1.025$ | $975,900 |
| Fixed Operating | $500 | $(1.05)^{0.5} = 1.025$ | $487.80 |
| **Subtotal 2025** | | | **$10,976,388** |

**Salvage Value (for 2025 investment):**

Since $2025 + 30 - 1 = 2054 > 2027$, salvage applies.

Sinking fund method:
$$\text{SV} = 10{,}000 \times \left(1 - \frac{(1.05)^{3} - 1}{(1.05)^{30} - 1}\right) = 10{,}000 \times (1 - 0.0477) = \$9{,}523$$

Discounted:
$$\text{DiscountedSV} = \frac{9{,}523}{(1.05)^{3}} = \$8{,}227$$

Key Insights

1. **Capital costs** are "paid" at the **beginning of the year** of installation
2. **Operating costs** are assumed to occur **throughout the year** (mid-year discounting)
3. **Salvage value** is a **credit** (subtracted) representing residual asset value beyond the model horizon
4. **All costs** are discounted to the **first year** ($y_0$) of the model
5. The **objective function** sums all discounted costs across all regions and years