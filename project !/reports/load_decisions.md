# Load Decisions

- Transactions with unknown agents or unknown services were rejected to keep foreign keys valid
- Transactions with invalid dates were rejected because `txn_ts` is required
- Agents with missing float limits or bad registration dates were rejected before transactions were checked against them
- The load was run twice and gave the same row counts both times, proving it's idempotent
- Customer phone numbers were masked, keeping only the last 4 digits