"""First-day experiences: retention of newcomers who were reverted, had a page deleted, or started on mobile."""

import altair as alt
import pandas as pd
import streamlit as st

from data import (BLUE, MIN_NEWCOMERS, ORANGE, TEXT, add_rate, filter_summary, hidden_note, line_by_year,
                  selected_groups, show_chart, style)

st.title("First-day experiences")
filter_summary()
st.write(
    "A newcomer's first day is the 24 hours from their first edit. **Reverted:** someone else undid one of those "
    "edits within 30 days. **Page deleted:** the page of one of those edits was deleted within 30 days. "
    "**Mobile:** the first edit was made on the mobile website or app (known from 2014)."
)

groups = selected_groups()
total = groups["newcomers"].sum()
retained = groups["retained_main"].sum()


def pair(experience, label_yes, label_no, newcomers_yes, retained_yes, newcomers_all, retained_all):
    # The "no" group is everyone in the selection minus the "yes" group
    return [
        {"experience": experience, "group": label_yes, "newcomers": newcomers_yes, "retained": retained_yes},
        {"experience": experience, "group": label_no, "newcomers": newcomers_all - newcomers_yes,
         "retained": retained_all - retained_yes},
    ]


rows = pair("Reverted on the first day", "Yes", "No", groups["reverted"].sum(),
            groups["reverted_retained_main"].sum(), total, retained)
rows += pair("Page deleted on the first day", "Yes", "No", groups["page_deleted"].sum(),
             groups["page_deleted_retained_main"].sum(), total, retained)
known_device = groups[groups["device"] != "unknown"]
mobile = known_device[known_device["device"] == "mobile"]
rows += pair("Started on mobile (2014–2025)", "Yes", "No", mobile["newcomers"].sum(), mobile["retained_main"].sum(),
             known_device["newcomers"].sum(), known_device["retained_main"].sum())
comparison = add_rate(pd.DataFrame(rows), "retained", "newcomers", "retained_pct")
shown = comparison.dropna(subset=["retained_pct"])

if shown.empty:
    st.info(f"Too few newcomers in the selection (fewer than {MIN_NEWCOMERS} in every group).")
else:
    # One small chart per experience, all on the same scale so the bars can be compared across them
    x_max = shown["retained_pct"].max() * 1.15
    for experience in dict.fromkeys(shown["experience"]):
        base = alt.Chart(shown[shown["experience"] == experience], title=experience).encode(
            y=alt.Y("group:N", title=None, sort=["Yes", "No"]),
            x=alt.X("retained_pct:Q", title="Retained in months 3–6 (%)", scale=alt.Scale(domain=[0, x_max]),
                    axis=alt.Axis(tickMinStep=1)),
            color=alt.Color("group:N", scale=alt.Scale(domain=["Yes", "No"], range=[ORANGE, BLUE]), legend=None),
            tooltip=[alt.Tooltip("group:N", title=experience),
                     alt.Tooltip("newcomers:Q", title="Newcomers", format=","),
                     alt.Tooltip("retained_pct:Q", title="Retained (%)", format=".1f")],
        )
        labels = base.mark_text(align="left", dx=6).encode(text=alt.Text("retained_pct:Q", format=".1f"),
                                                           color=alt.value(TEXT))
        # alt.Step gives each bar its own 34-pixel band, so the chart grows with the number of bars
        chart = (base.mark_bar(cornerRadiusEnd=4) + labels).properties(height=alt.Step(34))
        st.altair_chart(style(chart, height=None), width="stretch")
    hidden_note(comparison.assign(label=comparison["experience"] + ": " + comparison["group"]), "newcomers", "label")

st.subheader("Reverted or not, by cohort year")
by_year = groups.groupby("cohort_year", as_index=False)[
    ["newcomers", "retained_main", "reverted", "reverted_retained_main"]].sum().rename(columns={"cohort_year": "year"})
long = pd.concat([
    pd.DataFrame({"year": by_year["year"], "group": "Reverted on the first day", "newcomers": by_year["reverted"],
                  "retained": by_year["reverted_retained_main"]}),
    pd.DataFrame({"year": by_year["year"], "group": "Not reverted",
                  "newcomers": by_year["newcomers"] - by_year["reverted"],
                  "retained": by_year["retained_main"] - by_year["reverted_retained_main"]}),
])
long = add_rate(long, "retained", "newcomers", "retained_pct")
show_chart(line_by_year(long, "retained_pct", "Retained in months 3–6 (%)", series_column="group",
                        colors=[ORANGE, BLUE],
                        extra_tooltip=[alt.Tooltip("newcomers:Q", title="Newcomers", format=",")]))
hidden_note(long.assign(label=long["group"] + " " + long["year"].astype(str)), "newcomers", "label")

st.info(
    "These are plain comparisons. Newcomers who make more edits on their first day are both more likely to be "
    "reverted and more likely to stay, which hides part of the gap. Holding that and the year, account type and place "
    "of the first edit fixed, a first-day revert goes with 0.37 times the odds of staying, a deleted page 0.40, and a "
    "mobile start 0.73 (notebook 02). That is a strong pattern, not proof that rejection makes people leave: the "
    "A/B test is how to find out."
)
