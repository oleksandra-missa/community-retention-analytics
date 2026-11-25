"""Overview: headline numbers for the filtered newcomers, and the main findings."""

import streamlit as st

from data import MIN_NEWCOMERS, filter_summary, rate, selected_groups

st.title("Why do newcomers leave?")
st.write(
    "Newcomer retention in **Simple English Wikipedia**, 2008–2025. A newcomer is a registered account counted from "
    "its first edit; they are **retained** if they edit again 60–180 days later. Use the filters on the left to "
    "look at one period, account type or device."
)
filter_summary()

groups = selected_groups()
newcomers = groups["newcomers"].sum()


def show_rate(part):
    value = rate(groups[part].sum(), newcomers)
    return "too few" if value is None else f"{value:.1f}%"


tiles = st.columns(4)
tiles[0].metric("Newcomers", f"{newcomers:,}")
tiles[1].metric("Retained in months 3–6", show_rate("retained_main"),
                help="At least one edit 60–180 days after the first edit. The main metric.")
tiles[2].metric("Retained in the second month", show_rate("retained_second_month"),
                help="At least one edit 30–60 days after the first edit.")
tiles[3].metric("Reverted on the first day", show_rate("reverted"),
                help="At least one edit from their first 24 hours was undone by someone else within 30 days.")
if newcomers < MIN_NEWCOMERS:
    st.caption(f"Rates are hidden for fewer than {MIN_NEWCOMERS} newcomers.")

st.subheader("What the analysis found")
st.markdown("""
- **Retention fell, then partly recovered.** 14.3% of the 2008 newcomers were retained, 4.4% in 2019, and
  5.3–5.8% in 2022–2025. Who joins (the mix of account types) doesn't explain it.
- **Rejection on the first day goes with leaving.** A quarter of newcomers have a first-day edit reverted. With
  activity, year and account type held fixed, they have 0.37 times the odds of staying.
- **Most sign-ups never edit,** but more do now: 42–46% made a first edit in 2023–2025, against 22–30% in
  2013–2019.
- **The wiki runs on very few people.** Every year the top 1% of editors made 73–85% of the edits.
- **An A/B test could check whether a friendly message after a revert helps,** but on this wiki alone it would take
  about 4 years to detect a 1-point rise.
""")
st.caption(
    "The pages on the left show each part. The full analysis, with the methods and checks, is in the project's "
    "notebooks; the A/B test plan is in docs/ab_test_design.md."
)
