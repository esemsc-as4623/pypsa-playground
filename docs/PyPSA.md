# PyPSA Component Architecture and Parameters

This document provides a comprehensive, structured reference for **PyPSA (Python for Power System Analysis)** components, parameters, constraints, and optimization features. It is intended to support **model translation and interoperability**, in particular with **OSeMOSYS**, and to serve as a canonical reference for the pyoscomp project.

---

## 1. Overview of PyPSA

PyPSA is a Python-based open-source framework for:

* Power system analysis and optimization
* Sector-coupled energy system modeling (electricity, heat, hydrogen, fuels, CO₂, etc.)
* Capacity expansion planning (CEP)
* Unit commitment (UC)
* Multi-period investment optimization
* Stochastic programming

PyPSA models systems as **networks** composed of components connected by **buses**, with optimization formulated as a **linear or mixed-integer linear program** using *linopy*.

---

## 2. pyoscomp Translation Status

This section documents which PyPSA components and parameters are handled in the **pyoscomp** translation framework for generating OSeMOSYS-compatible datasets. Translation follows the phased Implementation Plan with foundational research complete and translation layer implementation in progress.

### Status Legend
- ✓ **Implemented**: Translation logic fully operational
- ○ **Partial**: Research complete, implementation in progress
- ✗ **Not Implemented**: Planned for future phases

### Bus Component Translation

| PyPSA Attribute | pyoscomp Translation Method | OSeMOSYS Mapping | Status |
|----------------|---------------------------|------------------|--------|
| name | translation/pypsa_translator.py - translate_buses() | REGION.csv entry | ✗ |
| carrier | Translation logic | Fuel/commodity categorization | ✗ |
| x, y (coordinates) | Geographic metadata | Not directly translated (metadata only) | ✗ |
| v_nom | Network parameter | Not translated (OSeMOSYS abstracts voltage) | ✗ |

**Implementation Target**: Phase 4 - Task 4.4 (Bus→REGION translation with carrier-based fuel generation)

**Translation Approach**: Each PyPSA bus maps to one OSeMOSYS REGION. Carrier attribute determines fuel/commodity generation strategy (electricity, heat, hydrogen, etc.). Geographic coordinates preserved as metadata but not used in OSeMOSYS optimization.

### Generator Component Translation

| PyPSA Attribute | pyoscomp Translation Method | OSeMOSYS Mapping | Status |
|----------------|---------------------------|------------------|--------|
| p_nom (fixed) | translation/pypsa_translator.py - translate_generators() | ResidualCapacity.csv | ✗ |
| p_nom (extendable) | Translation logic | Capacity optimization variables | ✗ |
| p_max_pu (time series) | Timeslice aggregation | CapacityFactor.csv (by TIMESLICE) | ✗ |
| efficiency | Performance translation | InputActivityRatio.csv (1/efficiency), OutputActivityRatio.csv | ✗ |
| capital_cost (€/MW) | Economics translation | CapitalCost.csv (€/GW, multiply by 1000) | ✗ |
| marginal_cost (€/MWh) | Economics translation | VariableCost.csv (€/PJ, unit conversion) | ✗ |
| carrier | Carrier mapping | Input/output fuel determination | ✗ |
| bus | Topology linkage | Region assignment | ✗ |

**Implementation Target**: Phase 4 - Task 4.5 (Generator translation with timeslice aggregation)

**Translation Challenges**:
- **p_max_pu aggregation**: PyPSA snapshot time series → OSeMOSYS timeslice representative values (weighted average or percentile-based)
- **Unit conversions**: MW→GW (×1000), €/MWh→€/PJ (×3.6 then adjust for activity units)
- **CapacityToActivityUnit**: Critical conversion factor (31.536 for PJ/GW/year or 8760 for GWh/GW/year)

### Load Component Translation

| PyPSA Attribute | pyoscomp Translation Method | OSeMOSYS Mapping | Status |
|----------------|---------------------------|------------------|--------|
| p_set (time series) | translation/pypsa_translator.py - translate_loads() | SpecifiedAnnualDemand.csv + SpecifiedDemandProfile.csv | ✗ |
| bus | Topology linkage | Region assignment for demand | ✗ |
| carrier | Fuel mapping | Demand fuel specification | ✗ |

**Implementation Target**: Phase 4 - Task 4.5 (Load translation with demand profile generation)

**Translation Approach**: 
1. Calculate annual total: `SpecifiedAnnualDemand = sum(p_set × snapshot_weightings)`
2. Generate timeslice profile: `SpecifiedDemandProfile[l] = (demand in timeslice l) / total annual`
3. Aggregate snapshots to timeslices using predefined timeslice structure

### StorageUnit Component Translation

| PyPSA Attribute | pyoscomp Translation Method | OSeMOSYS Mapping | Status |
|----------------|---------------------------|------------------|--------|
| p_nom (power capacity) | translation/pypsa_translator.py - translate_storage_units() | STORAGE capacity = p_nom × max_hours (energy) | ✗ |
| max_hours (E/P ratio) | Decomposition logic | Energy capacity calculation | ✗ |
| efficiency_store | Storage charge tech | InputActivityRatio for charge TECHNOLOGY | ✗ |
| efficiency_dispatch | Storage discharge tech | OutputActivityRatio for discharge TECHNOLOGY | ✗ |
| standing_loss | Storage loss approximation | MinStorageCharge approximation or ignored | ✗ |
| capital_cost | Economics translation | Split between STORAGE and charge/discharge TECHNOLOGYs | ✗ |

**Implementation Target**: Phase 4 - Task 4.5 (StorageUnit decomposition)

**Translation Strategy** (Decomposition):
1. Create **STORAGE facility** with capacity `e_nom = p_nom × max_hours`
2. Create **charge TECHNOLOGY** with `TechnologyToStorage` linkage, efficiency from `efficiency_store`
3. Create **discharge TECHNOLOGY** with `TechnologyFromStorage` linkage, efficiency from `efficiency_dispatch`
4. Couple charge/discharge capacity to storage power rating

**Critical Note**: Single PyPSA StorageUnit becomes **three OSeMOSYS entities**, requiring careful tracking and naming conventions (e.g., `BATTERY_01`, `BATTERY_01_CHARGE`, `BATTERY_01_DISCHARGE`).

### Store Component Translation

| PyPSA Attribute | pyoscomp Translation Method | OSeMOSYS Mapping | Status |
|----------------|---------------------------|------------------|--------|
| e_nom (energy capacity) | translation/pypsa_translator.py - translate_stores() | STORAGE.csv entry | ✗ |
| e_min_pu, e_max_pu | Storage constraints | MinStorageCharge, storage capacity limits | ✗ |
| e_initial | Initial state | StorageLevelStart.csv | ✗ |
| e_cyclic | Cyclic constraint | End-of-year = start-of-year constraint | ✗ |

**Implementation Target**: Phase 4 - Task 4.5 (Store + Link translation)

**Translation Strategy**: Store requires associated Link components for charging/discharging. Translation identifies Links connected to Store and decomposes into charge/discharge TECHNOLOGY entities with `TechnologyToStorage` / `TechnologyFromStorage` linkages.

### Link Component Translation

| PyPSA Attribute | pyoscomp Translation Method | OSeMOSYS Mapping | Status |
|----------------|---------------------------|------------------|--------|
| p_nom (capacity) | translation/pypsa_translator.py - translate_links() | TECHNOLOGY capacity or trade route capacity | ✗ |
| efficiency, efficiency2, ... | Multi-port decomposition | MODE_OF_OPERATION with InputActivityRatio/OutputActivityRatio per port | ✗ |
| bus0, bus1, bus2, ... | Port configuration | Regional fuel flow definitions per mode | ✗ |
| capital_cost, marginal_cost | Economics translation | CapitalCost, VariableCost for TECHNOLOGY | ✗ |

**Implementation Target**: Phase 4 - Task 4.5 (Link→MODE_OF_OPERATION decomposition)

**Translation Strategy** (Multi-Port Links):
1. Create single TECHNOLOGY for Link
2. Each port combination → separate MODE_OF_OPERATION entry
3. Input ports (bus0, negative efficiency) → InputActivityRatio per mode
4. Output ports (bus1+, positive efficiency) → OutputActivityRatio per mode
5. Enables sector coupling (e.g., electrolyzer: electricity input, H2 output, heat output)

**Example**: 3-port Link (electricity→hydrogen+heat) becomes TECHNOLOGY with MODE1 having:
- InputActivityRatio[ELEC] = 1.0 / efficiency
- OutputActivityRatio[H2] = efficiency × port1_fraction
- OutputActivityRatio[HEAT] = efficiency2 × port2_fraction

### Line Component Translation

| PyPSA Attribute | pyoscomp Translation Method | OSeMOSYS Mapping | Status |
|----------------|---------------------------|------------------|--------|
| bus0, bus1 | Regional mapping | TradeRoute if buses map to distinct REGIONs | ✗ |
| s_nom (capacity) | Trade capacity | Trade capacity limit (if applicable) | ✗ |
| r, x (impedance) | Network physics | Not translated (OSeMOSYS lacks network flow equations) | ✗ |

**Implementation Target**: Phase 4 - Task 4.5 (optional, if multi-region)

**Translation Limitation**: Lines represent **AC/DC power flow with network physics** (Kirchhoff's laws, impedance). OSeMOSYS uses **commodity flow model** without network equations. Translation is only meaningful if:
1. PyPSA buses aggregate to distinct OSeMOSYS regions
2. Lines between regions map to TradeRoute
3. User accepts loss of network flow detail (impedance, voltage, reactive power)

**Default Approach**: Single-region models ignore Lines (intra-regional network abstracted away). Multi-region models require user specification of bus→region mapping.

### Transformer Component Translation

| PyPSA Attribute | pyoscomp Translation Method | OSeMOSYS Mapping | Status |
|----------------|---------------------------|------------------|--------|
| bus0, bus1 | Voltage level mapping | Not directly translated | ✗ |
| s_nom (capacity) | Capacity limits | Not translated unless regional boundary | ✗ |

**Implementation Target**: Not planned (Phase 4+)

**Translation Limitation**: Transformers model **voltage transformation between buses**. OSeMOSYS abstracts voltage levels entirely. Transformers are ignored in translation unless they define regional boundaries (similar to Line treatment).

### Economics Integration

| PyPSA Parameter | pyoscomp Translation Method | OSeMOSYS Mapping | Status |
|----------------|---------------------------|------------------|--------|
| capital_cost (various components) | translation/pypsa_translator.py - translate_economics() | CapitalCost.csv (with unit conversion) | ✗ |
| marginal_cost (Generator, Link, etc.) | Economics translation | VariableCost.csv (with unit conversion) | ✗ |
| Discount rate (not explicit in PyPSA) | User-specified parameter | DiscountRate.csv (required by OSeMOSYS) | ✗ |

**Implementation Target**: Phase 4 - Task 4.6 (Economics parameter integration)

**Translation Challenges**:
- **Unit conversions**: PyPSA uses €/MW for capital, €/MWh for variable. OSeMOSYS uses consistent capacity/activity units (€/GW, €/PJ). Conversion factors must align with CapacityToActivityUnit.
- **Discount rate**: PyPSA doesn't require explicit discount rate (can be applied in post-processing). OSeMOSYS requires DiscountRate.csv for NPV calculations. Translation must accept user-specified value or apply default (e.g., 5%).
- **Fixed O&M**: PyPSA doesn't separate capital from fixed O&M as clearly as OSeMOSYS. May require user specification or standard assumptions (e.g., 2-4% of capital cost annually).

### Time Series Aggregation

| PyPSA Time Representation | pyoscomp Translation Method | OSeMOSYS Mapping | Status |
|--------------------------|---------------------------|------------------|--------|
| snapshots (flexible time steps) | translation/pypsa_translator.py - aggregate_timeseries() | TIMESLICE (predefined structure) | ✗ |
| snapshot_weightings (objective, store, generator) | Aggregation logic | YearSplit fractions (Conversionlh × Conversionld × Conversionls) | ✗ |
| Time series (p_max_pu, p_set, etc.) | Statistical aggregation (mean, percentile) | Timeslice representative values | ✗ |

**Implementation Target**: Phase 4 - Task 4.4 (Timeslice aggregation strategy)

**Translation Approach**:
1. **Predefine timeslice structure**: User specifies SEASON × DAYTYPE × DAILYTIMEBRACKET (e.g., 4×2×3 = 24 timeslices)
2. **Map snapshots to timeslices**: Assign each PyPSA snapshot to one OSeMOSYS timeslice based on temporal attributes
3. **Aggregate time series**: For each timeslice, calculate representative value:
   - **CapacityFactor**: Weighted mean or conservative percentile (e.g., P10 for reliability)
   - **Demand profile**: Mean demand in timeslice / annual total
   - **Snapshot weightings**: Sum weightings in timeslice → YearSplit fraction

**Key Decision**: Timeslice aggregation method (mean vs percentile) significantly affects results. Conservative approach uses low percentile for generation availability, high percentile for demand to ensure adequacy.

### Carrier Mapping

| PyPSA Carrier | pyoscomp Translation Method | OSeMOSYS FUEL | Status |
|--------------|---------------------------|---------------|--------|
| AC, DC (electricity) | Carrier translation | ELEC or ELEC_HV/ELEC_MV/ELEC_LV | ✗ |
| heat, urban_heat | Carrier translation | HEAT_DISTRICT or HEAT_LOW_TEMP | ✗ |
| H2, hydrogen | Carrier translation | H2_COMPRESSED or H2 | ✗ |
| gas, natural gas | Carrier translation | GAS_NAT | ✗ |
| oil, petroleum | Carrier translation | OIL_CRUDE or petroleum products | ✗ |
| biomass | Carrier translation | BIOMASS_SOLID or BIOMASS_GAS | ✗ |

**Implementation Target**: Phase 4 - Task 4.4 (Carrier→FUEL mapping)

**Translation Strategy**: PyPSA carriers define energy types flowing through network. Translation creates corresponding OSeMOSYS FUEL entries. Mapping can be:
- **1:1**: Simple carrier (e.g., `H2` → `H2`)
- **1:many**: Carrier with voltage levels (e.g., `AC` → `ELEC_HV`, `ELEC_MV`, `ELEC_LV`)
- **User-specified**: Custom mapping for specific modeling needs

### Implementation Notes

**Phase 1-3 (Complete/In Progress)**: Research and component scaffolding establish OSeMOSYS parameter generation logic. Planning.md mapping table documents all translation decisions.

**Phase 4 (In Progress)**: Translation layer orchestrates component usage to convert PyPSA Network objects to OSeMOSYS CSV datasets. Key tasks:
- Task 4.4: Bus→REGION, Carrier→FUEL, timeslice aggregation framework
- Task 4.5: Generator, Load, StorageUnit, Link translation with decomposition logic
- Task 4.6: Economics integration with unit conversion validation

**Critical Path Items**:
1. **CapacityToActivityUnit**: Conversion factor must be consistent across all translations (31.536 for PJ/GW/year or 8760 for GWh/GW/year)
2. **Timeslice structure**: User must specify before translation (cannot dynamically adjust OSeMOSYS timeslices)
3. **Storage decomposition naming**: StorageUnit generates 3 entities requiring clear naming convention
4. **Multi-port Link modes**: MODE_OF_OPERATION generation must handle arbitrary port counts

**Validation Strategy**: Translation outputs validated against:
- Energy balance: PyPSA annual energy totals ≈ OSeMOSYS annual activity × CapacityToActivityUnit
- Capacity limits: PyPSA p_nom constraints ≈ OSeMOSYS TotalCapacityAnnual
- Cost totals: PyPSA objective function ≈ OSeMOSYS TotalDiscountedCost (within unit conversion tolerance)

## 3. Component Type Hierarchy

PyPSA defines **14 primary component types**, grouped by topology and controllability.

### 2.1 Core Component Types

1. **Bus** – Network nodes enforcing energy balance
2. **Carrier** – Energy carrier / technology descriptors
3. **Generator** – Power generation or supply
4. **Load** – Power demand or exogenous supply
5. **Store** – Energy storage with independent energy capacity
6. **StorageUnit** – Energy storage with coupled power–energy capacity
7. **Line** – Passive AC/DC transmission line
8. **Transformer** – Passive voltage transformation
9. **Link** – Controllable power flow / conversion (multi-port)
10. **ShuntImpedance** – Reactive power compensation
11. **LineType** – Standard line parameter definitions
12. **TransformerType** – Standard transformer parameter definitions
13. **GlobalConstraint** – System-wide constraints
14. **SubNetwork** – Topological grouping of buses

### 2.2 Component Categorization

**One-Port Components**:

* Generator, Load, StorageUnit, Store, ShuntImpedance

**Branch Components**:

* Line, Transformer, Link

**Passive Branch Components**:

* Line, Transformer

**Controllable Components**:

* Generator, Load, StorageUnit, Store, Link

---

## 3. Bus Component

### Purpose

Network node enforcing Kirchhoff’s Current Law (nodal energy balance).

### Key Parameters

| Parameter | Unit    | Type   | Notes                                        |
| --------- | ------- | ------ | -------------------------------------------- |
| name      | –       | string | Unique identifier (required)                 |
| v_nom     | kV      | float  | Nominal voltage (default 1.0)                |
| carrier   | –       | string | Energy carrier (AC, DC, heat, H₂, CO₂, etc.) |
| control   | –       | string | PQ, PV, or Slack                             |
| x, y      | degrees | float  | Geographic coordinates                       |

### Outputs

* Active power balance `p` (MW)
* Reactive power balance `q` (MVAr)
* Voltage magnitude `v_mag_pu`
* Voltage angle `v_ang`

---

## 4. Generator Component

### Purpose

Represents electricity or energy supply technologies with optional unit commitment and capacity expansion.

### Capacity Parameters

| Parameter        | Unit | Description                 |
| ---------------- | ---- | --------------------------- |
| p_nom            | MW   | Installed capacity          |
| p_nom_extendable | –    | Enables investment decision |
| p_nom_min / max  | MW   | Capacity bounds             |
| p_nom_opt        | MW   | Optimized capacity (output) |

### Dispatch Parameters

| Parameter  | Unit | Description                |
| ---------- | ---- | -------------------------- |
| p_min_pu   | –    | Minimum output per unit    |
| p_max_pu   | –    | Maximum availability       |
| p_set      | MW   | Fixed dispatch             |
| efficiency | –    | Conversion efficiency      |
| sign       | ±1   | Supply (+1) or demand (-1) |

### Cost Parameters

| Parameter     | Unit  | Description             |
| ------------- | ----- | ----------------------- |
| capital_cost  | €/MW  | Investment cost         |
| marginal_cost | €/MWh | Variable operating cost |

### Unit Commitment Parameters

* committable
* start_up_cost, shut_down_cost
* min_up_time, min_down_time
* ramp_limit_up, ramp_limit_down

### Outputs

* Dispatch `p` (MW)
* Reactive power `q` (MVAr)
* Binary status `status`

---

## 5. Load Component

### Purpose

Represents electricity or energy demand at a bus.

### Key Parameters

| Parameter | Unit | Description                     |
| --------- | ---- | ------------------------------- |
| bus       | –    | Connected bus                   |
| p_set     | MW   | Demand time series              |
| q_set     | MVAr | Reactive demand                 |
| sign      | ±1   | Consumption (+1) or supply (-1) |

### Outputs

* Active power `p`
* Reactive power `q`

---

## 6. StorageUnit Component

### Purpose

Energy storage with **coupled power and energy capacity**:

> e_nom = p_nom × max_hours

### Capacity Parameters

| Parameter        | Unit | Description           |
| ---------------- | ---- | --------------------- |
| p_nom            | MW   | Power capacity        |
| max_hours        | h    | Energy-to-power ratio |
| p_nom_extendable | –    | Enables expansion     |

### Operational Parameters

| Parameter           | Unit | Description               |
| ------------------- | ---- | ------------------------- |
| p_min_pu            | –    | Charging limit (negative) |
| p_max_pu            | –    | Discharging limit         |
| efficiency_store    | –    | Charging efficiency       |
| efficiency_dispatch | –    | Discharging efficiency    |
| standing_loss       | –    | Self-discharge rate       |

### Outputs

* p_dispatch (MW)
* p_store (MW)
* state_of_charge (MWh)
* spill (MW)

---

## 7. Store Component

### Purpose

Energy storage with **independent energy capacity**, requiring external Links for charging/discharging.

### Capacity Parameters

| Parameter        | Unit | Description       |
| ---------------- | ---- | ----------------- |
| e_nom            | MWh  | Energy capacity   |
| e_nom_extendable | –    | Enables expansion |

### Operational Parameters

| Parameter           | Unit | Description            |
| ------------------- | ---- | ---------------------- |
| e_min_pu / e_max_pu | –    | State-of-charge bounds |
| e_initial           | MWh  | Initial energy         |
| e_cyclic            | –    | Cyclic condition       |

### Outputs

* Power `p` (MW)
* Energy `e` (MWh)

---

## 8. Line Component

### Purpose

Passive AC/DC transmission with impedance-based power flow.

### Key Parameters

| Parameter        | Unit | Description              |
| ---------------- | ---- | ------------------------ |
| bus0, bus1       | –    | Connected buses          |
| r, x             | Ω    | Resistance and reactance |
| s_nom            | MVA  | Thermal capacity         |
| s_nom_extendable | –    | Enables expansion        |
| s_max_pu         | –    | Time-varying limit       |

### Outputs

* p0, p1 (MW)
* q0, q1 (MVAr)
* s (MVA)

---

## 9. Transformer Component

### Purpose

Passive voltage transformation between buses.

### Additional Parameters

* tap_ratio
* tap_position
* phase_shift

Other parameters and outputs mirror those of **Line**.

---

## 10. Link Component

### Purpose

Controllable power flow and **multi-port energy conversion**, enabling sector coupling.

### Capacity Parameters

| Parameter        | Unit | Description       |
| ---------------- | ---- | ----------------- |
| p_nom            | MW   | Power capacity    |
| p_nom_extendable | –    | Enables expansion |

### Operational Parameters

| Parameter                | Unit | Description                  |
| ------------------------ | ---- | ---------------------------- |
| p_min_pu / p_max_pu      | –    | Dispatch bounds              |
| efficiency, efficiency2… | –    | Port conversion efficiencies |
| p_set                    | MW   | Fixed dispatch               |

### Outputs

* p0, p1, p2, … (MW)
* status (if committable)

---

## 11. ShuntImpedance Component

### Purpose

Reactive power compensation at a bus.

### Parameters

| Parameter | Unit | Description |
| --------- | ---- | ----------- |
| g         | S    | Conductance |
| b         | S    | Susceptance |

### Outputs

* p (MW)
* q (MVAr)

---

## 12. Carrier Component

### Purpose

Defines energy carriers and technology attributes.

### Key Parameters

| Parameter     | Unit      | Description      |
| ------------- | --------- | ---------------- |
| name          | –         | Carrier name     |
| co2_emissions | tCO₂/MWh  | Emissions factor |
| max_growth    | MW/period | Growth limit     |
| max_capacity  | MW        | Capacity cap     |

---

## 13. LineType and TransformerType

### Purpose

Standardized parameter definitions.

**LineType**:

* r_per_length, x_per_length, g_per_length, b_per_length
* i_nom

**TransformerType**:

* s_nom, r, x, g, b

---

## 14. GlobalConstraint Component

### Purpose

Imposes system-wide constraints.

### Parameters

| Parameter         | Description            |
| ----------------- | ---------------------- |
| type              | Constraint category    |
| carrier_attribute | Attribute to constrain |
| sense             | <=, >=, ==             |
| constant          | Constraint value       |

---

## 15. Time Representation

* Time modeled via **snapshots**
* Snapshot weightings convert MW to MWh in objectives
* Dynamic parameters stored as time series per component

---

## 16. Optimization Constraints

### Categories

* Capacity constraints
* Dispatch limits
* Storage state-of-charge dynamics
* Network (KCL, KVL)
* Unit commitment
* Global constraints (emissions, growth)

---

## 17. Multi-Period Investment Optimization

* Explicit investment periods
* build_year and lifetime tracking
* Automatic retirement
* Perfect foresight pathway optimization

---

## 18. Units Summary

| Quantity        | Unit     |
| --------------- | -------- |
| Power           | MW       |
| Energy          | MWh      |
| Apparent Power  | MVA      |
| Voltage         | kV       |
| Cost (capacity) | €/MW     |
| Cost (energy)   | €/MWh    |
| Emissions       | tCO₂/MWh |

---

## 19. Mapping Guidance to OSeMOSYS

### Direct Mappings

* Bus → Region
* Carrier → Fuel / Commodity
* Generator → Technology
* Load → SpecifiedAnnualDemand

### Key Translation Challenges

* Snapshots vs Timeslices
* MW/MWh vs PJ/year
* Marginal vs Variable cost
* Availability vs CapacityFactor
* Storage formulations
* Multi-port Links

---

## 20. PyPSA Features Not Translated to OSeMOSYS

This section documents PyPSA components, parameters, and features that **will not be translated** to OSeMOSYS in the pyoscomp framework. These exclusions reflect fundamental differences in model formulations and scope rather than implementation gaps.

### Reactive Power (q) Modeling

**PyPSA Features Excluded**:
- Reactive power variables `q` for all components (Generator, Load, Line, Transformer)
- Reactive power constraints and balance equations
- Voltage magnitude `v_mag_pu` and angle `v_ang` variables
- Power factor constraints
- Reactive power compensation (ShuntImpedance components)

**Rationale**: OSeMOSYS is an **active power and energy balance model** focused on long-term capacity expansion and energy dispatch. It does not include:
- Voltage level modeling
- Reactive power balance equations
- Power factor or VAR requirements
- Network stability constraints

PyPSA's reactive power features are essential for **AC power flow analysis**, **voltage stability studies**, and **short-term operational planning**. These are outside OSeMOSYS's scope, which abstracts away electrical network physics in favor of commodity flow representation.

**Translation Approach**: All reactive power parameters and constraints are **ignored**. Only active power `p` is translated to OSeMOSYS activity/energy variables.

**User Guidance**: If reactive power analysis is required, use PyPSA directly for operational studies. OSeMOSYS translation is appropriate for long-term strategic planning where reactive power details are not critical.

### AC/DC Network Flow Constraints

**PyPSA Features Excluded**:
- Kirchhoff's Voltage Law (KVL) and Current Law (KCL) constraints
- Line impedance (r, x) and admittance modeling
- AC power flow equations (P = V²/Z, reactive power flow)
- DC power flow linearization constraints
- Voltage angle differences across lines
- Line thermal limits based on impedance and voltage

**Rationale**: PyPSA models **explicit network topology** with lines, transformers, buses, and power flow equations. OSeMOSYS uses **regional commodity flow model** where:
- REGION entities represent aggregated geographic areas (not individual buses)
- TradeRoute represents inter-regional energy transfer (not physical lines)
- Energy balance constraints enforce supply-demand matching (not Kirchhoff's laws)
- No impedance, voltage, or power flow physics

Translating PyPSA's network model to OSeMOSYS requires **aggregating buses to regions** and **abstracting away network physics**. Detailed network constraints (impedance limits, voltage stability) cannot be preserved.

**Translation Approach**: 
- **Single-region**: All PyPSA buses aggregate to one OSeMOSYS REGION. Intra-regional network (Lines, Transformers) is abstracted away entirely.
- **Multi-region**: User specifies bus→region mapping. Lines connecting different regions map to TradeRoute with capacity limits, but impedance and voltage constraints are lost.

**User Guidance**: Use OSeMOSYS translation for **generation expansion** and **energy adequacy** studies where network physics are secondary. For **transmission expansion**, **congestion analysis**, or **voltage stability**, use PyPSA's native network optimization.

### Unit Commitment Features

**PyPSA Features Excluded**:
- Binary commitment status variables `status` (on/off)
- Minimum up time constraints `min_up_time`
- Minimum down time constraints `min_down_time`
- Start-up costs `start_up_cost`
- Shut-down costs `shut_down_cost`
- Ramp rate limits `ramp_limit_up`, `ramp_limit_down`
- Committable flag for generators `committable`

**Rationale**: Unit commitment (UC) optimizes **discrete on/off decisions** for generators with:
- Integer variables (binary status)
- Temporal coupling constraints (min up/down times)
- Non-convex costs (start-up/shut-down)
- Ramp rate limitations

OSeMOSYS is a **linear programming (LP) model** with:
- Continuous dispatch variables (no binary status)
- No explicit temporal coupling beyond storage dynamics
- Linear cost structure (no start-up costs)
- Limited ramp rate support

While OSeMOSYS can model **capacity reserves** and **peaking vs baseload** through CapacityFactor constraints, it **cannot represent true unit commitment** with minimum run times and start costs.

**Translation Approach**: Unit commitment features are **ignored**. PyPSA generators with `committable=True` translate as standard technologies with:
- Capacity constraints from `p_nom`
- Availability from `p_max_pu` (aggregated to CapacityFactor)
- Variable costs from `marginal_cost` (start-up costs omitted)

**Impact on Results**: OSeMOSYS dispatch will be **more flexible** than PyPSA UC results. Technologies can ramp instantly, operate at any level within p_min_pu to p_max_pu, and incur no start-up penalties. This is acceptable for **long-term planning** (multi-year, 5-year time steps) but inappropriate for **hourly operational modeling**.

**User Guidance**: Unit commitment features are critical for **short-term dispatch** and **operational feasibility**. OSeMOSYS translation is appropriate for:
- Multi-year capacity expansion (2020-2050)
- Strategic technology mix decisions
- Long-term energy adequacy

For operational studies requiring UC constraints, use PyPSA's native unit commitment optimization.

### Network Impedance and Voltage Constraints

**PyPSA Features Excluded**:
- Line resistance `r` and reactance `x`
- Line conductance `g` and susceptance `b`
- Line type parameters (r_per_length, x_per_length)
- Transformer impedance parameters
- Voltage magnitude limits `v_mag_pu_min`, `v_mag_pu_max`
- Voltage nominal values `v_nom`

**Rationale**: These parameters define **electrical properties** of transmission network for AC/DC power flow calculations. OSeMOSYS does not model network impedance or voltage levels, focusing instead on **energy commodity flow** between regions.

**Translation Approach**: All impedance and voltage parameters are **ignored**. OSeMOSYS represents energy transfer via TradeRoute (if multi-region) with simple capacity limits, not impedance-based flow equations.

**User Guidance**: Impedance and voltage are critical for **transmission planning**, **reactive power management**, and **voltage stability**. Use PyPSA for these analyses. OSeMOSYS is appropriate for **generation adequacy** where transmission constraints are secondary or can be approximated by inter-regional transfer limits.

### Transformer Operational Parameters

**PyPSA Features Excluded**:
- Tap ratio `tap_ratio`
- Tap position `tap_position`
- Phase shift `phase_shift`
- Transformer type specifications

**Rationale**: Transformers in PyPSA model **voltage level changes** and **phase shifting** for power flow control. OSeMOSYS does not distinguish voltage levels, making transformer parameters irrelevant.

**Translation Approach**: Transformers are **ignored** unless they define regional boundaries (similar to Lines). Intra-regional transformers are abstracted away.

### ShuntImpedance Components

**PyPSA Features Excluded**:
- Shunt conductance `g`
- Shunt susceptance `b`
- Reactive power compensation devices

**Rationale**: ShuntImpedance components provide **reactive power compensation** for voltage control. OSeMOSYS does not model reactive power, making shunts irrelevant.

**Translation Approach**: ShuntImpedance components are **completely ignored**.

### Flexible Snapshot Weightings

**PyPSA Features Excluded**:
- Multi-category snapshot weightings (objective, store, generator)
- Snapshot-specific weightings for different cost/balance equations
- Non-uniform temporal weighting strategies

**Rationale**: PyPSA allows **different weightings** for:
1. **objective**: Weight in cost minimization objective
2. **store**: Weight for storage state-of-charge dynamics
3. **generator**: Weight for global constraints and energy totals

This flexibility enables scenarios like "optimize for representative week but scale to annual" or "weight peak periods more heavily in objective".

OSeMOSYS uses **single temporal weighting** via YearSplit, which uniformly weights all constraints and objectives. You cannot have different weights for costs vs energy balance.

**Translation Approach**: PyPSA snapshot weightings translate to OSeMOSYS YearSplit using **objective weightings** as primary. Store and generator weightings are **not separately represented**, potentially causing discrepancies if PyPSA model uses different weighting categories strategically.

**Impact on Results**: If PyPSA model uses uniform weightings across all categories, translation is accurate. If PyPSA uses differentiated weightings (e.g., store weightings differ from objective), OSeMOSYS results may diverge because single YearSplit cannot capture this nuance.

**User Guidance**: Check PyPSA snapshot_weightings. If all three categories (objective, store, generator) are identical, translation is direct. If they differ significantly, consult with pyoscomp developers about handling strategy or manually adjust OSeMOSYS YearSplit.

### Carrier-Specific Advanced Features

**PyPSA Features Excluded**:
- Carrier emissions factors `co2_emissions` (partially translated in future)
- Carrier colors and visual attributes (metadata only)
- Carrier-specific growth limits `max_growth` (partially translatable)
- Carrier-specific capacity limits `max_capacity` (partially translatable)

**Rationale**: Some carrier attributes are **metadata** (colors) or **policy constraints** (emissions, growth limits) that require explicit constraint implementation in OSeMOSYS. Phase 1 focuses on **energy balance and capacity optimization fundamentals**.

**Translation Approach**:
- **Emissions**: Planned for Phase 2 enhancement (map to EmissionActivityRatio, EmissionsPenalty)
- **Growth/capacity limits**: Translatable to OSeMOSYS TotalAnnualMaxCapacity or global constraints if needed
- **Visual metadata**: Ignored (not relevant to optimization)

### GlobalConstraint Advanced Features

**PyPSA Features Excluded** (beyond basic constraints):
- Stochastic programming constraints
- Multi-scenario constraints
- Custom user-defined constraint functions

**Rationale**: OSeMOSYS has **predefined constraint structure** (emissions limits, RE targets, capacity bounds). PyPSA's GlobalConstraint mechanism allows **arbitrary linear constraints** on network variables. Full generality cannot be translated without custom OSeMOSYS constraint implementation.

**Translation Approach**: Common constraints (emissions cap, RE target, capacity limit) are translatable to OSeMOSYS equivalents. Exotic or stochastic constraints require **manual OSeMOSYS model modification** post-translation.

### Investment Period Weightings

**PyPSA Features Excluded**:
- Investment period objective weightings
- Investment period "years" elapsed time specification

**Rationale**: PyPSA supports **multi-period investment optimization** with explicit investment periods and weightings. OSeMOSYS uses **YEAR set** with implicit single-year or multi-year periods depending on time step choice (annual vs 5-year).

**Translation Approach**: PyPSA investment periods map to OSeMOSYS YEAR set entries. Investment weightings are **approximated** via DiscountRate and year spacing, but full control over investment period objective weights is not preserved.

**User Guidance**: OSeMOSYS discounting via DiscountRate provides similar inter-temporal weighting. Ensure PyPSA investment period structure aligns with OSeMOSYS YEAR definition for consistent temporal resolution.

### Translation Philosophy

**Focus on Energy Balance**: pyoscomp translates PyPSA's **energy system capacity and dispatch optimization** to OSeMOSYS's **commodity flow and capacity expansion framework**. Network physics, reactive power, unit commitment, and detailed operational constraints are intentionally excluded to maintain focus on long-term strategic planning.

**Use Case Alignment**: Translation is appropriate for:
- Multi-year/multi-decade capacity expansion
- Technology mix and investment decisions
- Energy adequacy and resource planning
- Sector coupling at strategic level (hydrogen, heat, electricity)

**PyPSA Retains Advantages For**:
- Hourly operational dispatch with unit commitment
- Transmission network expansion and congestion analysis
- Voltage stability and reactive power management
- AC/DC power flow optimization
- Short-term (day-ahead, real-time) market modeling

**OSeMOSYS Retains Advantages For**:
- Transparent, auditable linear programming formulation
- Explicit parameter control (all inputs via CSV files)
- Long-term least-cost optimization with simple setup
- Broad accessibility (no Python/programming required)
- Established use in developing country energy planning

**Interoperability Vision**: pyoscomp enables **PyPSA→OSeMOSYS translation** for users wanting:
1. PyPSA's network modeling and data integration capabilities
2. OSeMOSYS's transparent formulation for peer review/validation
3. Comparison of results between frameworks for robustness checking
4. OSeMOSYS compatibility for stakeholders requiring specific formulation

By clearly documenting what is **not translated**, users can make informed decisions about when translation is appropriate and when native PyPSA or OSeMOSYS is more suitable.