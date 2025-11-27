import logging
from pathlib import Path

import pypsa

logger = logging.getLogger(__name__)
save_directory = Path(__file__).parent

def add_nodes(n, t):
    buses = range(n)
    snapshots = range(t)

    n = pypsa.Network()
    n.add("Carrier", "AC", color="lightblue")
    n.add("Bus", buses)
    n.set_snapshots(snapshots)

    return n