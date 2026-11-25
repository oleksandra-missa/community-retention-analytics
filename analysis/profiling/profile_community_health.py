"""Profile how concentrated the work is, and measure the options for a concentration metric.

Read-only: it only runs queries on the cleaned `edits` table and prints tables. Run pipeline/build_tables.py first.
The chosen metric is decision 14 in AI_WORKFLOW.md.

It uses human edits (decisions 2 and 3) in 2008-2025, the years of the newcomer cohorts. Registered editors are
identified by their account ID. Logged-out editors can't be counted as people (an anonymous editor is an IP
address that many people can share, and a temporary account expires after 90 days), so they appear only as
a share of edits.

Usage:
    python analysis/profiling/profile_community_health.py
"""

from pathlib import Path

import duckdb
import pandas as pd

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "wiki.duckdb"

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 20)
pd.set_option("display.max_rows", 100)


def show(con, title, sql):
    print(f"\n== {title} ==")
    # convert_dtypes keeps whole numbers as integers instead of turning them into decimals
    print(con.sql(sql).df().convert_dtypes().to_string(index=False))


def top_share_sql(period_expression, edit_filter):
    """Share of edits made by the top 1% and top 10% of registered editors in each period.

    Editors are ranked by their number of edits in the period; the top 1% is the first ceil(1% of editors)
    in that ranking, with ties broken by user_id so the result is the same every run.
    """
    return f"""
        with per_editor as (
            select {period_expression} as period, user_id, count(*) as edits
            from edits
            where editor_type = 'registered'
              and year(event_timestamp) between 2008 and 2025
              and {edit_filter}
            group by all
        ),
        ranked as (
            select
                *,
                row_number() over (partition by period order by edits desc, user_id) as editor_rank,
                count(*) over (partition by period) as editors_in_period
            from per_editor
        )
        select
            period,
            any_value(editors_in_period) as editors,
            count(*) filter (where editor_rank <= ceil(0.01 * editors_in_period)) as top_1pct_editors,
            sum(edits) as edits,
            round(100 * sum(edits) filter (where editor_rank <= ceil(0.01 * editors_in_period)) / sum(edits), 1)
                as top_1pct_share,
            round(100 * sum(edits) filter (where editor_rank <= ceil(0.10 * editors_in_period)) / sum(edits), 1)
                as top_10pct_share,
            median(edits) as median_edits_per_editor
        from ranked
        group by period
        order by period
    """


def main():
    con = duckdb.connect(str(DB_PATH), read_only=True)

    show(con, "Option A: per calendar year, edits on every part of the wiki",
         top_share_sql("year(event_timestamp)", "true"))

    show(con, "Option B: per calendar year, article edits only",
         top_share_sql("year(event_timestamp)", "page_namespace = 0"))

    show(con, "Option C: all of 2008-2025 as one period, every part of the wiki",
         top_share_sql("'2008-2025'", "true"))

    show(con, "Option D: per calendar month, every part of the wiki (summary over the 216 months)", f"""
        with monthly as ({top_share_sql("date_trunc('month', event_timestamp)", "true")})
        select
            count(*) as months,
            median(editors) as median_editors,
            median(top_1pct_editors) as median_top_1pct_editors,
            min(top_1pct_share) as min_top_1pct_share,
            median(top_1pct_share) as median_top_1pct_share,
            max(top_1pct_share) as max_top_1pct_share
        from monthly
    """)

    # Who is in a year's top 1%: their edits are mostly in articles or elsewhere?
    show(con, "Top 1% per year, all namespaces: share of their edits made in articles vs. everyone else", """
        with per_editor as (
            select
                year(event_timestamp) as period, user_id, count(*) as edits,
                count(*) filter (where page_namespace = 0) as article_edits
            from edits
            where editor_type = 'registered' and year(event_timestamp) between 2008 and 2025
            group by all
        ),
        ranked as (
            select *, row_number() over (partition by period order by edits desc, user_id) as editor_rank,
                   count(*) over (partition by period) as editors_in_period
            from per_editor
        )
        select
            case when editor_rank <= ceil(0.01 * editors_in_period) then 'top 1%' else 'other 99%' end as editors,
            sum(edits) as edits,
            round(100 * sum(article_edits) / sum(edits), 1) as pct_of_their_edits_in_articles
        from ranked
        group by 1
    """)

    show(con, "Logged-out editors' share of all human edits, by year (every part of the wiki and articles only)", """
        select
            year(event_timestamp) as year,
            count(*) as human_edits,
            round(100 * avg((editor_type = 'logged_out')::int), 1) as logged_out_pct,
            round(100 * avg((editor_type = 'logged_out')::int) filter (where page_namespace = 0), 1)
                as logged_out_pct_of_article_edits
        from edits
        where year(event_timestamp) between 2008 and 2025
        group by 1
        order by 1
    """)


if __name__ == "__main__":
    main()
