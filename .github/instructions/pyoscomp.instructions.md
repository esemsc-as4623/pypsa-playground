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

- **Translation**: Bidirectional conversion of model parameters
- **Scenarios**: Building and managing model scenarios
- **Input/Output**: Reading and writing model data files

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
├── constants.py      # Immutable values, tolerance settings
├── structures.py     # Data classes (domain objects)
├── translate.py      # Transformation logic (algorithms)
├── results.py        # Result containers (output objects)
└── visualize.py      # Presentation logic (optional)
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
│  HELPERS (translate.py: create_daytypes_from_dates, etc.)       │
├─────────────────────────────────────────────────────────────────┤
│  CONSTANTS (constants.py: TOL, ENDOFDAY, etc.)                  │
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
def create_daytypes_from_dates(dates: List[date]) -> set[DayType]:
    """
    Create non-overlapping DayType objects from a list of dates.
    
    Takes a list of calendar dates and partitions the year into non-overlapping
    day-of-year ranges. Each input date represents a SINGLE DAY DayType, with
    gaps between dates filled by range DayTypes.
    
    Parameters
    ----------
    dates : List[date]
        List of datetime.date objects representing specific days of interest.
        Dates will be normalized to year 2000 (leap year) and sorted automatically.
    
    Returns
    -------
    Set[DayType]
        Set of DayType objects that partition the year (Jan 1 - Dec 31).
        Includes:
        
        - Single-day DayTypes for each input date
        - Range DayTypes for gaps between consecutive dates
        - Boundary DayTypes for start/end of year if needed
    
    Raises
    ------
    ValueError
        If dates list is empty.
    
    Notes
    -----
    Algorithm details:
    
    - All dates are normalized to year 2000 (leap year) for maximum inclusivity
    - Each input date becomes a 1-day DayType
    
    Examples
    --------
    Create DayTypes from specific dates:
    
    >>> from datetime import date
    >>> dates = [date(2025, 1, 1), date(2025, 6, 1)]
    >>> daytypes = create_daytypes_from_dates(dates)
    >>> for dt in sorted(daytypes):
    ...     print(f"{dt.name}: {dt.duration_days(2025)} days")
    
    See Also
    --------
    DayType : The day-of-year range structure created by this function
    create_timebrackets_from_times : Analogous function for time-of-day ranges
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
        Bracket name. Auto-generated if not provided.
    """
    hour_start: time
    hour_end: time
    name: str = field(default="")

    def __post_init__(self):
        self.validate()
        if not self.name:
            self._generate_name()
    
    def validate(self):
        """Validate hour_start is before hour_end."""
        if self.hour_end != ENDOFDAY and self.hour_start >= self.hour_end:
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
    daytypes: Set[DayType]
    dailytimebrackets: Set[DailyTimeBracket]
    timeslices: List[Timeslice]
    snapshot_to_timeslice: Dict[pd.Timestamp, List[Tuple[int, Timeslice]]]
    seasons: Set[str] = field(default_factory=lambda: set("X"))

    def validate_coverage(self) -> bool:
        """Validate that timeslices partition the year completely."""
        # Implementation...

    def export(self) -> Dict[str, pd.DataFrame]:
        """Generate OSeMOSYS-compatible CSV DataFrames."""
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
        Format: "Season_DayType_DailyTimeBracket"
    """
    return f"{self.season}_{self.daytype.name}_{self.dailytimebracket.name}"
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

def create_map(snapshots, timeslices) -> Dict:
    """Map snapshots to timeslices."""
    pass

# AVOID: Monolithic functions that do everything
def process_all_time_data(snapshots, years, seasons, ...):
    # 200 lines doing everything
    pass
```

### 6.2 Public API Functions

Main entry points should be clearly named and well-documented:

```python
def to_timeslices(snapshots: Union[pd.DatetimeIndex, pd.Index]) -> TimesliceResult:
    """
    Convert PyPSA sequential snapshots to OSeMOSYS hierarchical timeslice structure.
    
    This is a main entry point for the translation module.
    """
    # 1. Validate input
    if len(snapshots) == 0:
        raise ValueError("snapshots cannot be empty")
    
    # 2. Normalize input
    snapshots = pd.DatetimeIndex(pd.to_datetime(snapshots)).sort_values()
    
    # 3. Process using helper functions
    daytypes = create_daytypes_from_dates(unique_dates)
    dailytimebrackets = create_timebrackets_from_times(unique_times)
    
    # 4. Compose result
    result = TimesliceResult(...)
    
    # 5. Validate output
    if not result.validate_coverage():
        raise ValueError("Validation failed")
    
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
    
    # 6. Map snapshots to timeslices
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

Functions over 50 lines are candidates for decomposition. The `create_map` function at ~70 lines is at the upper limit.

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

from .constants import TOL, TIMEPRECISION, ENDOFDAY, is_leap_year, hours_in_year
from .structures import DayType, DailyTimeBracket, Timeslice
from .translate import to_timeslices, to_snapshots
from .results import TimesliceResult, SnapshotResult

__all__ = [
    # Constants
    'TOL',
    'TIMEPRECISION',
    'ENDOFDAY',
    # Structures
    'DayType', 
    'DailyTimeBracket', 
    'Timeslice', 
    # Results
    'TimesliceResult',
    'SnapshotResult',
    # Functions
    'to_timeslices',
    'to_snapshots',
    # Utilities
    'is_leap_year',
    'hours_in_year',
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
def to_timeslices(snapshots: Union[pd.DatetimeIndex, pd.Index]) -> TimesliceResult:
    """
    Convert PyPSA sequential snapshots to OSeMOSYS hierarchical timeslice structure.
    
    Parameters
    ----------
    snapshots : pd.DatetimeIndex or pd.Index
        PyPSA snapshot timestamps.
    
    Returns
    -------
    TimesliceResult
        Container with hierarchical timeslice structure and mapping.
    
    Raises
    ------
    ValueError
        If snapshots is empty or validation fails.
    
    Examples
    --------
    >>> snapshots = pd.date_range('2025-01-01', periods=8760, freq='H')
    >>> result = to_timeslices(snapshots)
    >>> result.validate_coverage()
    True
    """
    # 1. Validate input, convert, and sort
    if len(snapshots) == 0:
        raise ValueError("snapshots cannot be empty")
    snapshots = pd.DatetimeIndex(pd.to_datetime(snapshots)).sort_values()
    years = sorted(snapshots.year.unique().tolist())
    
    # 2. Initialize containers
    daytypes: Set[DayType] = set()
    dailytimebrackets: Set[DailyTimeBracket] = set()
    seasons: Set[str] = set("X")
    
    # 3. Remove time component and create daytypes from dates
    unique_dates = sorted(set(ts.date() for ts in snapshots))
    daytypes = create_daytypes_from_dates(unique_dates)

    # 4. Remove date component and create dailytimebrackets from times
    unique_times = sorted(set(ts.time() for ts in snapshots))
    dailytimebrackets = create_timebrackets_from_times(unique_times)
    
    # 5. Create timeslice for each combination
    timeslices = []
    for dt in sorted(daytypes):
        for dtb in sorted(dailytimebrackets):
            ts = Timeslice(
                season="X",
                daytype=dt,
                dailytimebracket=dtb,
            )
            timeslices.append(ts)
    
    # 6. Map snapshots to timeslices
    map = create_map(snapshots, timeslices)
    
    result = TimesliceResult(
        years=years,
        seasons=seasons,
        daytypes=daytypes,
        dailytimebrackets=dailytimebrackets,
        timeslices=timeslices,
        snapshot_to_timeslice=map,
    )

    if not result.validate_coverage():
        raise ValueError("Timeslice structure does not cover the entire year")

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