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
    |   ├── economics.py         # Logic for economics / investment
    |   └── performance.py       # Logic for energy type performance
    │
    └── rules/                   # Polymorphic rules for calculation
        ├── __init__.py
        ├── base_rule.py
        └── functions.py         # Specific math rules (Linear, Exponential, etc.)

## Code Improvements

[] OS-agnostic path handling
    - use `os.path.join(self.scenario_dir, filename)`
[] Deterministic ordering
    - reduce reliance on Python dictionary built-in preservation of insertion order
    - sort keys in `process_time_structure` before iterating (`s_fracs = dict(sorted(self._normalize(seasons).items()))`)
[] Name sanitization
    - user can provide names with space or comma
    - add validator in base component to ensure names are alphanumeric or underscores only
[] Precision handling
    - add validation step at the end of `process_time_structure` to assert that for every year, the sum of `YearSplit` = 1.0 with small epsilon
[] Enum + error handling to enforce valid choices
[] Duplication handling
    - ensure `self.annual_demand_data` does not accept duplicate rows from user input
[x] Profile summation
    - add validation to assert sum of demand profile over region, fuel, year = 1.0
    - if not, distribute residual error across slices to ensure perfect 1.0 sum
[x] CAGR edge cases
    - add assertions to ensure demand >= 0 in user input
[] Dataclasses or NamedTuples
    - to store profile configuration
[x] Decouple logic from I/O
    - `process` method in `DemandComponent` performs both calculation and I/O
    - create `calculate_profile_fractions` so that `process` only performs I/O
[] Define constants at the top of the class
    - for each column (e.g. REGION, TIMESLICE, YEAR, etc.)
[] Case sensitive matching
    - season, daytype, dailytimebracket
    - validate keys during `process` phase
[] Trend function
    - accept (year, prev_value) for recursive / compound logic
