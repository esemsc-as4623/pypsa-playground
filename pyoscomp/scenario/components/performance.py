"""
Performance Component - facade for technology performance parameters.
Delegates to SupplyComponent but provides cleaner semantic interface.
"""
import pandas as pd
from .base import ScenarioComponent

class PerformanceComponent(ScenarioComponent):
	"""
	Performance component facade for technology operational characteristics.
    
	Prerequisites:
		- Supply component must be initialized
    
	Note: This component delegates to SupplyComponent but provides
	a semantically cleaner interface for performance-related parameters.
	"""
    
	def __init__(self, scenario_dir, supply_component):
		"""
		:param scenario_dir: Scenario directory path
		:param supply_component: SupplyComponent instance to delegate to
		"""
		super().__init__(scenario_dir)
		self.supply = supply_component
    
	def set_efficiency(self, region, technology, efficiency, mode='MODE1', year=None):
		"""
		Set technology efficiency by calling SupplyComponent's conversion method.
		This is a convenience wrapper around set_conversion_technology.
        
		Note: Efficiency is expressed through InputActivityRatio/OutputActivityRatio
		in OSeMOSYS. This method handles the conversion.
		"""
		# For now, we're NOT duplicating the logic from supply.py
		# Just document that efficiency is set via supply.set_conversion_technology
		raise NotImplementedError(
			"Use SupplyComponent.set_conversion_technology() to set efficiency. "
			"PerformanceComponent is a semantic facade and doesn't duplicate functionality yet."
		)
    
	def load(self):
		"""No-op: SupplyComponent handles loading."""
		pass
    
	def save(self):
		"""No-op: SupplyComponent handles saving."""
		pass
