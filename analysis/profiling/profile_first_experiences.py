"""Profile newcomers' first-day experiences and how they relate to retention.

Read-only: it only runs queries on the cleaned tables (`edits`, `newcomers`) and prints tables.
Run pipeline/build_tables.py first.

A newcomer's first day is the 24 hours from their first human edit. The experiences are the ones defined in
docs/metrics_definitions.md: a reverted edit (decision 7) and an edit whose page was deleted within 30 days
(decision 11). The outcome is the main retention metric, an edit in days 60-180 (decision 6).
The chosen measure is decision 12 in AI_WORKFLOW.md.

Usage:
    python analysis/profiling/profile_first_experiences.py
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

    # One row per newcomer with what happened on their first day.
    # The very first edit is found by time, then revision_id, the same order as the edit numbers in build_tables.py.
    con.sql("""
        create temp table first_day as
        with first_day_edits as (
            select
                n.user_id,
                e.is_reverted,
                e.page_deleted_within_30_days,
                row_number() over (partition by n.user_id order by e.event_timestamp, e.revision_id) as edit_number
            from newcomers n
            join edits e
              on e.editor_type = 'registered'
             and e.user_id = n.user_id
             and e.event_timestamp < n.first_edit_at + interval 1 day
        )
        select
            n.user_id,
            n.cohort_year,
            n.created_by,
            n.retained_months_3_to_6,
            count(*) as first_day_edits,
            bool_or(f.is_reverted) as any_reverted,
            bool_or(f.is_reverted) filter (where f.edit_number = 1) as first_edit_reverted,
            bool_or(f.page_deleted_within_30_days) as any_page_deleted,
            bool_or(f.page_deleted_within_30_days) filter (where f.edit_number = 1) as first_edit_page_deleted
        from newcomers n
        join first_day_edits f using (user_id)
        group by all
    """)

    show(con, "Check: newcomers in the first-day table", """
        select count(*) as newcomers, sum(any_reverted::int) as any_first_day_edit_reverted,
               sum(any_page_deleted::int) as any_first_day_page_deleted
        from first_day
    """)

    show(con, "Retention by first-day experience", """
        select
            case when any_reverted and any_page_deleted then 'c) reverted and page deleted'
                 when any_reverted then 'a) reverted only'
                 when any_page_deleted then 'b) page deleted only'
                 else 'd) neither' end as first_day,
            count(*) as newcomers,
            round(100 * count(*) / sum(count(*)) over (), 1) as pct_of_newcomers,
            round(100 * avg(retained_months_3_to_6::int), 1) as retained_pct
        from first_day
        group by 1
        order by 1
    """)

    # More edits on the first day means more chances to be reverted, and more edits also go with staying.
    # So the number of first-day edits can hide or reverse the real relationship.
    show(con, "By number of first-day edits: chance of a revert, and retention", """
        select
            case when first_day_edits = 1 then 'a) 1'
                 when first_day_edits <= 4 then 'b) 2-4'
                 when first_day_edits <= 9 then 'c) 5-9'
                 else 'd) 10+' end as first_day_edits,
            count(*) as newcomers,
            round(100 * avg(any_reverted::int), 1) as pct_with_a_revert,
            round(100 * avg(any_page_deleted::int), 1) as pct_with_a_page_deleted,
            round(100 * avg(retained_months_3_to_6::int), 1) as retained_pct
        from first_day
        group by 1
        order by 1
    """)

    show(con, "Retention, reverted vs not, within each number of first-day edits", """
        select
            case when first_day_edits = 1 then 'a) 1'
                 when first_day_edits <= 4 then 'b) 2-4'
                 when first_day_edits <= 9 then 'c) 5-9'
                 else 'd) 10+' end as first_day_edits,
            count(*) filter (where any_reverted) as reverted_newcomers,
            round(100 * avg(retained_months_3_to_6::int) filter (where any_reverted), 1) as reverted_retained_pct,
            count(*) filter (where not any_reverted) as not_reverted_newcomers,
            round(100 * avg(retained_months_3_to_6::int) filter (where not any_reverted), 1) as not_reverted_retained_pct
        from first_day
        group by 1
        order by 1
    """)

    show(con, "Retention, page deleted vs not, within each number of first-day edits", """
        select
            case when first_day_edits = 1 then 'a) 1'
                 when first_day_edits <= 4 then 'b) 2-4'
                 when first_day_edits <= 9 then 'c) 5-9'
                 else 'd) 10+' end as first_day_edits,
            count(*) filter (where any_page_deleted) as deleted_newcomers,
            round(100 * avg(retained_months_3_to_6::int) filter (where any_page_deleted), 1) as deleted_retained_pct,
            count(*) filter (where not any_page_deleted) as not_deleted_newcomers,
            round(100 * avg(retained_months_3_to_6::int) filter (where not any_page_deleted), 1) as not_deleted_retained_pct
        from first_day
        group by 1
        order by 1
    """)

    # Looking only at the very first edit gives every newcomer the same single chance to be reverted.
    show(con, "Retention by what happened to the very first edit", """
        select
            case when first_edit_reverted then 'reverted'
                 else 'not reverted' end as first_edit,
            count(*) as newcomers,
            round(100 * avg(retained_months_3_to_6::int), 1) as retained_pct
        from first_day
        group by 1
        order by 1
    """)

    show(con, "Retention, reverted vs not (any first-day edit), by period of the cohort year", """
        select
            case when cohort_year <= 2012 then 'a) 2008-2012'
                 when cohort_year <= 2016 then 'b) 2013-2016'
                 when cohort_year <= 2020 then 'c) 2017-2020'
                 else 'd) 2021-2025' end as cohorts,
            round(100 * avg(any_reverted::int), 1) as pct_with_a_revert,
            round(100 * avg(retained_months_3_to_6::int) filter (where any_reverted), 1) as reverted_retained_pct,
            round(100 * avg(retained_months_3_to_6::int) filter (where not any_reverted), 1) as not_reverted_retained_pct
        from first_day
        group by 1
        order by 1
    """)

    show(con, "Retention, reverted vs not (any first-day edit), by creation method", """
        select
            created_by,
            count(*) as newcomers,
            round(100 * avg(any_reverted::int), 1) as pct_with_a_revert,
            round(100 * avg(retained_months_3_to_6::int) filter (where any_reverted), 1) as reverted_retained_pct,
            round(100 * avg(retained_months_3_to_6::int) filter (where not any_reverted), 1) as not_reverted_retained_pct
        from first_day
        group by 1
        order by newcomers desc
    """)


if __name__ == "__main__":
    main()
