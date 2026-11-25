"""Profile the numbers an A/B test design needs: who could be in the test, their retention, and the sample size.

Read-only: it only runs queries on the cleaned tables (`edits`, `newcomers`, and `raw_events` for the time of a revert)
and prints tables. Run pipeline/build_tables.py first.

The candidate target groups come from notebook 02: newcomers whose first-day edit was reverted (decision 7), newcomers
who were reverted or had a page deleted on their first day (decisions 11 and 12), and all newcomers.
The candidate metrics are the two retention metrics of decision 6.

Usage:
    python analysis/profiling/profile_ab_test.py
"""

import math
from pathlib import Path

import duckdb
import pandas as pd
import statsmodels.formula.api as smf
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "wiki.duckdb"

# The most recent five full cohort years: the base for what a test started today could expect
RECENT_YEARS = (2021, 2025)

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 20)
pd.set_option("display.max_rows", 100)


def show(con, title, sql):
    print(f"\n== {title} ==")
    # convert_dtypes keeps whole numbers as integers instead of turning them into decimals
    print(con.sql(sql).df().convert_dtypes().to_string(index=False))


def newcomers_per_group(baseline, lift, alpha, power):
    """Newcomers needed in EACH group (control and treatment) to detect a rise from `baseline` to `baseline + lift`.

    proportion_effectsize turns the two rates into one standardized difference (Cohen's h), and solve_power finds
    the sample size at which a two-sided test at level `alpha` detects that difference with probability `power`.
    """
    effect = proportion_effectsize(baseline + lift, baseline)
    n = NormalIndPower().solve_power(effect_size=effect, alpha=alpha, power=power, ratio=1, alternative="two-sided")
    # Rounded up: rounding down would leave the test just short of the planned power
    return math.ceil(n)


def main():
    con = duckdb.connect(str(DB_PATH), read_only=True)

    # One row per newcomer: what happened on the first day, and when the first revert of a first-day edit came.
    # The revert time is in raw_events only (seconds from the reverted edit to the reverting edit).
    con.sql("""
        create temp table first_day as
        with first_day_edits as (
            select
                n.user_id,
                e.is_reverted,
                e.page_deleted_within_30_days,
                -- time from the newcomer's first edit to the revert of this edit
                case when e.is_reverted then
                    epoch(e.event_timestamp - n.first_edit_at) + r.revision_seconds_to_identity_revert
                end as seconds_from_first_edit_to_revert
            from newcomers n
            join edits e
              on e.editor_type = 'registered'
             and e.user_id = n.user_id
             and e.event_timestamp < n.first_edit_at + interval 1 day
            join raw_events r
              on r.event_entity = 'revision'
             and r.revision_id = e.revision_id
        )
        select
            n.user_id,
            n.cohort_year,
            n.first_edit_at,
            n.retained_months_3_to_6::int as retained_main,
            n.retained_second_month::int as retained_second_month,
            bool_or(f.is_reverted) as reverted,
            bool_or(f.is_reverted or f.page_deleted_within_30_days) as reverted_or_deleted,
            min(f.seconds_from_first_edit_to_revert) / 3600 as hours_to_first_revert
        from newcomers n
        join first_day_edits f using (user_id)
        group by all
    """)

    show(con, "Check: newcomers in the table (should be 133,976, of whom 32,878 reverted)", """
        select count(*) as newcomers, sum(reverted::int) as reverted, sum(reverted_or_deleted::int) as reverted_or_deleted
        from first_day
    """)

    # The three candidate target groups, by cohort year, with both retention metrics
    group_sql = """
        select
            cohort_year,
            '{name}' as target_group,
            count(*) as newcomers,
            round(100 * avg(retained_main), 2) as retained_main_pct,
            round(100 * avg(retained_second_month), 2) as retained_second_month_pct
        from first_day
        where {condition} and cohort_year >= 2019
        group by 1
    """
    groups = {
        "a) reverted": "reverted",
        "b) reverted or page deleted": "reverted_or_deleted",
        "c) all newcomers": "true",
    }
    union = " union all ".join(group_sql.format(name=name, condition=condition) for name, condition in groups.items())
    show(con, "Candidate target groups by cohort year: size and retention", f"select * from ({union}) order by 2, 1")

    # Per-year averages over the recent cohorts: the baseline a test would start from
    recent = con.sql(f"""
        select * from ({union.replace('cohort_year >= 2019', f'cohort_year between {RECENT_YEARS[0]} and {RECENT_YEARS[1]}')})
    """).df()
    baseline = recent.groupby("target_group").agg(newcomers_per_year=("newcomers", "mean"))
    for name, condition in groups.items():
        rates = con.sql(f"""
            select avg(retained_main) as main, avg(retained_second_month) as second_month
            from first_day where {condition} and cohort_year between {RECENT_YEARS[0]} and {RECENT_YEARS[1]}
        """).fetchone()
        baseline.loc[name, "retained_main"] = rates[0]
        baseline.loc[name, "retained_second_month"] = rates[1]
    print(f"\n== Baseline, cohorts {RECENT_YEARS[0]}-{RECENT_YEARS[1]} (newcomers per year is the yearly average) ==")
    print(baseline.round(4).to_string())

    # A message after a revert can only be sent once the revert has happened: how soon is that?
    show(con, f"Reverted newcomers {RECENT_YEARS[0]}-{RECENT_YEARS[1]}: time from first edit to the first revert", f"""
        select
            count(*) as reverted_newcomers,
            round(100 * avg((hours_to_first_revert < 1)::int), 1) as within_1_hour_pct,
            round(100 * avg((hours_to_first_revert < 24)::int), 1) as within_1_day_pct,
            round(100 * avg((hours_to_first_revert < 24 * 7)::int), 1) as within_7_days_pct,
            round(median(hours_to_first_revert) * 60, 0) as median_minutes
        from first_day
        where reverted and cohort_year between {RECENT_YEARS[0]} and {RECENT_YEARS[1]}
    """)

    # Arrivals are not even across the year: the slowest months set how long enrolment takes
    show(con, f"Reverted newcomers per calendar month, {RECENT_YEARS[0]}-{RECENT_YEARS[1]}", f"""
        select
            month(first_edit_at) as month,
            -- an average over the five years
            round(count(*) / 5, 0) as reverted_per_month
        from first_day
        where reverted and cohort_year between {RECENT_YEARS[0]} and {RECENT_YEARS[1]}
        group by 1 order by 1
    """)

    # Sample size and duration for every combination of target group, metric, smallest lift and test settings
    follow_up_months = {"retained_second_month": 2, "retained_main": 6}
    settings = {"5% / 80%": (0.05, 0.80), "10% / 80%": (0.10, 0.80), "5% / 90%": (0.05, 0.90)}
    rows = []
    for name in groups:
        per_year = baseline.loc[name, "newcomers_per_year"]
        for metric, follow_up in follow_up_months.items():
            rate = baseline.loc[name, metric]
            for lift_pp in (0.5, 1.0, 2.0):
                for setting, (alpha, power) in settings.items():
                    per_group = newcomers_per_group(rate, lift_pp / 100, alpha, power)
                    enrol_months = 2 * per_group / (per_year / 12)
                    rows.append({
                        "target_group": name, "metric": metric, "baseline_pct": round(100 * rate, 2),
                        "lift_pp": lift_pp, "relative_lift_pct": round(100 * lift_pp / 100 / rate),
                        "alpha_power": setting, "per_group": per_group, "total": 2 * per_group,
                        "enrol_months": round(enrol_months, 1),
                        # the last newcomer enrolled still needs the whole metric window before the result is known
                        "months_to_result": round(enrol_months + follow_up, 1),
                    })
    sizes = pd.DataFrame(rows)
    print("\n== Sample size and duration (two-sided test, 50/50 split) ==")
    print(sizes.to_string(index=False))

    # A test can be made more precise by adjusting for what is known before the treatment. The sample it needs
    # shrinks by the share of variation those characteristics explain (R-squared). Only characteristics fixed before
    # the message count: the message is sent at the first revert, so edits after it could be changed by the message.
    covariates = con.sql(f"""
        with first_day_edits as (
            select
                n.user_id,
                n.created_by,
                n.first_edit_namespace,
                n.retained_second_month::int as retained_second_month,
                e.event_timestamp,
                e.revision_id,
                list_contains(string_split(coalesce(e.revision_tags, ''), ','), 'mobile edit') as is_mobile,
                case when e.is_reverted then
                    e.event_timestamp + to_seconds(r.revision_seconds_to_identity_revert)
                end as reverted_at
            from newcomers n
            join edits e
              on e.editor_type = 'registered'
             and e.user_id = n.user_id
             and e.event_timestamp < n.first_edit_at + interval 1 day
            join raw_events r
              on r.event_entity = 'revision'
             and r.revision_id = e.revision_id
            where n.cohort_year between {RECENT_YEARS[0]} and {RECENT_YEARS[1]}
        ),
        first_revert as (
            select user_id, min(reverted_at) as first_reverted_at
            from first_day_edits
            group by user_id
            having first_reverted_at is not null
        )
        select
            f.user_id,
            case when any_value(f.created_by) in ('self', 'system') then any_value(f.created_by) else 'other' end
                as created_by,
            (any_value(f.first_edit_namespace) = 0)::int as first_edit_in_article,
            arg_min(f.is_mobile, (f.event_timestamp, f.revision_id))::int as first_edit_mobile,
            least(count(*) filter (where f.event_timestamp < r.first_reverted_at), 10) as edits_before_revert,
            any_value(f.retained_second_month) as retained_second_month
        from first_day_edits f
        join first_revert r using (user_id)
        group by f.user_id
    """).df()
    model = smf.ols("retained_second_month ~ C(created_by) + first_edit_in_article + first_edit_mobile"
                    " + C(edits_before_revert)", covariates).fit()
    print(f"\n== Adjusting for what is known before the message ({len(covariates):,} reverted newcomers) ==")
    print(f"R-squared: {model.rsquared:.4f}, so the sample needed would shrink by {model.rsquared:.1%}")


if __name__ == "__main__":
    main()
