"""Shared pieces for the dashboard pages: loading the summary tables, the sidebar filters and the chart style.

The summary tables in dashboard/data/ are built by pipeline/build_dashboard_data.py (decision 17).
"""

from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

DATA_DIR = Path(__file__).resolve().parent / "data"

# Rates based on fewer newcomers than this are hidden: by chance alone they can be off by about ±6 points (decision 17)
MIN_NEWCOMERS = 50

CREATED_BY_LABELS = {
    "self": "Signed up here",
    "system": "Created automatically",
    "other": "Other (by another user or unknown)",
}
DEVICE_LABELS = {"all": "All devices", "mobile": "Mobile", "desktop": "Desktop"}

# Chart colors: the first categorical hues in fixed order, neutral ink for text, a recessive grid
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
TEXT, TEXT_MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


@st.cache_data
def load(name):
    """Read one summary table. Cached, so the file is read once, not every time a filter changes."""
    return pd.read_csv(DATA_DIR / f"{name}.csv")


def selected_groups():
    """The rows of newcomer_groups.csv that match the sidebar filters set in app.py."""
    groups = load("newcomer_groups")
    first_year, last_year = st.session_state["years"]
    keep = groups["cohort_year"].between(first_year, last_year) & groups["created_by"].isin(
        st.session_state["created_by"])
    if st.session_state["device"] != "all":
        # The device is only known from 2014, so earlier cohorts drop out when a device is chosen
        keep &= groups["device"] == st.session_state["device"]
    return groups[keep]


def selected_years():
    first_year, last_year = st.session_state["years"]
    return first_year, last_year


def rate(part, total):
    """Percentage, or None when it is based on too few newcomers to be read."""
    return 100 * part / total if total >= MIN_NEWCOMERS else None


def add_rate(table, part_column, total_column, name):
    """Add a percentage column; rows under MIN_NEWCOMERS get an empty value, so charts leave a gap."""
    table[name] = [rate(part, total) for part, total in zip(table[part_column], table[total_column])]
    return table


def hidden_note(table, total_column, label_column):
    """A caption naming the rows hidden by the small-group rule, if any."""
    hidden = table.loc[table[total_column] < MIN_NEWCOMERS, label_column].astype(str).tolist()
    if hidden:
        st.caption(f"Hidden, fewer than {MIN_NEWCOMERS} newcomers: {', '.join(hidden)}.")


def filter_summary():
    """One line describing the current filters, shown under each page title."""
    first_year, last_year = selected_years()
    if st.session_state["device"] != "all":
        first_year = max(first_year, 2014)  # the device is only known from 2014
    methods = ", ".join(CREATED_BY_LABELS[m].split(" (")[0].lower() for m in st.session_state["created_by"])
    device = DEVICE_LABELS[st.session_state["device"]].lower()
    st.caption(f"Newcomers of {first_year}–{last_year} · {methods} · {device}")


def style(chart, height=320):
    """The shared chart style: neutral text, a recessive grid, no frame. height=None keeps the chart's own heights."""
    if height:
        chart = chart.properties(height=height)
    return (
        chart.properties(background=SURFACE)
        .configure_view(strokeWidth=0)
        .configure_axis(labelColor=TEXT_MUTED, titleColor=TEXT_MUTED, gridColor=GRID, domainColor=GRID,
                        tickColor=GRID, labelFontSize=12, titleFontSize=12, titleFontWeight="normal")
        .configure_legend(labelColor=TEXT, titleColor=TEXT_MUTED, orient="top", title=None, labelFontSize=12)
        .configure_title(color=TEXT, anchor="start", fontSize=15)
    )


def year_axis(title="Cohort year (year of the first edit)"):
    # Years as plain numbers, without a thousands separator
    return alt.X("year:O", title=title, axis=alt.Axis(labelAngle=0, values=list(range(2008, 2026, 2))))


def line_by_year(table, value_column, value_title, series_column=None, colors=None, title="", percent=True,
                 extra_tooltip=(), x_title="Cohort year (year of the first edit)"):
    """A line chart over cohort years, with points and a hover tooltip on each point. None if nothing can be shown."""
    if table[value_column].notna().sum() == 0:
        return None
    value_format = ".1f" if percent else ",.0f"
    encoding = {
        "x": year_axis(x_title),
        "y": alt.Y(f"{value_column}:Q", title=value_title, scale=alt.Scale(zero=True)),
        "tooltip": [alt.Tooltip("year:O", title="Year"),
                    alt.Tooltip(f"{value_column}:Q", title=value_title, format=value_format),
                    *extra_tooltip],
    }
    if series_column:
        # Colors follow the order in which the series first appear in the table, not the alphabet
        series = list(dict.fromkeys(table[series_column]))
        encoding["color"] = alt.Color(f"{series_column}:N", sort=series,
                                      scale=alt.Scale(domain=series, range=colors or [BLUE, ORANGE, AQUA]))
        encoding["tooltip"].insert(0, alt.Tooltip(f"{series_column}:N", title=" "))
    base = alt.Chart(table, title=title).encode(**encoding)
    lines = base.mark_line(strokeWidth=2, color=BLUE)
    points = base.mark_point(filled=True, size=60, color=BLUE, stroke=SURFACE, strokeWidth=1.5)
    return style(lines + points)


def show_chart(chart):
    """Draw a chart, or a note when every value was hidden by the small-group rule."""
    if chart is None:
        st.info(f"Too few newcomers in the selection to show this chart (fewer than {MIN_NEWCOMERS} in every group).")
    else:
        st.altair_chart(chart, width="stretch")
