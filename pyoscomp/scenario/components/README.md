Contains functions to initialize various components of an energy system scenario.

## Module Structure
```
pyoscomp/
	 scenario/
	 	 components/
         	 base.py        # Base class with abstract and shared methods
             topology.py    # Spatial structure
             time.py        # Temporal structure
             demand.py      # Demand in space and time
             supply.py      # Generators options + residual/legacy capacity 
             storage.py     # TODO: Storage options + residual/legacy capacity
             performance.py # TODO: Generator/storage performance metrics
             economics.py   # TODO: Global and generator-/storage-specific costs
             trade.py       # NOTE: out-of-scope in v1.0.0
             emissions.py   # NOTE: out-of-scope in v1.0.0
             targets.py     # NOTE: out-of-scope in v1.0.0

tests/         		# Pytest suite
	 test_scenario/
	 	 test_components/
```