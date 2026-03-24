# Scenario Components

Scenario components are the mutable authoring layer that writes OSeMOSYS-style
CSV inputs. All components inherit `ScenarioComponent` and follow a common
`load()`/`validate()`/`process()`/`save()` lifecycle.

## Related READMEs

- [Package Overview](../../README.md)
- [Scenario Module](../README.md)
- [Scenario Validation](../validation/README.md)
- [Interfaces Module](../../interfaces/README.md)
- [Translation Module](../../translation/README.md)
- [Time Translation Submodule](../../translation/time/README.md)
- [Runners Module](../../runners/README.md)

## Ownership and Dependencies

| Component | Owns | Requires Before Init | Notes |
|---|---|---|---|
| `TopologyComponent` | `REGION.csv` | none | Defines spatial nodes |
| `TimeComponent` | `YEAR`, `TIMESLICE`, `SEASON`, `DAYTYPE`, `DAILYTIMEBRACKET`, `YearSplit`, `DaySplit`, conversions | none | Defines temporal hierarchy and fractions |
| `SupplyComponent` | `TECHNOLOGY`, `FUEL`, `MODE_OF_OPERATION`, `OperationalLife`, `ResidualCapacity` | topology + time files | Defines what exists |
| `DemandComponent` | `SpecifiedAnnualDemand`, `SpecifiedDemandProfile`, `AccumulatedAnnualDemand` | topology + time files | Defines demand volume and profile |
| `PerformanceComponent` | activity ratios, factors, capacity limits | topology + time + supply files | Defines how technologies operate |
| `EconomicsComponent` | `DiscountRate`, `CapitalCost`, `FixedCost`, `VariableCost` | topology + time files | Defines economic assumptions |
| `StorageComponent` | storage linkage and costs | topology + time files | Implemented and integrated in translators |
| `TradeComponent` | trade parameters | stub | Not implemented yet |

Key boundary: Supply defines WHAT technologies/fuels/modes exist. Performance
defines HOW those technologies behave.

## Lifecycle Pattern

1. Instantiate component with `scenario_dir`.
2. Populate via `add_*` / `set_*` methods.
3. Run `process()` when required (`DemandComponent`, `PerformanceComponent`).
4. Optionally run `validate()`.
5. Persist with `save()`.

## Example (Complete One-Region Setup)

```python
from pyoscomp.scenario.components import (
    TopologyComponent,
    TimeComponent,
    SupplyComponent,
    DemandComponent,
    PerformanceComponent,
    EconomicsComponent,
    StorageComponent,
)

scenario_dir = "path/to/scenario"

top = TopologyComponent(scenario_dir)
top.add_nodes(["R1"])
top.save()

time = TimeComponent(scenario_dir)
time.add_time_structure(
    years=[2025],
    seasons={"ALLSEASONS": 365},
    daytypes={"ALLDAYS": 1},
    brackets={"ALLTIMES": 24},
)
time.save()

supply = SupplyComponent(scenario_dir)
supply.add_technology("R1", "GAS_CCGT").with_operational_life(30).as_conversion(
    input_fuel="GAS", output_fuel="ELEC"
)
supply.save()

demand = DemandComponent(scenario_dir)
demand.add_annual_demand("R1", "ELEC", {2025: 100.0})
demand.set_profile("R1", "ELEC", timeslice_weights={"ALLSEASONS_ALLDAYS_ALLTIMES": 1.0})
demand.process()
demand.save()

performance = PerformanceComponent(scenario_dir)
performance.set_efficiency("R1", "GAS_CCGT", 0.5)
performance.set_capacity_factor("R1", "GAS_CCGT", 1.0)
performance.set_availability_factor("R1", "GAS_CCGT", 1.0)
performance.process()
performance.save()

economics = EconomicsComponent(scenario_dir)
economics.set_discount_rate("R1", 0.05)
economics.set_capital_cost("R1", "GAS_CCGT", {2025: 500.0})
economics.set_fixed_cost("R1", "GAS_CCGT", 10.0)
economics.set_variable_cost("R1", "GAS_CCGT", "MODE1", 2.0)
economics.save()

storage = StorageComponent(scenario_dir)
storage.add_storage("R1", "BATT").with_operational_life(15).with_energy_ratio(4.0)
storage.save()
```

## Interpolation Behavior

Several components accept trajectories and interpolation:

- `step`: holds last known value.
- `linear`: interpolates between known points.
- `cagr`: available in demand for growth-style trajectories.

## Common Edge Cases

- `SupplyComponent`, `DemandComponent`, `PerformanceComponent`, and
  `EconomicsComponent` require prerequisite files to exist first.
- `PerformanceComponent` looks up fuel/mode mappings from supply output; if supply
  has not been saved, efficiency setup can fail.
- `DemandComponent.set_profile()` requires `(region, fuel)` to already exist via
  `add_annual_demand()`.
- Storage links (`TechnologyToStorage` / `TechnologyFromStorage`) are not a full
  substitute for a complete trade or network transport model.

## Suggested Improvements

- Add stricter cross-checks between `StorageComponent` links and supply technology
  existence.
- Implement `TradeComponent` with full CSV ownership and validation.
- Add richer defaults/reporting for missing profile assignments.
- Add component-level summary methods for easier debugging and notebook display.