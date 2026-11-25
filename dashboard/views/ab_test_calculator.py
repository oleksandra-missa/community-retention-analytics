"""A/B test calculator: how many newcomers a test needs, and how long it takes on this wiki (decision 16)."""

import math

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize

from data import BLUE, SURFACE, load, style

BASE_YEARS = (2021, 2025)  # the five most recent full cohorts, as in notebook 05

st.title("A/B test calculator")
st.caption(f"Baselines from the cohorts {BASE_YEARS[0]}–{BASE_YEARS[1]}, all account types and devices. "
           "The sidebar filters don't apply on this page.")
st.write(
    "The planned test sends a friendly message to newcomers when an edit from their first day is reverted, and "
    "compares them with a control group that gets nothing new ([design](https://github.com/oleksandra-missa/"
    "community-retention-analytics/blob/main/docs/ab_test_design.md)). Change the settings to see how many newcomers "
    "the test needs and how long collecting them would take."
)

groups = load("newcomer_groups")
recent = groups[groups["cohort_year"].between(*BASE_YEARS)]
years = BASE_YEARS[1] - BASE_YEARS[0] + 1

left, right = st.columns(2)
with left:
    target = st.radio("Who is in the test", ["Reverted on the first day", "All newcomers"],
                      help="All newcomers would test a different treatment: a welcome message after the first edit.")
    metric = st.radio("Primary metric", ["Second month", "Months 3–6"],
                      help="The result is known 2 months (second month) or 6 months (months 3–6) after the last "
                           "newcomer joins the test.")
    wikis = st.slider("Newcomers available, compared with Simple English Wikipedia alone", 1, 10, 1, format="%d×",
                      help="Running the same test on several wikis at once multiplies the newcomers available.")
with right:
    lift_pp = st.slider("Smallest rise worth detecting (percentage points)", 0.25, 3.0, 1.0, step=0.25,
                        help="The minimum detectable effect. Halving it roughly quadruples the sample needed.")
    alpha = st.select_slider("Significance level", options=[0.01, 0.05, 0.10], value=0.05,
                             format_func=lambda a: f"{a:.0%}",
                             help="The chance of a false alarm: declaring a win when the message does nothing.")
    power = st.select_slider("Power", options=[0.70, 0.80, 0.90], value=0.80, format_func=lambda p: f"{p:.0%}",
                             help="The chance of detecting a real effect of the chosen size.")

# Baseline rate and newcomers per year for the chosen group and metric
if target == "Reverted on the first day":
    newcomers = recent["reverted"].sum()
    retained = recent["reverted_retained_second_month" if metric == "Second month" else "reverted_retained_main"].sum()
else:
    newcomers = recent["newcomers"].sum()
    retained = recent["retained_second_month" if metric == "Second month" else "retained_main"].sum()
baseline = retained / newcomers
per_month = newcomers / years / 12 * wikis
follow_up_months = 2 if metric == "Second month" else 6


def newcomers_per_group(lift):
    # Cohen's h turns the two rates into one standardized difference; solve_power finds the sample size per group
    effect = proportion_effectsize(baseline + lift, baseline)
    n = NormalIndPower().solve_power(effect_size=effect, alpha=alpha, power=power, ratio=1, alternative="two-sided")
    return math.ceil(n)  # rounded up, so the test isn't just short of the planned power


def months_to_result(per_group):
    return 2 * per_group / per_month + follow_up_months


per_group = newcomers_per_group(lift_pp / 100)
months = months_to_result(per_group)

tiles = st.columns(4)
tiles[0].metric("Baseline", f"{baseline:.2%}",
                help=f"{metric} retention of this group, {BASE_YEARS[0]}–{BASE_YEARS[1]}.")
tiles[1].metric("Newcomers per group", f"{per_group:,}", help="Control and treatment each need this many.")
tiles[2].metric("Newcomers in all", f"{2 * per_group:,}", help=f"About {per_month:,.0f} join the test a month.")
tiles[3].metric("Months to the result", f"{months:.0f}",
                help=f"Months to enrol everyone, plus {follow_up_months} for the last newcomer's metric window.")
st.caption(f"A rise from {baseline:.2%} to {baseline + lift_pp / 100:.2%}: "
           f"{lift_pp / 100 / baseline:.0%} in relative terms.")

lifts = np.arange(0.25, 3.01, 0.05)
curve = pd.DataFrame({"lift_pp": lifts, "months": [months_to_result(newcomers_per_group(x / 100)) for x in lifts]})
chosen = pd.DataFrame({"lift_pp": [lift_pp], "months": [months]})
line = alt.Chart(curve, title="Months until the result, by the smallest rise worth detecting").mark_line(
    color=BLUE, strokeWidth=2).encode(
    x=alt.X("lift_pp:Q", title="Smallest rise worth detecting (percentage points)",
            axis=alt.Axis(values=[0.5, 1, 1.5, 2, 2.5, 3], format=".1f")),
    # A log scale, because the months range from a few to hundreds; each gridline doubles the previous one
    y=alt.Y("months:Q", title="Months (log scale)", scale=alt.Scale(type="log"),
            axis=alt.Axis(values=[3, 6, 12, 24, 48, 96, 192, 384, 768, 1536], format=",.0f")),
    tooltip=[alt.Tooltip("lift_pp:Q", title="Rise (points)", format=".2f"),
             alt.Tooltip("months:Q", title="Months", format=",.0f")],
)
point = alt.Chart(chosen).mark_point(filled=True, size=110, color=BLUE, stroke=SURFACE, strokeWidth=2).encode(
    x="lift_pp:Q", y="months:Q")
st.altair_chart(style(line + point), width="stretch")

with st.expander("What these terms mean"):
    st.markdown("""
- **Randomization:** each eligible newcomer is put in the treatment or the control group by chance, so the groups
  are alike in everything else and a difference in retention is caused by the message.
- **Minimum detectable effect:** the smallest effect the test is built to detect. Smaller effects need many more
  newcomers.
- **Significance level:** the chance of a false alarm, a "significant" result when the message does nothing.
- **Power:** the chance of detecting a real effect of the chosen size. With 80%, one real effect in five is missed.
""")
