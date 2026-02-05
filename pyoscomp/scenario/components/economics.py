"""
Economics Component for scenario building in PyPSA-OSeMOSYS Comparison Framework.
Handles economic parameters: discount rates, capital costs, fixed costs, variable costs.
"""
import pandas as pd
import numpy as np

from .base import ScenarioComponent

class EconomicsComponent(ScenarioComponent):
	"""
	Economics component for cost parameters.
    
	Prerequisites:
		- Time component (for years)
		- Topology component (for regions)
		- Supply component (for technologies)
    
	Example usage::
		econ = EconomicsComponent(scenario_dir)
		econ.set_discount_rate('REGION1', 0.05)
		econ.set_capital_cost('REGION1', 'GAS_CCGT', {2026: 500})
		econ.set_variable_cost('REGION1', 'GAS_CCGT', 'MODE1', {2026: 2})
		econ.save()
	"""
    
	def __init__(self, scenario_dir):
		super().__init__(scenario_dir)
        
		# Check prerequisites
		self.years, self.regions = self.check_prerequisites()
        
		# Economics parameters
		self.discount_rate_df = pd.DataFrame(columns=["REGION", "VALUE"])
		self.capital_cost_df = pd.DataFrame(columns=["REGION", "TECHNOLOGY", "YEAR", "VALUE"])
		self.variable_cost_df = pd.DataFrame(columns=["REGION", "TECHNOLOGY", "MODE_OF_OPERATION", "YEAR", "VALUE"])
		self.fixed_cost_df = pd.DataFrame(columns=["REGION", "TECHNOLOGY", "YEAR", "VALUE"])
    
	def check_prerequisites(self):
		"""Check that Time and Topology components exist."""
		years = self.read_csv("YEAR.csv")["VALUE"].tolist()
		if not years:
			raise AttributeError("Time component is not defined for this scenario.")
        
		regions = self.read_csv("REGION.csv")["VALUE"].tolist()
		if not regions:
			raise AttributeError("Topology component is not defined for this scenario.")
        
		return years, regions
    
	def load(self):
		"""Load all economics parameter CSV files."""
		self.discount_rate_df = self.read_csv("DiscountRate.csv")
		self.capital_cost_df = self.read_csv("CapitalCost.csv")
		self.variable_cost_df = self.read_csv("VariableCost.csv")
		self.fixed_cost_df = self.read_csv("FixedCost.csv")
    
	def save(self):
		"""Save all economics parameter DataFrames to CSV."""
		self.write_dataframe("DiscountRate.csv", self.discount_rate_df)
		self.write_dataframe("CapitalCost.csv", self.capital_cost_df)
		self.write_dataframe("VariableCost.csv", self.variable_cost_df)
		self.write_dataframe("FixedCost.csv", self.fixed_cost_df)
    
	def set_discount_rate(self, region, rate):
		"""
		Set discount rate for a region.
        
		:param region: str, Region identifier
		:param rate: float, Discount rate (e.g., 0.05 for 5%)
		"""
		if region not in self.regions:
			raise ValueError(f"Region '{region}' not defined in scenario.")
		if not (0 <= rate <= 1):
			raise ValueError(f"Discount rate must be between 0 and 1, got {rate}")
        
		record = [{"REGION": region, "VALUE": rate}]
		self.discount_rate_df = self.add_to_dataframe(
			self.discount_rate_df, record, key_columns=["REGION"]
		)
    
	def set_capital_cost(self, region, technology, cost_trajectory):
		"""
		Set capital cost for a technology.
        
		:param region: str, Region identifier
		:param technology: str, Technology identifier
		:param cost_trajectory: dict or float, {year: cost} or single cost for all years
        
		Example::
			econ.set_capital_cost('REGION1', 'GAS_CCGT', {2026: 500, 2030: 450})
			econ.set_capital_cost('REGION1', 'SOLAR_PV', 300)  # Same cost all years
		"""
		if region not in self.regions:
			raise ValueError(f"Region '{region}' not defined in scenario.")
        
		# Convert single value to trajectory
		if isinstance(cost_trajectory, (int, float)):
			cost_trajectory = {y: cost_trajectory for y in self.years}
        
		records = []
		for year in self.years:
			cost = cost_trajectory.get(year, 0)
			if cost < 0:
				raise ValueError(f"Capital cost cannot be negative: {cost} for {technology} in {year}")
			records.append({
				"REGION": region,
				"TECHNOLOGY": technology,
				"YEAR": year,
				"VALUE": cost
			})
        
		self.capital_cost_df = self.add_to_dataframe(
			self.capital_cost_df, records, key_columns=["REGION", "TECHNOLOGY", "YEAR"]
		)
    
	def set_variable_cost(self, region, technology, mode, cost_trajectory):
		"""
		Set variable cost for a technology and mode.
        
		:param region: str, Region identifier
		:param technology: str, Technology identifier
		:param mode: str, Mode of operation (e.g., 'MODE1', 1)
		:param cost_trajectory: dict or float, {year: cost} or single cost for all years
		"""
		if region not in self.regions:
			raise ValueError(f"Region '{region}' not defined in scenario.")
        
		# Convert mode to string for consistency
		mode = str(mode)
        
		# Convert single value to trajectory
		if isinstance(cost_trajectory, (int, float)):
			cost_trajectory = {y: cost_trajectory for y in self.years}
        
		records = []
		for year in self.years:
			cost = cost_trajectory.get(year, 0)
			if cost < 0:
				raise ValueError(f"Variable cost cannot be negative: {cost} for {technology} in {year}")
			records.append({
				"REGION": region,
				"TECHNOLOGY": technology,
				"MODE_OF_OPERATION": mode,
				"YEAR": year,
				"VALUE": cost
			})
        
		self.variable_cost_df = self.add_to_dataframe(
			self.variable_cost_df, records,
			key_columns=["REGION", "TECHNOLOGY", "MODE_OF_OPERATION", "YEAR"]
		)
    
	def set_fixed_cost(self, region, technology, cost_trajectory):
		"""
		Set fixed annual O&M cost for a technology.
        
		:param region: str, Region identifier
		:param technology: str, Technology identifier
		:param cost_trajectory: dict or float, {year: cost} or single cost for all years
		"""
		if region not in self.regions:
			raise ValueError(f"Region '{region}' not defined in scenario.")
        
		# Convert single value to trajectory
		if isinstance(cost_trajectory, (int, float)):
			cost_trajectory = {y: cost_trajectory for y in self.years}
        
		records = []
		for year in self.years:
			cost = cost_trajectory.get(year, 0)
			if cost < 0:
				raise ValueError(f"Fixed cost cannot be negative: {cost} for {technology} in {year}")
			records.append({
				"REGION": region,
				"TECHNOLOGY": technology,
				"YEAR": year,
				"VALUE": cost
			})
        
		self.fixed_cost_df = self.add_to_dataframe(
			self.fixed_cost_df, records, key_columns=["REGION", "TECHNOLOGY", "YEAR"]
		)
