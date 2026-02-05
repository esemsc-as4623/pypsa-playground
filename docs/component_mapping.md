# OSeMOSYS Parameter to Component Mapping

*Last updated: February 5, 2026*

This document defines which pyoscomp scenario component is responsible for each OSeMOSYS parameter. This mapping resolves ownership ambiguities and provides a clear reference for developers.

---

## Table of Contents
1. [Component Overview](#component-overview)
2. [Set Mappings](#set-mappings)
3. [Parameter Mappings](#parameter-mappings)
4. [Ownership Conflicts & Resolutions](#ownership-conflicts--resolutions)
5. [Implementation Status](#implementation-status)

---

## Component Overview

| Component | Responsibility | Status |
|-----------|----------------|--------|
| **TopologyComponent** | Spatial structure (regions, nodes) | ✅ Implemented |
| **TimeComponent** | Temporal resolution (years, timeslices) | ✅ Implemented |
| **DemandComponent** | Energy demand and load profiles | ✅ Implemented |
| **SupplyComponent** | Technology registry and metadata | ✅ Implemented |
| **EconomicsComponent** | Costs and discount rates | ✅ Implemented |
| **PerformanceComponent** | Technology operational characteristics | ⚠️ Partial (P1.3) |
| **StorageComponent** | Storage facilities and parameters | ❌ Not implemented |
| **EmissionsComponent** | Emissions and environmental constraints | ❌ Not implemented |
| **TargetsComponent** | Policy targets and capacity constraints | ❌ Not implemented |

---

## Set Mappings

OSeMOSYS defines 11 sets. Each set is owned by one component.

| OSeMOSYS Set | Component | CSV File | Column Name | Notes |
|--------------|-----------|----------|-------------|-------|
| `YEAR` | TimeComponent | `YEAR.csv` | `VALUE` | Model years |
| `TECHNOLOGY` | SupplyComponent | `TECHNOLOGY.csv` | `VALUE` | Auto-created when technologies are added |
| `TIMESLICE` | TimeComponent | `TIMESLICE.csv` | `VALUE` | Generated from seasons × daytypes × brackets |
| `FUEL` | SupplyComponent | `FUEL.csv` | `VALUE` | Auto-created from input/output activity ratios |
| `EMISSION` | EmissionsComponent | `EMISSION.csv` | `VALUE` | Future implementation |
| `MODE_OF_OPERATION` | SupplyComponent | `MODE_OF_OPERATION.csv` | `VALUE` | Auto-created from technology modes |
| `REGION` | TopologyComponent | `REGION.csv` | `VALUE` | Spatial nodes |
| `SEASON` | TimeComponent | `SEASON.csv` | `VALUE` | Seasonal subdivisions |
| `DAYTYPE` | TimeComponent | `DAYTYPE.csv` | `VALUE` | Day type classifications (e.g., weekday, weekend) |
| `DAILYTIMEBRACKET` | TimeComponent | `DAILYTIMEBRACKET.csv` | `VALUE` | Intra-day time brackets |
| `STORAGE` | StorageComponent | `STORAGE.csv` | `VALUE` | Future implementation |

**Convention:** All sets use a single column named `VALUE` containing the set members.

---

## Parameter Mappings

### 1. Topology Parameters

| OSeMOSYS Parameter | Component | CSV File | Columns | Status |
|--------------------|-----------|----------|---------|--------|
| `TradeRoute{r, rr, f, y}` | TopologyComponent | `TradeRoute.csv` | `REGION`, `REGION2`, `FUEL`, `YEAR`, `VALUE` | ❌ Future |

**Notes:**
- Trade routes define connections between regions for specific fuels
- Currently only single-region scenarios are supported
- Multi-region support is Priority 7 (P7.5)

---

### 2. Time Parameters

| OSeMOSYS Parameter | Component | CSV File | Columns | Status |
|--------------------|-----------|----------|---------|--------|
| `YearSplit{l, y}` | TimeComponent | `YearSplit.csv` | `TIMESLICE`, `YEAR`, `VALUE` | ✅ Implemented |
| `DaySplit{lh, y}` | TimeComponent | `DaySplit.csv` | `DAILYTIMEBRACKET`, `YEAR`, `VALUE` | ✅ Implemented |
| `Conversionls{l, ls}` | TimeComponent | `Conversionls.csv` | `TIMESLICE`, `SEASON`, `VALUE` | ✅ Implemented |
| `Conversionld{l, ld}` | TimeComponent | `Conversionld.csv` | `TIMESLICE`, `DAYTYPE`, `VALUE` | ✅ Implemented |
| `Conversionlh{l, lh}` | TimeComponent | `Conversionlh.csv` | `TIMESLICE`, `DAILYTIMEBRACKET`, `VALUE` | ✅ Implemented |
| `DaysInDayType{ls, ld, y}` | TimeComponent | `DaysInDayType.csv` | `SEASON`, `DAYTYPE`, `YEAR`, `VALUE` | ✅ Implemented |

**Notes:**
- `YearSplit` must sum to 1.0 for each year (fraction of year per timeslice)
- `DaySplit` must sum to 1.0 for each year (fraction of day per bracket)
- Conversion tables are binary (0 or 1) mappings between timeslices and their components
- TimeComponent validates temporal consistency

---

### 3. Demand Parameters

| OSeMOSYS Parameter | Component | CSV File | Columns | Status |
|--------------------|-----------|----------|---------|--------|
| `SpecifiedAnnualDemand{r, f, y}` | DemandComponent | `SpecifiedAnnualDemand.csv` | `REGION`, `FUEL`, `YEAR`, `VALUE` | ✅ Implemented |
| `SpecifiedDemandProfile{r, f, l, y}` | DemandComponent | `SpecifiedDemandProfile.csv` | `REGION`, `FUEL`, `TIMESLICE`, `YEAR`, `VALUE` | ✅ Implemented |
| `AccumulatedAnnualDemand{r, f, y}` | DemandComponent | `AccumulatedAnnualDemand.csv` | `REGION`, `FUEL`, `YEAR`, `VALUE` | ✅ Implemented |

**Notes:**
- `SpecifiedAnnualDemand`: Total annual energy demand (MWh/year)
- `SpecifiedDemandProfile`: Fraction of annual demand in each timeslice (must sum to 1.0 per year)
- `AccumulatedAnnualDemand`: Flexible demand that can be met anytime during the year
- DemandComponent provides `add_annual_demand()` and `set_subannual_profile()` methods

---

### 4. Supply Parameters

| OSeMOSYS Parameter | Component | CSV File | Columns | Status |
|--------------------|-----------|----------|---------|--------|
| `ResidualCapacity{r, t, y}` | SupplyComponent | `ResidualCapacity.csv` | `REGION`, `TECHNOLOGY`, `YEAR`, `VALUE` | ✅ Implemented |

**Notes:**
- SupplyComponent manages the technology registry (`add_technology()`)
- Residual capacity represents existing/pre-installed capacity (MW)
- Technologies are auto-added to `TECHNOLOGY.csv` when registered

---

### 5. Economics Parameters

| OSeMOSYS Parameter | Component | CSV File | Columns | Status |
|--------------------|-----------|----------|---------|--------|
| `DiscountRate{r}` | EconomicsComponent | `DiscountRate.csv` | `REGION`, `VALUE` | ✅ Implemented |
| `DiscountRateIdv{r, t}` | EconomicsComponent | `DiscountRateIdv.csv` | `REGION`, `TECHNOLOGY`, `VALUE` | ❌ Future |
| `CapitalCost{r, t, y}` | EconomicsComponent | `CapitalCost.csv` | `REGION`, `TECHNOLOGY`, `YEAR`, `VALUE` | ✅ Implemented |
| `VariableCost{r, t, m, y}` | EconomicsComponent | `VariableCost.csv` | `REGION`, `TECHNOLOGY`, `MODE_OF_OPERATION`, `YEAR`, `VALUE` | ✅ Implemented |
| `FixedCost{r, t, y}` | EconomicsComponent | `FixedCost.csv` | `REGION`, `TECHNOLOGY`, `YEAR`, `VALUE` | ✅ Implemented |
| `DepreciationMethod{r}` | EconomicsComponent | `DepreciationMethod.csv` | `REGION`, `VALUE` | ❌ Future |

**Notes:**
- `DiscountRate`: Regional discount rate for NPV calculations
- `DiscountRateIdv`: Technology-specific discount rate (overrides regional if set)
- `CapitalCost`: Capital investment cost per unit capacity ($/MW)
- `VariableCost`: Operating cost per unit activity ($/MWh)
- `FixedCost`: Annual fixed O&M cost per unit capacity ($/MW/year)
- EconomicsComponent provides trajectory support (dict or single value)

---

### 6. Performance Parameters

**⚠️ OWNERSHIP CONFLICT RESOLUTION**

These parameters were previously in SupplyComponent but conceptually belong to performance. Current status:

| OSeMOSYS Parameter | Current Owner | Future Owner | CSV File | Columns | Status |
|--------------------|---------------|--------------|----------|---------|--------|
| `OperationalLife{r, t}` | SupplyComponent | PerformanceComponent | `OperationalLife.csv` | `REGION`, `TECHNOLOGY`, `VALUE` | ✅ In SupplyComponent |
| `CapacityToActivityUnit{r, t}` | SupplyComponent | PerformanceComponent | `CapacityToActivityUnit.csv` | `REGION`, `TECHNOLOGY`, `VALUE` | ✅ In SupplyComponent |
| `InputActivityRatio{r, t, f, m, y}` | SupplyComponent | PerformanceComponent | `InputActivityRatio.csv` | `REGION`, `TECHNOLOGY`, `FUEL`, `MODE_OF_OPERATION`, `YEAR`, `VALUE` | ✅ In SupplyComponent |
| `OutputActivityRatio{r, t, f, m, y}` | SupplyComponent | PerformanceComponent | `OutputActivityRatio.csv` | `REGION`, `TECHNOLOGY`, `FUEL`, `MODE_OF_OPERATION`, `YEAR`, `VALUE` | ✅ In SupplyComponent |
| `CapacityFactor{r, t, l, y}` | SupplyComponent | PerformanceComponent | `CapacityFactor.csv` | `REGION`, `TECHNOLOGY`, `TIMESLICE`, `YEAR`, `VALUE` | ✅ In SupplyComponent |
| `AvailabilityFactor{r, t, y}` | SupplyComponent | PerformanceComponent | `AvailabilityFactor.csv` | `REGION`, `TECHNOLOGY`, `YEAR`, `VALUE` | ✅ In SupplyComponent |

**Decision (P1.3):** PerformanceComponent implemented as a **facade/wrapper** that delegates to SupplyComponent. This avoids disruptive refactoring while providing semantic clarity.

**Rationale:**
- Performance parameters are tightly coupled to technology definitions
- Moving them would require extensive refactoring of SupplyComponent methods
- Facade pattern provides cleaner API without code duplication
- Future refactoring can migrate implementation if needed

**Notes:**
- `OperationalLife`: Asset lifetime in years
- `CapacityToActivityUnit`: Conversion factor (default 8760 for MW to MWh/year)
- `InputActivityRatio`: Input fuel requirement per unit output (e.g., MWh_gas / MWh_elec)
- `OutputActivityRatio`: Output production per unit activity (typically 1.0 for primary output)
- `CapacityFactor`: Maximum capacity utilization per timeslice (0-1)
- `AvailabilityFactor`: Annual availability accounting for maintenance (0-1)

---

### 7. Capacity Constraint Parameters

| OSeMOSYS Parameter | Component | CSV File | Columns | Status |
|--------------------|-----------|----------|---------|--------|
| `CapacityOfOneTechnologyUnit{r, t, y}` | TargetsComponent | `CapacityOfOneTechnologyUnit.csv` | `REGION`, `TECHNOLOGY`, `YEAR`, `VALUE` | ❌ Future |
| `TotalAnnualMaxCapacity{r, t, y}` | TargetsComponent | `TotalAnnualMaxCapacity.csv` | `REGION`, `TECHNOLOGY`, `YEAR`, `VALUE` | ❌ Future |
| `TotalAnnualMinCapacity{r, t, y}` | TargetsComponent | `TotalAnnualMinCapacity.csv` | `REGION`, `TECHNOLOGY`, `YEAR`, `VALUE` | ❌ Future |
| `TotalAnnualMaxCapacityInvestment{r, t, y}` | TargetsComponent | `TotalAnnualMaxCapacityInvestment.csv` | `REGION`, `TECHNOLOGY`, `YEAR`, `VALUE` | ❌ Future |
| `TotalAnnualMinCapacityInvestment{r, t, y}` | TargetsComponent | `TotalAnnualMinCapacityInvestment.csv` | `REGION`, `TECHNOLOGY`, `YEAR`, `VALUE` | ❌ Future |

**Notes:**
- These define bounds on capacity expansion
- Used for policy constraints (e.g., max coal capacity, min renewable capacity)
- Future implementation in TargetsComponent (Priority 7)

---

### 8. Activity Constraint Parameters

| OSeMOSYS Parameter | Component | CSV File | Columns | Status |
|--------------------|-----------|----------|---------|--------|
| `TotalTechnologyAnnualActivityUpperLimit{r, t, y}` | TargetsComponent | `TotalTechnologyAnnualActivityUpperLimit.csv` | `REGION`, `TECHNOLOGY`, `YEAR`, `VALUE` | ❌ Future |
| `TotalTechnologyAnnualActivityLowerLimit{r, t, y}` | TargetsComponent | `TotalTechnologyAnnualActivityLowerLimit.csv` | `REGION`, `TECHNOLOGY`, `YEAR`, `VALUE` | ❌ Future |
| `TotalTechnologyModelPeriodActivityUpperLimit{r, t}` | TargetsComponent | `TotalTechnologyModelPeriodActivityUpperLimit.csv` | `REGION`, `TECHNOLOGY`, `VALUE` | ❌ Future |
| `TotalTechnologyModelPeriodActivityLowerLimit{r, t}` | TargetsComponent | `TotalTechnologyModelPeriodActivityLowerLimit.csv` | `REGION`, `TECHNOLOGY`, `VALUE` | ❌ Future |

**Notes:**
- Activity limits constrain energy production/consumption
- Annual limits apply per year; model period limits apply over entire horizon
- Future implementation in TargetsComponent (Priority 7)

---

### 9. Reserve Margin Parameters

| OSeMOSYS Parameter | Component | CSV File | Columns | Status |
|--------------------|-----------|----------|---------|--------|
| `ReserveMarginTagTechnology{r, t, y}` | TargetsComponent | `ReserveMarginTagTechnology.csv` | `REGION`, `TECHNOLOGY`, `YEAR`, `VALUE` | ❌ Future |
| `ReserveMarginTagFuel{r, f, y}` | TargetsComponent | `ReserveMarginTagFuel.csv` | `REGION`, `FUEL`, `YEAR`, `VALUE` | ❌ Future |
| `ReserveMargin{r, y}` | TargetsComponent | `ReserveMargin.csv` | `REGION`, `YEAR`, `VALUE` | ❌ Future |

**Notes:**
- Reserve margin ensures sufficient capacity above peak demand
- Tags identify which technologies/fuels contribute to reserve
- Future implementation in TargetsComponent (Priority 7)

---

### 10. Renewable Energy Target Parameters

| OSeMOSYS Parameter | Component | CSV File | Columns | Status |
|--------------------|-----------|----------|---------|--------|
| `RETagTechnology{r, t, y}` | TargetsComponent | `RETagTechnology.csv` | `REGION`, `TECHNOLOGY`, `YEAR`, `VALUE` | ❌ Future |
| `RETagFuel{r, f, y}` | TargetsComponent | `RETagFuel.csv` | `REGION`, `FUEL`, `YEAR`, `VALUE` | ❌ Future |
| `REMinProductionTarget{r, y}` | TargetsComponent | `REMinProductionTarget.csv` | `REGION`, `YEAR`, `VALUE` | ❌ Future |

**Notes:**
- RE targets mandate minimum renewable energy production
- Tags identify which technologies/fuels count as renewable
- Future implementation in TargetsComponent (Priority 7)

---

### 11. Storage Parameters

| OSeMOSYS Parameter | Component | CSV File | Columns | Status |
|--------------------|-----------|----------|---------|--------|
| `TechnologyToStorage{r, t, s, m}` | StorageComponent | `TechnologyToStorage.csv` | `REGION`, `TECHNOLOGY`, `STORAGE`, `MODE_OF_OPERATION`, `VALUE` | ❌ Future |
| `TechnologyFromStorage{r, t, s, m}` | StorageComponent | `TechnologyFromStorage.csv` | `REGION`, `TECHNOLOGY`, `STORAGE`, `MODE_OF_OPERATION`, `VALUE` | ❌ Future |
| `StorageLevelStart{r, s}` | StorageComponent | `StorageLevelStart.csv` | `REGION`, `STORAGE`, `VALUE` | ❌ Future |
| `StorageMaxChargeRate{r, s}` | StorageComponent | `StorageMaxChargeRate.csv` | `REGION`, `STORAGE`, `VALUE` | ❌ Future |
| `StorageMaxDischargeRate{r, s}` | StorageComponent | `StorageMaxDischargeRate.csv` | `REGION`, `STORAGE`, `VALUE` | ❌ Future |
| `MinStorageCharge{r, s, y}` | StorageComponent | `MinStorageCharge.csv` | `REGION`, `STORAGE`, `YEAR`, `VALUE` | ❌ Future |
| `OperationalLifeStorage{r, s}` | StorageComponent | `OperationalLifeStorage.csv` | `REGION`, `STORAGE`, `VALUE` | ❌ Future |
| `CapitalCostStorage{r, s, y}` | StorageComponent | `CapitalCostStorage.csv` | `REGION`, `STORAGE`, `YEAR`, `VALUE` | ❌ Future |
| `ResidualStorageCapacity{r, s, y}` | StorageComponent | `ResidualStorageCapacity.csv` | `REGION`, `STORAGE`, `YEAR`, `VALUE` | ❌ Future |

**Notes:**
- Storage parameters define energy storage facilities (batteries, pumped hydro, etc.)
- `TechnologyToStorage`: Rate at which technology charges storage (e.g., MWh/h)
- `TechnologyFromStorage`: Rate at which technology discharges storage
- Future implementation in StorageComponent (Priority 7.1)

---

### 12. Emissions Parameters

| OSeMOSYS Parameter | Component | CSV File | Columns | Status |
|--------------------|-----------|----------|---------|--------|
| `EmissionActivityRatio{r, t, e, m, y}` | EmissionsComponent | `EmissionActivityRatio.csv` | `REGION`, `TECHNOLOGY`, `EMISSION`, `MODE_OF_OPERATION`, `YEAR`, `VALUE` | ❌ Future |
| `EmissionsPenalty{r, e, y}` | EmissionsComponent | `EmissionsPenalty.csv` | `REGION`, `EMISSION`, `YEAR`, `VALUE` | ❌ Future |
| `AnnualExogenousEmission{r, e, y}` | EmissionsComponent | `AnnualExogenousEmission.csv` | `REGION`, `EMISSION`, `YEAR`, `VALUE` | ❌ Future |
| `AnnualEmissionLimit{r, e, y}` | EmissionsComponent | `AnnualEmissionLimit.csv` | `REGION`, `EMISSION`, `YEAR`, `VALUE` | ❌ Future |
| `ModelPeriodExogenousEmission{r, e}` | EmissionsComponent | `ModelPeriodExogenousEmission.csv` | `REGION`, `EMISSION`, `VALUE` | ❌ Future |
| `ModelPeriodEmissionLimit{r, e}` | EmissionsComponent | `ModelPeriodEmissionLimit.csv` | `REGION`, `EMISSION`, `VALUE` | ❌ Future |

**Notes:**
- Emissions tracking and constraints for environmental policy analysis
- `EmissionActivityRatio`: Emissions per unit activity (e.g., tCO2/MWh)
- `EmissionsPenalty`: Carbon price or penalty ($/ton)
- Limits can be annual or over entire model period
- Future implementation in EmissionsComponent (Priority 7.3)

---

## Ownership Conflicts & Resolutions

### 1. Performance Parameters (RESOLVED)

**Conflict:** Parameters like `OperationalLife`, `CapacityFactor`, `InputActivityRatio`, `OutputActivityRatio` are conceptually "performance" but implemented in SupplyComponent.

**Resolution:** 
- **Keep implementation in SupplyComponent** (SupplyComponent lines 38-40, 194-197, 263-270, etc.)
- **PerformanceComponent acts as a facade** providing semantic clarity without code duplication
- Methods like `set_conversion_technology()` remain in SupplyComponent
- Future refactoring can migrate if needed (Priority 5+)

**Rationale:**
- These parameters are tightly coupled to technology registration
- SupplyComponent's `add_technology()` initializes operational life and capacity unit
- `set_conversion_technology()` directly manipulates input/output ratios
- Moving would require extensive refactoring with high risk of breakage
- Facade pattern (P1.3) provides clean API without disruption

---

### 2. FUEL Set (RESOLVED)

**Conflict:** FUEL is a set, but not explicitly created by user—it's auto-generated from technology definitions.

**Resolution:**
- **Owner: SupplyComponent**
- Auto-created when `InputActivityRatio` or `OutputActivityRatio` are set
- Tracks fuels in `self.defined_fuels` set
- Future: Add explicit `add_fuel()` method for manual control

---

### 3. MODE_OF_OPERATION Set (RESOLVED)

**Conflict:** MODE_OF_OPERATION is auto-generated from technology modes.

**Resolution:**
- **Owner: SupplyComponent**
- Auto-created when modes are defined via `set_conversion_technology()` or `set_multimode_technology()`
- Tracks modes in `self.mode_definitions` dict
- Future: Add explicit `add_mode()` method for manual control

---

### 4. Discount Rate (RESOLVED)

**Conflict:** `DiscountRate` is regional (economics) but `DiscountRateIdv` is technology-specific.

**Resolution:**
- **Owner: EconomicsComponent**
- `DiscountRate{r}`: Regional default implemented (P1.2)
- `DiscountRateIdv{r, t}`: Technology override not yet implemented (Priority 2+)
- Default behavior: use regional discount rate for all technologies

---

### 5. Residual Capacity (RESOLVED)

**Conflict:** `ResidualCapacity` could belong to SupplyComponent (technology data) or TargetsComponent (capacity constraints).

**Resolution:**
- **Owner: SupplyComponent**
- Represents existing capacity, conceptually part of technology inventory
- Distinct from capacity limits (min/max) which are policy constraints
- Set via `add_technology()` or separate setter

---

## Implementation Status

### ✅ Fully Implemented (Priority 1 Complete)

| Component | Parameters Supported | Methods Available |
|-----------|---------------------|-------------------|
| TopologyComponent | `REGION` | `add_nodes()` |
| TimeComponent | `YEAR`, `TIMESLICE`, `SEASON`, `DAYTYPE`, `DAILYTIMEBRACKET`, `YearSplit`, `DaySplit`, `Conversion*`, `DaysInDayType` | `add_time_structure()` |
| DemandComponent | `SpecifiedAnnualDemand`, `SpecifiedDemandProfile`, `AccumulatedAnnualDemand` | `add_annual_demand()`, `set_subannual_profile()`, `add_flexible_demand()` |
| SupplyComponent | `TECHNOLOGY`, `FUEL`, `MODE_OF_OPERATION`, `ResidualCapacity`, `OperationalLife`, `CapacityToActivityUnit`, `Input/OutputActivityRatio`, `CapacityFactor`, `AvailabilityFactor` | `add_technology()`, `set_conversion_technology()`, `set_multimode_technology()`, `set_resource_technology()` |
| EconomicsComponent | `DiscountRate`, `CapitalCost`, `VariableCost`, `FixedCost` | `set_discount_rate()`, `set_capital_cost()`, `set_variable_cost()`, `set_fixed_cost()` |

### ⚠️ Partially Implemented

| Component | Status | Notes |
|-----------|--------|-------|
| PerformanceComponent | Facade only | Delegates to SupplyComponent; no independent implementation |

### ❌ Not Implemented (Future Priority)

| Component | Priority | Parameters Count |
|-----------|----------|------------------|
| StorageComponent | P7.1 | 9 parameters |
| EmissionsComponent | P7.3 | 6 parameters |
| TargetsComponent | P7.4 | 14 parameters (capacity/activity limits, reserve margin, RE targets) |

---

## Usage Guidelines

### For Users

**1. Always check component prerequisites:**
```python
# DemandComponent requires Time and Topology to be set first
topology.add_nodes(['REGION1'])
topology.save()

time.add_time_structure(years, seasons, daytypes, brackets)
time.save()

# Now safe to use DemandComponent
demand = DemandComponent(scenario_dir)
```

**2. Use semantic component names:**
```python
# ✅ Good: Clear intent
economics.set_capital_cost('REGION1', 'SOLAR_PV', 300)

# ❌ Bad: Implementation detail
supply.capital_cost_df = ...  # Don't manipulate DataFrames directly
```

**3. Follow component ordering:**
```
Topology → Time → (Demand + Supply + Economics + Performance) → Save All
```

### For Developers

**1. Adding new parameters:**
- Identify correct component from this mapping
- Add DataFrame to component's `__init__()`
- Implement getter/setter methods
- Update `load()` and `save()` methods
- Add validation in setter
- Update this document

**2. Resolving ambiguous ownership:**
- Ask: "What is the primary responsibility?"
- Economic data → EconomicsComponent
- Operational data → PerformanceComponent
- Policy constraints → TargetsComponent
- When in doubt, discuss in issues/PR

**3. Auto-generated vs. explicit sets:**
- Sets like FUEL, MODE_OF_OPERATION are auto-generated from parameters
- Always provide explicit setter methods for user control
- Track in internal state (e.g., `self.defined_fuels`)

---

## Change Log

| Date | Change | Reason |
|------|--------|--------|
| 2026-02-05 | Initial version | P1.5 - Document component ownership |
| 2026-02-05 | Resolved performance parameter conflict | P1.3 implementation decision |
| 2026-02-05 | Added EconomicsComponent mappings | P1.2 implementation |

---

## References

- [OSeMOSYS Documentation](http://www.osemosys.org/)
- [pyoscomp tasks.md](../pyoscomp/tasks.md) - Implementation priorities
- [simple.ipynb](../notebooks/simple.ipynb) - Reference scenario
- [OSeMOSYS.txt](./OSeMOSYS.txt) - GMPL model definition
