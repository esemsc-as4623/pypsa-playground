## Sub-directory Structure

pyoscomp/
│
├── scenarios_master_list.csv    # Tracking file
├── osemosys_config.yaml         # Config file
│
└── scenario/
    ├── __init__.py
    ├── manager.py               # Handles UUIDs, loading, saving, directory creation
    ├── core.py                  # The main 'Scenario' class that holds components
    │
    ├── components/              # Sub-directory for modular logic
    │   ├── __init__.py
    │   ├── base.py              # Abstract Base Class for all components
    │   ├── time.py              # Logic for horizons and time steps
    │   ├── topology.py          # Logic for nodes (regions)
    │   ├── demand.py            # Logic for demand
    │   ├── supply.py            # Logic for supply
    |   ├── economics.py         # Logic for economics / cost / investment
    |   └── performance.py       # Logic for energy type performance
    │
    └── rules/                   # Polymorphic rules for calculation
        ├── __init__.py
        ├── base_rule.py
        └── functions.py         # Specific math rules (Linear, Exponential, etc.)

## Code Improvements

[] OS-agnostic path handling
    - use `os.path.join(self.scenario_dir, filename)`
[] Modularize prerequisite checks
    - each component class has its own prerequisite check as static method
    - use this to check prerequisite files for all components with dependencies
[] Modularize input validation checks in base.py or elsewhere to minimize repeated code?
    - establish basic rules, e.g. data type, non-negative, etc that are used commonly
    - add specific input validation checks within relevant functions
[] Put functions and interpolations in `scenario/rules`
[] Add extrapolation for before first trajectory point and after last trajectory point
[] Enum + error handling to enforce valid choices
[] Dataclasses or NamedTuples
    - to store profile configuration