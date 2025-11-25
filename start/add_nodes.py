import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa

logger = logging.getLogger(__name__)
save_directory = Path(__file__).parent

def add_nodes(n, t):
    buses = range(n)
    snapshots = range(t)

    n = pypsa.Network()
    n.set_snapshots(snapshots)
    n.add("Bus", buses)

    return n