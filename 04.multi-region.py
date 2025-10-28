"""
Scenario Context:
We are modeling a high-level, three-node national system where 
each region has unique wind and solar resources. The system 
needs to load these regional data profiles from an external 
source (a simulated CSV file) and calculate the necessary 
inter-regional power exchange.

PyPSA Functionalities to Demo:

External Data Loading: Simulating loading external time-series 
data using pandas.read_csv and integrating it into PyPSA.
Component Linking: Using Links or Transformers to model 
inter-regional tie-lines and convert power between AC and DC 
(if a DC link is desired).
Querying/Filtering: Using network.buses.query() to select 
and modify components based on criteria.
Network Plotting: Using pypsa.plot() for basic spatial 
visualization of the network (assuming coordinates are provided).

What is Achieved:
The final script demonstrates how to efficiently populate a 
large, complex PyPSA model using real-world data structures and 
provides a foundational step for visualizing the geographical 
aspects of the resulting system.
"""