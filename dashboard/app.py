"""Newcomer retention in Simple English Wikipedia: the dashboard.

Run from the project root:
    streamlit run dashboard/app.py

Streamlit runs this script again from the top every time a filter changes. The filters are set here, in the sidebar,
so they stay the same when you move between pages; each page reads them through data.selected_groups().
"""

import streamlit as st

from data import CREATED_BY_LABELS, DEVICE_LABELS, REPO_URL

st.set_page_config(page_title="Newcomer retention", page_icon="📈", layout="wide")

pages = st.navigation([
    st.Page("views/overview.py", title="Overview", default=True),
    st.Page("views/cohort_retention.py", title="Cohort retention"),
    st.Page("views/activation_funnel.py", title="Activation funnel"),
    st.Page("views/first_day.py", title="First-day experiences"),
    st.Page("views/community_health.py", title="Community health"),
    st.Page("views/ab_test_calculator.py", title="A/B test calculator"),
])

with st.sidebar:
    st.header("Filters")
    st.slider("Cohort years", min_value=2008, max_value=2025, value=(2008, 2025), key="years")
    st.multiselect("How the account was created", options=list(CREATED_BY_LABELS),
                   default=list(CREATED_BY_LABELS), format_func=CREATED_BY_LABELS.get, key="created_by")
    st.radio("Device of the first edit", options=list(DEVICE_LABELS), format_func=DEVICE_LABELS.get, key="device",
             help="Known from 2014, when the mobile tag starts. Choosing a device leaves out earlier cohorts.")
    st.caption("Community health and the A/B test calculator use only some of the filters; each page says which.")
    st.divider()
    st.caption("Data: Wikimedia MediaWiki history dumps, snapshot 2026-10. Editors are counted, never named.")
    st.caption(f"Notebooks, docs and code: [on GitHub]({REPO_URL})")

if not st.session_state["created_by"]:
    st.warning("Choose at least one way the account was created.")
    st.stop()

pages.run()
