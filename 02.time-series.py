"""
Scenario Context:
An energy market operator needs to determine the lowest-cost
way to dispatch a mix of dispatchable gas generation, 
intermittent wind power, and a battery storage system to meet 
a fluctuating hourly load profile over a 48-hour period.

PyPSA Functionalities to Demo:

Time-Dependent Data: Adding and assigning time series data
(e.g., load profiles to loads_t.p_set, renewable availability
to generators_t.p_max_pu).
Storage Modeling: Adding a Store component (a battery) with 
efficiency, capacity, and state-of-charge constraints.
Optimal Power Flow (OPF): Running a time-series coupled 
Linear Optimal Power Flow (network.lopf()) to find the 
cost-optimal unit commitment and dispatch.

Result Interpretation: Analyzing the hourly dispatch results 
for generators and the state of charge for the battery.

What is Achieved:
The script successfully performs a minimum-cost operational 
dispatch optimization over two full days, showcasing how 
PyPSA handles time-coupling constraints (like battery 
charge/discharge) and finds the optimal hourly operation of 
the system.
"""