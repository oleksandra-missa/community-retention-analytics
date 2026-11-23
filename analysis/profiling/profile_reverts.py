"""Profile reverts in `raw_events` and compare the two ways to tell that an edit was undone.

Read-only: it only runs queries and prints tables.

The two measures:
- identity revert (`revision_is_identity_reverted`): a later edit brought the page back to exactly
  the content it had before this edit. Calculated by Wikimedia for every year.
- the `mw-reverted` tag (in `revision_tags`): added by the wiki software when an edit is undone.

It uses the earlier decisions: registered accounts only (decision 3), bot edits removed (decision 2),
and newcomers whose first human edit was in 2008-2025 (decision 5).

Usage:
    python analysis/profiling/profile_reverts.py
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

    # Every edit, with who made it, so the editor of a reverting edit can be looked up.
    con.sql("""
        create temp table all_edits as
        select
            revision_id,
            event_user_id as user_id,
            event_timestamp,
            case when event_user_is_permanent
                      and coalesce(event_user_is_bot_by_historical, '') = ''
                      and coalesce(event_user_is_bot_by, '') = '' then 'registered human'
                 when event_user_is_permanent then 'bot'
                 when event_user_is_anonymous or event_user_is_temporary then 'logged-out'
                 else 'unknown' end as editor_type,
            coalesce(revision_is_identity_reverted, false) as identity_reverted,
            revision_first_identity_reverting_revision_id as reverting_revision_id,
            revision_seconds_to_identity_revert as seconds_to_revert,
            -- list_contains checks the comma-separated tags for an exact tag name
            coalesce(list_contains(string_split(revision_tags, ','), 'mw-reverted'), false) as tag_reverted
        from raw_events
        where event_entity = 'revision'
    """)

    # Human edits by registered accounts, with who undid them (if anyone).
    con.sql("""
        create temp table human_edits as
        select
            e.*,
            min(e.event_timestamp) over (partition by e.user_id) as first_edit_at,
            r.user_id as reverter_user_id,
            r.editor_type as reverter_type
        from all_edits e
        left join all_edits r on r.revision_id = e.reverting_revision_id
        where e.editor_type = 'registered human'
    """)

    show(con, "Share of human edits undone, by year: identity revert vs. mw-reverted tag", """
        select
            year(event_timestamp) as edit_year,
            count(*) as edits,
            round(100.0 * avg(identity_reverted::int), 1) as pct_identity_reverted,
            round(100.0 * avg(tag_reverted::int), 1) as pct_tag_reverted
        from human_edits
        where year(event_timestamp) between 2008 and 2026
        group by edit_year
        order by edit_year
    """)

    # Where both measures exist, do they mark the same edits?
    show(con, "Agreement between the two measures, human edits 2021-2025", """
        select
            identity_reverted,
            tag_reverted,
            count(*) as edits
        from human_edits
        where year(event_timestamp) between 2021 and 2025
        group by all
        order by all
    """)

    # A self-revert is someone undoing their own edit: a correction, not a rejection by others.
    show(con, "Who undid the edit (identity reverts of human edits)", """
        select
            case when reverter_user_id = user_id then 'the editor themselves'
                 else reverter_type end as reverted_by,
            count(*) as edits,
            round(100.0 * count(*) / sum(count(*)) over (), 1) as pct
        from human_edits
        where identity_reverted
        group by reverted_by
        order by edits desc
    """)

    show(con, "How long until the edit was undone (identity reverts of human edits)", """
        select
            case when seconds_to_revert < 3600 then '1) under 1 hour'
                 when seconds_to_revert < 86400 then '2) 1 hour to 1 day'
                 when seconds_to_revert < 7 * 86400 then '3) 1 to 7 days'
                 when seconds_to_revert < 30 * 86400 then '4) 7 to 30 days'
                 when seconds_to_revert < 60 * 86400 then '5) 30 to 60 days'
                 when seconds_to_revert is not null then '6) 60 days or more'
                 else '7) no time recorded' end as time_to_revert,
            count(*) as edits,
            round(100.0 * count(*) / sum(count(*)) over (), 1) as pct
        from human_edits
        where identity_reverted
        group by time_to_revert
        order by time_to_revert
    """)

    # The newcomer view: was at least one of their first-day edits undone by someone else?
    show(con, "Newcomers 2008-2025 with a first-day edit undone, by cohort year", """
        with first_day as (
            select
                user_id,
                year(first_edit_at) as cohort_year,
                bool_or(identity_reverted) as any_identity_reverted,
                bool_or(identity_reverted and reverter_user_id is distinct from user_id) as any_reverted_by_others,
                bool_or(identity_reverted and reverter_user_id is distinct from user_id
                        and seconds_to_revert < 30 * 86400) as any_reverted_by_others_within_30_days,
                bool_or(tag_reverted) as any_tag_reverted
            from human_edits
            where event_timestamp < first_edit_at + interval 1 day
              and year(first_edit_at) between 2008 and 2025
            group by user_id, cohort_year
        )
        select
            cohort_year,
            count(*) as newcomers,
            round(100.0 * avg(any_identity_reverted::int), 1) as pct_identity,
            round(100.0 * avg(any_reverted_by_others::int), 1) as pct_identity_by_others,
            round(100.0 * avg(any_reverted_by_others_within_30_days::int), 1) as pct_by_others_within_30_days,
            round(100.0 * avg(any_tag_reverted::int), 1) as pct_tag
        from first_day
        group by cohort_year
        order by cohort_year
    """)

    show(con, "Impact on newcomers 2008-2025 (first-day edits)", """
        with first_day as (
            select
                user_id,
                bool_or(identity_reverted) as a,
                bool_or(identity_reverted and reverter_user_id is distinct from user_id) as b,
                bool_or(identity_reverted and reverter_user_id is distinct from user_id
                        and seconds_to_revert < 30 * 86400) as c,
                bool_or(tag_reverted) as d
            from human_edits
            where event_timestamp < first_edit_at + interval 1 day
              and year(first_edit_at) between 2008 and 2025
            group by user_id
        )
        select
            count(*) as newcomers,
            sum(a::int) as a_identity_reverted,
            sum(b::int) as b_identity_reverted_by_others,
            sum(c::int) as c_by_others_within_30_days,
            sum(d::int) as d_tag_reverted
        from first_day
    """)


if __name__ == "__main__":
    main()
