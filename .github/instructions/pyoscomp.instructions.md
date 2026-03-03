---
applyTo: "pyoscomp/**/*.py"
---
# PyOSComp Comprehensive Development Guide

This document provides comprehensive guidelines for AI agents and developers working on the PyOSComp package. The code in `pyoscomp/translation/time/` serves as the gold standard reference implementation.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Code Architecture Principles](#2-code-architecture-principles)
3. [Style Guide](#3-style-guide)
4. [Documentation Standards](#4-documentation-standards)
5. [Data Structures & Classes](#5-data-structures--classes)
6. [Function Design Patterns](#6-function-design-patterns)
7. [Error Handling](#7-error-handling)
8. [Testing & Validation](#8-testing--validation)
9. [Common Anti-Patterns to Avoid](#9-common-anti-patterns-to-avoid)
10. [Module Organization](#10-module-organization)
11. [Reference Examples](#11-reference-examples)
12. [Improvement Suggestions](#12-improvement-suggestions-for-gold-standard)

---

## 1. Project Overview

PyOSComp is a framework for comparing energy system models, specifically translating between PyPSA and OSeMOSYS formats. The package handles:

- **Scenarios**: (Authoring layer) building and managing model scenarios
- **Interfaces**: (Data transfer layer) immutable, validated data classes for downstream consumption
- **Translation**: Bidirectional conversion of model parameters
- **Input/Output**: Reading and writing model data files

scenario module (mutable)          interfaces module (immutable)
┌──────────────────────┐           ┌──────────────────────────┐
│  TopologyComponent   │           │  OSeMOSYSSets            │
│  TimeComponent       │──build──▶ │  TimeParameters          │
│  DemandComponent     │  +        │  DemandParameters        │
│  SupplyComponent     │  to_      │  SupplyParameters        │
│  PerformanceComponent│  scenario │  PerformanceParameters   │
│  EconomicsComponent  │  data()   │  EconomicsParameters     │
└──────────────────────┘           └──────────┬───────────────┘
                                              │
                                     ScenarioData (frozen)
                                              │
                                   ┌──────────▼───────────────┐
                                   │  Translators / Runners   │
                                   │  (PyPSA, OSeMOSYS, etc.) │
                                   └──────────────────────────┘

### Core Translation Concept

```
PyPSA (Sequential Snapshots) ←→ OSeMOSYS (Hierarchical Timeslices)
```

When developing new translation modules, understand that you're bridging two fundamentally different data paradigms.

---

## 2. Code Architecture Principles

### 2.1 Separation of Concerns

Organize code into distinct modules by responsibility. For example:

```
translation/time/
├── structures.py     # Data classes (domain objects)
├── helpers.py        # Helper functions for specific tasks (algorithms)
├── translate.py      # Transformation logic (algorithms)
└── results.py        # Result containers (output objects)
```

**Pattern**: Each module should have ONE primary responsibility.

### 2.2 Layered Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│  PUBLIC API (translate.py: to_timeslices, to_snapshots)         │
├─────────────────────────────────────────────────────────────────┤
│  RESULT CONTAINERS (results.py: TimesliceResult, SnapshotResult)│
├─────────────────────────────────────────────────────────────────┤
│  DOMAIN OBJECTS (structures.py: DayType, Timeslice, etc.)       │
├─────────────────────────────────────────────────────────────────┤
│  HELPERS (helpers.py: create_daytypes_from_dates, etc.)         │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 Composition Over Inheritance

Prefer composing objects from smaller, focused components:

```python
# GOOD: Timeslice composed of simpler structures
@dataclass
class Timeslice:
    daytype: DayType
    dailytimebracket: DailyTimeBracket
    season: Optional[str] = "X"

# AVOID: Deep inheritance hierarchies for data objects
class Timeslice(TemporalEntity, Validatable, Serializable):  # Too complex
    pass
```

---

## 3. Style Guide

### 3.1 PEP 8 Compliance

- **Indentation**: 4 spaces per level
- **Line length**: Maximum 79 characters (hard limit), prefer 72 for docstrings
- **Blank lines**: 2 between top-level definitions, 1 within classes

### 3.2 Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Module | lowercase_underscore | `time_structures.py` |
| Class | CapitalizedWords | `DailyTimeBracket` |
| Function | lowercase_underscore | `create_daytypes_from_dates` |
| Constant | ALL_CAPS_UNDERSCORE | `HOURS_PER_YEAR` |
| Private | `_single_underscore` | `_validate_internal` |
| Type var | Single capital letter or descriptive | `T`, `TimeSource` |

### 3.3 Import Organization

```python
# 1. Standard library imports
import pandas as pd
import numpy as np
from datetime import time, date, datetime
from typing import List, Set, Dict, Union, Tuple, Optional
from dataclasses import dataclass, field

# 2. Related third-party imports (blank line above)
import pypsa

# 3. Local application imports (blank line above)
from .constants import TOL, ENDOFDAY, hours_in_year
from .structures import DayType, DailyTimeBracket, Timeslice
from ...scenario.components.time import TimeComponent
```

### 3.4 Type Annotations

**Always use type annotations** for function signatures:

```python
# GOOD: Full type annotation with return type
def create_map(
    snapshots: Union[pd.DatetimeIndex, pd.Index],
    timeslices: List[Timeslice]
) -> Dict[pd.Timestamp, List[Tuple[int, Timeslice]]]:
    pass

# AVOID: Missing type hints
def create_map(snapshots, timeslices):
    pass
```

For complex nested types, consider type aliases:

```python
# At module level
TimesliceMapping = Dict[pd.Timestamp, List[Tuple[int, Timeslice]]]

# In function
def create_map(...) -> TimesliceMapping:
    pass
```

---

## 4. Documentation Standards

### 4.1 Module Docstrings

Every module should start with a descriptive docstring:

```python
# pyoscomp/translation/time/structures.py

"""
Time structure definitions for PyPSA-OSeMOSYS translation.

This module provides the core data classes for representing temporal
structures in both frameworks: DailyTimeBracket (time-of-day ranges),
DayType (day-of-year ranges), and Timeslice (combined temporal slices).
"""
```

### 4.2 Function/Method Docstrings (NumPy/Sphinx Style)

Use comprehensive docstrings with these sections **in order**:

```python
def create_timebrackets_from_times(times: List[time]) -> Set[DailyTimeBracket]:
    """
    Create non-overlapping DailyTimeBracket objects from a list of times.
    
    Takes a list of time-of-day values and partitions the 24-hour day into
    non-overlapping brackets. Each input time represents the START of a bracket,
    with the bracket extending until the next time (or end of day for the last bracket).
    
    Parameters
    ----------
    times : List[time]
        List of datetime.time objects representing bracket start times.
        Times will be sorted automatically. If midnight (00:00:00) is not
        included, it will be prepended automatically.
    
    Returns
    -------
    Set[DailyTimeBracket]
        Set of non-overlapping DailyTimeBracket objects that partition the
        24-hour day. Each bracket has half-open interval [start, end), except
        the final bracket which extends to ENDOFDAY (inclusive 23:59:59.999999).
    
    Notes
    -----
    Special handling:
    
    - If the first time is within 1 second of midnight, it's adjusted to 00:00:00
    - If any time is within 1 second of ENDOFDAY (23:59:59.999999), it's adjusted
      and becomes the final bracket
    - The last bracket always extends to ENDOFDAY (inclusive)
    - Duplicate times are automatically removed
    
    The function ensures complete coverage of the 24-hour day with no gaps or overlaps.
    
    Examples
    --------
    Create day/night brackets:
    
    >>> from datetime import time
    >>> times = [time(0, 0), time(6, 0), time(18, 0)]
    >>> brackets = create_timebrackets_from_times(times)
    >>> for b in sorted(brackets):
    ...     print(f"{b.hour_start} - {b.hour_end}: {b.duration_hours():.1f} hours")
    00:00:00 - 06:00:00: 6.0 hours
    06:00:00 - 18:00:00: 12.0 hours
    18:00:00 - 23:59:59.999999: 6.0 hours
    
    Midnight is added automatically:
    
    >>> times = [time(12, 0)]  # Only noon
    >>> brackets = create_timebrackets_from_times(times)
    >>> len(brackets)
    2  # 00:00-12:00 and 12:00-24:00
    
    See Also
    --------
    DailyTimeBracket : The time-of-day range structure created by this function
    create_daytypes_from_dates : Analogous function for creating day-of-year ranges
    """
```

### 4.3 Docstring Section Order

Follow this order (include only relevant sections):

1. **Summary line** (one line, imperative mood: "Create...", "Calculate...")
2. **Extended summary** (paragraph(s) explaining purpose/behavior)
3. **Parameters** (argument descriptions with types)
4. **Returns** (return value description with type)
5. **Raises** (exceptions that may be raised)
6. **Notes** (algorithm details, implementation notes)
7. **Examples** (executable doctest examples)
8. **See Also** (related functions/classes)

### 4.4 Inline Comments

Use sparingly and explain *why*, not *what*:

```python
# GOOD: Explains reasoning
# Use leap year for most inclusive daytype definitions
year = 2000

# AVOID: Explains obvious code
# Set year to 2000
year = 2000
```

---

## 5. Data Structures & Classes

### 5.1 Use Dataclasses for Domain Objects

```python
from dataclasses import dataclass, field

@dataclass
class DailyTimeBracket:
    """
    Time-of-day range structure (day- and year-agnostic).
    
    Represents a bracket within a 24-hour day using half-open interval [start, end),
    except when end=ENDOFDAY which represents inclusive 23:59:59.999999.
    
    Attributes
    ----------
    hour_start : time
        Start time of the bracket (inclusive).
    hour_end : time
        End time of the bracket (exclusive, unless ENDOFDAY).
    name : str, optional
        Bracket name. Auto-generated if not provided (e.g., "T0600_1200").
    """
    hour_start: time
    hour_end: time
    name: str = field(default="")

    def __post_init__(self):
        self.validate()
        if not self.name:
            if self.is_full_day():
                self.name = "DAY"
            else:
                end_str = "2400" if self.hour_end == ENDOFDAY else self.hour_end.strftime('%H%M')
                self.name = f"T{self.hour_start.strftime('%H%M')}_to_{end_str}"
    
    def validate(self):
        """
        Validate hour_start is before hour_end.
        
        Raises
        ------
        ValueError
            If hour_start >= hour_end (excluding ENDOFDAY case).
        """
        if self.hour_end != ENDOFDAY:
            if self.hour_start >= self.hour_end:
                raise ValueError(
                    f"hour_start ({self.hour_start}) must be before hour_end ({self.hour_end})"
                )
```

### 5.2 Implement Comparison Methods for Sorting

```python
def __hash__(self):
    """Compute hash based on defining attributes."""
    return hash((self.hour_start, self.hour_end))

def __eq__(self, other):
    """Check equality based on defining attributes."""
    if not isinstance(other, DailyTimeBracket):
        return False
    return (self.hour_start == other.hour_start and 
            self.hour_end == other.hour_end)

def __lt__(self, other):
    """Enable sorting by start time."""
    if not isinstance(other, DailyTimeBracket):
        return NotImplemented
    return self.hour_start < other.hour_start
```

### 5.3 Result Container Pattern

Create dedicated result classes for complex return values:

```python
@dataclass
class TimesliceResult:
    """
    Container for PyPSA → OSeMOSYS conversion results.
    
    Provides validation, export methods, and encapsulates all conversion outputs.
    """
    years: List[int]
    seasons: Set[Season]
    daytypes: Set[DayType]
    dailytimebrackets: Set[DailyTimeBracket]
    timeslices: List[Timeslice]

    def validate_coverage(self) -> bool:
        """Validate that timeslices partition the year completely."""
        # Implementation...

    def export(self) -> Dict[str, pd.DataFrame]:
        """Generate OSeMOSYS-compatible CSV DataFrames."""
        # Implementation...

    def to_csv(self, output_dir: str) -> None:
        """Write OSeMOSYS-compatible CSV files to output_dir."""
        # Implementation...
```

### 5.4 Properties for Computed Attributes

```python
@property
def name(self) -> str:
    """
    Generate OSeMOSYS-compatible timeslice name.
    
    Returns
    -------
    str
        Format: "Season_DayType_DailyTimeBracket" (e.g., "01_to_01_10_to_15_T0600_to_1200").
    """
    return f"{self.season.name}_{self.daytype.name}_{self.dailytimebracket.name}"
```

---

## 6. Function Design Patterns

### 6.1 Single Responsibility

Each function should do ONE thing well:

```python
# GOOD: Focused functions
def create_timebrackets_from_times(times: List[time]) -> Set[DailyTimeBracket]:
    """Create non-overlapping time brackets from times."""
    pass

def create_daytypes_from_dates(dates: List[date]) -> set[DayType]:
    """Create non-overlapping day types from dates."""
    pass

# AVOID: Monolithic functions that do everything
def process_all_time_data(snapshots, years, seasons, ...):
    # 200 lines doing everything
    pass
```

### 6.2 Public API Functions

Main entry points should be clearly named and well-documented:

```python
def to_timeslices(snapshots: Union[pd.DatetimeIndex, pd.Index, List[pd.Timestamp], List[datetime]]) -> TimesliceResult:
    """
    Convert PyPSA sequential snapshots to OSeMOSYS hierarchical timeslice structure.
    
    This is a main entry point for the translation module.
    """
    # 1. Validate input, convert, and sort
    if len(snapshots) == 0:
        raise ValueError("snapshots cannot be empty")
    try:
        snapshots = pd.DatetimeIndex(pd.to_datetime(snapshots)).sort_values()
    except (TypeError, ValueError) as e:
        raise TypeError(
            f"snapshots must contain datetime-like values. "
            f"If you have date strings, convert them first with pd.to_datetime(). "
            f"Original error: {e}"
        ) from e
    years = sorted(snapshots.year.unique().tolist())
    
    # 2. Initialize containers
    seasons: Set[Season] = set()
    daytypes: Set[DayType] = set()
    dailytimebrackets: Set[DailyTimeBracket] = set()
    
    # 3. Remove time component and create seasons and daytypes from dates
    unique_dates = sorted(set(ts.date() for ts in snapshots))
    seasons = create_seasons_from_dates(unique_dates)
    daytypes = create_daytypes_from_dates(unique_dates)

    # 4. Remove date component and create dailytimebrackets from times
    unique_times = sorted(set(ts.time() for ts in snapshots))
    dailytimebrackets = create_timebrackets_from_times(unique_times)
    
    # 5. Create timeslice for each combination
    # ...

    if not result.validate_coverage():
        raise ValueError(
            "Timeslice structure does not cover the entire year"
        )

    return result
```

### 6.3 Use Clear Step Comments

```python
def to_timeslices(snapshots):
    # 1. Validate input, convert, and sort
    if len(snapshots) == 0:
        raise ValueError("snapshots cannot be empty")
    snapshots = pd.DatetimeIndex(pd.to_datetime(snapshots)).sort_values()
    years = sorted(snapshots.year.unique().tolist())
    
    # 2. Initialize containers
    daytypes: Set[DayType] = set()
    dailytimebrackets: Set[DailyTimeBracket] = set()
    
    # 3. Remove time component and create daytypes from dates
    unique_dates = sorted(set(ts.date() for ts in snapshots))
    daytypes = create_daytypes_from_dates(unique_dates)
    
    # 4. Remove date component and create dailytimebrackets from times
    unique_times = sorted(set(ts.time() for ts in snapshots))
    dailytimebrackets = create_timebrackets_from_times(unique_times)
    
    # 5. Create timeslice for each combination
    # ...
```

### 6.4 Accept Multiple Input Types

Use `Union` to accept flexible inputs, then normalize internally:

```python
def to_snapshots(
    source: Union[TimeComponent, str],
    multi_investment_periods: bool = True
) -> SnapshotResult:
    """Accept either a TimeComponent object or a path string."""
    
    # Normalize input to consistent type
    if isinstance(source, str):
        time_component = TimeComponent(source)
        time_component.load()
    elif isinstance(source, TimeComponent):
        time_component = source
    else:
        raise TypeError(
            f"source must be TimeComponent or str, got {type(source)}"
        )
    
    # Continue with normalized data...
```

---

## 7. Error Handling

### 7.1 Validate Early, Fail Fast

```python
def to_timeslices(snapshots):
    # Validate at entry point
    if len(snapshots) == 0:
        raise ValueError("snapshots cannot be empty")
    
    # Don't wait until deep in processing to discover bad input
```

### 7.2 Use Specific Exception Types

```python
# GOOD: Specific exception with context
raise ValueError(
    f"hour_start ({self.hour_start}) must be before hour_end ({self.hour_end})"
)

# GOOD: TypeError for wrong argument types
raise TypeError(
    f"source must be TimeComponent or str path, got {type(source)}"
)

# AVOID: Generic exceptions
raise Exception("Something went wrong")
```

### 7.3 Informative Error Messages

Include context in error messages:

```python
# GOOD: Provides debugging context
if diff_seconds > 1:
    raise ValueError(
        f"Mismatch! snapshot duration = {snapshot_timedelta}, "
        f"timeslice duration = {total_timedelta}"
        f"\n(year, timeslice) pairs = {[(y, timeslices[j]) for (y, j) in idx_list]}"
    )

# AVOID: Vague error
raise ValueError("Duration mismatch")
```

### 7.4 Validation Methods

Provide explicit validation in result containers:

```python
def validate_coverage(self) -> bool:
    """Validate that timeslices partition the year completely."""
    for year in self.years:
        total_hours = sum(
            ts.duration_hours(year) 
            for ts in self.timeslices
        )
        expected_hours = hours_in_year(year)
        if abs(total_hours - expected_hours) > TOL:
            return False
    return True
```

---

## 8. Testing & Validation

To test any code on the terminal, first activate the correct python environment:

```bash
source /Users/as4623/pypsa-playground/.venv/bin/activate
```

### 8.1 Built-in Validation

Always validate that transformations preserve invariants:

```python
result = TimesliceResult(...)

if not result.validate_coverage():
    raise ValueError(
        "Timeslice structure does not cover the entire year"
    )
```

### 8.2 Use Tolerance Constants

```python
# constants.py
TOL = 1e-8  # tolerance for floating point comparisons

# Usage
if abs(total_hours - expected_hours) > TOL:
    return False
```

### 8.3 Doctest Examples

Include executable examples in docstrings:

```python
def create_timebrackets_from_times(times: List[time]) -> Set[DailyTimeBracket]:
    """
    Examples
    --------
    Create day/night brackets:
    
    >>> from datetime import time
    >>> times = [time(0, 0), time(6, 0), time(18, 0)]
    >>> brackets = create_timebrackets_from_times(times)
    >>> for b in sorted(brackets):
    ...     print(f"{b.hour_start} - {b.hour_end}: {b.duration_hours():.1f} hours")
    00:00:00 - 06:00:00: 6.0 hours
    06:00:00 - 18:00:00: 12.0 hours
    18:00:00 - 23:59:59.999999: 6.0 hours
    """
```

---

## 9. Common Anti-Patterns to Avoid

### 9.1 ❌ Avoid Wildcard Imports

```python
# AVOID
from datetime import *
from .structures import *

# GOOD
from datetime import time, date, datetime
from .structures import DayType, DailyTimeBracket, Timeslice
```

### 9.2 ❌ Avoid Deep Nesting

```python
# AVOID: Deeply nested logic
for year in years:
    for dt in daytypes:
        for dtb in dailytimebrackets:
            if condition1:
                if condition2:
                    if condition3:
                        # Hard to follow

# GOOD: Extract to helper functions, use early returns
def process_timeslice(year, dt, dtb):
    if not condition1:
        return None
    if not condition2:
        return None
    return result
```

### 9.3 ❌ Avoid Magic Numbers

```python
# AVOID
if diff_seconds > 1:  # What is 1?
    pass

# GOOD
TOLERANCE_SECONDS = 1  # Maximum allowed mismatch
if diff_seconds > TOLERANCE_SECONDS:
    pass
```

### 9.4 ❌ Avoid Mutable Default Arguments

```python
# AVOID: Mutable default
def process(items: List[str] = []):  # Bug!
    items.append("new")
    return items

# GOOD: Use None and create inside
def process(items: List[str] = None):
    items = items or []
    items.append("new")
    return items

# OR use dataclass field factory
seasons: Set[str] = field(default_factory=lambda: set("X"))
```

### 9.5 ❌ Avoid Overly Long Functions

Functions over 50 lines are candidates for decomposition.

### 9.6 ❌ Avoid Inconsistent Return Types

```python
# AVOID: Sometimes returns None, sometimes raises
def find_timeslice(name):
    for ts in timeslices:
        if ts.name == name:
            return ts
    # Implicit return None - confusing

# GOOD: Be explicit
def find_timeslice(name) -> Optional[Timeslice]:
    """Return timeslice with given name, or None if not found."""
    for ts in timeslices:
        if ts.name == name:
            return ts
    return None

# OR raise if absence is exceptional
def get_timeslice(name) -> Timeslice:
    """Return timeslice with given name. Raises KeyError if not found."""
    for ts in timeslices:
        if ts.name == name:
            return ts
    raise KeyError(f"No timeslice named '{name}'")
```

---

## 10. Module Organization

### 10.1 `__init__.py` Pattern

Export all public API elements:

```python
# pyoscomp/translation/time/__init__.py

"""
Time translation handling submodule for PyPSA-OSeMOSYS Comparison Framework.
"""

from .structures import Season, DayType, DailyTimeBracket, Timeslice
from .translate import to_timeslices, to_snapshots
from .results import TimesliceResult, SnapshotResult
from .helpers import create_daytypes_from_dates, create_timebrackets_from_times, create_seasons_from_dates

__all__ = [
    # Structures
    'Season',
    'DayType', 
    'DailyTimeBracket', 
    'Timeslice', 
    # Results
    'TimesliceResult',
    'SnapshotResult',
    # Functions
    'to_timeslices',
    'to_snapshots',
    # Helpers
    'create_seasons_from_dates',
    'create_daytypes_from_dates',
    'create_timebrackets_from_times'
]
```

### 10.2 File Headers

Start each file with module path comment:

```python
# pyoscomp/translation/time/structures.py

"""Module docstring here."""
```

---

## 11. Reference Examples

### 11.1 Complete Dataclass Example

See `structures.py` → `DailyTimeBracket`:

```python
@dataclass
class DailyTimeBracket:
    """
    Time-of-day range structure (day- and year-agnostic).
    
    Represents a bracket within a 24-hour day using half-open interval [start, end),
    except when end=ENDOFDAY which represents inclusive 23:59:59.999999.
    
    Attributes
    ----------
    hour_start : time
        Start time of the bracket (inclusive).
    hour_end : time
        End time of the bracket (exclusive, unless ENDOFDAY).
    name : str, optional
        Bracket name. Auto-generated if not provided (e.g., "T0600_1200").
    """
    hour_start: time
    hour_end: time
    name: str = field(default="")

    def __post_init__(self):
        self.validate()
        if not self.name:
            if self.is_full_day():
                self.name = "DAY"
            else:
                end_str = "24:00" if self.hour_end == ENDOFDAY else self.hour_end.strftime('%H%M')
                self.name = f"T{self.hour_start.strftime('%H%M')}_{end_str}"
    
    def validate(self):
        """Validate hour_start is before hour_end."""
        if self.hour_end != ENDOFDAY:
            if self.hour_start >= self.hour_end:
                raise ValueError(
                    f"hour_start ({self.hour_start}) must be before hour_end ({self.hour_end})"
                )

    def is_full_day(self) -> bool:
        """Check if bracket covers full 24-hour day."""
        return (self.hour_start == time(0, 0, 0) and 
                self.hour_end == ENDOFDAY)
    
    def contains_time(self, t: time) -> bool:
        """Check if a time falls within this bracket."""
        if self.hour_end == ENDOFDAY:
            return self.hour_start <= t
        return self.hour_start <= t < self.hour_end
    
    def duration_hours(self) -> float:
        """Calculate bracket duration in hours."""
        start_seconds = (self.hour_start.hour * 3600 + 
                        self.hour_start.minute * 60 + 
                        self.hour_start.second)
        if self.hour_end == ENDOFDAY:
            end_seconds = 24 * 3600
        else:
            end_seconds = (self.hour_end.hour * 3600 + 
                          self.hour_end.minute * 60 + 
                          self.hour_end.second)
        return (end_seconds - start_seconds) / 3600
    
    def __hash__(self):
        return hash((self.hour_start, self.hour_end))
    
    def __eq__(self, other):
        if not isinstance(other, DailyTimeBracket):
            return False
        return (self.hour_start == other.hour_start and 
                self.hour_end == other.hour_end)
    
    def __lt__(self, other):
        if not isinstance(other, DailyTimeBracket):
            return NotImplemented
        return self.hour_start < other.hour_start
```

### 11.2 Complete Public Function Example

See `translate.py` → `to_timeslices`:

```python
def to_timeslices(snapshots: Union[pd.DatetimeIndex, pd.Index, List[pd.Timestamp], List[datetime]]) -> TimesliceResult:
    """
    Convert PyPSA sequential snapshots to OSeMOSYS hierarchical timeslice structure.
    
    Transforms PyPSA's datetime-based sequential representation into OSeMOSYS's
    categorical hierarchical structure (seasons/daytypes/dailytimebrackets/timeslices).
    The conversion preserves temporal coverage and duration weightings.
    
    Parameters
    ----------
    snapshots : pd.DatetimeIndex or pd.Index or List[pd.Timestamp] or List[datetime]
        PyPSA snapshot timestamps. Must contain datetime-like values that can be
        converted to pd.DatetimeIndex. The function extracts unique dates and times
        to construct the OSeMOSYS time structure.

        - **pd.DatetimeIndex**: Native PyPSA format (recommended)
        - **pd.Index**: Will be converted if contains datetime-parseable values
        - **List[pd.Timestamp]**: List of pandas Timestamp objects
        - **List[datetime]**: List of Python datetime objects
    
    Returns
    -------
    TimesliceResult
        Container with hierarchical timeslice structure and mapping from snapshots
        to timeslices. Includes methods for validation and CSV export.
    
    Raises
    ------
    ValueError
        If snapshots is empty.
    ValueError
        If timeslice structure does not cover the entire year (validation fails).
        This can occur if snapshots have gaps or inconsistent temporal coverage.
    TypeError
        If snapshots contains non-datetime objects or cannot be converted.
    
    Notes
    -----
    Conversion algorithm:
    
    1. **Extract years**: Identify unique years from snapshot timestamps
    2. **Create Seasons**: Group snapshot dates into non-overlapping month(s)-of-year ranges
    3. **Create DayTypes**: Group snapshot dates into non-overlapping day(s)-of-month(s) ranges
    4. **Create DailyTimeBrackets**: Group snapshot times into non-overlapping time-of-day ranges
    5. **Form Timeslices**: Create cartesian product of Seasons x DayTypes × DailyTimeBrackets
    6. **Validate**: Ensure timeslices partition each year completely (sum to 8760/8784 hours)
    
    The resulting structure uses:
    
    - Seasons capturing month(s)-of-year granularity from snapshot dates
    - DayTypes capturing day(s)-of-month(s) granularity from snapshot dates
    - DailyTimeBrackets capturing time-of-day granularity from snapshot times
    
    Performance considerations:
    
    - Memory: O(n_dates × n_times) timeslices created
    - Time complexity: O(n_snapshots × n_timeslices) for mapping
    
    Examples
    --------
    Convert hourly snapshots for one year:
    
    >>> snapshots = pd.date_range('2025-01-01', periods=8760, freq='H')
    >>> result = to_timeslices(snapshots)
    >>> print(f"Created {len(result.timeslices)} timeslices")
    Created 8928 timeslices
    # Creates 12 Seasons, 31 DayTypes, 24 DailyTimeBrackets
    # Note that some Timeslices will have no duration
    >>> print(f"Years: {result.years}")
    Years: [2025]
    >>> result.validate_coverage()
    True
    
    Convert daily snapshots (two time-of-day samples per day):
    
    >>> snapshots = pd.DatetimeIndex([
    ...     '2025-01-01 06:00', '2025-01-01 18:00',
    ...     '2025-01-02 06:00', '2025-01-02 18:00',
    ...     # ... continue for full year
    ... ])
    >>> result = to_timeslices(snapshots)
    >>> print(f"Years: {result.years}")
    Years: [2025]
    >>> print(f"Seasons: {len(result.seasons)}")
    Seasons: 12  # One per month
    >>> print(f"DayTypes: {len(result.daytypes)}")
    DayTypes: 31  # One per day in longest month
    >>> print(f"DailyTimeBrackets: {len(result.dailytimebrackets)}")
    DailyTimeBrackets: 3  # 00:00 to 06:00, 06:00 to 18:00, 18:00-ENDOFDAY
    >>> print(f"Timeslices: {len(result.timeslices)}")
    Timeslices: 1116
    
    Export to OSeMOSYS CSV files:
    
    >>> result = to_timeslices(snapshots)
    >>> csv_dict = result.export()
    >>> import os
    >>> os.makedirs('osemosys_scenario', exist_ok=True)
    >>> for filename, df in csv_dict.items():
    ...     df.to_csv(f'osemosys_scenario/{filename}.csv', index=False)
    >>> print(f"Created {len(csv_dict)} CSV files")
    Created 11 CSV files
    
    Multi-year conversion:
    
    >>> snapshots = pd.date_range('2026-01-01', '2028-12-31', freq='D')
    >>> result = to_timeslices(snapshots)
    >>> print(f"Years: {result.years}")
    Years: [2026, 2027, 2028]
    >>> for year in result.years:
    ...     timeslices = result.timeslices
    ...     total_hours = sum(ts.duration_hours(year) for ts in timeslices)
    ...     print(f"{year}: {total_hours:.0f} hours")
    2026: 8760 hours
    2027: 8760 hours
    2028: 8784 hours
    
    See Also
    --------
    to_snapshots : Convert OSeMOSYS timeslices to PyPSA snapshots (inverse operation)
    TimesliceResult : Container class for conversion results
    create_seasons_from_dates : Helper for creating month(s)-of-year ranges
    create_daytypes_from_dates : Helper for creating day(s)-of-month(s) ranges
    create_timebrackets_from_times : Helper for creating time-of-day ranges
    Season : Month(s)-of-year range structure
    DayType : Day(s)-of-month(s) range structure
    DailyTimeBracket : Time-of-day range structure
    Timeslice : Combined temporal slice structure
    """
    # 1. Validate input, convert, and sort
    if len(snapshots) == 0:
        raise ValueError("snapshots cannot be empty")
    try:
        snapshots = pd.DatetimeIndex(pd.to_datetime(snapshots)).sort_values()
    except (TypeError, ValueError) as e:
        raise TypeError(
            f"snapshots must contain datetime-like values. "
            f"If you have date strings, convert them first with pd.to_datetime(). "
            f"Original error: {e}"
        ) from e
    years = sorted(snapshots.year.unique().tolist())
    
    # 2. Initialize containers
    seasons: Set[Season] = set()
    daytypes: Set[DayType] = set()
    dailytimebrackets: Set[DailyTimeBracket] = set()
    
    # 3. Remove time component and create seasons and daytypes from dates
    unique_dates = sorted(set(ts.date() for ts in snapshots))
    seasons = create_seasons_from_dates(unique_dates)
    daytypes = create_daytypes_from_dates(unique_dates)

    # 4. Remove date component and create dailytimebrackets from times
    unique_times = sorted(set(ts.time() for ts in snapshots))
    dailytimebrackets = create_timebrackets_from_times(unique_times)
    
    # 5. Create timeslice for each combination
    timeslices = []
    for s in sorted(seasons):
        for dt in sorted(daytypes):
            for dtb in sorted(dailytimebrackets):
                    ts = Timeslice(
                        season=s,
                        daytype=dt,
                        dailytimebracket=dtb,
                    )
                    timeslices.append(ts)
    
    result = TimesliceResult(
        years=years,
        seasons=seasons,
        daytypes=daytypes,
        dailytimebrackets=dailytimebrackets,
        timeslices=timeslices,
    )

    if not result.validate_coverage():
        raise ValueError(
            "Timeslice structure does not cover the entire year"
        )

    return result
```

---

## Summary Checklist

Before submitting code, verify:

- [ ] All functions have type annotations
- [ ] All public functions have NumPy-style docstrings with Parameters, Returns, Examples
- [ ] Imports are organized (stdlib → third-party → local)
- [ ] No wildcard imports
- [ ] Constants are UPPER_CASE and documented
- [ ] Dataclasses implement `__hash__`, `__eq__`, `__lt__` if needed for collections
- [ ] Error messages include relevant context
- [ ] Validation happens early (fail fast)
- [ ] Complex return values use result container classes
- [ ] Code follows numbered step comments for complex algorithms
- [ ] `__init__.py` exports all public API elements with `__all__`
- [ ] No shadowing of built-in names (`map`, `list`, `type`, etc.)