"""Profile bot activity in `raw_events` and measure the impact of each way to identify bots.

Read-only: it only runs queries and prints tables. The chosen rule is recorded as
decision 2 in AI_WORKFLOW.md.

Usage:
    python analysis/profiling/profile_bots.py
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

    # Edits by registered (permanent) accounts only. Bots are always registered accounts:
    # no anonymous or temporary-account edit has a bot flag.
    # Each bot column holds 'name', 'group', both ('name,group') or NULL.
    con.sql("""
        create temp table registered_edits as
        select
            event_user_id as user_id,
            coalesce(event_user_is_bot_by_historical, '') as bot_flag_at_the_time,
            coalesce(event_user_is_bot_by, '') as bot_flag_today
        from raw_events
        where event_entity = 'revision'
          and event_user_is_permanent
    """)

    # One row per account, to see bots as accounts rather than single edits.
    con.sql("""
        create temp table accounts as
        select
            user_id,
            count(*) as edits,
            count(*) filter (where bot_flag_at_the_time <> '') as flagged_edits,
            bool_or(bot_flag_at_the_time like '%group%' or bot_flag_today like '%group%') as in_bot_group_ever,
            bool_or(bot_flag_at_the_time like '%name%' or bot_flag_today like '%name%') as bot_name_ever
        from registered_edits
        group by user_id
    """)

    show(con, "Edits by bot flag, at the time of the edit vs. today", """
        select bot_flag_at_the_time, bot_flag_today, count(*) as edits, count(distinct user_id) as editors
        from registered_edits
        group by all
        order by edits desc
    """)

    show(con, "Accounts by type of bot flag (at any time)", """
        select
            case when in_bot_group_ever then 'bot group'
                 when bot_name_ever then 'bot-like name only'
                 else 'no flag' end as account_type,
            count(*) as accounts,
            sum(edits) as edits,
            median(edits) as median_edits_per_account,
            count(*) filter (where edits <= 10) as accounts_with_10_edits_or_fewer
        from accounts
        group by account_type
        order by edits desc
    """)

    # Some accounts were flagged for only part of their edits. If only a small share is
    # flagged, they're most likely people who got a bot flag for a short automated task.
    show(con, "Flagged accounts by share of their edits flagged at the time", """
        select
            case when flagged_edits = 0 then 'a) none (flagged only today)'
                 when flagged_edits < 0.5 * edits then 'b) under half'
                 when flagged_edits < edits then 'c) half or more'
                 else 'd) all' end as share_of_edits_flagged,
            count(*) as accounts,
            sum(edits) as edits,
            sum(edits - flagged_edits) as unflagged_edits,
            median(edits) as median_edits_per_account
        from accounts
        where in_bot_group_ever or bot_name_ever
        group by share_of_edits_flagged
        order by share_of_edits_flagged
    """)

    show(con, "Impact of each rule (edits and accounts removed)", """
        select 'Start: edits by registered accounts' as bot_rule, count(*) as edits, count(distinct user_id) as accounts
        from registered_edits
        union all
        select 'A: per edit, flagged at the time', count(*), count(distinct user_id)
        from registered_edits where bot_flag_at_the_time <> ''
        union all
        select 'B: per edit, flagged at the time or today (chosen)', count(*), count(distinct user_id)
        from registered_edits where bot_flag_at_the_time <> '' or bot_flag_today <> ''
        union all
        select 'C: whole account, flagged ever', count(*), count(distinct user_id)
        from registered_edits join accounts using (user_id)
        where in_bot_group_ever or bot_name_ever
        union all
        select 'D: per edit, bot group only (at the time or today)', count(*), count(distinct user_id)
        from registered_edits where bot_flag_at_the_time like '%group%' or bot_flag_today like '%group%'
    """)

    show(con, "User talk messages (namespace 3) by editor type", """
        select
            case when event_user_is_anonymous then 'anonymous'
                 when coalesce(event_user_is_bot_by_historical, '') <> ''
                   or coalesce(event_user_is_bot_by, '') <> '' then 'bot'
                 else 'registered, not a bot' end as editor_type,
            count(*) as edits
        from raw_events
        where event_entity = 'revision' and page_namespace_historical = 3
        group by editor_type
        order by edits desc
    """)


if __name__ == "__main__":
    main()
