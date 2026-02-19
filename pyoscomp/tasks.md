# PyOSComp Task List: Harmonization Protocol

*Updated: February 2026*

This task list is focused on building the **Harmonization Protocol** required for the paper:

> **Temporal Representation and Storage Valuation in Energy System Models: A Comparative Analysis of OSeMOSYS and PyPSA**

**Research Question:** How does the choice between chronological snapshots (PyPSA) and representative timeslices (OSeMOSYS) propagate through model formulations to affect storage investment recommendations in offshore wind systems?

---

## Table of Contents
1. [Harmonization Protocol Requirements](#harmonization-protocol-requirements)
2. [Prioritized Task List](#prioritized-task-list)
3. [Verification Strategy](#verification-strategy)
4. [Critical Design Issues](#critical-design-issues)
5. [Detailed Analysis by Module](#detailed-analysis-by-module)

---

## Harmonization Protocol Requirements

Before comparing temporal representation effects, **all implementation differences must be harmonized**:

| Parameter Category | Harmonization Requirement | Verification Metric |
|--------------------|---------------------------|---------------------|
| **Discount Rate** | Identical rate in both models | `r_OSeMOSYS == r_PyPSA` |
| **Technology Costs** | Same CAPEX, Fixed O&M, Variable O&M | `∑Costs_OSeMOSYS == ∑Costs_PyPSA` (undiscounted) |
| **Technology Lifetimes** | Same operational life, depreciation | `L_OSeMOSYS == L_PyPSA` |
| **Demand Profile** | Same annual total AND hourly shape | `∫D(t)dt` and `corr(D_osemosys, D_pypsa) > 0.99` |
| **Wind Capacity Factor** | Same annual total, average, distribution | `CF_annual`, `mean(CF)`, `std(CF)`, `percentiles` |
| **Topology** | PyPSA copper-plate = OSeMOSYS single-region | Single bus, single region |
| **Cost Accounting** | NPV basis with explicit salvage value | `NPV_OSeMOSYS == NPV_PyPSA` for identical scenarios |

### The Isolation Principle

To measure the **pure effect of temporal representation**:
1. Hold ALL harmonizable parameters constant
2. Vary ONLY the time discretization:
   - PyPSA: Full 8760-hour chronology
   - OSeMOSYS: Representative timeslices (N timeslices)
3. Measure: Storage capacity recommendation, utilization, value

---

## Prioritized Task List

### Priority -1: Core Integration (BLOCKING - Must Complete First)
*Goal: Connect Scenario.build() → ScenarioData → Translator → Runner*

**Current Problem:** The `scenario/` module and `translation/` module are disconnected:
- Scenario components build OSeMOSYS CSVs directly
- Translators expect `ScenarioData` but have inconsistent implementations
- `PyPSAInputTranslator` uses both `self.scenario_data` AND `self.input_data` (broken)
- Runners work independently, not using translators

| ID | Task | Description | Files Affected |
|----|------|-------------|----------------|
| **P-1.4** | Create `PyPSARunner.from_scenario_data()` | Accept ScenarioData, use translator internally | `runners/pypsa.py` |
| **P-1.5** | Create `OSeMOSYSRunner.from_scenario_data()` | Accept ScenarioData, export CSVs, run model | `runners/osemosys.py` |
| **P-1.6** | Add unified `pyoscomp.run()` function | Entry point: `run(scenario_data, model='both')` | New: `pyoscomp/run.py` |
| **P-1.7** | Create `simple-demo.ipynb` notebook | Demonstrate full pipeline: build → translate → run → compare | `notebooks/simple-demo.ipynb` |
| **P-1.8** | Add integration test | Test that same scenario produces equivalent results | `tests/test_integration/test_pipeline.py` |

**Verification:** The demo notebook must show:
1. Build a scenario using components
2. Convert to ScenarioData
3. Translate to PyPSA Network
4. Translate to OSeMOSYS CSVs
5. Run both models
6. Compare results

### Priority 0: Harmonization Protocol Infrastructure
*Goal: Build the validation framework to PROVE models are harmonized*

| ID | Task | Description | Files Affected |
|----|------|-------------|----------------|
| **P0.1** | Create `HarmonizationValidator` class | Validates that a scenario satisfies all harmonization requirements. Reports discrepancies with tolerances. | New: `pyoscomp/validation/harmonization.py` |
| **P0.2** | Implement discount rate validation | Compare `DiscountRate.csv` (OSeMOSYS) vs network settings (PyPSA) | `validation/harmonization.py` |
| **P0.3** | Implement cost validation | Sum CAPEX/OPEX by technology, compare across models | `validation/harmonization.py` |
| **P0.4** | Implement demand validation | Compare annual totals, compute correlation of profiles | `validation/harmonization.py` |
| **P0.5** | Implement capacity factor validation | Compare wind CF: annual, mean, std, percentiles (5, 25, 50, 75, 95) | `validation/harmonization.py` |
| **P0.6** | Create `HarmonizationReport` dataclass | Structured output showing pass/fail for each requirement with values | `validation/harmonization.py` |
| **P0.7** | Add `scenario.validate_harmonization()` method | Entry point to run all harmonization checks | `scenario/core.py` |

### Priority 1: Storage Component (Critical for Paper)
*Goal: Full storage modeling capability in both frameworks*

| ID | Task | Description | Files Affected |
|----|------|-------------|----------------|
| **P1.1** | Implement `StorageComponent` core | Storage technology registry: name, type (battery, pumped hydro, etc.) | `scenario/components/storage.py` |
| **P1.2** | Add storage capacity parameters | `TechnologyToStorage`, `TechnologyFromStorage`, `StorageMaxChargeRate`, `StorageMaxDischargeRate` | `scenario/components/storage.py` |
| **P1.3** | Add storage economics parameters | `CapitalCostStorage`, storage cycling costs, degradation factor | `scenario/components/storage.py`, `economics.py` |
| **P1.4** | Add storage operational parameters | `OperationalLifeStorage`, `MinStorageCharge`, `StorageLevelStart` | `scenario/components/storage.py` |
| **P1.5** | Implement storage efficiency handling | Round-trip efficiency consistent across models (η_charge × η_discharge) | `scenario/components/storage.py` |
| **P1.6** | Add PyPSA storage translation | Map to `StorageUnit` with proper `efficiency_store`, `efficiency_dispatch`, `max_hours` | `translation/pypsa_translator.py` |
| **P1.7** | Add OSeMOSYS storage export | Generate storage-related CSVs compatible with otoole | `translation/osemosys_translator.py` |
| **P1.8** | Test storage round-trip | Build scenario → translate both → verify equivalent storage formulation | `tests/test_translation/test_storage.py` |

### Priority 2: Wind/Renewable Supply (Offshore Wind Focus)
*Goal: Accurate capacity factor handling for variable renewables*

| ID | Task | Description | Files Affected |
|----|------|-------------|----------------|
| **P2.1** | Implement variable renewable technology type | `is_variable_renewable` flag on technologies, special CF handling | `scenario/components/supply.py` |
| **P2.2** | Add hourly capacity factor profile ingestion | Load from CSV/DataFrame, associate with technology | `scenario/components/supply.py` |
| **P2.3** | Implement CF aggregation for timeslices | When converting to OSeMOSYS, aggregate hourly CF to timeslice-average CF | `translation/osemosys_translator.py` |
| **P2.4** | Add CF profile statistics computation | Calculate: annual total, mean, std, percentiles, autocorrelation | New: `pyoscomp/analysis/capacity_factors.py` |
| **P2.5** | Validate CF preservation across translation | After aggregation, verify statistical properties are preserved (within tolerance) | `validation/harmonization.py` |
| **P2.6** | Create wind profile visualizations | Time series, duration curves, histogram, seasonal patterns | `analysis/capacity_factors.py` |

### Priority 3: Translation Completeness
*Goal: Same scenario runs identically in both models (modulo temporal representation)*

| ID | Task | Description | Files Affected |
|----|------|-------------|----------------|
| **P3.1** | Complete PyPSA supply translation | Add generators with efficiency, marginal_cost, capital_cost, p_nom_extendable | `translation/pypsa_translator.py` |
| **P3.2** | Add PyPSA cost handling | Translate CAPEX to annualized costs OR use multi-period investment | `translation/pypsa_translator.py` |
| **P3.3** | Implement salvage value in PyPSA | For consistency, add salvage value calculation post-optimization | New: `analysis/cost_accounting.py` |
| **P3.4** | Complete OSeMOSYS translator | Generate all required CSVs from ScenarioData, validate against otoole | `translation/osemosys_translator.py` |
| **P3.5** | Add time structure translation tests | Verify YearSplit sums to 1.0, snapshot weightings match | `tests/test_translation/test_time.py` |
| **P3.6** | Document temporal representation differences | Explain how the SAME underlying data becomes snapshots vs timeslices | `docs/temporal_representation.md` |

### Priority 4: Economics & Cost Accounting
*Goal: Consistent NPV calculation across models*

| ID | Task | Description | Files Affected |
|----|------|-------------|----------------|
| **P4.1** | Verify EconomicsComponent completeness | Ensure discount rate, capital/fixed/variable costs are fully implemented | `scenario/components/economics.py` |
| **P4.2** | Add explicit salvage value calculation | OSeMOSYS calculates automatically; add equivalent for PyPSA post-processing | `analysis/cost_accounting.py` |
| **P4.3** | Implement NPV comparison function | Given results from both models, compute and compare NPV | `analysis/cost_accounting.py` |
| **P4.4** | Add cost breakdown visualization | Stacked bar: CAPEX, Fixed O&M, Variable O&M, Salvage, by technology | `analysis/cost_accounting.py` |
| **P4.5** | Validate cost consistency | Test: identical scenario → identical NPV (within tolerance) | `tests/test_integration/test_cost_consistency.py` |

### Priority 5: Runner Infrastructure
*Goal: Execute both models from unified interface*

| ID | Task | Description | Files Affected |
|----|------|-------------|----------------|
| **P5.1** | Fix OSeMOSYS runner paths | Make model file path configurable, add proper error handling | `runners/osemosys.py` |
| **P5.2** | Connect PyPSA runner to translator | Use `PyPSAInputTranslator` output instead of raw CSVs | `runners/pypsa.py` |
| **P5.3** | Standardize result extraction | Common interface: `RunResult` with objective, capacities, dispatch, costs | New: `runners/results.py` |
| **P5.4** | Add solver configuration | Timeout, gap tolerance, solver selection for both models | `runners/*.py` |
| **P5.5** | Create unified `pyoscomp.run()` | Single entry point: `run(scenario, model='both')` returns comparable results | `__main__.py` or `runners/__init__.py` |

### Priority 6: Verification & Visualization
*Goal: PROVE harmonization works and SHOW the temporal representation effect*

| ID | Task | Description | Files Affected |
|----|------|-------------|----------------|
| **P6.1** | Create harmonization summary visualization | Dashboard showing all harmonization checks: pass/fail with values | New: `visualization/harmonization.py` |
| **P6.2** | Implement demand profile comparison plot | Side-by-side or overlay: PyPSA hourly vs OSeMOSYS timeslice demand | `visualization/harmonization.py` |
| **P6.3** | Implement CF comparison plot | Duration curves, distributions for both representations | `visualization/harmonization.py` |
| **P6.4** | Create storage dispatch comparison | Time series of storage charge/discharge across both models | `visualization/storage.py` |
| **P6.5** | Implement storage value decomposition | Revenue from arbitrage, capacity credit, ancillary services | `analysis/storage_value.py` |
| **P6.6** | Create sensitivity analysis tools | Vary timeslice count, measure storage recommendation changes | `analysis/sensitivity.py` |

### Priority 7: Paper Artifacts
*Goal: Generate figures and tables for the paper*

| ID | Task | Description | Files Affected |
|----|------|-------------|----------------|
| **P7.1** | Create `paper_scenarios.py` | Offshore wind + storage scenario configurations for the paper | New: `scenarios/paper_scenarios.py` |
| **P7.2** | Build comparison notebook | `notebooks/temporal_comparison.ipynb`: full workflow demonstrating harmonization | `notebooks/temporal_comparison.ipynb` |
| **P7.3** | Generate Figure 1: Temporal representation schematic | Visual explanation of snapshots vs timeslices | Notebook or `visualization/` |
| **P7.4** | Generate Figure 2: Harmonization validation | Show that non-temporal parameters are identical | Notebook |
| **P7.5** | Generate Figure 3: Storage results comparison | Side-by-side: optimal storage capacity, utilization, value | Notebook |
| **P7.6** | Generate Figure 4: Sensitivity to timeslice count | How storage recommendation changes with N timeslices | Notebook |
| **P7.7** | Generate Table 1: Input parameter summary | All harmonized parameters with values | Notebook |
| **P7.8** | Generate Table 2: Model comparison results | Key outputs: objective, storage capacity, wind curtailment | Notebook |
| **P7.9** | Export publication-quality figures | High-DPI PNG/PDF with consistent styling | `visualization/style.py` |

---

## Verification Strategy

### Level 1: Unit Verification (Per Component)
- Each harmonization check has a standalone test
- Example: `test_discount_rate_harmonized()` compares rates from both models

### Level 2: Integration Verification (Full Scenario)
- Build a "trivial" scenario (1 tech, 1 region, 1 year, minimal time)
- Verify IDENTICAL results from both models (objective, dispatch)
- This proves the models are equivalent WHEN temporal structure is identical

### Level 3: Controlled Variation (The Experiment)
- Build offshore wind + storage scenario
- Run with IDENTICAL scenarios except:
  - PyPSA: 8760 hours
  - OSeMOSYS: 12, 24, 48, 96, 288 timeslices
- Measure:
  - Optimal storage capacity
  - Storage utilization (cycles/year, avg state of charge)
  - Wind curtailment
  - System cost

### Verification Outputs

| Output | Purpose | Format |
|--------|---------|--------|
| `harmonization_report.json` | Machine-readable validation results | JSON |
| `harmonization_report.md` | Human-readable summary | Markdown |
| `comparison_results.csv` | Model outputs for statistical analysis | CSV |
| `figures/*.pdf` | Publication-ready visualizations | PDF |

---

## Critical Design Issues

### 1. **Architecture & Coupling Problems**

#### 1.1 Scenario/Translation Disconnect
The `scenario/` module and `translation/` module operate independently without a clear integration point. The scenario components build OSeMOSYS CSV files directly, but the translation layer (`translation/pypsa_translator.py`) expects a generic `input_data: Dict[str, pd.DataFrame]` format. There is no clear path from:
```
Scenario.build() → Translator.translate() → Runner.run()
```

**Fix:** Define a clear `ScenarioData` interface that both scenario building and translation consume.

#### 1.2 Storage Component Missing
[storage.py](pyoscomp/scenario/components/storage.py) is **EMPTY** - critical blocker for the paper.

#### 1.3 Component Dependencies Not Enforced
Components claim prerequisites (e.g., `demand.py` requires Time and Topology) but:
- No formal dependency injection or ordering mechanism
- `Scenario.build()` doesn't validate component readiness

### 2. **Model Equivalence Issues (Critical for Paper)**

#### 2.1 OSeMOSYS-PyPSA Semantic Gaps
- OSeMOSYS `CapacityFactor` = max annual capacity factor (scalar per timeslice)
- PyPSA `p_max_pu` = time series (value per snapshot)
- **These must be reconciled for fair comparison**

#### 2.2 Cost Accounting Differences
- OSeMOSYS: Explicit salvage value in objective function
- PyPSA: Typically uses annualized costs, no explicit salvage
- **Must add salvage calculation to PyPSA post-processing**

#### 2.3 Time Handling
- OSeMOSYS: Year-agnostic timeslice fractions (`YearSplit`)
- PyPSA: Explicit datetime snapshots with weights
- **Translation must preserve energy balance and chronology effects**

### 3. **Validation Gaps**

#### 3.1 No Harmonization Validation
Currently no way to verify that two model representations are consistent.

#### 3.2 No Cross-Model Result Comparison
No infrastructure to compare outputs from OSeMOSYS and PyPSA runs.

---

## Detailed Analysis by Module

### `scenario/components/storage.py` (CRITICAL BLOCKER)
**Status:** Empty file
**Required for paper:** YES - storage valuation is central to research question

**Implementation Priority:**
1. Define storage technology structure (name, type, capacity)
2. Add efficiency parameters (charge/discharge efficiencies)
3. Add economic parameters (CAPEX, cycling costs)
4. Add operational constraints (min/max charge rates, losses)

### `scenario/components/supply.py`
**Issues:**
- No variable renewable technology flag
- No hourly capacity factor profile handling
- Aggregation to timeslices not implemented

**For Paper:**
- Must handle offshore wind CF profiles
- Must support aggregation for OSeMOSYS timeslices

### `translation/pypsa_translator.py`
**Issues:**
- `_add_supply()` is empty placeholder
- No storage translation
- No cost handling (CAPEX not translated)

**For Paper:**
- Must translate storage to `StorageUnit`
- Must handle variable renewable `p_max_pu` from CF profiles

### `translation/osemosys_translator.py`
**Status:** Stub only
**Required:** Full implementation for otoole compatibility

### `validation/` (NEW MODULE NEEDED)
**Purpose:** Harmonization validation framework
**Must implement:**
- Cross-model parameter comparison
- Statistical validation (mean, std, percentiles)
- Report generation

---

## Implementation Order for Paper

```
Week 1-2: Harmonization Infrastructure (P0)
    ├── P0.1-P0.6: Build HarmonizationValidator
    └── Output: Can PROVE two scenarios are harmonized

Week 3-4: Storage Component (P1)
    ├── P1.1-P1.5: Build StorageComponent
    ├── P1.6-P1.7: Storage translation
    └── Output: Can model battery storage in both frameworks

Week 5-6: Wind/Renewables (P2) + Translation (P3)
    ├── P2.1-P2.6: Variable renewable handling
    ├── P3.1-P3.4: Complete translators
    └── Output: Offshore wind scenario runs in both models

Week 7-8: Economics & Runners (P4, P5)
    ├── P4.1-P4.5: Cost consistency
    ├── P5.1-P5.5: Unified run interface
    └── Output: Single command runs both models, extracts results

Week 9-10: Verification & Paper (P6, P7)
    ├── P6.1-P6.6: Visualizations
    ├── P7.1-P7.9: Paper artifacts
    └── Output: All figures and tables for paper
```

---

## Appendix: Key Technical Decisions

### Temporal Representation Translation

**PyPSA → OSeMOSYS Aggregation:**
```python
# Hourly capacity factor to timeslice capacity factor
cf_timeslice[ts] = weighted_mean(cf_hourly[hours_in_ts], weights=duration_hours)

# Verification: Energy must be preserved
E_hourly = sum(cf_hourly * P_nom * dt)
E_timeslice = sum(cf_timeslice * P_nom * YearSplit * 8760)
assert abs(E_hourly - E_timeslice) < TOL
```

**OSeMOSYS → PyPSA Disaggregation:**
```python
# For each snapshot, find containing timeslice, use that CF
cf_hourly[t] = cf_timeslice[find_timeslice(t)]
# Note: This loses hourly variability information
```

### Storage Model Equivalence

| OSeMOSYS | PyPSA | Notes |
|----------|-------|-------|
| `TechnologyToStorage` | `StorageUnit.store` | Links generator to storage |
| `TechnologyFromStorage` | `StorageUnit.dispatch` | Links storage to demand |
| `StorageMaxChargeRate` | `StorageUnit.p_nom * efficiency_store` | MW |
| `StorageMaxDischargeRate` | `StorageUnit.p_nom` | MW |
| `MinStorageCharge` | `StorageUnit.state_of_charge_initial` | Fraction |
| `OperationalLifeStorage` | (Post-processing) | Used in salvage calc |
| Round-trip efficiency | `efficiency_store * efficiency_dispatch` | Must be consistent |

### NPV Calculation Equivalence

**OSeMOSYS (built-in):**
```
NPV = Σ_y [ (CAPEX + FixedOM + VariableOM) / (1+r)^y ] - SalvageValue / (1+r)^Y
```

**PyPSA (requires post-processing):**
```python
# PyPSA uses annualized costs, must convert back to NPV
annuity = capital_cost * CRF  # CRF = r(1+r)^n / ((1+r)^n - 1)
# OR: Use multi-period investment with explicit salvage
```

### Magic Numbers → Constants

| Magic Number | Constant | Location |
|-------------|----------|----------|
| `8760` | `HOURS_PER_YEAR` | `pyoscomp/constants.py` |
| `8784` | `HOURS_PER_LEAP_YEAR` | `pyoscomp/constants.py` |
| `31.536` | `GW_TO_PJ_FACTOR` | `pyoscomp/constants.py` |
| `1e-8` | `TOL` | `pyoscomp/constants.py` |

---

## Acceptance Criteria

### For Harmonization Validation
- [ ] `HarmonizationValidator` passes for identical scenarios
- [ ] Clear error messages for harmonization failures
- [ ] Report shows exact values and tolerances

### For Storage Component
- [ ] Can define battery with: capacity, efficiency, costs
- [ ] Translates correctly to both OSeMOSYS and PyPSA
- [ ] Storage dispatch matches when time structure is identical

### For Paper Readiness
- [ ] Offshore wind + storage scenario defined
- [ ] Both models run from same scenario definition
- [ ] Results are comparable (same units, same accounting)
- [ ] Figures generated in publication quality
- [ ] Sensitivity analysis complete (N timeslices vs storage capacity)