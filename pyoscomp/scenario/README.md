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
[] Enum + error handling to enforce valid choices
[] Dataclasses or NamedTuples
    - to store profile configuration
[] Case sensitive matching
    - season, daytype, dailytimebracket
    - validate keys during `process` phase