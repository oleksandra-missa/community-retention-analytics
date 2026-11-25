"""Activation funnel: from sign-up to the 1st, 5th and 50th edit, each within 180 days."""

import altair as alt
import pandas as pd
import streamlit as st

from data import (BLUE, TEXT, add_rate, filter_summary, hidden_note, line_by_year, load, selected_groups,
                  selected_years, show_chart, style)

st.title("Activation funnel")
filter_summary()
st.write(
    "Each step must be reached within 180 days. Accounts created automatically (when someone signed in to another "
    "Wikimedia wiki first) show a visit, not a sign-up, so they join the funnel at their first edit."
)

groups = selected_groups()
newcomers = groups["newcomers"].sum()
steps = pd.DataFrame({
    "step": ["Newcomers (1st edit)", "5th edit", "50th edit"],
    "count": [newcomers, groups["fifth_edit"].sum(), groups["fiftieth_edit"].sum()],
})
steps["pct_of_newcomers"] = 100 * steps["count"] / max(newcomers, 1)
# Each bar is labeled with its count and its share of newcomers, so the bars need no axis
steps["label"] = [f"{count:,} ({pct:.1f}%)" for count, pct in zip(steps["count"], steps["pct_of_newcomers"])]

bars = alt.Chart(steps, title="From the first edit to the 50th").encode(
    y=alt.Y("step:N", sort=None, title=None, axis=alt.Axis(labelLimit=220, labelFontSize=13)),
    x=alt.X("count:Q", axis=None, scale=alt.Scale(domain=[0, max(newcomers, 1) * 1.18])),
    tooltip=[alt.Tooltip("step:N", title="Step"), alt.Tooltip("count:Q", title="Newcomers", format=","),
             alt.Tooltip("pct_of_newcomers:Q", title="% of newcomers", format=".1f")],
)
labels = bars.mark_text(align="left", dx=6, color=TEXT, fontSize=13).encode(text="label:N")
st.altair_chart(style(bars.mark_bar(color=BLUE, cornerRadiusEnd=4, height=24) + labels, height=130),
                width="stretch")

left, right = st.columns(2)
by_year = groups.groupby("cohort_year", as_index=False)[["newcomers", "fifth_edit", "fiftieth_edit"]].sum().rename(
    columns={"cohort_year": "year"})
by_year = add_rate(by_year, "fifth_edit", "newcomers", "fifth_pct")
by_year = add_rate(by_year, "fiftieth_edit", "fifth_edit", "fiftieth_of_fifth_pct")

with left:
    show_chart(line_by_year(by_year, "fifth_pct", "% of newcomers", title="Newcomer → 5th edit",
                            extra_tooltip=[alt.Tooltip("newcomers:Q", title="Newcomers", format=",")]))
    hidden_note(by_year, "newcomers", "year")
with right:
    show_chart(line_by_year(by_year, "fiftieth_of_fifth_pct", "% of those with a 5th edit",
                            title="5th edit → 50th edit",
                            extra_tooltip=[alt.Tooltip("fifth_edit:Q", title="With a 5th edit", format=",")]))
    hidden_note(by_year.rename(columns={"fifth_edit": "with_fifth_edit"}), "with_fifth_edit", "year")

st.subheader("Before the first edit: people who sign up")
st.write("Accounts created by a person (on this wiki, or by another user for them) that made a first edit within "
         "180 days. Only the year filter applies here.")
signups = load("signups").rename(columns={"created_year": "year"})
first_year, last_year = selected_years()
signups = signups[signups["year"].between(first_year, last_year)]
signups = add_rate(signups, "first_edit_within_180_days", "accounts_created", "first_edit_pct")
show_chart(line_by_year(signups, "first_edit_pct", "% of sign-ups", title="Sign-up → first edit, by year of sign-up",
                        x_title="Year of sign-up",
                        extra_tooltip=[alt.Tooltip("accounts_created:Q", title="Sign-ups", format=","),
                                       alt.Tooltip("first_edit_within_180_days:Q", title="Made a first edit",
                                                   format=",")]))
