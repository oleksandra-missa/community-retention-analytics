# Project rules for Claude Code

## About the project
Portfolio project: newcomer retention in Simple English Wikipedia, using the Wikimedia
MediaWiki history dumps. The goal is a clear, reproducible analysis that a hiring manager
at a tech company can follow.

## Stack
- Python 3.12, virtual environment in `.venv`
- DuckDB database at `data/wiki.duckdb`
- SQL for transformations, pandas for analysis, Streamlit for the dashboard

## Data layers
- `data/raw/`: the downloaded dump file. Never modify it.
- `raw_events`: the dump loaded into DuckDB unchanged (all 78 columns). Never modify it.
- Cleaned and modeled tables are built from `raw_events` by scripts, never edited by hand.

## Analytical rules
- Cleaning rules and metric definitions are decided by the project owner.
  Propose options with their impact (rows, editors and edits affected); don't pick silently.
- Every decision goes in the "Data decisions" table in `docs/data_decisions.md`.
- Report row counts before and after every filtering step.

## Privacy
- Identify editors by numeric ID only. Never show usernames or IP addresses in
  results, notebooks, the dashboard or commits.

## Code conventions
- Readable code over clever code: comments explain *why*.
- snake_case for columns, tables and files.
- Never commit data files or the DuckDB database. The one exception is the dashboard's summary tables in
  `dashboard/data/` (counts by year and group, no account IDs), built by `pipeline/build_dashboard_data.py`.

## Where files go
- `pipeline/` builds the data, `analysis/` studies it (`notebooks/`, and `profiling/` for the scripts behind the
  data decisions), `dashboard/` shows it, `docs/` explains it.
