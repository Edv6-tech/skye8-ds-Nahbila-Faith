# Data Quality Report

Totals: 1,055/1,290 agents loaded, 18/18 services loaded, 160,285/214,816 transactions loaded, 54,411 rejected.

1. Duplicate ids in all 3 files, kept the first one and dropped the rest.

2. 235 agents dropped for a bad registration date or a missing float limit.

3. 21,493 transactions dropped for a date that couldn't be read, about 10% of the file. Still need to sample the raw values to see why so many failed.

4. 1,927 transactions dropped for a missing amount or fee.

5. 30,991 transactions dropped for pointing to an agent that doesn't exist anymore. Most of these aren't a separate problem, they're transactions that belonged to the 235 agents already dropped in point 2.

6. 0 transactions dropped for an unknown service, that data was clean.

7. Customer phone numbers are masked, only the last 4 digits are kept, so they can't be used to identify or contact anyone.

8. Cohort retention for the most recent 2-3 registration months looks noisy (goes up instead of down for month 4-6), probably because those cohorts don't have a full 6 months of data yet in this snapshot. Worth treating those months with caution.