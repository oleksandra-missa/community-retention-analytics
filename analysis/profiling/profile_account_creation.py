"""Profile how new accounts were created in `raw_events`: by the person, automatically by the system, or by another user.

Read-only: it only runs queries and prints tables.

Background: anyone with an account on another Wikimedia wiki (e.g. English Wikipedia) gets an account
created automatically when they visit Simple English Wikipedia while logged in. Those accounts are
marked `user_is_created_by_system`. Temporary accounts are created by the system too.

Usage:
    python analysis/profiling/profile_account_creation.py
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

    # One row per new account (user/create event), with how it was created.
    con.sql("""
        create temp table new_accounts as
        select
            user_id,
            event_timestamp as created_at,
            user_first_edit_timestamp as first_edit_at,
            case when user_is_temporary then 'temporary' else 'registered' end as account_kind,
            case when user_is_created_by_self then 'self'
                 when user_is_created_by_system then 'system'
                 when user_is_created_by_peer then 'peer'
                 else 'unknown' end as created_by
        from raw_events
        where event_entity = 'user' and event_type = 'create'
    """)

    # Per registered account: its edits, with bot edits removed by decision 2
    # (flagged as a bot at the time of the edit or today).
    con.sql("""
        create temp table editors as
        with human_edits as (
            select
                event_user_id as user_id,
                event_timestamp,
                page_namespace_historical,
                event_user_revision_count,
                coalesce(revision_is_identity_reverted, false) as is_reverted,
                min(event_timestamp) over (partition by event_user_id) as first_edit_at
            from raw_events
            where event_entity = 'revision'
              and event_user_is_permanent
              and coalesce(event_user_is_bot_by_historical, '') = ''
              and coalesce(event_user_is_bot_by, '') = ''
        )
        select
            user_id,
            min(first_edit_at) as first_edit_at,
            count(*) as edits,
            count(*) filter (where event_timestamp < first_edit_at + interval 30 day) as edits_first_30_days,
            -- a rough activity check: did they edit again between day 30 and day 60 after their first edit?
            bool_or(event_timestamp >= first_edit_at + interval 30 day
                    and event_timestamp < first_edit_at + interval 60 day) as edited_days_30_to_60,
            -- the editor's own first edit (their running edit count is 1)
            bool_or(event_user_revision_count = 1 and is_reverted) as first_edit_reverted,
            bool_or(event_user_revision_count = 1 and page_namespace_historical = 0) as first_edit_in_article
        from human_edits
        group by user_id
    """)

    show(con, "New accounts by kind and creation method", """
        select
            account_kind,
            created_by,
            count(*) as accounts,
            count(first_edit_at) as accounts_that_edited,
            round(100.0 * count(first_edit_at) / count(*), 1) as pct_that_edited,
            min(created_at)::date as first_created,
            max(created_at)::date as last_created
        from new_accounts
        group by all
        order by account_kind, accounts desc
    """)

    show(con, "Registered accounts per year by creation method (created, and how many ever edited)", """
        select
            year(created_at) as created_year,
            count(*) filter (where created_by = 'self') as self_created,
            count(*) filter (where created_by = 'self' and first_edit_at is not null) as self_edited,
            count(*) filter (where created_by = 'system') as system_created,
            count(*) filter (where created_by = 'system' and first_edit_at is not null) as system_edited,
            count(*) filter (where created_by = 'peer') as peer_created,
            count(*) filter (where created_by = 'unknown') as unknown_method
        from new_accounts
        where account_kind = 'registered'
        group by created_year
        order by created_year
    """)

    # If automatically created accounts were mostly experienced editors from other wikis,
    # their first edits should be undone less often and they should stay active more often.
    show(con, "Behavior of human editors whose first edit was in 2008-2025, by creation method", """
        select
            a.created_by,
            count(*) as editors,
            median(e.edits) as median_edits,
            round(100.0 * avg((e.edits_first_30_days >= 5)::int), 1) as pct_5_plus_edits_first_30_days,
            round(100.0 * avg(e.edited_days_30_to_60::int), 1) as pct_edited_days_30_to_60,
            round(100.0 * avg(e.first_edit_reverted::int), 1) as pct_first_edit_reverted,
            round(100.0 * avg(e.first_edit_in_article::int), 1) as pct_first_edit_in_article
        from new_accounts a
        join editors e using (user_id)
        where year(e.first_edit_at) between 2008 and 2025
        group by a.created_by
        order by editors desc
    """)

    show(con, "Speed: how soon after the account was created was the first edit?", """
        select
            created_by,
            count(*) as accounts_that_edited,
            round(100.0 * avg((date_diff('minute', created_at, first_edit_at) between 0 and 10)::int), 1)
                as pct_within_10_minutes,
            count(*) filter (where first_edit_at < created_at) as first_edit_before_creation
        from new_accounts
        where account_kind = 'registered' and first_edit_at is not null
        group by created_by
        order by accounts_that_edited desc
    """)

    show(con, "Registered editors with no account-creation event", """
        select count(*) as editors_without_create_event
        from editors
        anti join new_accounts using (user_id)
    """)

    # Impact of each option on the two places accounts enter the analysis:
    # the funnel's first step (an account was created) and the newcomer cohorts (people who edited).
    # "Created by a person" means self or peer: someone chose to create the account on this wiki.
    show(con, "Impact of each option (registered accounts, bot edits removed)", """
        select
            'A: newcomers from all methods; funnel starts from accounts created by a person' as account_rule,
            count(*) filter (where created_by in ('self', 'peer')) as funnel_start_accounts,
            count(e.user_id) as newcomers_who_edited
        from new_accounts a left join editors e using (user_id)
        where account_kind = 'registered'
        union all
        select
            'B: only accounts created by a person, everywhere',
            count(*),
            count(e.user_id)
        from new_accounts a left join editors e using (user_id)
        where account_kind = 'registered' and created_by in ('self', 'peer')
        union all
        select
            'C: all methods everywhere, also in the funnel',
            count(*),
            count(e.user_id)
        from new_accounts a left join editors e using (user_id)
        where account_kind = 'registered'
    """)

    # The create event's own timestamp vs. user_creation_timestamp (which comes from the account-creation log).
    show(con, "Account-creation timestamps: event time vs. creation log", """
        select
            created_by,
            count(*) as accounts,
            count(*) filter (where user_creation_timestamp is null) as no_creation_log,
            count(*) filter (where abs(date_diff('second', user_creation_timestamp, event_timestamp)) > 60)
                as log_differs_by_over_a_minute
        from raw_events
        join new_accounts using (user_id)
        where event_entity = 'user' and event_type = 'create' and account_kind = 'registered'
        group by created_by
        order by accounts desc
    """)


if __name__ == "__main__":
    main()
