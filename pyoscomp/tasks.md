# PyOSComp Task List: Updated Roadmap

Updated: March 2026

This roadmap reflects current code reality and prioritizes what is still needed
to meet the paper goal: quantifying model-attributable uncertainty rather than
implementation-attributable differences.

## Current Status Snapshot

| Area | Status | Notes |
|---|---|---|
| Scenario components | Partial-to-strong | Core components implemented; trade still stubbed |
| Storage | Implemented with assumptions | End-to-end support exists but structural assumptions need explicit validation |
| Interfaces (`ScenarioData`, `ModelResults`) | Strong | Immutable contracts implemented and used |
| Harmonization checks | Strong baseline | Input + translation + NPV parity checks implemented |
| Translators | Strong baseline | PyPSA and OSeMOSYS translators implemented |
| Time translation | Strong | Bidirectional conversion with coverage checks |
| Runners | Usable | OSeMOSYS Pyomo path still not implemented |
| CLI | Weak | Placeholder logic in `__main__.py` |

## Critical Reflection Against Project Goal

The package now has the architecture needed for fair comparison, but paper-grade
robustness still depends on tighter experiment control:

1. Validation should move from pass/fail-only to richer diagnostics and audit logs.
2. Structural disagreements (especially storage aggregation and chronology loss)
     need explicit quantification in outputs.
3. Repeatable experiment packaging (scenarios, seeds, solver configs, metadata)
     needs standardization.

## Prioritized Task List

### P0: Reproducibility and Run Integrity

| ID | Task | Why It Matters | Target Files |
|---|---|---|---|
| P0.1 | Add runner pre-flight checks (`otoole`, `glpsol`, solver availability) | Avoid ambiguous runtime failures | `run.py`, `runners/osemosys.py`, `runners/pypsa.py` |
| P0.2 | Add standardized run manifest (`scenario hash`, solver versions, options) | Reproducibility and paper auditability | new `runners/results.py` or `interfaces/results.py` extension |
| P0.3 | Add deterministic test harness for multi-year/multi-region runs | Prevent regressions in weighting/index behavior | `tests/test_runners/` |

### P1: Harmonization Diagnostics Expansion

| ID | Task | Why It Matters | Target Files |
|---|---|---|---|
| P1.1 | Emit harmonization reports as JSON + markdown artifacts | Make checks auditable per run | `run.py`, new report writers |
| P1.2 | Add per-technology harmonization metrics (cost, CF, efficiency) | Locate divergence sources quickly | `interfaces/harmonization.py` |
| P1.3 | Add strict-mode profiles for different study types | Avoid over/under-constraining checks | `interfaces/containers.py`, `interfaces/harmonization.py` |

### P2: Structural-Disagreement Accounting

| ID | Task | Why It Matters | Target Files |
|---|---|---|---|
| P2.1 | Quantify storage aggregation disagreement (triplet vs StorageUnit) | Core to fair storage-value comparison | new `analysis/storage_structural_gap.py` |
| P2.2 | Add chronology-loss diagnostics for snapshot/timeslice conversion | Core paper claim on temporal representation | `translation/time/`, new analysis module |
| P2.3 | Add explicit uncertainty decomposition report (implementation vs structural) | Align outputs to research framing | new `analysis/divergence_decomposition.py` |

### P3: Feature Completeness Gaps

| ID | Task | Why It Matters | Target Files |
|---|---|---|---|
| P3.1 | Implement `TradeComponent` and translation to PyPSA links / OSeMOSYS trade tables | Multi-region realism | `scenario/components/trade.py`, translators |
| P3.2 | Complete OSeMOSYS Pyomo runner path or remove dead branch | Reduce maintenance ambiguity | `runners/osemosys.py` |
| P3.3 | Add robust CLI workflow (`validate`, `translate`, `run`, `compare`) | Reproducible non-notebook usage | `__main__.py` |

### P4: Validation and Testing Depth

| ID | Task | Why It Matters | Target Files |
|---|---|---|---|
| P4.1 | Add property-based tests for time conversion invariants | Stress edge cases beyond fixtures | `tests/test_translation/test_time/` |
| P4.2 | Add storage translation parity tests (capacity/efficiency/cost attribution) | Prevent silent storage drift | new `tests/test_translation/test_storage.py` |
| P4.3 | Add end-to-end parity tests for objective components under controlled scenarios | Validate NPV decomposition rigor | `tests/test_integration/` |

### P5: Paper Workflow Artifacts

| ID | Task | Why It Matters | Target Files |
|---|---|---|---|
| P5.1 | Create canonical paper scenarios as code | Repeatable experiment definitions | new `scenarios/paper_scenarios.py` |
| P5.2 | Produce automated figure/table pipeline from saved run manifests | No manual figure drift | notebooks + `visualization/` + new scripts |
| P5.3 | Add publication-ready harmonization dashboard export | Transparent model comparability evidence | `visualization/harmonization_plots.py` |

## Verification Strategy (Updated)

### Level 1: Contract Validation

- `ScenarioData.validate()` and strict protocol checks must pass.
- Required harmonization metrics must be persisted as artifacts.

### Level 2: Controlled Parity Runs

- One-region one-tech scenarios with known analytic expectations.
- Compare objective components (capex, fixed, variable, salvage) not only total.

### Level 3: Experimental Sensitivity Runs

- Hold non-temporal parameters fixed.
- Sweep temporal resolution and compare storage recommendations with uncertainty
    decomposition.

## Acceptance Criteria

- [ ] Every run emits machine-readable harmonization and manifest artifacts.
- [ ] Structural disagreement metrics are reported separately from implementation
            mismatch metrics.
- [ ] Storage comparison includes both power and energy capacity parity checks.
- [ ] Temporal sensitivity pipeline is scripted and reproducible end-to-end.
- [ ] Paper figures/tables can be regenerated from versioned scenarios and manifests.