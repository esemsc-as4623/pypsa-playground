# Debugging
- Representation mismatch
    - check duration of snapshot (with endpoints)
    - check duration of timeslices (with specific year)
    - compare

# PyTest
E. Integration Tests (test_to_timeslices.py)
By snapshot patterns:

Hourly snapshots (single day)
Hourly snapshots (multiple days)
Daily snapshots (consecutive)
Daily snapshots (gapped)
Annual snapshots (multi-year, gapped)
Mixed times (00:00, 12:00, etc.)
Timeslice count validation:

Verify number of daytypes created
Verify number of timebrackets created
Verify total timeslices = daytypes × timebrackets

F. Validation Tests (test_validation.py)
Property-based invariants:

Coverage: Sum of all timeslice hours = hours in year (for each year)
Mapping consistency: Snapshot duration = sum of mapped timeslice durations
No duplicates: Each timeslice index appears once per snapshot mapping
Completeness: Every snapshot has at least one mapped timeslice