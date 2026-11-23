"""Profile edits on pages that were later deleted, and their effect on newcomer counts and retention.

Read-only: it only runs queries and prints tables.

When a page is deleted, its edits stay in the dump and are marked with `revision_is_deleted_by_page_deletion`
and `revision_deleted_by_page_deletion_timestamp`.

It uses the earlier decisions: human edits by registered accounts (decisions 2 and 3), newcomers whose first
human edit was in 2008-2025 (decision 5) and the main retention metric, an edit in days 60-180 (decision 6).

Usage:
    python analysis/profiling/profile_deleted_pages.py
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


def newcomer_retention_sql(edits_table):
    """Newcomers 2008-2025 and the main retention metric, computed from the given table of edits."""
    return f"""
        with edits as (
            select *, min(event_timestamp) over (partition by user_id) as first_edit_at
            from {edits_table}
        )
        select
            count(distinct user_id) as newcomers,
            count(distinct user_id) filter (
                where event_timestamp >= first_edit_at + interval 60 day
                  and event_timestamp < first_edit_at + interval 180 day) as retained
        from edits
        where year(first_edit_at) between 2008 and 2025
    """


def main():
    con = duckdb.connect(str(DB_PATH), read_only=True)

    # Human edits by registered accounts (decisions 2 and 3), with when their page was deleted (if it was).
    con.sql("""
        create temp table human_edits as
        select
            event_user_id as user_id,
            event_timestamp,
            revision_id,
            page_namespace_historical as namespace,
            coalesce(revision_is_deleted_by_page_deletion, false) as page_later_deleted,
            revision_deleted_by_page_deletion_timestamp as page_deleted_at,
            coalesce(page_is_deleted, false) as page_deleted_today,
            min(event_timestamp) over (partition by event_user_id) as first_edit_at
        from raw_events
        where event_entity = 'revision'
          and event_user_is_permanent
          and coalesce(event_user_is_bot_by_historical, '') = ''
          and coalesce(event_user_is_bot_by, '') = ''
    """)

    show(con, "Human edits on later-deleted pages, by year of the edit", """
        select
            year(event_timestamp) as edit_year,
            count(*) as edits,
            count(*) filter (where page_later_deleted) as on_deleted_pages,
            round(100.0 * avg(page_later_deleted::int), 1) as pct_on_deleted_pages
        from human_edits
        where year(event_timestamp) between 2008 and 2025
        group by edit_year
        order by edit_year
    """)

    show(con, "Human edits on later-deleted pages, by namespace (2008-2025, top 6)", """
        select
            namespace,
            count(*) filter (where page_later_deleted) as on_deleted_pages,
            round(100.0 * avg(page_later_deleted::int), 1) as pct_of_namespace_edits
        from human_edits
        where year(event_timestamp) between 2008 and 2025
        group by namespace
        order by on_deleted_pages desc
        limit 6
    """)

    # A page can be deleted and later restored; its old edits keep the deletion mark.
    show(con, "Edits marked as on a deleted page, by whether the page is deleted today", """
        select page_deleted_today, count(*) as edits
        from human_edits
        where page_later_deleted
        group by page_deleted_today
        order by page_deleted_today
    """)

    show(con, "How long after the edit the page was deleted (2008-2025 edits)", """
        select
            case when date_diff('second', event_timestamp, page_deleted_at) < 86400 then '1) within 1 day'
                 when date_diff('second', event_timestamp, page_deleted_at) < 7 * 86400 then '2) 1 to 7 days'
                 when date_diff('second', event_timestamp, page_deleted_at) < 30 * 86400 then '3) 7 to 30 days'
                 when date_diff('second', event_timestamp, page_deleted_at) < 365 * 86400 then '4) 30 days to 1 year'
                 else '5) 1 year or more' end as time_to_deletion,
            count(*) as edits,
            round(100.0 * count(*) / sum(count(*)) over (), 1) as pct
        from human_edits
        where page_later_deleted and year(event_timestamp) between 2008 and 2025
        group by time_to_deletion
        order by time_to_deletion
    """)

    # The newcomer view, one row per newcomer 2008-2025.
    con.sql("""
        create temp table newcomers as
        select
            user_id,
            count(*) as edits,
            count(*) filter (where page_later_deleted) as edits_on_deleted_pages,
            arg_min(page_later_deleted, (event_timestamp, revision_id)) as first_edit_page_deleted,
            -- coalesce: for pages never deleted, page_deleted_at is NULL and the comparison would be NULL, not false
            bool_or(event_timestamp < first_edit_at + interval 1 day
                    and coalesce(page_deleted_at < event_timestamp + interval 30 day, false))
                as first_day_page_deleted_within_30_days,
            count(*) filter (where event_timestamp >= first_edit_at + interval 60 day
                             and event_timestamp < first_edit_at + interval 180 day) >= 1 as retained
        from human_edits
        where year(first_edit_at) between 2008 and 2025
        group by user_id
    """)

    show(con, "Newcomers 2008-2025 and later-deleted pages", """
        select
            count(*) as newcomers,
            count(*) filter (where first_edit_page_deleted) as first_edit_on_deleted_page,
            count(*) filter (where first_day_page_deleted_within_30_days) as first_day_page_deleted_within_30_days,
            count(*) filter (where edits_on_deleted_pages = edits) as all_edits_on_deleted_pages
        from newcomers
    """)

    show(con, "Main retention metric by whether a first-day edit's page was deleted within 30 days", """
        select
            first_day_page_deleted_within_30_days,
            count(*) as newcomers,
            round(100.0 * avg(retained::int), 1) as pct_retained
        from newcomers
        group by first_day_page_deleted_within_30_days
        order by first_day_page_deleted_within_30_days
    """)

    # Option B: drop every edit on a later-deleted page, then recompute newcomers and retention.
    con.sql("create temp view kept_edits as select * exclude (first_edit_at) from human_edits where not page_later_deleted")
    con.sql("create temp view all_edits as select * exclude (first_edit_at) from human_edits")
    show(con, "Newcomers and retention: keeping vs. excluding edits on later-deleted pages", f"""
        select 'A: keep all edits' as option, * from ({newcomer_retention_sql('all_edits')})
        union all
        select 'B: exclude edits on deleted pages', * from ({newcomer_retention_sql('kept_edits')})
    """)


if __name__ == "__main__":
    main()
