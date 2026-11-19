"""Profile edits by logged-out editors in `raw_events`: anonymous (IP) editors and temporary accounts.

Read-only: it only runs queries and prints tables.

Background: editors who weren't logged in used to be shown by their IP address ("anonymous").
Since September 2025 they get a temporary account instead, which has an ID but expires after 90 days.

Usage:
    python analysis/profiling/profile_logged_out.py
"""

from pathlib import Path

import duckdb
import pandas as pd

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "wiki.duckdb"

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 20)


def show(con, title, sql):
    print(f"\n== {title} ==")
    # convert_dtypes keeps whole numbers as integers instead of turning them into decimals
    print(con.sql(sql).df().convert_dtypes().to_string(index=False))


def main():
    con = duckdb.connect(str(DB_PATH), read_only=True)

    # Each edit gets one editor type from the three true/false columns.
    # A few edits have none of them set, so they get their own types instead of being hidden.
    con.sql("""
        create temp view edits as
        select
            *,
            case when event_user_is_permanent then 'registered'
                 when event_user_is_temporary then 'temporary account'
                 when event_user_is_anonymous then 'anonymous (IP)'
                 when event_user_id is not null then 'unknown type, has ID'
                 else 'unknown type, no ID' end as editor_type
        from raw_events
        where event_entity = 'revision'
    """)

    show(con, "Edits by editor type", """
        select
            editor_type,
            count(*) as edits,
            round(100.0 * count(*) / sum(count(*)) over (), 1) as pct_of_all_edits,
            count(distinct event_user_id) as accounts,
            min(event_timestamp)::date as first_edit,
            max(event_timestamp)::date as last_edit
        from edits
        group by editor_type
        order by edits desc
    """)

    show(con, "Edits per year by editor type", """
        select
            year(event_timestamp) as edit_year,
            count(*) filter (where editor_type = 'registered') as registered,
            count(*) filter (where editor_type = 'anonymous (IP)') as anonymous_ip,
            count(*) filter (where editor_type = 'temporary account') as temporary_account,
            round(100.0 * count(*) filter (where editor_type in ('anonymous (IP)', 'temporary account'))
                  / count(*), 1) as pct_logged_out
        from edits
        group by edit_year
        order by edit_year
    """)

    # What logged-out editors do, compared with registered ones.
    show(con, "What each editor type edits, and how often it's undone", """
        select
            editor_type,
            count(*) as edits,
            round(100.0 * avg((page_namespace_historical = 0)::int), 1) as pct_in_articles,
            count(*) filter (where page_namespace_historical = 3) as user_talk_edits,
            round(100.0 * avg(coalesce(revision_is_identity_reverted, false)::int), 1) as pct_reverted
        from edits
        group by editor_type
        order by edits desc
    """)

    show(con, "New accounts by type (user/create events)", """
        select
            case when user_is_temporary then 'temporary account' else 'registered' end as account_type,
            count(*) as accounts,
            count(user_first_edit_timestamp) as accounts_that_edited,
            min(event_timestamp)::date as first_created,
            max(event_timestamp)::date as last_created
        from raw_events
        where event_entity = 'user' and event_type = 'create'
        group by account_type
        order by accounts desc
    """)

    # A temporary account expires after 90 days, which limits how long it can be followed.
    show(con, "How long temporary accounts are used", """
        with per_account as (
            select
                event_user_id,
                count(*) as edits,
                date_diff('day', min(event_timestamp), max(event_timestamp)) as days_first_to_last_edit
            from edits
            where editor_type = 'temporary account'
            group by event_user_id
        )
        select
            count(*) as accounts,
            median(edits) as median_edits,
            count(*) filter (where edits = 1) as accounts_with_one_edit,
            count(*) filter (where days_first_to_last_edit >= 30) as used_30_days_or_more,
            max(days_first_to_last_edit) as longest_use_in_days
        from per_account
    """)

    show(con, "Edits with an unknown editor type", """
        select
            editor_type,
            count(*) as edits,
            count(distinct event_user_id) as accounts,
            count(*) filter (where revision_deleted_parts is not null) as edits_with_hidden_parts,
            min(event_timestamp)::date as first_edit,
            max(event_timestamp)::date as last_edit
        from edits
        where editor_type like 'unknown%'
        group by editor_type
    """)


if __name__ == "__main__":
    main()
