# Why Do Newcomers Leave? Newcomer Retention in an Online Community

A product analytics study of how a real online community, **Simple English Wikipedia**, gains and loses
its new members. Built on the full public edit history (2001–2026).

## Why this question

Every community-driven product has to get new users to stay, from social networks to open-source projects and Wikipedia.
Most newcomers make a few contributions and leave. This project measures **how many stay, when they leave,
and which early experiences make a difference**, then turns that into recommendations a product team can test.

## Questions

| # | Question | Method |
|---|---|---|
| 1 | How many new accounts make a 1st, 5th and 50th edit? | Activation funnel |
| 2 | What share of each year's newcomers is still editing in the second month and in months 3–6? Is it changing over the years? | Cohort retention |
| 3 | Are newcomers whose first edits are reverted less likely to stay? Does editing on mobile matter? | Retention drivers |
| 4 | How concentrated is the work? What share of edits comes from the most active 1% of editors? | Community health metrics |
| 5 | How would we test a feature that might help, such as a welcome message? | A/B test design |

## What's in this project

- Download the edit history and load it into DuckDB (15.2M events, 2001–2026)
- Profile the data and decide on cleaning rules (bots, anonymous editors, deleted pages)
- Write a [metrics definitions document](docs/metrics_definitions.md): what counts as "active", "retained" and "reverted"

## Data

[MediaWiki history dumps](https://dumps.wikimedia.org/other/mediawiki_history/readme.html) from the
Wikimedia Foundation (snapshot 2026-10, `simplewiki`). Every edit, page event and user account event
in the wiki's history, one row per event, with 78 columns. Column documentation is
[on Wikitech](https://wikitech.wikimedia.org/wiki/Data_Platform/Data_Lake/Edits/MediaWiki_history_dumps).

Key fields for this project:

| Field | Meaning |
|---|---|
| `event_entity`, `event_type` | What happened, e.g. `revision` + `create` is an edit, `user` + `create` is a new account |
| `event_timestamp` | When it happened |
| `event_user_id` | Who did it (editors are identified by ID only in this analysis) |
| `event_user_is_bot_by`, `event_user_is_permanent` | Whether the editor is a bot and whether they have a registered account |
| `page_namespace_historical` | Where the edit was made: articles, talk pages, user pages, etc. |
| `revision_is_identity_reverted` | Whether another editor later undid this edit |
| `revision_tags` | Edit labels, such as `mobile edit` |

**Ethics:** the data is public, but the analysis is about patterns, not individuals. Editors appear only as
numeric IDs in results and the dashboard, never by username.

## Stack

| Layer | Tool |
|---|---|
| Storage and querying | DuckDB + SQL |
| Analysis | Python (pandas, Jupyter) |
| Dashboard | Streamlit |

## Project structure

```
├── data/              # raw download and the DuckDB database (not in git)
├── pipeline/
│   ├── load_data.py   # downloads the dump and loads it into DuckDB
│   └── columns.csv    # the dump's 78 column names and types, from the official docs
├── analysis/
│   └── profiling/   # scripts that compare the options behind each data decision and measure their impact
├── docs/
│   └── metrics_definitions.md   # exact definitions of every metric
└── AI_WORKFLOW.md     # data decisions: what I chose, why, and the impact
```

## How to run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python pipeline/load_data.py
```

## How this was built

I built this project with [Claude Code](https://claude.com/claude-code) as a coding assistant.
I made the analytical decisions (cleaning rules, metric definitions, conclusions) and checked the outputs.
[AI_WORKFLOW.md](AI_WORKFLOW.md) lists every data decision I made, why, and its impact.
