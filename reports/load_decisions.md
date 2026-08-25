# Load Decisions

1.Transactions with unknown agents were rejected to keep the foreign key valid.

2.Transactions with invalid dates were rejected because `txn_ts` is required.

3.The load was run twice. The row counts stayed the same:
- Agents: 1250
- Services: 18
- Transactions: 192564
This proves the load is idempotent.