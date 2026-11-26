# Why Do Newcomers Leave? Newcomer Retention in an Online Community

A product analytics study of how a real online community, **Simple English Wikipedia**, gains and loses
its new members. Built on the full public edit history (2001–2026).

## Key findings

- **Only 6.3% of newcomers stay.** Of the 133,976 registered accounts that made a first edit in 2008–2025, 6.3% were still
  editing three to six months later. Retention fell from 14.3% (2008) to 4.4% (2019) and has only partly
  recovered (5.3–5.8% in 2022–2025).
- **Rejection on the first day goes with leaving.** A quarter of newcomers have a first-day edit reverted.
  Compared with similar newcomers (same first-day activity, year and account type), they have 0.37 times the
  odds of staying.
- **There is a moment to act.** About half of those reverts come within 10 minutes of the first edit, while the
  newcomer is often still on the site.
- **The wiki depends on very few people.** Every year the top 1% of editors make 73–85% of the edits.

**Recommendation:** an A/B test of a friendly message sent right after a newcomer's first revert. On this wiki
alone it would take about 4 years; across several wikis, about 11 months. The
[memo to a product team](docs/memo.md) has all six findings and four recommendations.

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
| 5 | How would we test a feature that might help, such as a message after a newcomer's first revert? | A/B test design |

## What's in this project

- **Data:** the full edit history loaded into DuckDB (15.2M events, 2001–2026), profiled and cleaned, with every
  rule recorded in the [data decisions](docs/data_decisions.md) (bots, logged-out editors, deleted pages)
- **Definitions:** a [metrics definitions document](docs/metrics_definitions.md): what counts as "active",
  "retained" and "reverted"
- **Analysis:** five [notebooks](analysis/notebooks/) on the funnel, cohort retention, first-day experiences,
  community health and the A/B test's sample size
- **Experiment design:** an [A/B test plan](docs/ab_test_design.md) for a message to newcomers after their first revert
- **Dashboard:** a [Streamlit dashboard](dashboard/) with filters by year, account type and device, and an A/B test
  calculator
- **Memo:** a [memo to a product team](docs/memo.md): what we found and what to test

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
| Analysis | Python (pandas, statsmodels, Jupyter) |
| Dashboard | Streamlit + Altair |

## Project structure

```
├── data/              # raw download and the DuckDB database (not in git)
├── pipeline/
│   ├── load_data.py   # downloads the dump and loads it into DuckDB
│   ├── build_tables.py   # builds the cleaned tables (edits, accounts, newcomers) from raw_events
│   ├── build_dashboard_data.py   # builds the dashboard's summary tables from the cleaned tables
│   └── columns.csv    # the dump's 78 column names and types, from the official docs
├── analysis/
│   ├── notebooks/
│   │   ├── 01_cohort_retention.ipynb   # retention by cohort year, 2008–2025
│   │   ├── 02_first_experiences.ipynb   # first-day reverts, deletions and mobile, and retention
│   │   ├── 03_activation_funnel.ipynb   # sign-up → 1st → 5th → 50th edit, by year
│   │   ├── 04_community_health.ipynb   # active editors, logged-out editing and how concentrated the work is
│   │   └── 05_ab_test_power.ipynb   # sample size, duration and power for the A/B test
│   └── profiling/   # scripts that compare the options behind each data decision and measure their impact
├── dashboard/
│   ├── app.py   # the Streamlit app: filters and page navigation
│   ├── data.py   # loads the summary tables, applies the filters, chart style
│   ├── views/   # one file per page
│   └── data/   # small summary tables the dashboard reads (counts only, no account IDs)
└── docs/
    ├── ab_test_design.md   # the A/B test plan: hypothesis, metrics, sample size and risks
    ├── data_decisions.md   # every cleaning rule and metric definition I chose, why, and the impact
    ├── memo.md   # short summary for a product team: findings and recommendations
    └── metrics_definitions.md   # exact definitions of every metric
```

## How to run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python pipeline/load_data.py
python pipeline/build_tables.py
jupyter lab analysis/notebooks/   # the analysis notebooks
python pipeline/build_dashboard_data.py   # only needed to refresh the dashboard's summary tables
streamlit run dashboard/app.py   # the dashboard
```

## How this was built

I built this project with [Claude Code](https://claude.com/claude-code) as a coding assistant.
I made the analytical decisions (cleaning rules, metric definitions, conclusions) and checked the outputs.
[Data decisions](docs/data_decisions.md) lists every one of those decisions, why I made it, and its impact.

## License

The code is under the [MIT license](LICENSE). The data isn't included: it comes from the Wikimedia Foundation's public dumps (see [Data](#data)).
