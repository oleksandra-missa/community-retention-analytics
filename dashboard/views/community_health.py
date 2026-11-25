"""Community health: active editors, logged-out editing and how concentrated the work is."""

import altair as alt
import streamlit as st

from data import BLUE, ORANGE, TEXT, line_by_year, load, selected_years, show_chart, style, year_axis

st.title("Community health")
first_year, last_year = selected_years()
st.caption(f"Calendar years {first_year}–{last_year}. Only the year filter applies on this page: these numbers "
           "cover every editor, not only newcomers.")

health = load("community_health")
health = health[health["year"].between(first_year, last_year)].copy()
health["logged_out_pct"] = 100 * health["logged_out_edits"] / health["human_edits"]

latest = health.iloc[-1]
tiles = st.columns(4)
tiles[0].metric(f"Active editors, {latest['year']:.0f}", f"{latest['active_editors_avg_month']:,.0f}",
                help="Registered editors with 5 or more edits in a calendar month, in an average month of the year.")
tiles[1].metric(f"Very active editors, {latest['year']:.0f}", f"{latest['very_active_editors_avg_month']:,.0f}",
                help="100 or more edits in a calendar month.")
tiles[2].metric(f"Edits by the top 1%, {latest['year']:.0f}", f"{latest['top_1pct_share']:.1f}%")
tiles[3].metric(f"Edits by logged-out editors, {latest['year']:.0f}", f"{latest['logged_out_pct']:.1f}%")

left, right = st.columns(2)
with left:
    editors = health.melt(id_vars="year", value_vars=["editors_avg_month", "active_editors_avg_month"],
                          var_name="group", value_name="editors")
    editors["group"] = editors["group"].map({"editors_avg_month": "Editors (1+ edit)",
                                             "active_editors_avg_month": "Active editors (5+ edits)"})
    show_chart(line_by_year(editors, "editors", "Editors per month", series_column="group",
                            colors=[BLUE, ORANGE], percent=False, title="Registered editors in an average month",
                            x_title="Year"))
with right:
    show_chart(line_by_year(health, "very_active_editors_avg_month", "Editors per month", percent=False,
                            title="Very active editors (100+ edits) in an average month",
                            x_title="Year"))

left, right = st.columns(2)
with left:
    show_chart(line_by_year(health, "top_1pct_share", "% of registered editors' edits",
                            title="Share of edits made by the top 1% of editors", x_title="Year"))
with right:
    bars = alt.Chart(health, title="Editors who together make half of all edits").encode(
        x=year_axis("Year"),
        y=alt.Y("editors_making_half:Q", title="Editors"),
        tooltip=[alt.Tooltip("year:O", title="Year"), alt.Tooltip("editors_making_half:Q", title="Editors")],
    )
    labels = bars.mark_text(dy=-8, color=TEXT, fontSize=11).encode(text="editors_making_half:Q")
    st.altair_chart(style(bars.mark_bar(color=BLUE, cornerRadiusEnd=4) + labels), width="stretch")

show_chart(line_by_year(health, "logged_out_pct", "% of human edits",
                        title="Share of human edits made by logged-out editors", x_title="Year"))
st.caption("Logged-out editors are anonymous editors and, from September 2025, temporary accounts. They can't be "
           "counted as people, so they appear as a share of edits.")
