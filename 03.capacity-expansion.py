"""
Scenario Context:
A national grid planner must decide how much new transmission 
capacity, solar generation, and storage capacity to build to 
achieve a carbon reduction target while minimizing total 
system costs. They can choose to build a new inter-regional 
link and new generators.

PyPSA Functionalities to Demo:

Investment Variables: Setting component attributes like 
p_nom_extendable = True and s_nom_extendable = True for 
generators, storage, and lines.
Investment Costs: Assigning capital_cost to components to 
model investment expenditure.

Objective Function: Utilizing the integrated objective 
function (minimizing total system cost: O&M + Investment).

System-Wide Constraint: Implementing a custom constraint, 
such as setting a minimum renewable share or a maximum 
$\text{CO}_2$ emissions limit.

What is Achieved:
This is the full Optimal Expansion Planning (OEP) workflow. 
The script determines the optimal mix and size (P_nom) of new 
generation, storage, and transmission assets.
"""