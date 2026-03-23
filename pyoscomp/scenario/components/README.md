Scenario components are the mutable authoring layer for building an OSeMOSYS-style scenario in CSV form. Each component owns a distinct subset of files and writes validated DataFrames through the shared base class.

Component output is consumed by:
- interfaces layer (immutable transfer objects)
- runners/translators (PyPSA and OSeMOSYS execution paths)

## Design Intent

- Use one component per concern, with clear file ownership.
- Keep scenario assembly explicit and incremental.
- Use load/process/save lifecycle consistently.
- Let ScenarioComponent handle shared CSV/schema mechanics.

## Module Structure

```
pyoscomp/
    scenario/
        components/
            base.py         # Shared schema IO, merge utilities, prerequisites
            topology.py     # REGION definition
            time.py         # YEAR/TIMESLICE hierarchy and time mappings
            demand.py       # Annual and profile demand
            supply.py       # TECHNOLOGY/FUEL/MODE registry and supply metadata
            performance.py  # Efficiency, factors, capacity limits
            economics.py    # Discount and cost trajectories
            storage.py      # Reserved for future storage authoring component
            trade.py        # Reserved for future trade authoring component
```

## Recommended Initialization Order

Instantiate and populate components in dependency order:

1. TopologyComponent
2. TimeComponent
3. SupplyComponent
4. DemandComponent
5. PerformanceComponent
6. EconomicsComponent

Why this order:
- REGION is required by most downstream parameters.
- YEAR and TIMESLICE are required for demand and performance profiles.
- Supply writes technology and mode registries used by performance.

## Ownership Boundaries

Follow these boundaries to avoid duplicated writes and conflicting values.

- TopologyComponent owns REGION set only.
- TimeComponent owns YEAR/TIMESLICE hierarchy and time conversion tables.
- SupplyComponent owns technology existence and fuel/mode assignments.
- PerformanceComponent owns how technologies operate
    (ratios, factors, limits).
- DemandComponent owns demand volume/profile parameters.
- EconomicsComponent owns discount and cost parameters.

Key rule:
Supply answers WHAT exists. Performance answers HOW it behaves.

## Lifecycle Pattern

For each component:

1. Construct component with scenario directory.
2. Add or set values with component methods.
3. Call process() where available (Demand, Performance).
4. Optionally call validate() for early checks.
5. Call save() to write schema-validated CSV files.

If editing an existing scenario, call load() first, then mutate, then save().

## Minimal End-to-End Example

```python
from pyoscomp.scenario.components import (
        TopologyComponent,
        TimeComponent,
        SupplyComponent,
        DemandComponent,
        PerformanceComponent,
        EconomicsComponent,
)

scenario_dir = "path/to/scenario"

# 1) Topology
topology = TopologyComponent(scenario_dir)
topology.add_nodes(["R1", "R2"])
topology.save()

# 2) Time
time = TimeComponent(scenario_dir)
time.add_time_structure(
        years=[2026, 2027, 2028],
        seasons={"Winter": 90, "Summer": 90, "Shoulder": 185},
        daytypes={"Weekday": 5, "Weekend": 2},
        brackets={"Day": 16, "Night": 8},
)
time.save()

# 3) Supply
supply = SupplyComponent(scenario_dir)
supply.add_technology("R1", "GAS_CCGT") \
        .with_operational_life(30) \
        .as_conversion(input_fuel="GAS", output_fuel="ELEC")
supply.save()

# 4) Demand
demand = DemandComponent(scenario_dir)
demand.add_annual_demand(
        region="R1",
        fuel="ELEC",
        trajectory={2026: 100.0, 2028: 120.0},
        interpolation="linear",
)
demand.process()
demand.save()

# 5) Performance
performance = PerformanceComponent(scenario_dir)
performance.set_efficiency("R1", "GAS_CCGT", 0.55)
performance.set_capacity_factor("R1", "GAS_CCGT", 0.90)
performance.process()
performance.save()

# 6) Economics
economics = EconomicsComponent(scenario_dir)
economics.set_discount_rate("R1", 0.05)
economics.set_capital_cost("R1", "GAS_CCGT", {2026: 700, 2028: 650})
economics.save()
```

## Interpolation Methods

Components support multiple interpolation methods for trajectory data (year-dependent parameters). Choose based on your use case:

### Interpolation Method Comparison

| Method | Behavior | Use Case | Example |
|--------|----------|----------|---------|
| **'step'** | Constant value between points (backward-fill) | Policy-style transitions, technology deployments | Mandate coal phase-out in 2030: `{2025: 100, 2030: 0}` → step |
| **'linear'** | Linear interpolation between points | Smooth cost reductions, gradual capacity ramps | Solar cost decline: `{2020: 200, 2030: 50}` → linear |
| **'cagr'** | Compound Annual Growth Rate between points | Exponential processes (efficiency gains, demand growth) | Battery cost CAGR -15%: `{2020: 100, 2030: 20.6}` → cagr |

### How Each Method Works

**Step Interpolation**:
```python
trajectory = {2025: 100, 2030: 110}
# Years 2025-2029 → 100, Year 2030+ → 110
```

**Linear Interpolation**:
```python
trajectory = {2025: 100, 2030: 110}
# 2026 → 102, 2027 → 104, 2028 → 106, 2029 → 108, 2030 → 110
```

**CAGR (Compound Annual Growth Rate)**:
```python
trajectory = {2025: 100, 2030: 121.55}  # ≈4% annual growth
# 2026 → 104.0, 2027 → 108.2, 2028 → 112.6, 2029 → 117.2, 2030 → 121.55
# Forward: 2031 → 126.5 (continues 4% rate)
```

### Boundaries Outside Trajectory

- **Before first year**: Uses first point value
- **After last year**: Depends on method
  - 'step': Uses last point value
  - 'linear' or 'cagr': Extrapolates using trend from last two points

## Practical Notes

- Prefer replacing records through repeated set/add calls rather than direct
    DataFrame mutation.
- Choose interpolation intentionally:
    - 'step' for policy mandates and step-change events
    - 'linear' for smooth cost or parameter transitions
    - 'cagr' for technology cost curves and growth processes
- TimeComponent normalization preserves relative weights even when seasonal
    day counts or bracket hours do not match calendar totals exactly.
- Always call `process()` on Demand and Performance before `save()`.
- When setting profiles (demand or performance), ensure weights/factors are reasonable;
    process() normalizes but cannot fix fundamentally broken inputs.

## Profile Setup Guide

Both Demand and Performance components support sub-annual profiles (how volume/capacity is distributed across timeslices).

### Demand Profiles

Set how demand is distributed across timeslices:

```python
demand = DemandComponent(scenario_dir)
demand.add_annual_demand("R1", "ELEC", {2026: 100.0})  # 100 units total

# Option 1: Direct timeslice weights
# Specify exact weight for each timeslice
demand.set_profile(
    region="R1",
    fuel="ELEC",
    weights={
        "DayType1_DailyBracket1": 0.2,
        "DayType1_DailyBracket2": 0.3,
        "DayType2_DailyBracket1": 0.3,
        "DayType2_DailyBracket2": 0.2,
    },
    year=2026
)

# Option 2: Hierarchical (season/daytype/bracket)
# Specify weights at coarser granularity; auto-expands to timeslices
demand.set_profile(
    region="R1",
    fuel="ELEC",
    season_weights={"Season1": 0.5, "Season2": 0.5},
    daytype_weights={"Weekday": 0.7, "Weekend": 0.3},
    bracket_weights={"Day": 0.7, "Night": 0.3},
    year=2026
)

demand.process()  # Normalize and generate SpecifiedDemandProfile
demand.save()
```

### Performance Profiles (Capacity Factor)

Set sub-annual capacity availability:

```python
performance = PerformanceComponent(scenario_dir)

# Option 1: Single annual capacity factor (uniform across timeslices)
performance.set_capacity_factor("R1", "SOLAR_PV", 0.25)

# Option 2: Time-varying capacity factor
performance.set_capacity_factor(
    "R1", "SOLAR_PV",
    factor={2026: 0.22, 2030: 0.25},  # Improves with time
    interpolation="linear"
)

# Option 3: Sub-annual profile (e.g., hourly variation)
performance.set_capacity_factor(
    "R1", "SOLAR_PV",
    timeslice_weights={
        "DayType1_DailyBracket_Day": 0.8,      # High during day
        "DayType1_DailyBracket_Night": 0.0,    # Zero at night
        ...
    }
)

performance.process()  # Normalize profiles
performance.save()
```

## Troubleshooting

### "ImportError: cannot import name..." on component use

**Cause**: Component not initialized yet or prerequisite not satisfied.

**Solution**: Ensure components are initialized in dependency order (see Recommended Initialization Order). Components check prerequisites and raise clear errors if missing.

```python
# WRONG: Performance used before Supply is saved
performance.set_efficiency("R1", "TECH1", 0.9)  # Raises error

# CORRECT: Supply must be saved first
supply.add_technology("R1", "TECH1").as_conversion(...)
supply.save()  # Writes TECHNOLOGY.csv
performance.set_efficiency("R1", "TECH1", 0.9)  # Works
```

### "Profiles do not sum to 1.0" after save

**Cause**: Forgot to call `process()` before `save()` on Demand or Performance.

**Solution**: Always call `process()` on components with profile methods:

```python
demand.add_annual_demand(...)
demand.set_profile(...)
demand.process()      # REQUIRED: Normalizes and generates SpecifiedDemandProfile
demand.save()
```

### "KeyError: TECHNOLOGY not in records"

**Cause**: Trying to set performance/cost for a technology that doesn't exist in Supply.

**Solution**: Add technology to Supply first:

```python
# WRONG: Performance references non-existent tech
performance.set_efficiency("R1", "UNKNOWN_TECH", 0.9)

# CORRECT: Create tech in supply first
supply.add_technology("R1", "UNKNOWN_TECH").as_conversion(...)
supply.save()
performance.set_efficiency("R1", "UNKNOWN_TECH", 0.9)
```

### Profile weights are negative or sum to >1.0

**Cause**: Invalid profile specification (typo, logic error).

**Solution**: 
1. Check that weights/factors are in valid range:
   - Capacity/Availability Factors: [0.0, 1.0]
   - Demand/Capacity weights: [0.0, ∞) (will normalize if >1.0)
2. Verify timeslice names match those from TimeComponent
3. Use `set_profile()` consistently (don't mix option 1 and 2)

```python
# Verify timeslice names exist
time = TimeComponent(scenario_dir)
time.load()
print(time.timeslices)  # See valid timeslice names

# Then use exact names in set_profile
demand.set_profile(
    region="R1", fuel="ELEC",
    weights={"ValidTimeslice1": 0.5, "ValidTimeslice2": 0.5}
)
```

## Testing Pointers

- Validate each component immediately after setup during development.
- Add tests per component in tests/test_scenario to keep ownership clear.
- Prefer assertions on output CSV semantics
    (uniqueness keys, sums to 1.0, non-negative bounds).
- Use `component.validate()` before `component.save()` to catch errors early.

## Testing Pointers