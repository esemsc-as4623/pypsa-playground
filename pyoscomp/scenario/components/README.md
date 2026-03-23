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
├── scenario/
│   ├── components/
│   │   ├── base.py         # Shared schema IO, merge utilities, prerequisites
│   │   ├── topology.py     # REGION definition
│   │   ├── time.py         # YEAR/TIMESLICE hierarchy and time mappings
│   │   ├── demand.py       # Annual and profile demand
│   │   ├── supply.py       # TECHNOLOGY/FUEL/MODE registry and supply metadata
│   │   ├── performance.py  # Efficiency, factors, capacity limits
│   │   ├── economics.py    # Discount and cost trajectories
│   │   ├── storage.py      # Reserved for future storage authoring component
│   │   ├── trade.py        # Reserved for future trade authoring component
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

## Practical Notes

- Prefer replacing records through repeated set/add calls rather than direct
    DataFrame mutation.
- Use interpolation methods intentionally:
    step for policy-style trajectories, linear for smooth transitions.
- TimeComponent normalization preserves relative weights even when seasonal
    day counts or bracket hours do not match calendar totals exactly.
- Performance and Demand process() fill defaults where needed; call it before
    save() when you used assignment-style methods.

## Testing Pointers

- Validate each component immediately after setup during development.
- Add tests per component in tests/test_scenario to keep ownership clear.
- Prefer assertions on output CSV semantics
    (uniqueness keys, sums to 1.0, non-negative bounds).