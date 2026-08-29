# skye8-ds-nahbila-faith

Loads agents, services and transactions csvs into postgres, answers business questions in sql and pandas.

## setup

1. clone the repo
2. install requirements
```
pip install -r requirements.txt
```
3. create a .env file in the project root
```
DATABASE_URL=postgresql://username:password@localhost:5432/skye8
```
4. database used: TODO - confirm postgres local or supabase
5. build the tables
```
psql "$DATABASE_URL" -f sql/schema.sql
```
6. put the csvs in data/raw/, not committed

## running the loader

```
python src/load.py
```

prints row counts when done. safe to run twice, already loaded rows get skipped not duplicated, see reports/load_decisions.md

## customer_msisdn

full phone number is never stored, only the last 4 digits are kept, rest is masked with X's

## data cleaning

see reports/load_decisions.md and reports/data_quality.md for what got rejected and why

## memory reduction

joined table (transactions + agents + services with rank and division share added) reduced using category dtype and downcasting

before: 122,547,572 bytes (116.9 MB)
after: 39,268,507 bytes (37.4 MB)
reduction: 67.96%

full before/after output is in notebooks/stage_e_verification.ipynb

## tests

```
pytest tests/test_cleaning.py -v
```

13 tests on the cleaning functions in src/cleaning.py, includes a test proving the load is idempotent

## repo structure

```
data/         raw csvs
src/          load.py, cleaning.py
sql/          schema.sql, exercises.sql, analytics.sql,GroupByComparison
notebooks/    pandas verification work
tests/        pytest tests
reports/      load_decisions.md, data-quality.md, conflict-note.md
```