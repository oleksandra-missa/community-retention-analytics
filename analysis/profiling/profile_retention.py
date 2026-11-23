"""Profile what newcomers do after their first edit, and compare ways to define "retained".

Read-only: it only runs queries and prints tables.

It uses the earlier decisions: registered accounts only (decision 3), bot edits removed (decision 2),
accounts from every creation method (decision 4), and newcomers whose first human edit
was in 2008-2025 (decision 5).

The data ends on 2026-11-01, so a newcomer from December 2025 can be followed for about 300 days.
Every window below ends by day 300, so all cohorts can be measured the same way.

Usage:
    python analysis/profiling/profile_retention.py
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


def main():
    con = duckdb.connect(str(DB_PATH), read_only=True)

    # Human edits by registered accounts (decisions 2 and 3), with each edit's day since the
    # editor's first edit. Day 0 is the first 24 hours after the first edit.
    con.sql("""
        create temp table newcomer_edits as
        with human_edits as (
            select
                event_user_id as user_id,
                event_timestamp,
                page_namespace_historical as namespace,
                min(event_timestamp) over (partition by event_user_id) as first_edit_at
            from raw_events
            where event_entity = 'revision'
              and event_user_is_permanent
              and coalesce(event_user_is_bot_by_historical, '') = ''
              and coalesce(event_user_is_bot_by, '') = ''
        )
        select
            user_id,
            first_edit_at,
            year(first_edit_at) as cohort_year,
            namespace,
            date_diff('second', first_edit_at, event_timestamp) / 86400.0 as days_since_first_edit
        from human_edits
        where year(first_edit_at) between 2008 and 2025
    """)

    # One row per newcomer, with a true/false column for each candidate definition.
    con.sql("""
        create temp table newcomers as
        select
            user_id,
            cohort_year,
            count(*) as edits_total,
            count(*) filter (where days_since_first_edit < 1) as edits_first_day,
            -- A: at least one edit in the second month (days 30-60)
            count(*) filter (where days_since_first_edit >= 30 and days_since_first_edit < 60) >= 1
                as retained_a_second_month,
            -- B: at least one edit in months 3-6 (days 60-180)
            count(*) filter (where days_since_first_edit >= 60 and days_since_first_edit < 180) >= 1
                as retained_b_months_3_to_6,
            -- C: at least 5 edits in the second month (Wikimedia's threshold for an "active editor")
            count(*) filter (where days_since_first_edit >= 30 and days_since_first_edit < 60) >= 5
                as retained_c_active_second_month,
            -- D: at least one edit in month 10 (days 270-300), the longest window every cohort allows
            count(*) filter (where days_since_first_edit >= 270 and days_since_first_edit < 300) >= 1
                as retained_d_month_10,
            -- A, counting article edits only
            count(*) filter (where days_since_first_edit >= 30 and days_since_first_edit < 60
                             and namespace = 0) >= 1 as retained_a_articles_only
        from newcomer_edits
        group by user_id, cohort_year
    """)

    show(con, "How much newcomers edit", """
        select
            count(*) as newcomers,
            round(100.0 * avg((edits_total = 1)::int), 1) as pct_only_one_edit,
            round(100.0 * avg((edits_total = edits_first_day)::int), 1) as pct_all_edits_on_first_day,
            median(edits_total) as median_edits,
            round(100.0 * avg((edits_total >= 10)::int), 1) as pct_10_plus_edits
        from newcomers
    """)

    # The share of newcomers who edit at all in each 30-day month after their first edit.
    show(con, "Share of newcomers editing in each month after their first edit", """
        select
            floor(days_since_first_edit / 30)::int + 1 as month_after_first_edit,
            round(100.0 * count(distinct user_id) / (select count(*) from newcomers), 1) as pct_of_newcomers_editing
        from newcomer_edits
        where days_since_first_edit < 300
        group by month_after_first_edit
        order by month_after_first_edit
    """)

    show(con, "Retained under each definition (all 2008-2025 newcomers)", """
        select
            count(*) as newcomers,
            sum(retained_a_second_month::int) as a_second_month,
            sum(retained_b_months_3_to_6::int) as b_months_3_to_6,
            sum(retained_c_active_second_month::int) as c_active_second_month,
            sum(retained_d_month_10::int) as d_month_10,
            sum(retained_a_articles_only::int) as a_articles_only
        from newcomers
    """)

    # If the definitions tell the same story over time, the choice matters less for trends.
    show(con, "Retention rate (%) by cohort year under each definition", """
        select
            cohort_year,
            count(*) as newcomers,
            round(100.0 * avg(retained_a_second_month::int), 1) as a_second_month,
            round(100.0 * avg(retained_b_months_3_to_6::int), 1) as b_months_3_to_6,
            round(100.0 * avg(retained_c_active_second_month::int), 1) as c_active_second_month,
            round(100.0 * avg(retained_d_month_10::int), 1) as d_month_10,
            round(100.0 * avg(retained_a_articles_only::int), 1) as a_articles_only
        from newcomers
        group by cohort_year
        order by cohort_year
    """)

    # How the definitions overlap: are newcomers retained by A also retained later?
    show(con, "Overlap: newcomers retained in the second month (A) vs. in months 3-6 (B)", """
        select
            retained_a_second_month,
            retained_b_months_3_to_6,
            count(*) as newcomers
        from newcomers
        group by all
        order by all
    """)


if __name__ == "__main__":
    main()
