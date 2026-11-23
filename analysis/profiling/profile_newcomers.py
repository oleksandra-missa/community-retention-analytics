"""Profile when a newcomer's clock could start: at account creation, at the first edit, or at the first article edit.

Read-only: it only runs queries and prints tables.

It uses the earlier decisions: registered accounts only (decision 3), bot edits removed (decision 2),
and accounts from every creation method (decision 4).

Usage:
    python analysis/profiling/profile_newcomers.py
"""

from pathlib import Path

import duckdb
import pandas as pd

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "wiki.duckdb"

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 20)
pd.set_option("display.max_rows", 100)

SECONDS_PER_DAY = 86400


def show(con, title, sql):
    print(f"\n== {title} ==")
    # convert_dtypes keeps whole numbers as integers instead of turning them into decimals
    print(con.sql(sql).df().convert_dtypes().to_string(index=False))


def main():
    con = duckdb.connect(str(DB_PATH), read_only=True)

    # Registered accounts and when they were created. The create event's own time is used:
    # user_creation_timestamp (from the creation log) is years later for about 8,000 accounts.
    con.sql("""
        create temp table accounts as
        select
            user_id,
            event_timestamp as created_at,
            user_first_edit_timestamp as dump_first_edit_at,
            case when user_is_created_by_self then 'self'
                 when user_is_created_by_system then 'system'
                 when user_is_created_by_peer then 'peer'
                 else 'unknown' end as created_by
        from raw_events
        where event_entity = 'user' and event_type = 'create'
          and not coalesce(user_is_temporary, false)
    """)

    # Each account's human edits: bot edits removed by decision 2.
    con.sql("""
        create temp table human_edits as
        select
            event_user_id as user_id,
            event_timestamp,
            revision_id,
            page_namespace_historical as namespace,
            coalesce(revision_is_deleted_by_page_deletion, false) as page_later_deleted
        from raw_events
        where event_entity = 'revision'
          and event_user_is_permanent
          and coalesce(event_user_is_bot_by_historical, '') = ''
          and coalesce(event_user_is_bot_by, '') = ''
    """)

    # One row per editor: their first edit anywhere and their first edit in an article (namespace 0).
    # arg_min picks the value from the earliest edit; revision_id breaks ties between edits in the same second.
    con.sql("""
        create temp table first_edits as
        select
            user_id,
            min(event_timestamp) as first_edit_at,
            arg_min(namespace, (event_timestamp, revision_id)) as first_edit_namespace,
            arg_min(page_later_deleted, (event_timestamp, revision_id)) as first_edit_page_later_deleted,
            min(event_timestamp) filter (where namespace = 0) as first_article_edit_at,
            count(*) as edits
        from human_edits
        group by user_id
    """)

    show(con, "Our first human edit vs. the dump's user_first_edit_timestamp", """
        select
            count(*) as editors,
            count(*) filter (where a.dump_first_edit_at = f.first_edit_at) as same_time,
            count(*) filter (where a.dump_first_edit_at < f.first_edit_at) as dump_is_earlier
        from accounts a
        join first_edits f using (user_id)
    """)

    # If the gap is long, the creation date says little about when someone actually started editing.
    show(con, "Time from account creation to first edit, by creation method", f"""
        with gaps as (
            select a.created_by, date_diff('second', a.created_at, f.first_edit_at) as gap_seconds
            from accounts a
            join first_edits f using (user_id)
        )
        select
            created_by,
            count(*) as editors,
            round(100.0 * avg((gap_seconds < {SECONDS_PER_DAY})::int), 1) as pct_within_1_day,
            round(100.0 * avg((gap_seconds >= {SECONDS_PER_DAY} and gap_seconds < 30 * {SECONDS_PER_DAY})::int), 1)
                as pct_1_to_30_days,
            round(100.0 * avg((gap_seconds >= 30 * {SECONDS_PER_DAY} and gap_seconds < 365 * {SECONDS_PER_DAY})::int), 1)
                as pct_30_to_365_days,
            round(100.0 * avg((gap_seconds >= 365 * {SECONDS_PER_DAY})::int), 1) as pct_over_1_year,
            count(*) filter (where gap_seconds < 0) as first_edit_before_creation
        from gaps
        group by created_by
        order by editors desc
    """)

    show(con, "Where the first edit was made (top namespaces)", """
        select
            first_edit_namespace,
            count(*) as editors,
            round(100.0 * count(*) / sum(count(*)) over (), 1) as pct_of_editors,
            count(*) filter (where first_article_edit_at is null) as never_edited_an_article,
            count(*) filter (where first_edit_page_later_deleted) as first_edit_on_page_later_deleted
        from first_edits
        group by first_edit_namespace
        order by editors desc
        limit 8
    """)

    show(con, "Newcomers per year of first edit", """
        select
            year(first_edit_at) as first_edit_year,
            count(*) as newcomers_first_edit,
            count(first_article_edit_at) as newcomers_who_edited_an_article
        from first_edits
        group by first_edit_year
        order by first_edit_year
    """)

    # Decision 5 uses cohorts from full years 2008-2025: 2026 is a partial year.
    show(con, "Impact of each option", """
        select 'A: clock starts at first edit, any namespace' as newcomer_rule,
               count(*) as newcomers,
               count(*) filter (where year(first_edit_at) between 2008 and 2025) as newcomers_2008_to_2025
        from first_edits
        union all
        select 'B: clock starts at first article edit',
               count(first_article_edit_at),
               count(*) filter (where year(first_article_edit_at) between 2008 and 2025)
        from first_edits
        union all
        select 'C: clock starts at account creation',
               count(*),
               count(*) filter (where year(a.created_at) between 2008 and 2025)
        from first_edits f
        join accounts a using (user_id)
    """)

    show(con, "Last edit in the data (limits how long the latest newcomers can be followed)", """
        select max(event_timestamp) as last_edit_in_data
        from human_edits
    """)


if __name__ == "__main__":
    main()
