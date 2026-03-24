import marimo

__generated_with = "0.21.1"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md("""
    # Temporal Representation and Storage Valuation
    ## A Comparative Analysis of OSeMOSYS and PyPSA

    This notebook implements a **controlled complexity ladder** of experiments
    to isolate and quantify each structural disagreement (SD1-SD5) between
    PyPSA and OSeMOSYS.

    | ID | Structural Disagreement | First Active |
    |----|------------------------|-------------|
    | SD1 | Cost accounting (lump-sum+salvage vs annualized) | Exp 0 |
    | SD2 | Temporal resolution (timeslice-averaged vs hourly) | Exp 2 |
    | SD3 | Storage inter-year (no cross-year energy carry) | Exp 5 |
    | SD4 | Storage component model (3 vs 1 StorageUnit) | Exp 4 |
    | SD5 | Curtailment (not native OSeMOSYS output) | Exp 3 |
    """)
    return


@app.cell
def _():
    import logging
    logging.basicConfig(level=logging.WARNING)
    # Suppress verbose solver output
    logging.getLogger("pyoscomp").setLevel(logging.WARNING)
    logging.getLogger("pypsa").setLevel(logging.WARNING)
    logging.getLogger("linopy").setLevel(logging.WARNING)

    import pandas as pd
    import matplotlib.pyplot as plt
    import numpy as np
    from pyoscomp.experiments import (
        build_experiment_scenario,
        run_comparison,
        summarize_results,
        summarize_all,
    )

    return (
        build_experiment_scenario,
        np,
        pd,
        plt,
        run_comparison,
        summarize_all,
    )


@app.cell
def _(mo):
    mo.md("""
    ## Experiment 0: Dispatchable Baseline (Gas Only)

    **Activates**: SD1 (cost accounting)

    Single region, single year, single timeslice. One dispatchable gas technology.
    Both models have identical temporal resolution — only cost formulation differs.

    **Expected**: Capacity agrees exactly. Objective values differ due to SD1.
    """)
    return


@app.cell
def _(build_experiment_scenario, run_comparison):
    exp0_sd = build_experiment_scenario(
        region="HUB",
        years=[2030],
        seasons={"1": 365},
        daytypes={"1": 1},
        brackets={"1": 24},
        annual_demand=100.0,
        technologies=[{
            "name": "GAS_CCGT",
            "type": "dispatchable",
            "capex": 500,
            "variable_cost": 2,
            "fixed_cost": 0,
            "oplife": 30,
            "efficiency": 0.5,
            "capacity_factor": 1.0,
        }],
        discount_rate=0.05,
    )
    exp0 = run_comparison(exp0_sd, "Exp 0: Gas Baseline")
    return (exp0,)


@app.cell
def _(exp0, mo, pd):
    _supply = exp0.comparison.get("supply", pd.DataFrame())
    _obj = exp0.comparison.get("objective", pd.DataFrame())
    mo.md(f"""
    ### Results

    **Supply (Installed Capacity GW)**

    {_supply.to_markdown(index=False)}

    **Objective Values**

    {_obj.to_markdown(index=False)}

    **Divergence Flags**: {len(exp0.flags)}
    """)
    for _f in exp0.flags:
        mo.md(f"- `{_f}`")
    return


@app.cell
def _(mo):
    mo.md("""
    ## Experiment 1: Flat Renewable (Wind CF=1.0)

    **Activates**: SD1 only (CF=1.0 eliminates temporal effects)

    Same structure as Exp 0 but wind instead of gas. CF=1.0 means no curtailment,
    no temporal aggregation effect.

    **Expected**: Identical capacity and dispatch. Cost objectives differ (SD1).
    """)
    return


@app.cell
def _(build_experiment_scenario, run_comparison):
    exp1_sd = build_experiment_scenario(
        region="HUB",
        years=[2030],
        seasons={"1": 365},
        daytypes={"1": 1},
        brackets={"1": 24},
        annual_demand=100.0,
        technologies=[{
            "name": "WIND",
            "type": "renewable",
            "capex": 1500,
            "variable_cost": 0,
            "fixed_cost": 0,
            "oplife": 25,
            "capacity_factor": 1.0,
        }],
        discount_rate=0.05,
    )
    exp1 = run_comparison(exp1_sd, "Exp 1: Flat Wind")
    return (exp1,)


@app.cell
def _(exp1, mo, pd):
    _supply = exp1.comparison.get("supply", pd.DataFrame())
    _obj = exp1.comparison.get("objective", pd.DataFrame())
    mo.md(f"""
    ### Results

    **Supply (Installed Capacity GW)**

    {_supply.to_markdown(index=False)}

    **Objective Values**

    {_obj.to_markdown(index=False)}

    **Divergence Flags**: {len(exp1.flags)}
    """)
    for _f in exp1.flags:
        mo.md(f"- `{_f}`")
    return


@app.cell
def _(mo):
    mo.md("""
    ## Experiment 2: Variable Renewable (Seasonal Wind)

    **Activates**: SD1 + SD2 (temporal resolution)

    4 seasons, seasonal CF variation. Gas backup available.
    Timeslice-averaged CF vs snapshot-level CF creates first temporal divergence.

    **Expected**: Small capacity difference. OSeMOSYS may over-value wind slightly.
    """)
    return


@app.cell
def _(build_experiment_scenario, run_comparison):
    exp2_sd = build_experiment_scenario(
        region="HUB",
        years=[2030],
        seasons={"1": 90, "2": 92, "3": 92, "4": 91},
        daytypes={"1": 1},
        brackets={"1": 24},
        annual_demand=500.0,
        technologies=[
            {
                "name": "WIND",
                "type": "renewable",
                "capex": 1500,
                "variable_cost": 0,
                "fixed_cost": 0,
                "oplife": 25,
                "capacity_factor": {
                    "base": 0.36,
                    "season_weights": {"1": 1.25, "2": 0.97, "3": 0.69, "4": 1.11},
                },
            },
            {
                "name": "GAS_CCGT",
                "type": "dispatchable",
                "capex": 500,
                "variable_cost": 2,
                "fixed_cost": 0,
                "oplife": 30,
                "efficiency": 0.5,
            },
        ],
        discount_rate=0.05,
    )
    exp2 = run_comparison(exp2_sd, "Exp 2: Seasonal Wind")
    return (exp2,)


@app.cell
def _(exp2, mo, pd):
    _supply = exp2.comparison.get("supply", pd.DataFrame())
    _obj = exp2.comparison.get("objective", pd.DataFrame())
    mo.md(f"""
    ### Results

    **Supply (Installed Capacity GW)**

    {_supply.to_markdown(index=False)}

    **Objective Values**

    {_obj.to_markdown(index=False)}

    **Divergence Flags**: {len(exp2.flags)}
    """)
    for _f in exp2.flags:
        mo.md(f"- `{_f}`")
    return


@app.cell
def _(mo):
    mo.md("""
    ## Experiment 3: Curtailment Regime

    **Activates**: SD1 + SD2 + SD5 (curtailment)

    High wind penetration with expensive gas backup forces wind overbuilding.
    PyPSA reports curtailment natively; OSeMOSYS does not.

    **Expected**: Capacity similar. Curtailment divergence quantifiable.
    """)
    return


@app.cell
def _(build_experiment_scenario, run_comparison):
    exp3_sd = build_experiment_scenario(
        region="HUB",
        years=[2030],
        seasons={"1": 90, "2": 92, "3": 92, "4": 91},
        daytypes={"1": 1},
        brackets={"1": 24},
        annual_demand=200.0,
        technologies=[
            {
                "name": "WIND",
                "type": "renewable",
                "capex": 800,
                "variable_cost": 0,
                "oplife": 25,
                "capacity_factor": {
                    "base": 0.36,
                    "season_weights": {"1": 1.25, "2": 0.97, "3": 0.69, "4": 1.11},
                },
            },
            {
                "name": "GAS_CCGT",
                "type": "dispatchable",
                "capex": 1500,
                "variable_cost": 50,
                "oplife": 30,
                "efficiency": 0.5,
            },
        ],
        discount_rate=0.05,
    )
    exp3 = run_comparison(exp3_sd, "Exp 3: Curtailment")
    return (exp3,)


@app.cell
def _(exp3, mo, pd):
    _supply = exp3.comparison.get("supply", pd.DataFrame())
    _obj = exp3.comparison.get("objective", pd.DataFrame())
    _curt = exp3.comparison.get("dispatch_curtailment", pd.DataFrame())
    mo.md(f"""
    ### Results

    **Supply (Installed Capacity GW)**

    {_supply.to_markdown(index=False)}

    **Curtailment**

    {_curt.to_markdown(index=False) if not _curt.empty else "No curtailment data"}

    **Objective Values**

    {_obj.to_markdown(index=False)}

    **Divergence Flags**: {len(exp3.flags)}
    """)
    for _f in exp3.flags:
        mo.md(f"- `{_f}`")
    return


@app.cell
def _(mo):
    mo.md("""
    ## Experiment 4: Short-Duration Storage (4h Battery)

    **Activates**: SD1 + SD2 + SD4 (storage component model)

    12 timeslices (4 seasons x 3 brackets). Wind + battery + gas.
    OSeMOSYS 3-component model vs PyPSA single StorageUnit.

    **Expected**: Similar total storage investment. Different cost attribution.
    """)
    return


@app.cell
def _(build_experiment_scenario, run_comparison):
    exp4_sd = build_experiment_scenario(
        region="HUB",
        years=[2030],
        seasons={"1": 90, "2": 92, "3": 92, "4": 91},
        daytypes={"1": 1},
        brackets={"1": 8, "2": 8, "3": 8},
        annual_demand=500.0,
        technologies=[
            {
                "name": "WIND",
                "type": "renewable",
                "capex": 1500,
                "variable_cost": 0,
                "oplife": 25,
                "capacity_factor": {
                    "base": 0.36,
                    "season_weights": {"1": 1.25, "2": 0.97, "3": 0.69, "4": 1.11},
                },
            },
            {
                "name": "GAS_CCGT",
                "type": "dispatchable",
                "capex": 500,
                "variable_cost": 2,
                "oplife": 30,
                "efficiency": 0.5,
            },
        ],
        storage=[{
            "name": "BATT_STOR",
            "charge_tech": "BATT_CHARGE",
            "discharge_tech": "BATT_DISCHARGE",
            "energy_ratio": 4.0,
            "round_trip_eff": 0.9,
            "capex_power": 200,
            "capex_energy": 100,
            "oplife": 20,
        }],
        discount_rate=0.05,
    )
    exp4 = run_comparison(exp4_sd, "Exp 4: Battery")
    return (exp4,)


@app.cell
def _(exp4, mo, pd):
    _supply = exp4.comparison.get("supply", pd.DataFrame())
    _obj = exp4.comparison.get("objective", pd.DataFrame())
    _stor_mw = exp4.comparison.get("storage_installed_capacity", pd.DataFrame())
    _stor_mwh = exp4.comparison.get("storage_installed_energy_capacity", pd.DataFrame())
    mo.md(f"""
    ### Results

    **Supply (Installed Capacity GW)**

    {_supply.to_markdown(index=False)}

    **Storage Power Capacity (MW)**

    {_stor_mw.to_markdown(index=False) if not _stor_mw.empty else "N/A"}

    **Storage Energy Capacity (MWh)**

    {_stor_mwh.to_markdown(index=False) if not _stor_mwh.empty else "N/A"}

    **Objective Values**

    {_obj.to_markdown(index=False)}

    **Divergence Flags**: {len(exp4.flags)}
    """)
    for _f in exp4.flags:
        mo.md(f"- `{_f}`")
    return


@app.cell
def _(mo):
    mo.md("""
    ## Experiment 5: Seasonal Storage (Cross-Year)

    **Activates**: SD1 + SD2 + SD3 + SD4 (inter-year storage)

    4 timeslices (4 seasons x 1 bracket). Wind + long-duration H2 storage.
    OSeMOSYS cannot carry energy across year boundaries (SD3).

    **Expected**: Significant storage capacity divergence. PyPSA values seasonal storage higher.
    """)
    return


@app.cell
def _(build_experiment_scenario, run_comparison):
    exp5_sd = build_experiment_scenario(
        region="HUB",
        years=[2030],
        seasons={"1": 90, "2": 92, "3": 92, "4": 91},
        daytypes={"1": 1},
        brackets={"1": 24},
        annual_demand=500.0,
        technologies=[
            {
                "name": "WIND",
                "type": "renewable",
                "capex": 1500,
                "variable_cost": 0,
                "oplife": 25,
                "capacity_factor": {
                    "base": 0.36,
                    "season_weights": {"1": 1.25, "2": 0.97, "3": 0.69, "4": 1.11},
                },
            },
            {
                "name": "GAS_CCGT",
                "type": "dispatchable",
                "capex": 500,
                "variable_cost": 2,
                "oplife": 30,
                "efficiency": 0.5,
            },
        ],
        storage=[{
            "name": "H2_STORE",
            "charge_tech": "H2_CHARGE",
            "discharge_tech": "H2_DISCHARGE",
            "energy_ratio": 200.0,
            "round_trip_eff": 0.4,
            "capex_power": 500,
            "capex_energy": 10,
            "oplife": 30,
        }],
        discount_rate=0.05,
    )
    exp5 = run_comparison(exp5_sd, "Exp 5: Seasonal Storage")
    return (exp5,)


@app.cell
def _(exp5, mo, pd):
    _supply = exp5.comparison.get("supply", pd.DataFrame())
    _obj = exp5.comparison.get("objective", pd.DataFrame())
    _stor_mw = exp5.comparison.get("storage_installed_capacity", pd.DataFrame())
    _stor_mwh = exp5.comparison.get("storage_installed_energy_capacity", pd.DataFrame())
    mo.md(f"""
    ### Results

    **Supply (Installed Capacity GW)**
    {_supply.to_markdown(index=False)}

    **Storage Power Capacity (MW)**
    {_stor_mw.to_markdown(index=False) if not _stor_mw.empty else "N/A"}

    **Storage Energy Capacity (MWh)**
    {_stor_mwh.to_markdown(index=False) if not _stor_mwh.empty else "N/A"}

    **Objective Values**
    {_obj.to_markdown(index=False)}

    **Divergence Flags**: {len(exp5.flags)}
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Experiment 6: High Temporal Resolution

    **Activates**: All SDs at maximum resolution

    24 timeslices (4 seasons x 2 daytypes x 3 brackets). Wind + battery + gas.
    Maximum temporal complexity — quantify cumulative divergence.

    **Expected**: Largest divergence. Dispatch patterns diverge most in storage.
    """)
    return


@app.cell
def _(build_experiment_scenario, run_comparison):
    exp6_sd = build_experiment_scenario(
        region="HUB",
        years=[2030],
        seasons={"1": 90, "2": 92, "3": 92, "4": 91},
        daytypes={"1": 5, "2": 2},
        brackets={"1": 8, "2": 8, "3": 8},
        annual_demand=1000.0,
        technologies=[
            {
                "name": "WIND",
                "type": "renewable",
                "capex": 1500,
                "variable_cost": 0,
                "oplife": 25,
                "capacity_factor": {
                    "base": 0.36,
                    "season_weights": {"1": 1.25, "2": 0.97, "3": 0.69, "4": 1.11},
                },
            },
            {
                "name": "GAS_CCGT",
                "type": "dispatchable",
                "capex": 500,
                "variable_cost": 2,
                "oplife": 30,
                "efficiency": 0.5,
            },
        ],
        storage=[{
            "name": "BATT_STOR",
            "charge_tech": "BATT_CHARGE",
            "discharge_tech": "BATT_DISCHARGE",
            "energy_ratio": 4.0,
            "round_trip_eff": 0.9,
            "capex_power": 200,
            "capex_energy": 100,
            "oplife": 20,
        }],
        discount_rate=0.05,
    )
    exp6 = run_comparison(exp6_sd, "Exp 6: High Resolution")
    return (exp6,)


@app.cell
def _(exp6, mo, pd):
    _supply = exp6.comparison.get("supply", pd.DataFrame())
    _obj = exp6.comparison.get("objective", pd.DataFrame())
    _stor_mw = exp6.comparison.get("storage_installed_capacity", pd.DataFrame())
    mo.md(f"""
    ### Results

    **Supply (Installed Capacity GW)**
    {_supply.to_markdown(index=False)}

    **Storage Power Capacity (MW)**
    {_stor_mw.to_markdown(index=False) if not _stor_mw.empty else "N/A"}

    **Objective Values**
    {_obj.to_markdown(index=False)}

    **Divergence Flags**: {len(exp6.flags)}
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Experiment 7: Multi-Year Investment

    **Activates**: All SDs + investment period dynamics

    24 timeslices, 3 investment periods (2025, 2030, 2035).
    Demand growth (1000 -> 1200 -> 1500 GWh/yr). No storage
    (OSeMOSYS requires contiguous years for storage level tracking).

    **Expected**: Different investment timing between models due to SD1.
    """)
    return


@app.cell
def _(build_experiment_scenario, run_comparison):
    exp7_sd = build_experiment_scenario(
        region="HUB",
        years=[2025, 2030, 2035],
        seasons={"1": 90, "2": 92, "3": 92, "4": 91},
        daytypes={"1": 5, "2": 2},
        brackets={"1": 8, "2": 8, "3": 8},
        demand_by_year={2025: 1000.0, 2030: 1200.0, 2035: 1500.0},
        technologies=[
            {
                "name": "WIND",
                "type": "renewable",
                "capex": 1500,
                "variable_cost": 0,
                "oplife": 25,
                "capacity_factor": {
                    "base": 0.36,
                    "season_weights": {"1": 1.25, "2": 0.97, "3": 0.69, "4": 1.11},
                },
            },
            {
                "name": "GAS_CCGT",
                "type": "dispatchable",
                "capex": 500,
                "variable_cost": 2,
                "oplife": 30,
                "efficiency": 0.5,
            },
        ],
        discount_rate=0.05,
    )
    exp7 = run_comparison(exp7_sd, "Exp 7: Multi-Year")
    return (exp7,)


@app.cell
def _(exp7, mo, pd):
    _supply = exp7.comparison.get("supply", pd.DataFrame())
    _obj = exp7.comparison.get("objective", pd.DataFrame())
    mo.md(f"""
    ### Results

    **Supply (Installed Capacity GW)**
    {_supply.to_markdown(index=False)}

    **Objective Values**
    {_obj.to_markdown(index=False)}

    **Divergence Flags**: {len(exp7.flags)}
    """)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Summary: All Experiments
    """)
    return


@app.cell
def _(exp0, exp1, exp2, exp3, exp4, exp5, exp6, exp7, mo, summarize_all):
    all_results = [exp0, exp1, exp2, exp3, exp4, exp5, exp6, exp7]
    _summary = summarize_all(all_results)
    mo.md(f"""
    {_summary.to_markdown(index=False)}
    """)
    return (all_results,)


@app.cell
def _(mo):
    mo.md("""
    ## Visualization: Installed Capacity Comparison
    """)
    return


@app.cell
def _(all_results, np, plt):
    def _(results):
        fig, axes = plt.subplots(2, 4, figsize=(16, 8))
        axes = axes.flatten()

        for i, result in enumerate(results):
            ax = axes[i]
            supply = result.comparison.get("supply")
            if supply is not None and not supply.empty:
                techs = supply["TECHNOLOGY"].values
                pypsa_vals = supply["PyPSA"].values
                osemosys_vals = supply["OSeMOSYS"].values
                x = np.arange(len(techs))
                width = 0.35
                ax.bar(x - width / 2, pypsa_vals * 1000, width, label="PyPSA", color="#2196F3")
                ax.bar(x + width / 2, osemosys_vals * 1000, width, label="OSeMOSYS", color="#FF9800")
                ax.set_xticks(x)
                ax.set_xticklabels(techs, rotation=45, ha="right", fontsize=7)
                ax.set_ylabel("MW")
            ax.set_title(result.label.split(":")[0], fontsize=9)
            if i == 0:
                ax.legend(fontsize=7)

        fig.suptitle("Installed Capacity: PyPSA vs OSeMOSYS", fontsize=14)
        plt.tight_layout()
        return fig

    _(all_results)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Visualization: Objective Value Divergence
    """)
    return


@app.cell
def _(all_results, np, plt):
    def _(results):
        labels = [r.label.split(":")[0] for r in results]
        pypsa_objs = [r.pypsa_results.objective for r in results]
        osemosys_objs = [r.osemosys_results.objective for r in results]
        rel_diffs = [
            abs(p - o) / max(abs(p), abs(o), 1e-10)
            for p, o in zip(pypsa_objs, osemosys_objs)
        ]

        fig2, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

        x = np.arange(len(labels))
        width = 0.35
        ax1.bar(x - width / 2, pypsa_objs, width, label="PyPSA", color="#2196F3")
        ax1.bar(x + width / 2, osemosys_objs, width, label="OSeMOSYS", color="#FF9800")
        ax1.set_xticks(x)
        ax1.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
        ax1.set_ylabel("Objective Value")
        ax1.set_title("Absolute Objective Values")
        ax1.legend()

        ax2.bar(x, rel_diffs, color="#E91E63")
        ax2.set_xticks(x)
        ax2.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
        ax2.set_ylabel("Relative Difference")
        ax2.set_title("Objective Value Relative Divergence")
        ax2.axhline(y=0.05, color="gray", linestyle="--", alpha=0.5, label="5% threshold")
        ax2.legend()

        plt.tight_layout()
        return fig2


    _(all_results)
    return


@app.cell
def _(mo):
    mo.md("""
    ## Divergence Flag Heatmap
    """)
    return


@app.cell
def _(all_results, np, plt):
    categories = ["capacity", "dispatch", "curtailment", "economics", "capex",
                   "objective", "effective_cf", "storage_capacity_mw", "storage_capacity_mwh"]
    exp_labels = [r.label.split(":")[0] for r in all_results]

    heatmap_data = np.zeros((len(categories), len(exp_labels)))
    for j, result in enumerate(all_results):
        for flag in result.flags:
            if flag.category in categories:
                i = categories.index(flag.category)
                heatmap_data[i, j] = flag.max_rel_diff

    fig3, ax3 = plt.subplots(figsize=(12, 6))
    im = ax3.imshow(heatmap_data, aspect="auto", cmap="YlOrRd")
    ax3.set_xticks(range(len(exp_labels)))
    ax3.set_xticklabels(exp_labels, rotation=45, ha="right", fontsize=8)
    ax3.set_yticks(range(len(categories)))
    ax3.set_yticklabels(categories, fontsize=8)
    ax3.set_title("Max Relative Divergence by Category and Experiment")
    plt.colorbar(im, ax=ax3, label="Max Relative Difference")
    plt.tight_layout()
    fig3
    return


if __name__ == "__main__":
    app.run()
