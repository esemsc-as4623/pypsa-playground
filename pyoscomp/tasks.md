# Set-up
[] initialize REGION.csv
    [] one
    [] multiple N
    [] list of strings
[] initialize YEAR.csv
    [] one (current)
    [] all in range (with open/closed bounds)
    [] every X in range
[] initialize SEASON.csv
    [] one
    [] multiple N
    [] list of strings
    [] non-uniform split?
[] initialize DAYTYPE.csv
    [] one
    [] multiple N
    [] list of strings
    [] non-uniform split?
[] initialize DAILYTIMEBRACKET.csv
    [] one
    [] every hour
    [] every X hours
    [] list of time bounds
[] initialize TIMESLICE.csv
    [] non-uniform?
[] initialize 

# OSeMOSYS to PyPSA
[x] create buses from REGION
[x] create snapshots from YEAR, SEASONS, DAYTYPE, DAILYTIMEBRACKET
[x] create snapshots from TIMESLICE
[x] create demand from SPECIFIEDANNUALDEMAND
[x] create demand from SPECIFIEDDEMANDPROFILE
[] create demand from ACCUMULATEDANNUALDEMAND
[] create supply from 
