# Import necessary libraries.
# PyPSA is the core library for power system analysis.
# Matplotlib is used for plotting data.
# add_legend_patches is a PyPSA utility for creating legends on map plots.
# Cartopy is used for creating maps.
import pypsa
import matplotlib.pyplot as plt
from pypsa.plot import add_legend_patches
import cartopy.crs as ccrs
import random

random.seed(42)

# Load an example PyPSA network model.
# `pypsa.examples.scigrid_de()` loads a model of the German transmission grid.
# This model is based on the SciGRID dataset and includes generators, loads,
# transmission lines, and other components for Germany.
# The `from_master=True` argument ensures that the latest version of the example
# dataset is downloaded from the PyPSA GitHub repository.
# The variable 'n' (short for network) holds the entire energy system model.
# This network object contains pandas DataFrames for each component type (buses, generators, lines, etc.).
n = pypsa.examples.scigrid_de(from_master=True)

# Print the buses (nodes) in the network.
# `n.buses` is a pandas DataFrame where each row represents a bus (a specific location or substation in the grid).
# Columns contain information (e.g. voltage level, location (x, y coordinates), etc.).
print(n.buses)

# --- Security Constraints and Network Pre-processing ---

# An n-1 security constraint is a reliability standard in power system operations.
# It requires that the system remains stable and within operational limits even after the
# unexpected failure of any single component (like a transmission line or generator).
# In this case, we are considering the failure of a single transmission line.
# If one line fails, the power it was carrying is rerouted through other lines in the network.
# This can cause overloads on those other lines if they are already operating near their maximum capacity.

# To approximate the n-1 security criterion in a simplified way, we limit the maximum
# power flow on each line to 70% of its thermal rating (`s_max_pu = 0.7`).
# `s_max_pu` stands for "maximum apparent power per unit". A value of 1.0 would mean 100% of its nominal capacity.
# By setting it to 0.7, we create a safety margin. It is assumed that this spare 30% capacity
# is sufficient to handle the rerouted power flow if another line fails, thus preventing cascading failures.
n.lines.s_max_pu = 0.7

# Print the lines DataFrame to see the effect of the change.
# `n.lines` is a DataFrame containing all transmission lines in the model.
# You can see columns like `bus0`, `bus1` (the two buses it connects), `s_nom` (nominal power capacity),
# and our newly set `s_max_pu`.
print(n.lines)

# --- Data Exploration and Visualization ---

# The following sections plot various aspects of the input data before running the optimization.
# This is a crucial step to understand the system you are modeling.

# Plot the total electricity demand (load) over time.
# `n.loads_t` is a DataFrame containing time-series data for all loads. The `_t` suffix in PyPSA
# indicates time-varying data.
# `p_set` is the active power demand that must be met at each time step.
# `.sum(axis=1)` aggregates the demand from all different locations into a single total for each hour.
# `.div(1e3)` converts the units from MW to GW.
plt.figure()
n.loads_t.p_set.sum(axis=1).div(1e3).plot(ylim=[0, 60], ylabel="MW")
plt.tight_layout()
plt.savefig('scrigrid-de-demand.png')

# Plot the availability of renewable energy sources over time, known as the "capacity factor".
# `n.generators_t.p_max_pu` gives the per-unit availability of each generator at each time step.
# For conventional generators (gas, coal), this is usually 1 (they are always available).
# For renewables (wind, solar), this value varies between 0 and 1 depending on the weather
# (e.g., how much the wind is blowing or the sun is shining).
# We group the generators by their `carrier` (e.g., 'onwind', 'solar') and calculate the mean
# availability for each type of generator over time.
plt.figure()
n.generators_t.p_max_pu.T.groupby(n.generators.carrier).mean().T.plot(ylabel="p.u.")
plt.tight_layout()
plt.savefig('scrigrid-de-capacity-factor.png')

# Plot the total installed generation capacity for each type of energy source (carrier).
# `n.generators.p_nom` is the nominal (or nameplate) capacity of each individual generator in MW.
# We group by `carrier` and sum up the capacities to get the total installed capacity for each type.
# `.div(1e3)` converts from MW to GW.
plt.figure()
n.generators.groupby("carrier").p_nom.sum().div(1e3).plot.barh()
plt.xlabel("GW")
plt.tight_layout()
plt.savefig('scrigrid-de-total-capacity.png')

# Plot the geographical distribution of electricity loads at the first time step.
# We first calculate the total load at each bus.
load = n.loads_t.p_set.sum(axis=0).groupby(n.loads.bus).sum()
fig = plt.figure()
# We use a map projection (EqualEarth) for a more accurate geographical representation.
ax = plt.axes(projection=ccrs.EqualEarth())
# `n.plot.map()` is a PyPSA function to plot the network on a map.
# We use the `bus_sizes` argument to represent the magnitude of the load at each bus.
# The size of the circle at each bus location will be proportional to its electricity demand.
n.plot.map(ax=ax, bus_sizes=load / 2e5)
plt.tight_layout()
plt.savefig('scrigrid-de-load-distribution_t0.png')

# Plot the geographical distribution of generation capacity.
# First, we calculate the total generation capacity at each bus for each carrier.
capacities = n.generators.groupby(["bus", "carrier"]).p_nom.sum()
# We get a list of all unique energy carriers to assign them colors for the plot legend.
carriers = list(n.generators.carrier.unique()) + list(n.storage_units.carrier.unique())
# Generate a random color for each carrier.
colors = ["#%06x" % random.randint(0, 0xFFFFFF) for _ in carriers]
# Add this color information to the network object.
n.add("Carrier", carriers, color=colors, overwrite=True)

fig = plt.figure()
ax = plt.axes(projection=ccrs.EqualEarth())
# This time, `bus_sizes` represents the installed generation capacity at each bus.
n.plot.map(ax=ax, bus_sizes=capacities / 2e4)
# Add a legend to the map to show which color corresponds to which energy carrier.
add_legend_patches(ax, colors, carriers, legend_kw=dict(frameon=False, bbox_to_anchor=(0, 1)))
plt.tight_layout()
plt.savefig('scrigrid-de-generation-capacity.png')

# --- Optimal Power Flow Simulation ---

# Now we run the core of the simulation: an Optimal Power Flow (OPF).
# The OPF decides how much electricity each generator should produce in each hour
# to meet the demand at the minimum possible cost, while respecting the physical
# limits of the power grid.

# We reset the line capacity limit. The previous setting of 70% (`s_max_pu = 0.7`)
# might make the problem "infeasible", meaning there is no possible way to supply all
# the demand without overloading the transmission lines under this strict condition.
# We relax this constraint to 95% to allow the optimization to find a solution.
# In a real study, an infeasible result would prompt further investigation into
# whether there is insufficient generation or transmission capacity in the model.
n.lines.s_max_pu = 0.95

# This is the main command to run the optimization.
# PyPSA builds a large-scale linear optimization problem that represents the energy system.
# The objective is to minimize the total operational cost, which is the sum of the marginal
# costs of all generators multiplied by their production.
# The constraints are:
# 1. At each bus and for each hour, power generation must equal power demand (Kirchhoff's Current Law).
# 2. The power flow on each transmission line cannot exceed its maximum capacity.
# 3. The output of each generator cannot exceed its available capacity.
# `solver_name="highs"` tells PyPSA to use the HiGHS solver, which is a high-performance open-source solver.
# After `n.optimize()` runs, the network object `n` is populated with the results of the simulation
# (e.g., generator dispatch, power flows, prices).
n.optimize(solver_name="highs")

# --- Analysis and Visualization of Results ---

# The following sections analyze and plot the results from the optimization.

# Plot the loading of the transmission lines.
# `n.lines_t.p0` contains the active power flow on each line for each time step after optimization.
# We look at the first hour (`.iloc[0]`) and calculate the loading as a percentage of the line's capacity.
line_loading = n.lines_t.p0.iloc[0].abs() / n.lines.s_nom / n.lines.s_max_pu * 100
# We create a color normalization to map loading values (0-100%) to a color spectrum.
norm = plt.Normalize(vmin=0, vmax=100)
fig = plt.figure(figsize=(7, 7))
ax = plt.axes(projection=ccrs.EqualEarth())

# We plot the network map again, but this time we color the lines based on their loading.
# `line_colors` is set to our calculated loading, and `line_cmap="plasma"` defines the color map.
# `line_widths` are scaled by the nominal capacity of the lines, so thicker lines have higher capacity.
n.plot.map(
    ax=ax,
    bus_sizes=0,
    line_colors=line_loading,
    line_norm=norm,
    line_cmap="plasma",
    line_widths=n.lines.s_nom / 1000,
)

# Add a color bar to show what the colors represent (line loading in %).
plt.colorbar(
    plt.cm.ScalarMappable(cmap="plasma", norm=norm),
    ax=ax,
    label="Relative line loading [%]",
    shrink=0.6,
)

plt.tight_layout()
plt.savefig('scrigrid-de-line-loading.png')

# Plot the hourly electricity generation (dispatch) from each energy source.
# `n.generators_t.p` contains the optimized power output of each generator for each hour.
# We group by carrier and sum to get the total dispatch for each type of energy source.
p_by_carrier = n.generators_t.p.T.groupby(n.generators.carrier).sum().T.div(1e3)
fig, ax = plt.subplots(figsize=(11, 4))

# We create a stacked area plot to show the contribution of each carrier to meeting the demand over time.
p_by_carrier.plot(
    kind="area",
    ax=ax,
    linewidth=0,
    cmap="tab20b",
)

ax.legend(ncol=5, loc="upper left", frameon=False)
ax.set_ylabel("GW")
ax.set_ylim(0, 80)
plt.tight_layout()
plt.savefig('scrigrid-de-dispatch-by-carrier.png')

# Plot the behavior of energy storage units (in this case, pumped hydro).
# `n.storage_units_t.p` shows the dispatch of storage units. A positive value means discharging (generating electricity),
# and a negative value means charging (consuming electricity).
# `n.storage_units_t.state_of_charge` shows how much energy is stored in the unit at each hour.
fig, ax = plt.subplots()

p_storage = n.storage_units_t.p.sum(axis=1).div(1e3)
state_of_charge = n.storage_units_t.state_of_charge.sum(axis=1).div(1e3)

p_storage.plot(label="Pumped hydro dispatch [GW]", ax=ax)
state_of_charge.plot(label="State of charge [GWh]", ax=ax)

ax.grid()
ax.legend()
ax.set_ylabel("MWh or MW")
plt.tight_layout()
plt.savefig('scrigrid-de-pumped-hydro.png')

# Plot the Locational Marginal Prices (LMPs).
# The LMP (or marginal price) at a bus is the cost to supply one additional MWh of electricity
# at that specific location and time. It is a key result from the optimization, representing the
# wholesale price of electricity.
# Differences in LMPs between locations are caused by transmission congestion. If a cheap generator
# cannot supply a load because the transmission line is full, a more expensive local generator
# must be used, increasing the price at that location.
# `n.buses_t.marginal_price` contains the LMP for each bus at each hour. We take the mean price over time.
fig = plt.figure(figsize=(7, 7))
ax = plt.axes(projection=ccrs.EqualEarth())

norm = plt.Normalize(vmin=0, vmax=100)  # €/MWh

# We plot the map and color the buses according to their average LMP.
n.plot.map(
    ax=ax,
    bus_colors=n.buses_t.marginal_price.mean(),
    bus_cmap="plasma",
    bus_norm=norm,
    bus_alpha=0.7,
)

# Add a color bar to show the price scale.
plt.colorbar(
    plt.cm.ScalarMappable(cmap="plasma", norm=norm),
    ax=ax,
    label="LMP [€/MWh]",
    shrink=0.6,
)
plt.tight_layout()
plt.savefig('scrigrid-de-lmp.png')