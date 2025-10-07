import pypsa

network = pypsa.Network()

# bus is the node to which loads, generators, storage units, lines, transformers and links attach
# role is to enforce energy conservation for all elements connected to it
n_buses = 3
for i in range(n_buses):
    network.add("Bus", f"Bus {i}", v_nom=20.0) # v_nom is nominal voltage in kV
print(network.buses)

# energy enters the model in:
# 1. generators
# 2. storage units or stores with higher energy before than after the simulation
# 3. any components with efficiency greater than 1 (e.g. heat pumps)

# energy leaves the model in:
# 1. loads
# 2. storage units or stores with higher energy after than before the simulation
# 3. all lines, links or storage units with efficiency less than 1

for i in range(n_buses):
    network.add(
        "Line",
        f"Line {i}",
        bus0=f"Bus {i}",
        bus1=f"Bus {(i + 1) % n_buses}",
        x=0.1,
        r=0.01,
    )
print(network.lines)

network.add("Generator", "Generator 0", bus="Bus 0", p_set=100, control="PQ")
print(network.generators)

# static data stored in memory using pandas DataFrames
# attribute of pypsa.Network object
# to list attributes: print(n.components[COMPONENT]["attrs"])
# n.buses
# n.generators
# n.loads
# n.lines
# n.links
# n.storage_units
# n.stores
# n.transformers

# time-varying data stored in memory as dictionaries of pandas DataFrames
# attributes stored for different snapshots
# n.buses_t
# n.generators_t
# n.loads_t
# n.lines_t
# n.links_t
# n.storage_units_t
# n.stores_t
# n.transformers_t