# PyOSComp Critical Review & Task List

*Generated: February 2026*

This document provides a comprehensive critical review of the `pyoscomp` package, identifying design flaws, inconsistencies, and missing functionality. Tasks are prioritized based on the philosophy of **starting small, verifying repeatedly, then growing complexity**.

---

## Table of Contents
1. [Critical Design Issues](#critical-design-issues)
2. [Prioritized Task List](#prioritized-task-list)
3. [Detailed Analysis by Module](#detailed-analysis-by-module)

---

## Critical Design Issues

### 1. **Architecture & Coupling Problems**

#### 1.1 Scenario/Translation Disconnect
The `scenario/` module and `translation/` module operate independently without a clear integration point. The scenario components build OSeMOSYS CSV files directly, but the translation layer (`translation/pypsa_translator.py`) expects a generic `input_data: Dict[str, pd.DataFrame]` format. There is no clear path from:
```
Scenario.build() → Translator.translate() → Runner.run()
```

**Fix:** Define a clear `ScenarioData` interface that both scenario building and translation consume.

#### 1.2 Missing Economics and Performance Components
- [economics.py](pyoscomp/scenario/components/economics.py) - **EMPTY**
- [performance.py](pyoscomp/scenario/components/performance.py) - **EMPTY**

These are core to `simple.ipynb` (capital_costs, variable_costs, discount_rate, efficiency) but have no implementation.

#### 1.3 Component Dependencies Not Enforced
Components claim prerequisites (e.g., `demand.py` requires Time and Topology) but:
- No formal dependency injection or ordering mechanism
- `Scenario.build()` doesn't validate component readiness
- Circular import pattern: `DemandComponent` imports `TimeComponent` at runtime

### 2. **Data Validation & Consistency**

#### 2.1 No Schema Validation
CSVs are written and read with ad-hoc column expectations. There's no formal schema definition that ensures:
- Required columns are present
- Data types are correct
- Foreign key relationships are valid (e.g., TECHNOLOGY in CapacityFactor must exist in TECHNOLOGY.csv)

#### 2.2 Inconsistent Error Handling
- Some methods use `raise ValueError`
- Some use `print(f"WARNING: ...")`
- Some silently return or continue

**Fix:** Establish a logging/error handling strategy with clear severity levels.

#### 2.3 Floating Point Tolerance Inconsistency
- `TimeComponent` uses `TOL = 1e-6` and `math.isclose()`
- No tolerance handling elsewhere
- Decimal arithmetic mixed with float arithmetic

### 3. **Testing & Reproducibility**

#### 3.1 Test Coverage Gaps
- `translation/time/` has comprehensive tests
- `scenario/components/` has **NO TESTS**
- `runners/` has **NO TESTS**
- No integration tests that run the full pipeline

#### 3.2 No Fixtures for Scenario Components
The test fixtures (`conftest.py`) only cover OSeMOSYS file structures, not the component API.

### 4. **API Design Issues**

#### 4.1 Mutable State Without Transaction Semantics
Components modify internal DataFrames incrementally via `add_to_dataframe()`, but:
- No rollback mechanism if validation fails mid-operation
- No atomic "build" that validates everything before writing
- `save()` can be called with partially-valid state

#### 4.2 Inconsistent Method Signatures
- `add_technology()` takes positional args, `set_conversion_technology()` uses keywords
- Some methods accept `year=None` meaning "all years", others require explicit list
- `trajectory: dict` vs `factor_dict: dict` naming inconsistency

#### 4.3 No Builder Pattern for Complex Objects
Setting up a technology requires multiple calls:
```python
supply.add_technology(...)
supply.set_conversion_technology(...)
supply.set_capacity_bounds(...)  # If it exists
supply.set_capacity_factor_profile(...)  # If it exists
```
Should be:
```python
supply.add_technology(...).with_conversion(...).with_bounds(...).build()
```

### 5. **Documentation Gaps**

#### 5.1 No End-to-End Example
- `simple.ipynb` shows raw OSeMOSYS/PyPSA usage, not pyoscomp usage
- No notebook demonstrating `ScenarioManager → Scenario → Translator → Runner` workflow

#### 5.2 Docstrings Incomplete
- Many methods have docstrings but lack `Raises:` section
- No type hints on many method signatures
- Example code in docstrings is untested and may be outdated

### 6. **Model Equivalence Issues**

#### 6.1 OSeMOSYS-PyPSA Semantic Gaps Not Documented
- OSeMOSYS `CapacityFactor` ≠ PyPSA `p_max_pu` (one is annual max, other is per-snapshot)
- OSeMOSYS `YearSplit` is year-agnostic fraction; PyPSA snapshots have explicit datetime
- No clear mapping documentation or validation of equivalent behavior

#### 6.2 Time Translation is Incomplete
- `translation/time/` has sophisticated structures but unclear integration with scenario building
- `Timeslice` class not connected to `TimeComponent.add_time_structure()`

---

## Prioritized Task List

### Priority 2: Validation & Robustness
*Goal: Prevent silent failures and catch errors early*

| ID | Task | Description | Files Affected |
|----|------|-------------|----------------|
| **P2.2** | Validate cross-component references | Ensure TECHNOLOGYs referenced in supply exist in TECHNOLOGY.csv, FUELs exist in FUEL.csv, etc. | `scenario/core.py`, `scenario/validation/` |
| **P2.3** | Standardize error handling | Replace all `print("WARNING")` with proper logging. Define when to warn vs raise. | All component files |
| **P2.4** | Add unit tests for scenario components | Test each component's `add_*`, `set_*`, `load()`, `save()` methods | `tests/test_scenario/test_*.py` |
| **P2.5** | Validate YearSplit/DaySplit sums to 1.0 | Add validation in TimeComponent that doesn't just warn but optionally raises | `scenario/components/time.py` |

### Priority 3: Translation Pipeline
*Goal: Reliable conversion between OSeMOSYS CSVs and PyPSA Network*

| ID | Task | Description | Files Affected |
|----|------|-------------|----------------|
| **P3.1** | Define ScenarioData interface | Create typed dataclass/protocol for scenario data that bridges scenario building and translation | New: `pyoscomp/interfaces.py` |
| **P3.2** | Fix PyPSAInputTranslator to use ScenarioData | Refactor to accept standardized interface, not raw dict | `translation/pypsa_translator.py` |
| **P3.3** | Implement OSeMOSYSInputTranslator properly | Currently a stub. Should convert ScenarioData to otoole-compatible format | `translation/osemosys_translator.py` |
| **P3.4** | Document time translation semantics | Explain how timeslices map to snapshots, edge cases, leap years | `docs/time_translation.md` |
| **P3.5** | Add integration test: same scenario → both models → compare results | Extend simple.ipynb pattern programmatically | `tests/test_integration/test_model_comparison.py` |

### Priority 4: Runner Infrastructure
*Goal: Executable end-to-end workflow*

| ID | Task | Description | Files Affected |
|----|------|-------------|----------------|
| **P4.1** | Test OSeMOSYSRunner with simple scenario | Ensure otoole conversion + glpsol execution works | `tests/test_runners/test_osemosys.py` |
| **P4.2** | Fix PyPSARunner to use translator output | Current implementation reads CSVs directly; should use PyPSAInputTranslator | `runners/pypsa.py` |
| **P4.3** | Add result extraction to runners | Standardized way to extract and return optimization results | `runners/*.py` |
| **P4.4** | Create unified run interface | `pyoscomp.run(scenario, model='osemosys')` entry point | `pyoscomp/__main__.py` or new CLI |

### Priority 5: API Ergonomics
*Goal: Intuitive, hard-to-misuse API*

| ID | Task | Description | Files Affected |
|----|------|-------------|----------------|
| **P5.1** | Add type hints to all public methods | Enable IDE support and static analysis | All files |
| **P5.2** | Implement builder pattern for technologies | Fluent API: `supply.technology("GAS_CCGT").with_efficiency(0.55).build()` | `scenario/components/supply.py` |
| **P5.3** | Add method chaining where appropriate | Return `self` from mutator methods to enable chaining | All component files |
| **P5.4** | Create scenario templates/presets | E.g., `Scenario.from_template("simple_power_system")` | New: `scenario/templates/` |
| **P5.5** | Unify trajectory/profile handling | Single consistent API for time-varying parameters across all components | All component files |

### Priority 6: Comprehensive Documentation
*Goal: Users can learn from examples and reference docs*

| ID | Task | Description | Files Affected |
|----|------|-------------|----------------|
| **P6.1** | Create end-to-end tutorial notebook | Build scenario → translate → run → compare, using pyoscomp API | `notebooks/pyoscomp_tutorial.ipynb` |
| **P6.2** | Document all OSeMOSYS ↔ PyPSA parameter mappings | Table showing equivalents and semantic differences | `docs/parameter_mapping.md` |
| **P6.3** | Add doctest examples | Executable examples in docstrings | All component files |
| **P6.4** | Create API reference documentation | Auto-generated from docstrings | `docs/api/` |
| **P6.5** | Document known limitations and gotchas | What can't pyoscomp do? What are the assumptions? | `docs/limitations.md` |

### Priority 7: Complexity Expansion (After Core is Stable)
*Goal: Support more sophisticated scenarios*

| ID | Task | Description | Files Affected |
|----|------|-------------|----------------|
| **P7.1** | Implement StorageComponent | Support OSeMOSYS storage parameters | `scenario/components/storage.py` |
| **P7.2** | Add storage translation to PyPSA | Map to PyPSA StorageUnit/Store components | `translation/pypsa_translator.py` |
| **P7.3** | Implement EmissionsComponent | Support EmissionsPenalty, AnnualEmissionLimit, etc. | New: `scenario/components/emissions.py` |
| **P7.4** | Add targets/constraints component | RE targets, capacity limits, etc. | New: `scenario/components/targets.py` |
| **P7.5** | Support multi-region with trade | TradeRoute, connections between regions | Extend `topology.py` |

---

## Detailed Analysis by Module

### `scenario/core.py`
**Issues:**
- Hardcoded component list (only topology, time, demand, supply)
- `build()` method doesn't validate component ordering or dependencies
- No way to skip components or add custom ones

**Recommendation:** Use a registry pattern for components with declared dependencies.

### `scenario/components/base.py`
**Issues:**
- `copy()` is static method but operates on directories, not component instances
- `add_to_dataframe()` silently drops duplicates based on `keep='last'` - may hide user errors
- No validation that key_columns exist before attempting dedup

**Recommendation:** Add option to raise on duplicate keys; make copy an instance method.

### `scenario/components/time.py`
**Issues:**
- 525 lines - too large, should be split into structure generation and visualization
- `_sanitize()` replaces `_` with `__` to avoid ambiguity, but this is fragile
- `load_time_axis()` is a static method that takes `scenario` arg - confusing API
- Visualization logic shouldn't be in data class

**Recommendation:** Extract visualization to separate module. Use proper namespacing for timeslice names.

### `scenario/components/supply.py`
**Issues:**
- 1133 lines - far too large
- Mixes technology metadata, capacity bounds, efficiency, and activity ratios
- `check_prerequisites()` hardcodes column names that may not exist
- No clear boundary with would-be PerformanceComponent

**Recommendation:** Split into SupplyComponent (technology registry), CapacityComponent (bounds), and clarify boundary with PerformanceComponent.

### `scenario/components/demand.py`
**Issues:**
- Trajectory interpolation logic is complex and duplicated
- `add_annual_demand()` silently converts invalid interpolation to 'step'
- `set_subannual_profile()` year=None applies only first year's profile to all - unclear

**Recommendation:** Extract trajectory handling to shared utility. Clarify year=None behavior.

### `scenario/manager.py`
**Issues:**
- UUID generation happens at init even if loading existing scenario
- `_create_empty_csv_files()` reads OSeMOSYS config but writes simplified headers
- Master list CSV-based tracking is fragile; no locking, no cleanup of deleted scenarios

**Recommendation:** Consider SQLite or YAML for scenario registry. Add scenario deletion support.

### `translation/time/`
**Issues:**
- Well-documented and tested, but isolated from rest of package
- `Timeslice` dataclass not used by `TimeComponent`
- `create_map()` returns complex nested structure that's hard to use

**Recommendation:** Bridge gap between `translation/time/structures.py` and `scenario/components/time.py`. Consider making `Timeslice` the canonical representation.

### `translation/pypsa_translator.py`
**Issues:**
- `_create_snapshots()` calculates 8760 hours/year hardcoded
- `_add_demand()` has complex pivot/stack logic that's hard to follow
- `_add_supply()` is empty placeholder
- No handling of efficiency, capacity bounds, or costs

**Recommendation:** Implement supply translation. Use constants for hours_in_year. Add comprehensive tests.

### `translation/osemosys_translator.py`
**Issues:**
- Completely stubbed - just returns input data unchanged
- No actual translation logic

**Recommendation:** Implement proper CSV generation compatible with otoole.

### `runners/osemosys.py`
**Issues:**
- Hardcoded path `os.path.join("start", "OSeMOSYS.txt")` - fragile
- No error capture from subprocess calls
- Pyomo path marked NotImplementedError

**Recommendation:** Make model file path configurable. Add proper error handling and output capture.

### `runners/pypsa.py`
**Issues:**
- `build_network()` reads CSVs directly instead of using translator
- `import_from_dataframe()` may not exist on all PyPSA components
- No handling for components not matching PyPSA names

**Recommendation:** Use PyPSAInputTranslator. Handle unknown components gracefully.

---

## Implementation Order Summary

```
Phase 1 (Weeks 1-2): P1.1 → P1.2 → P1.3 → P1.4 → P1.5
    ↓ Working scenario builder for simple case
Phase 2 (Weeks 3-4): P2.1 → P2.2 → P2.3 → P2.4 → P2.5
    ↓ Robust validation
Phase 3 (Weeks 5-6): P3.1 → P3.2 → P3.3 → P3.4 → P3.5
    ↓ Working translation
Phase 4 (Weeks 7-8): P4.1 → P4.2 → P4.3 → P4.4
    ↓ End-to-end execution
Phase 5 (Weeks 9-10): P5.1 → P5.2 → ... → P6.5
    ↓ Polish & documentation
Phase 6 (Ongoing): P7.1 → P7.2 → ...
    ↓ Expand capabilities
```

---

## Appendix: Specific Code Smells

### Duplicated Trajectory/Interpolation Logic
- `demand.py:add_annual_demand()` lines 137-216
- Similar pattern likely needed in `supply.py` for time-varying efficiency
- **Fix:** Create `pyoscomp/utils/trajectories.py`

### Inconsistent Year Handling
```python
# demand.py - treats year=None as "all years"
if isinstance(year, int):
    years = [year]
elif isinstance(year, list):
    years = year
else:
    years = [self.years[0]]  # ← Only applies to first year!

# supply.py - treats year=None as "all years"
if year is None:
    years = self.years  # ← Applies to all years
```

### Magic Numbers
- `8760` hours/year appears in multiple places
- `31.536` capacity_to_activity default (GW to PJ) undocumented
- `365` days/year (no leap year handling)

**Fix:** Define constants in central `pyoscomp/constants.py`

### Circular Import Pattern
```python
# In demand.py and supply.py
def load_time_axis(self):
    from pyoscomp.scenario.components.time import TimeComponent
    time_data = TimeComponent.load_time_axis(self)
```
This import inside method is a code smell indicating coupling issues.

---

## Acceptance Criteria for "Done"

A task is complete when:
1. Code passes all existing tests
2. New tests added for new functionality (>80% coverage)
3. Type hints added to public API
4. Docstrings updated with examples
5. No new `print()` statements (use logging)
6. Code reviewed and merged to main branch