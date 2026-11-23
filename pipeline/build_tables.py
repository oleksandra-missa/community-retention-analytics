"""Build the cleaned tables from `raw_events`, applying the decisions in AI_WORKFLOW.md.

It creates three tables in data/wiki.duckdb, replacing them if they exist:

- `edits`: one row per edit by a registered human or a logged-out editor (decisions 2, 3, 7, 11)
- `accounts`: one row per registered account, with how it was created and its first human edit (decisions 3, 4)
- `newcomers`: one row per newcomer of 2008-2025, with retention and funnel results (decisions 5, 6, 8)

`raw_events` is only read, never changed. The script prints the row count before and after every step.
The definitions are in docs/metrics_definitions.md.

Usage:
    python pipeline/build_tables.py
"""

from pathlib import Path

import duckdb

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "wiki.duckdb"

FIRST_COHORT_YEAR = 2008  # decision 5
LAST_COHORT_YEAR = 2025
REVERT_DAYS = 30  # decision 7
DELETION_DAYS = 30  # decision 11
FUNNEL_DAYS = 180  # decision 8


def count(con, table):
    return con.sql(f"select count(*) from {table}").fetchone()[0]


def report(step, rows_before, rows_after):
    """Print one filtering step: rows before, rows after and how many were removed."""
    print(f"  {step:<55} {rows_before:>12,} -> {rows_after:>12,}  ({rows_before - rows_after:,} removed)")


def build_edits(con):
    print("\nedits")

    rows_all_events = count(con, "raw_events")
    con.sql("""
        create temp table step_revisions as
        select * from raw_events where event_entity = 'revision'
    """)
    report("keep edits (event_entity = 'revision')", rows_all_events, count(con, "step_revisions"))

    # Decision 3: every edit needs a known editor type; logged-out editors are kept as their own group.
    con.sql("""
        create temp table step_known_type as
        select
            *,
            case when event_user_is_permanent then 'registered'
                 else 'logged_out' end as editor_type
        from step_revisions
        where event_user_is_permanent or event_user_is_anonymous or event_user_is_temporary
    """)
    report("remove edits of unknown editor type (decision 3)", count(con, "step_revisions"),
           count(con, "step_known_type"))

    # Decision 2: a bot edit is flagged by name or group, at the time of the edit or today.
    con.sql("""
        create temp table step_no_bots as
        select * from step_known_type
        where coalesce(event_user_is_bot_by_historical, '') = ''
          and coalesce(event_user_is_bot_by, '') = ''
    """)
    report("remove bot edits (decision 2)", count(con, "step_known_type"), count(con, "step_no_bots"))

    # The final table, with the reverted (decision 7) and page-deleted (decision 11) flags.
    # The reverting edit is looked up to find who made it: undoing your own edit doesn't count.
    # coalesce(..., false) turns "unknown" into "no", e.g. when the editor has no ID (anonymous).
    con.sql(f"""
        create or replace table edits as
        select
            e.revision_id,
            e.event_timestamp,
            e.editor_type,
            e.event_user_id as user_id,
            e.page_id,
            e.page_namespace_historical as page_namespace,
            e.revision_text_bytes_diff as text_bytes_diff,
            e.revision_tags,
            coalesce(e.revision_is_identity_reverted, false)
                and e.revision_seconds_to_identity_revert < {REVERT_DAYS} * 86400
                and not coalesce(reverter.event_user_id = e.event_user_id, false)
                as is_reverted,
            coalesce(e.revision_is_deleted_by_page_deletion, false)
                and coalesce(e.revision_deleted_by_page_deletion_timestamp
                             < e.event_timestamp + interval {DELETION_DAYS} day, false)
                as page_deleted_within_30_days
        from step_no_bots e
        left join raw_events reverter
            on reverter.event_entity = 'revision'
           and reverter.revision_id = e.revision_first_identity_reverting_revision_id
    """)
    print(f"  edits table: {count(con, 'edits'):,} rows")


def build_accounts(con):
    print("\naccounts")

    con.sql("""
        create temp table step_account_creations as
        select * from raw_events where event_entity = 'user' and event_type = 'create'
    """)
    rows_created = count(con, "step_account_creations")

    # Decision 3: temporary accounts are logged-out editors, not registered accounts.
    # Decision 4: creation method is kept as a segment.
    # The create event's own time is used: user_creation_timestamp is years later for about 8,000 accounts.
    con.sql("""
        create or replace table accounts as
        select
            a.user_id,
            a.event_timestamp as created_at,
            case when a.user_is_created_by_self then 'self'
                 when a.user_is_created_by_peer then 'peer'
                 when a.user_is_created_by_system then 'system'
                 else 'unknown' end as created_by,
            first_edits.first_edit_at
        from step_account_creations a
        left join (
            select user_id, min(event_timestamp) as first_edit_at
            from edits
            where editor_type = 'registered'
            group by user_id
        ) first_edits on first_edits.user_id = a.user_id
        where not coalesce(a.user_is_temporary, false)
    """)
    report("remove temporary accounts (decision 3)", rows_created, count(con, "accounts"))


def build_newcomers(con):
    print("\nnewcomers")

    # Each registered editor's human edits, numbered in time order, with days since their first edit.
    # revision_id breaks ties between edits made in the same second.
    con.sql("""
        create temp table registered_edits as
        select
            user_id,
            event_timestamp,
            page_namespace,
            row_number() over (partition by user_id order by event_timestamp, revision_id) as edit_number,
            date_diff('second', min(event_timestamp) over (partition by user_id), event_timestamp) / 86400.0
                as days_since_first_edit
        from edits
        where editor_type = 'registered'
    """)

    rows_accounts = count(con, "accounts")
    con.sql("create temp table step_editors as select * from accounts where first_edit_at is not null")
    report("keep accounts with at least one human edit", rows_accounts, count(con, "step_editors"))

    # Decision 5: newcomers are counted from their first human edit, cohorts 2008-2025.
    # Decision 6: the two retention metrics. Decision 8: the 5th and 50th edit funnel steps.
    con.sql(f"""
        create or replace table newcomers as
        select
            a.user_id,
            year(a.first_edit_at) as cohort_year,
            a.first_edit_at,
            a.created_at as account_created_at,
            a.created_by,
            min(e.page_namespace) filter (where e.edit_number = 1) as first_edit_namespace,
            count(*) as edits_total,
            count(*) filter (where e.days_since_first_edit >= 60 and e.days_since_first_edit < 180) >= 1
                as retained_months_3_to_6,
            count(*) filter (where e.days_since_first_edit >= 30 and e.days_since_first_edit < 60) >= 1
                as retained_second_month,
            count(*) filter (where e.edit_number = 5 and e.days_since_first_edit < {FUNNEL_DAYS}) = 1
                as fifth_edit_within_180_days,
            count(*) filter (where e.edit_number = 50 and e.days_since_first_edit < {FUNNEL_DAYS}) = 1
                as fiftieth_edit_within_180_days
        from step_editors a
        join registered_edits e using (user_id)
        where year(a.first_edit_at) between {FIRST_COHORT_YEAR} and {LAST_COHORT_YEAR}
        group by all
    """)
    report(f"keep first edits in {FIRST_COHORT_YEAR}-{LAST_COHORT_YEAR} (decision 5)",
           count(con, "step_editors"), count(con, "newcomers"))


def print_summary(con):
    """Headline numbers, to compare with docs/metrics_definitions.md."""
    print("\nsummary")
    print(con.sql("""
        select
            count(*) as newcomers,
            sum(retained_months_3_to_6::int) as retained_months_3_to_6,
            sum(retained_second_month::int) as retained_second_month,
            sum(fifth_edit_within_180_days::int) as fifth_edit_within_180_days,
            sum(fiftieth_edit_within_180_days::int) as fiftieth_edit_within_180_days
        from newcomers
    """))


def main():
    con = duckdb.connect(str(DB_PATH))
    build_edits(con)
    build_accounts(con)
    build_newcomers(con)
    print_summary(con)
    con.close()


if __name__ == "__main__":
    main()
