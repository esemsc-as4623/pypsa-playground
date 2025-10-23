import pypsa
import pandas as pd
import matplotlib.pyplot as plt
import os

# --- 1. Setup and Initialization ---

# Define a directory for output images
save_directory = "01.static-network"
if not os.path.exists(save_directory):
    os.makedirs(save_directory, exist_ok=True)

# Initialize PyPSA Network object
# this will hold all the components and their data
n = pypsa.Network()

# Define a single snapshot (time step) for static analysis
# all component dataframes will have this single index in their timeseries tables (_t)
n.set_snapshots(pd.Index(["snapshot_0"]))

print("Initialized empty network with snapshots:", n.snapshots)

# --- 2. Addition Components ---

# add 3 buses (nodes) with coordinates
# v_nom is the nominal volatage (kV)
n.add("Bus", "Bus A", v_nom=0.4, x=0, y=10)
n.add("Bus", "Bus B", v_nom=0.4, x=10, y=10)
n.add("Bus", "Bus C", v_nom=0.4, x=20, y=10)

# add fixed load (demand) at Bus B
# p_set = 100 MW means this demand must be met in our single snapshot
n.add("Load", "Load at Bus B", bus="Bus B", p_set=100)

# add a conventional generator at Bus A
# p_nom = 200 MW is the max capacity
# marginal cost = 50 EUR/MWh is the production cost
# cost drives the optimization to only dispatch what is necessary
n.add("Generator", "Gas Generator at Bus A", bus="Bus A",
      p_nom=200, marginal_cost=50,
      p_min_pu=0) # can turn it off completely

# add AC transmission lines
# s_nom (nominal apparent power) defines the line's thermal flow limit (MVA)
n.add("Line", "Line A-B", bus0="Bus A", bus1="Bus B", x=0.01, r=0.001, s_nom=120, length=10)
n.add("Line", "Line B-C", bus0="Bus B", bus1="Bus C", x=0.02, r=0.002, s_nom=150, length=10)

# --- 3. Static Optimal Power Flow ---

# Run the Linear Optimal Power Flow (L-OPF)
# calculates the minimum cost dispatch for the single snapshot
# respects the physical limits of the network (Kirchhoff's laws, line limits, etc.)
n.optimize(solver_name="highs", log_to_console=False)
print("\n" + "="*30)
print(n.model)
print("="*30 + "\n")

print(n.model.constraints["Bus-nodal_balance"])

# --- 4. Data Access and Results ---

# a. System Cost
print(f"\nOptimal System Cost for Snapshot: {n.objective:.2f} EUR")

# b. Generator Dispatch (Active Power [MW])
print("\nGenerator Dispatch (Active Power [MW]):")
print(n.generators_t.p)

# c. Line Flows [MW]
# line A-B should be carrying all 100 MW of power from the generator to the load
# line B-C flow should be 0 as there is no load or generator at Bus C
print("\nLine Active Power Flows [MW]:")
print(n.lines_t.p0)

# d. Bus Voltage Magnitudes (V_mag_pu)
# voltages should be near 1.0 p.u., with minor drops due to line impedance
print("\nBus Voltage Magnitudes (V_mag_pu - relative to V_nom):")
print(n.buses_t.v_mag_pu)

# --- 5. Visualization ---

fig, ax = plt.subplots(1, 1, figsize=(8, 4))

# Plot the network topology
# scale the line width by the resulting active power flow magnitude.
# Line A-B is thick, Line B-C is thin/invisible.
n.plot(
    ax=ax,
    bus_sizes=0.5, # Small fixed bus size
    line_widths=n.lines_t.p0.iloc[0].abs() / 20, # Scale line width by flow
    line_colors='black',
    title="PyPSA Basic Static Network and Power Flow Results"
)

# add annotations for voltage results at each bus
for bus_name, bus in n.buses.iterrows():
    v_mag = n.buses_t.v_mag_pu.loc["snapshot_0", bus_name]
    ax.text(bus.x, bus.y + 1, f"V={v_mag:.3f} p.u.",
            horizontalalignment='center', fontsize=9, fontweight='bold')

# add annotations for the Load and Generation
ax.text(n.buses.loc["Bus A", "x"], n.buses.loc["Bus A", "y"] - 1.5,
        f"Gen: {n.generators_t.p.loc['snapshot_0', 'Gas Gen A']:.0f} MW",
        horizontalalignment='center', color='green', fontsize=9)

ax.text(n.buses.loc["Bus B", "x"], n.buses.loc["Bus B", "y"] - 1.5,
        f"Load: {n.loads_t.p_set.loc['snapshot_0', 'Load B']:.0f} MW",
        horizontalalignment='center', color='red', fontsize=9)

ax.set_aspect('equal')
ax.set_xticks([]) # Hide x ticks
ax.set_yticks([]) # Hide y ticks

plt.tight_layout()
plt.savefig(f'{save_directory}/static_load_flow.png')
print(f"\nVisualization saved to {save_directory}/static_load_flow.png")
