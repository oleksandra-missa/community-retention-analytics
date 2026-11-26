# Memo: why newcomers leave Simple English Wikipedia, and what to test

**To:** a product team working on the newcomer experience
**Date:** 2026-11-25
**Based on:** the full edit history of Simple English Wikipedia, 2008–2025 (Wikimedia dumps, snapshot 2026-10)

## In short

Only **6.3%** of newcomers are still editing three to six months after their first edit. Most of them are lost in
the first hours and weeks. The strongest early signal is **rejection on the first day**: a quarter of newcomers
have an edit undone on day one, and they stay far less often. We recommend **an A/B test of a friendly message sent
right after that first revert**, run on several wikis at once, since on this wiki alone it would take about 4 years.

## What we found

**1. Retention fell sharply and has only partly recovered.** 14.3% of the 2008 newcomers were retained, 4.4% in
2019, and 5.3–5.8% in 2022–2025. More newcomers stay each year now (636 in 2025, against about 280 a year in
2014–2016), but only because more people join: the share who stay is about what it was in 2014 (5.4% then, 5.3% in
2024). The mix of account types doesn't explain the trend.

**2. The funnel leaks early.** Of every 1,000 people who sign up, 317 make a first edit, 68 reach a 5th edit and 6
a 50th. Those who edit almost always do it at once: 88% make their first edit within an hour of signing up. After
the first month, only 3–8% of a year's newcomers edit again in the second.

**3. Rejection on the first day goes with leaving.** 24.5% of newcomers have a first-day edit reverted by someone
else. They are retained at 3.0%, against 7.3% for the rest. Newcomers who do more on day one are both reverted more
and stay more, so we compared newcomers with the same activity, year, account type and place of first edit: a
first-day revert still goes with **0.37 times the odds of staying** (0.34–0.40). Having a page deleted on day one
looks similar (0.40). Published research on English Wikipedia found the same direction (Halfaker et al., 2013).

**4. Reverts are fast, so there is a moment to act.** About half of first reverts come within 10 minutes of the
newcomer's first edit and 68% within an hour, while the newcomer is often still on the site.

**5. Starting on mobile matters less than it did.** A third of newcomers now start on mobile (32% in 2025). They
stay less often (0.73 times the odds), but the gap has narrowed from 0.41 in 2014–2016 to 0.82 in 2021–2025.

**6. The wiki depends on very few people.** Every year the top 1% of editors make 73–85% of the edits, and half of
all edits come from 7 to 26 people. With a core this small, each newcomer who becomes a regular editor matters.

## What we recommend

**1. Test a friendly message after a newcomer's first revert.** The message would explain that reverts are normal,
show where to see why, and invite the newcomer to try again. Newcomers are split at random between the message and
the current experience, and compared on second-month retention, with guardrails on long-term retention and on how
many of their later edits are reverted. To detect a rise from 2.8% to 3.8% (5% significance, 80% power), the test
needs 4,945 newcomers per group. Simple English Wikipedia has about 2,570 reverted newcomers a year, so the result
would take about **4 years**; on wikis with five times as many reverted newcomers together, about **11 months**.
The full plan is in [ab_test_design.md](ab_test_design.md).

**2. Learn which reverted newcomers meant well.** Some reverted newcomers are vandals who never meant to stay, so the
0.37 mixes two groups. Labeling first-day edits as good-faith or not (by hand, or with a
language model checked against hand-labeled examples) would show how large the effect is for the newcomers a message
could actually help, and allow the test to target them.

**3. Find out what raised first edits since 2020.** The share of sign-ups who make a first edit rose from 22–30% in
2013–2019 to 42–46% in 2023–2025, with no change in where they edit. Something worked; knowing what (changes to the
sign-up or newcomer pages are the first place to look) would show what to keep and build on.

**4. Watch mobile, but don't prioritize it yet.** The mobile gap is closing on its own and is smaller than the revert
effect.

## What this can't tell us yet

- **Cause and effect.** The revert finding is a strong pattern that holds in every year and group, not proof that
  rejection makes people leave. That is what the A/B test is for.
- **Good faith versus vandalism.** See recommendation 2.
- **Other wikis.** Simple English Wikipedia is small and has its own rules; the pattern should be checked on the
  wikis where the test would run.
- **Logged-out editors.** A quarter to a third of edits (24–32% since 2014) come from people without an account, who
  can't be followed over time.

## Where to look

- **Dashboard:** `dashboard/` in this repository (`streamlit run dashboard/app.py`), with filters by year, account
  type and device, and an A/B test calculator.
- **Analysis:** the five notebooks in [`analysis/notebooks/`](../analysis/notebooks/), and every definition in
  [metrics_definitions.md](metrics_definitions.md).
