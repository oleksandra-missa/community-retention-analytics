"""Cohort retention: the share of each year's newcomers who stay, and how editing fades month by month."""

import altair as alt
import pandas as pd
import streamlit as st

from data import (AQUA, BLUE, MIN_NEWCOMERS, ORANGE, SURFACE, add_rate, filter_summary, hidden_note, line_by_year,
                  selected_groups, show_chart, style)

st.title("Cohort retention")
filter_summary()

metric = st.segmented_control(
    "Metric", options=["retained_main", "retained_second_month"], default="retained_main", required=True,
    format_func={"retained_main": "Months 3–6 (main)", "retained_second_month": "Second month"}.get,
)
metric_title = {"retained_main": "Retained in months 3–6 (%)",
                "retained_second_month": "Retained in the second month (%)"}[metric]

groups = selected_groups()
by_year = groups.groupby("cohort_year", as_index=False)[["newcomers", metric]].sum().rename(
    columns={"cohort_year": "year"})
by_year = add_rate(by_year, metric, "newcomers", "retained_pct")

show_chart(line_by_year(by_year, "retained_pct", metric_title, title="Retention by cohort year",
                        extra_tooltip=[alt.Tooltip("newcomers:Q", title="Newcomers", format=","),
                                       alt.Tooltip(f"{metric}:Q", title="Retained", format=",")]))
hidden_note(by_year, "newcomers", "year")

st.subheader("How editing fades after the first month")
st.write(
    "The share of newcomers who edit in each 30-day month after their first edit. Month 1 is always 100%, because it "
    "contains the first edit, so the chart starts at month 2. The cohorts are grouped into three periods."
)

periods = {"2008–2013": (2008, 2013), "2014–2020": (2014, 2020), "2021–2025": (2021, 2025)}
rows = []
for period, (first, last) in periods.items():
    in_period = groups[groups["cohort_year"].between(first, last)]
    newcomers = in_period["newcomers"].sum()
    for month in range(2, 11):
        rows.append({"period": period, "month": month, "newcomers": newcomers,
                     "editing": in_period[f"editing_month_{month}"].sum()})
curve = add_rate(pd.DataFrame(rows), "editing", "newcomers", "editing_pct").dropna(subset=["editing_pct"])

if curve.empty:
    st.info(f"Too few newcomers in the selection (fewer than {MIN_NEWCOMERS} in every period).")
else:
    base = alt.Chart(curve, title="Newcomers editing, by month after the first edit").encode(
        x=alt.X("month:O", title="Month after the first edit", axis=alt.Axis(labelAngle=0)),
        y=alt.Y("editing_pct:Q", title="Newcomers editing (%)", scale=alt.Scale(zero=True)),
        # each period keeps its own color, and the legend lists only the periods shown
        color=alt.Color("period:N", scale=alt.Scale(domain=list(periods), range=[BLUE, ORANGE, AQUA]),
                        legend=alt.Legend(values=list(curve["period"].unique()))),
        tooltip=[alt.Tooltip("period:N", title="Cohorts"), alt.Tooltip("month:O", title="Month"),
                 alt.Tooltip("editing_pct:Q", title="Editing (%)", format=".1f"),
                 alt.Tooltip("newcomers:Q", title="Newcomers", format=",")],
    )
    chart = base.mark_line(strokeWidth=2) + base.mark_point(filled=True, size=60, stroke=SURFACE, strokeWidth=1.5)
    st.altair_chart(style(chart), width="stretch")
    st.caption("Only the periods inside the selected years are shown.")
