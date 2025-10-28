import pypsa

# --- 1. Setup and Initialization ---

# Initialize PyPSA Network object
# this will hold all the components and their data
n = pypsa.Network()

# Define a single snapshot (time step) for static analysis
# all component dataframes will have this single index in their timeseries tables (_t)
n.set_snapshots(range(1))

print("Initialized empty network with snapshots:", n.snapshots)

# --- 2. Adding Components ---

# add 3 buses (nodes) with coordinates
# v_nom is the nominal volatage (kV)
n.add("Bus", ["Bus A", "Bus B", "Bus C"], v_nom=0.4)

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
n.add("Line", "Line A-B", bus0="Bus A", bus1="Bus B", x=0.01, r=0.001, s_nom=120)
n.add("Line", "Line B-C", bus0="Bus B", bus1="Bus C", x=0.02, r=0.002, s_nom=150)

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