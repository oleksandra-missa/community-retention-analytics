"""Profile editing on mobile, and whether newcomers who start on mobile stay less or more often.

Read-only: it only runs queries on the cleaned tables (`edits`, `newcomers`) and prints tables.
Run pipeline/build_tables.py first.

An edit counts as a mobile edit when the software tagged it `mobile edit`. That tag is added to every edit made on
the mobile website (`mobile web edit`) and in the Wikipedia apps (`mobile app edit`).
The outcome is the main retention metric, an edit in days 60-180 (decision 6).
The chosen measure is decision 15 in docs/data_decisions.md.

Usage:
    python analysis/profiling/profile_mobile.py
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

    # revision_tags is comma-separated text; splitting it avoids matching 'advanced mobile edit' by accident
    con.sql("""
        create temp table tagged_edits as
        select
            *,
            list_contains(string_split(coalesce(revision_tags, ''), ','), 'mobile edit') as is_mobile,
            list_contains(string_split(coalesce(revision_tags, ''), ','), 'mobile app edit') as is_app,
            list_contains(string_split(coalesce(revision_tags, ''), ','), 'newcomer task') as is_newcomer_task
        from edits
    """)

    show(con, "Mobile edits by year: share of human edits, registered and logged-out", """
        select
            year(event_timestamp) as year,
            count(*) filter (where is_mobile) as mobile_edits,
            round(100 * avg(is_mobile::int) filter (where editor_type = 'registered'), 1) as registered_mobile_pct,
            round(100 * avg(is_mobile::int) filter (where editor_type = 'logged_out'), 1) as logged_out_mobile_pct,
            round(100 * avg(is_app::int) filter (where is_mobile), 1) as app_pct_of_mobile
        from tagged_edits
        where year(event_timestamp) between 2008 and 2026
        group by 1
        order by 1
    """)

    # Tags could be missing on edits whose page was later deleted: compare the mobile share with and without deletion
    show(con, "Check: mobile share of registered edits 2015-2025, by whether the page was deleted within 30 days", """
        select
            page_deleted_within_30_days,
            count(*) as edits,
            round(100 * avg(is_mobile::int), 1) as mobile_pct,
            round(100 * avg((coalesce(revision_tags, '') = '')::int), 1) as no_tags_pct
        from tagged_edits
        where editor_type = 'registered' and year(event_timestamp) between 2015 and 2025
        group by 1
    """)

    # One row per newcomer: how their first edit and their first day were made
    con.sql("""
        create temp table first_day as
        with first_day_edits as (
            select
                n.user_id,
                e.is_mobile,
                e.is_app,
                e.is_newcomer_task,
                row_number() over (partition by n.user_id order by e.event_timestamp, e.revision_id) as edit_number
            from newcomers n
            join tagged_edits e
              on e.editor_type = 'registered'
             and e.user_id = n.user_id
             and e.event_timestamp < n.first_edit_at + interval 1 day
        )
        select
            n.user_id,
            n.cohort_year,
            case when n.created_by in ('self', 'system') then n.created_by else 'other' end as created_by,
            n.retained_months_3_to_6::int as retained,
            count(*) as first_day_edits,
            bool_or(f.is_mobile) filter (where f.edit_number = 1) as first_edit_mobile,
            bool_or(f.is_app) filter (where f.edit_number = 1) as first_edit_app,
            bool_or(f.is_mobile) as any_first_day_mobile,
            avg(f.is_mobile::int) as first_day_mobile_share,
            bool_or(f.is_newcomer_task) as any_first_day_newcomer_task
        from newcomers n
        join first_day_edits f using (user_id)
        group by all
    """)

    show(con, "Newcomers by cohort year: first edit on mobile, and retention by device of the first edit", """
        select
            cohort_year,
            count(*) as newcomers,
            round(100 * avg(first_edit_mobile::int), 1) as first_edit_mobile_pct,
            round(100 * avg(first_edit_app::int), 1) as first_edit_app_pct,
            round(100 * avg(retained) filter (where first_edit_mobile), 1) as mobile_retained_pct,
            round(100 * avg(retained) filter (where not first_edit_mobile), 1) as desktop_retained_pct
        from first_day
        group by 1
        order by 1
    """)

    show(con, "Options for the mobile measure, newcomers of 2015-2025", """
        select 'A: first edit on mobile' as measure,
               count(*) filter (where first_edit_mobile) as mobile_newcomers,
               round(100 * avg(retained) filter (where first_edit_mobile), 1) as mobile_retained_pct,
               round(100 * avg(retained) filter (where not first_edit_mobile), 1) as other_retained_pct
        from first_day where cohort_year >= 2015
        union all
        select 'B: any first-day edit on mobile',
               count(*) filter (where any_first_day_mobile),
               round(100 * avg(retained) filter (where any_first_day_mobile), 1),
               round(100 * avg(retained) filter (where not any_first_day_mobile), 1)
        from first_day where cohort_year >= 2015
        union all
        select 'C: every first-day edit on mobile',
               count(*) filter (where first_day_mobile_share = 1),
               round(100 * avg(retained) filter (where first_day_mobile_share = 1), 1),
               round(100 * avg(retained) filter (where first_day_mobile_share < 1), 1)
        from first_day where cohort_year >= 2015
    """)

    show(con, "First edit on mobile vs. not, within each number of first-day edits (2015-2025)", """
        select
            case when first_day_edits = 1 then 'a) 1'
                 when first_day_edits <= 4 then 'b) 2-4'
                 when first_day_edits <= 9 then 'c) 5-9'
                 else 'd) 10+' end as first_day_edits,
            count(*) filter (where first_edit_mobile) as mobile_newcomers,
            round(100 * avg(retained) filter (where first_edit_mobile), 1) as mobile_retained_pct,
            count(*) filter (where not first_edit_mobile) as desktop_newcomers,
            round(100 * avg(retained) filter (where not first_edit_mobile), 1) as desktop_retained_pct
        from first_day
        where cohort_year >= 2015
        group by 1
        order by 1
    """)

    show(con, "First edit on mobile vs. not, by creation method (2015-2025)", """
        select
            created_by,
            count(*) as newcomers,
            round(100 * avg(first_edit_mobile::int), 1) as first_edit_mobile_pct,
            round(100 * avg(retained) filter (where first_edit_mobile), 1) as mobile_retained_pct,
            round(100 * avg(retained) filter (where not first_edit_mobile), 1) as desktop_retained_pct
        from first_day
        where cohort_year >= 2015
        group by 1
        order by newcomers desc
    """)

    show(con, "First edit in the mobile website vs. the apps (2015-2025)", """
        select
            case when first_edit_app then 'app'
                 when first_edit_mobile then 'mobile website'
                 else 'desktop' end as first_edit_on,
            count(*) as newcomers,
            round(100 * avg(retained), 1) as retained_pct
        from first_day
        where cohort_year >= 2015
        group by 1
        order by newcomers desc
    """)

    # Newcomer tasks are suggested edits shown to new accounts; they may explain the rise in sign-ups' first edits
    show(con, "Newcomers with a first-day 'newcomer task' edit, by cohort year", """
        select
            cohort_year,
            count(*) filter (where any_first_day_newcomer_task) as newcomers_with_task,
            round(100 * avg(any_first_day_newcomer_task::int), 1) as pct_of_newcomers,
            round(100 * avg(retained) filter (where any_first_day_newcomer_task), 1) as task_retained_pct
        from first_day
        where cohort_year >= 2019
        group by 1
        order by 1
    """)


if __name__ == "__main__":
    main()
