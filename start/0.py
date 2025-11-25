import logging
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pypsa

logger = logging.getLogger(__name__)
pypsa.network.power_flow.logger.setLevel(logging.WARNING)

save_directory = Path(__file__).parent

buses = range(5)
snapshots = range(365)

n = pypsa.Network()
n.set_snapshots(snapshots)
n.add("Bus", buses)

# add load as numpy array
n.add("Load",
      n.buses.index + " load",
      bus=buses,
      p_set=np.random.rand(len(snapshots), len(buses)))

# visualize demand profile
plt.figure()
n.loads_t.p_set.sum(axis=1).plot()
plt.tight_layout()
plt.savefig(f"{save_directory}/demand_profile.png")

# add fully-connected transmission lines
for i in range(len(buses)-1):
    for j in range(i+1, len(buses)):
        n.add("Line",
              f"{i} <-> {j}",
              bus0=i,
              bus1=j,
              x=0.1,
              r=0.01,
              s_nom=100)

scenario = "nearly-free"  # options: "nearly-free", "curtailment", None

# add (nearly) free, fully available energy generators
if scenario == "nearly-free":
    n.add("Generator",
        buses,
        suffix = f" {scenario}",
        bus = buses,
        p_nom_extendable=True,
        capital_cost = 1e-8, # does not work with 0 cost
        p_max_pu = np.ones((len(snapshots), len(buses))))
elif scenario == "curtailment":
    n.add("Generator",
        buses,
        suffix = f" {scenario}",
        bus = buses,
        p_nom_extendable=True,
        capital_cost = -1e-8, # negative cost
        p_max_pu = np.ones((len(snapshots), len(buses))))
    
# visualize availability
# plt.figure()
# n.generators_t.p_max_pu.T.mean().T.plot(ylabel="p.u.")
# plt.tight_layout()
# plt.savefig(f'{save_directory}/capacity-factor.png')

n.optimize(solver_name="highs")