"""Build the small summary tables the dashboard reads, from the cleaned tables in data/wiki.duckdb.

The dashboard can't use the 2.6 GB database online, so this script writes counts by year and group to CSV files in
dashboard/data/. They hold no account IDs or usernames, only counts (decision 17). Run pipeline/build_tables.py first.

Files written:
- newcomer_groups.csv: one row per cohort year × creation method × device of the first edit, with the number of
  newcomers, how many were retained, reached the 5th and 50th edit, had a first-day edit reverted or a page deleted,
  and how many edited in each month after their first edit (months 1-10).
- signups.csv: per year, accounts created by a person and how many made a first edit within 180 days.
- community_health.csv: per year, active editors, logged-out editing and how concentrated the work is.

Usage:
    python pipeline/build_dashboard_data.py
"""

from pathlib import Path

import duckdb

PROJECT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_DIR / "data" / "wiki.duckdb"
OUT_DIR = PROJECT_DIR / "dashboard" / "data"


def build_newcomer_groups(con):
    # One row per newcomer: their segment and their first-day experiences (decisions 12 and 15)
    con.sql("""
        create temp table newcomer_summary as
        with first_day_edits as (
            select
                n.user_id,
                e.is_reverted,
                e.page_deleted_within_30_days,
                list_contains(string_split(coalesce(e.revision_tags, ''), ','), 'mobile edit') as is_mobile,
                row_number() over (partition by n.user_id order by e.event_timestamp, e.revision_id) as edit_number
            from newcomers n
            join edits e
              on e.editor_type = 'registered'
             and e.user_id = n.user_id
             and e.event_timestamp < n.first_edit_at + interval 1 day
        ),
        first_day as (
            select
                user_id,
                bool_or(is_reverted) as reverted,
                bool_or(page_deleted_within_30_days) as page_deleted,
                bool_or(is_mobile) filter (where edit_number = 1) as first_edit_mobile
            from first_day_edits
            group by user_id
        )
        select
            n.user_id,
            n.cohort_year,
            -- the grouping used in notebooks 01 and 02: another user and unknown are small, so they are combined
            case when n.created_by in ('self', 'system') then n.created_by else 'other' end as created_by,
            -- the mobile tag only exists from 2013, so earlier cohorts have no device (decision 15)
            case when n.cohort_year < 2014 then 'unknown'
                 when f.first_edit_mobile then 'mobile'
                 else 'desktop' end as device,
            n.retained_months_3_to_6::int as retained_main,
            n.retained_second_month::int as retained_second_month,
            n.fifth_edit_within_180_days::int as fifth_edit,
            n.fiftieth_edit_within_180_days::int as fiftieth_edit,
            f.reverted::int as reverted,
            f.page_deleted::int as page_deleted
        from newcomers n
        join first_day f using (user_id)
    """)

    # Months after the first edit in which each newcomer edited: month 1 is days 0-30, month 2 days 30-60, ...
    # (decision 10). Month 10 ends at day 300, the longest follow-up the last cohort allows.
    con.sql("""
        create temp table months_edited as
        select distinct
            n.user_id,
            floor(date_diff('second', n.first_edit_at, e.event_timestamp) / 86400.0 / 30)::int + 1 as month
        from newcomers n
        join edits e on e.editor_type = 'registered' and e.user_id = n.user_id
        where date_diff('second', n.first_edit_at, e.event_timestamp) < 300 * 86400
    """)

    month_columns = ",\n".join(
        f"count(*) filter (where m.month = {k}) as editing_month_{k}" for k in range(1, 11))
    return con.sql(f"""
        with per_group as (
            select
                cohort_year, created_by, device,
                count(*) as newcomers,
                sum(retained_main)::bigint as retained_main,
                sum(retained_second_month)::bigint as retained_second_month,
                sum(fifth_edit)::bigint as fifth_edit,
                sum(fiftieth_edit)::bigint as fiftieth_edit,
                sum(reverted)::bigint as reverted,
                sum(retained_main * reverted)::bigint as reverted_retained_main,
                sum(retained_second_month * reverted)::bigint as reverted_retained_second_month,
                sum(page_deleted)::bigint as page_deleted,
                sum(retained_main * page_deleted)::bigint as page_deleted_retained_main
            from newcomer_summary
            group by all
        ),
        per_group_months as (
            select s.cohort_year, s.created_by, s.device, {month_columns}
            from newcomer_summary s
            join months_edited m using (user_id)
            group by all
        )
        select *
        from per_group
        join per_group_months using (cohort_year, created_by, device)
        order by cohort_year, created_by, device
    """).df()


def build_signups(con):
    # Steps 1-2 of the activation funnel: accounts created by a person (decision 8)
    return con.sql("""
        select
            year(created_at) as created_year,
            count(*) as accounts_created,
            count(*) filter (where first_edit_at < created_at + interval 180 day) as first_edit_within_180_days
        from accounts
        where created_by in ('self', 'peer')
          and year(created_at) between 2008 and 2025
        group by 1
        order by 1
    """).df()


def build_community_health(con):
    # The same definitions as notebook 04 (decisions 3, 9 and 14)
    return con.sql("""
        with per_editor_month as (
            select date_trunc('month', event_timestamp) as edit_month, user_id, count(*) as edits
            from edits
            where editor_type = 'registered' and year(event_timestamp) between 2008 and 2025
            group by all
        ),
        monthly as (
            select
                edit_month,
                count(*) as editors,
                count(*) filter (where edits >= 5) as active_editors,
                count(*) filter (where edits >= 100) as very_active_editors
            from per_editor_month
            group by edit_month
        ),
        active as (
            select
                year(edit_month) as year,
                avg(editors) as editors_avg_month,
                avg(active_editors) as active_editors_avg_month,
                avg(very_active_editors) as very_active_editors_avg_month
            from monthly
            group by 1
        ),
        logged_out as (
            select
                year(event_timestamp) as year,
                count(*) as human_edits,
                count(*) filter (where editor_type = 'logged_out') as logged_out_edits
            from edits
            where year(event_timestamp) between 2008 and 2025
            group by 1
        ),
        per_editor as (
            select year(event_timestamp) as year, user_id, count(*) as edits
            from edits
            where editor_type = 'registered' and year(event_timestamp) between 2008 and 2025
            group by all
        ),
        ranked as (
            select
                *,
                row_number() over (partition by year order by edits desc, user_id) as editor_rank,
                count(*) over (partition by year) as editors_in_year,
                sum(edits) over (partition by year order by edits desc, user_id) as edits_up_to_this_editor,
                sum(edits) over (partition by year) as edits_in_year
            from per_editor
        ),
        concentration as (
            select
                year,
                100 * sum(edits) filter (where editor_rank <= ceil(0.01 * editors_in_year)) / any_value(edits_in_year)
                    as top_1pct_share,
                min(editor_rank) filter (where edits_up_to_this_editor >= 0.5 * edits_in_year) as editors_making_half
            from ranked
            group by year
        )
        select *
        from active
        join logged_out using (year)
        join concentration using (year)
        order by year
    """).df()


def main():
    con = duckdb.connect(str(DB_PATH), read_only=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    tables = {
        "newcomer_groups": build_newcomer_groups(con),
        "signups": build_signups(con),
        "community_health": build_community_health(con),
    }
    for name, table in tables.items():
        path = OUT_DIR / f"{name}.csv"
        table.to_csv(path, index=False, float_format="%.4f")
        print(f"{path.relative_to(PROJECT_DIR)}: {len(table)} rows, {path.stat().st_size / 1024:.1f} KB")

    # Checks against the totals in docs/metrics_definitions.md
    groups = tables["newcomer_groups"]
    print("\nChecks:")
    print(f"  newcomers: {groups['newcomers'].sum():,} (expected 133,976)")
    print(f"  retained, main metric: {groups['retained_main'].sum():,} (expected 8,415)")
    print(f"  retained in the second month: {groups['retained_second_month'].sum():,} (expected 6,013)")
    print(f"  editing in month 2: {groups['editing_month_2'].sum():,} (should equal the line above)")
    print(f"  reverted on the first day: {groups['reverted'].sum():,} (expected 32,878)")
    print(f"  page deleted on the first day: {groups['page_deleted'].sum():,} (expected 25,385)")
    print(f"  5th edit: {groups['fifth_edit'].sum():,} (expected 27,220)")
    print(f"  50th edit: {groups['fiftieth_edit'].sum():,} (expected 2,803)")
    signups = tables["signups"]
    print(f"  sign-ups: {signups['accounts_created'].sum():,} (expected 148,478); "
          f"first edit: {signups['first_edit_within_180_days'].sum():,} (expected 47,122)")
    mobile = groups[groups["device"] != "unknown"]
    print(f"  started on mobile, 2014-2025: {mobile.loc[mobile['device'] == 'mobile', 'newcomers'].sum():,} "
          f"of {mobile['newcomers'].sum():,} (expected 25,531 of 97,170)")


if __name__ == "__main__":
    main()
