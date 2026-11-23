"""Count the activation funnel and active editors, as defined in docs/metrics_definitions.md.

Read-only: it only runs queries and prints tables.

Usage:
    python analysis/profiling/profile_funnel_and_activity.py
"""

from pathlib import Path

import duckdb
import pandas as pd

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "wiki.duckdb"

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 20)

FUNNEL_DAYS = 180  # time allowed for each funnel step (decision 8)


def show(con, title, sql):
    print(f"\n== {title} ==")
    # convert_dtypes keeps whole numbers as integers instead of turning them into decimals
    print(con.sql(sql).df().convert_dtypes().to_string(index=False))


def main():
    con = duckdb.connect(str(DB_PATH), read_only=True)

    # Human edits by registered accounts (decisions 2 and 3), numbered per editor in time order.
    # revision_id breaks ties between edits made in the same second.
    con.sql("""
        create temp table human_edits as
        select
            event_user_id as user_id,
            event_timestamp,
            row_number() over (partition by event_user_id order by event_timestamp, revision_id) as edit_number,
            min(event_timestamp) over (partition by event_user_id) as first_edit_at
        from raw_events
        where event_entity = 'revision'
          and event_user_is_permanent
          and coalesce(event_user_is_bot_by_historical, '') = ''
          and coalesce(event_user_is_bot_by, '') = ''
    """)

    # Funnel part 1: accounts created by a person (decision 4), by year of creation.
    show(con, f"Funnel part 1: accounts created by a person in 2008-2025 -> first edit within {FUNNEL_DAYS} days", f"""
        with first_edits as (
            select user_id, min(first_edit_at) as first_edit_at
            from human_edits
            group by user_id
        )
        select
            count(*) as accounts_created,
            count(*) filter (where f.first_edit_at < a.event_timestamp + interval {FUNNEL_DAYS} day)
                as first_edit_within_limit
        from raw_events a
        left join first_edits f on f.user_id = a.user_id
        where a.event_entity = 'user' and a.event_type = 'create'
          and not coalesce(a.user_is_temporary, false)
          and (a.user_is_created_by_self or a.user_is_created_by_peer)
          and year(a.event_timestamp) between 2008 and 2025
    """)

    # Funnel part 2: all newcomers (decision 5), whatever way their account was created.
    show(con, f"Funnel part 2: newcomers 2008-2025 -> 5th and 50th edit within {FUNNEL_DAYS} days of the first", f"""
        select
            count(distinct user_id) as newcomers,
            count(*) filter (where edit_number = 5
                             and event_timestamp < first_edit_at + interval {FUNNEL_DAYS} day) as fifth_edit_within_limit,
            count(*) filter (where edit_number = 50
                             and event_timestamp < first_edit_at + interval {FUNNEL_DAYS} day) as fiftieth_edit_within_limit
        from human_edits
        where year(first_edit_at) between 2008 and 2025
    """)

    # Active editors (decision 9): registered human accounts per calendar month.
    show(con, "Registered human editors per calendar month, 2008-2025 (median over the 216 months)", """
        with per_month as (
            select date_trunc('month', event_timestamp) as edit_month, user_id, count(*) as edits
            from human_edits
            where year(event_timestamp) between 2008 and 2025
            group by edit_month, user_id
        ),
        counts as (
            select
                edit_month,
                count(*) as editors,
                count(*) filter (where edits >= 5) as active_editors,
                count(*) filter (where edits >= 100) as very_active_editors
            from per_month
            group by edit_month
        )
        select
            count(*) as months,
            median(editors) as median_editors,
            median(active_editors) as median_active_editors,
            median(very_active_editors) as median_very_active_editors
        from counts
    """)


if __name__ == "__main__":
    main()
