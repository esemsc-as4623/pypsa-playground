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
    │   └── supply.py            # Logic for supply
    │
    └── rules/                   # Polymorphic rules for calculation
        ├── __init__.py
        ├── base_rule.py
        └── functions.py         # Specific math rules (Linear, Exponential, etc.)

## Code Improvements
[x] Consolidate I/O logic
    - `ScenarioComponent` has `write_csv` for lists; `TimeComponent` has `_write_df` for dataframes
    - move `_write_df` into `ScenarioComponent` base class, rename to `write_dataframe` to prevent code duplication and to ensure all components handle file writing and potential permissions errors identically
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