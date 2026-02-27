from abc import ABC, abstractmethod

# The Interface
class CalculationRule(ABC):
    @abstractmethod
    def apply(self, base_value, years):
        pass

# Implementation 1: Constant Value
class ConstantRule(CalculationRule):
    def apply(self, base_value, years):
        return {year: base_value for year in years}

# Implementation 2: Linear Growth
class LinearGrowthRule(CalculationRule):
    def __init__(self, growth_rate):
        self.growth_rate = growth_rate

    def apply(self, base_value, years):
        data = {}
        current = base_value
        for year in years:
            data[year] = current
            current += self.growth_rate
        return data
    
# Implementation 3: Exponential Growth
class ExponentialGrowthRule(CalculationRule):
    def __init__(self, growth_rate):
        self.growth_rate = growth_rate

    def apply(self, base_value, years):
        data = {}
        for year in years:
            data[year] = base_value * ((1 + self.growth_rate) ** (year - years[0]))
        return data