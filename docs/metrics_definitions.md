# Metrics definitions

The exact definitions behind every number in this analysis. Each one comes from a decision in the
[Data decisions](../AI_WORKFLOW.md#data-decisions) table, shown in brackets. Column names refer to the table
`raw_events`.

Counts are for snapshot 2026-10 of Simple English Wikipedia and can be reproduced with the `analysis/profiling/profile_*.py` scripts.

## Conventions

- **Time** is in UTC. The data ends on 2026-11-01.
- **Days** are counted from an exact moment in 24-hour units, not by calendar date. "Days 30–60" means from
  30 × 24 hours up to, but not including, 60 × 24 hours after that moment.
- **A month after the first edit** is a 30-day period: month 1 is days 0–30, month 2 is days 30–60, and so on.
- **A calendar month** (used for active editors) is a month on the calendar, such as March 2024.

## Who is counted

### Human edit [2, 3]
An edit by a registered account that isn't a bot.

```sql
event_entity = 'revision'
and event_user_is_permanent
and coalesce(event_user_is_bot_by_historical, '') = ''  -- no bot flag at the time of the edit
and coalesce(event_user_is_bot_by, '') = ''             -- and no bot flag today
```

A bot is flagged by its username (`name`) or by being in the bot group (`group`).

### Logged-out editors [3]
Edits by anonymous editors (`event_user_is_anonymous`, shown by IP address until September 2025) and by
temporary accounts (`event_user_is_temporary`, from September 2025). They are reported as a separate group in
community health and are not newcomers. Edits where none of `event_user_is_permanent`, `event_user_is_anonymous`
and `event_user_is_temporary` is true are excluded (6,546 edits).

### Newcomer [4, 5]
A registered account, created in any way, counted from its **first human edit** anywhere on the wiki.

- **Cohort:** the calendar year of the first human edit. Cohorts 2008–2025 are analyzed.
- **Size:** 133,976 newcomers, from 5,130 (2014) to 12,201 (2024) per cohort.
- **Segments:**
  - Creation method: by the person (`user_is_created_by_self`), by another user (`user_is_created_by_peer`),
    automatically by the system (`user_is_created_by_system`), or unknown (none of these).
  - Where the first edit was made: `page_namespace_historical` of the first human edit (0 = article, 2 = own profile page, etc.).

## Retention

### Retained, main metric [6]
A newcomer with **at least one human edit in days 60–180** after their first edit (months 3–6).

- 8,415 of 133,976 newcomers (6.3%).

### Retained in the second month, secondary metric [6]
A newcomer with **at least one human edit in days 30–60** after their first edit.

- 6,013 of 133,976 newcomers (4.5%).
- A newcomer can be retained by one metric and not the other: 5,442 are retained by the main metric without editing in the second month.

### Retention curve [10]
The share of newcomers with at least one human edit in each month after their first edit, months 1–10.
Month 10 ends at day 300, the longest follow-up the last cohort (December 2025) allows.

| Month | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Newcomers editing, 2008–2025 | 100% | 4.5% | 3.3% | 2.5% | 2.2% | 1.9% | 1.8% | 1.6% | 1.5% | 1.4% |

Month 1 is 100% by definition: it contains the first edit.

## Activation funnel [4, 8]

Each step must be reached **within 180 days**.

| Step | Definition | Count | Share of the step's base |
|---|---|---:|---:|
| 1. Account created | An account created by a person (self or another user) in 2008–2025, by year of creation | 148,478 | |
| 2. First edit | Step 1 accounts with a first human edit within 180 days of account creation | 47,122 | 31.7% of step 1 |
| 3. 5th edit | Newcomers (all creation methods) whose 5th human edit came within 180 days of their first | 27,220 | 20.3% of 133,976 newcomers |
| 4. 50th edit | Newcomers whose 50th human edit came within 180 days of their first | 2,803 | 2.1% of 133,976 newcomers |

Accounts created automatically or in an unknown way aren't in steps 1–2: an automatic account's creation shows
a visit, not a sign-up. They enter the funnel as newcomers, the base of steps 3–4. So steps 1–2 are counted on
sign-ups, and steps 3–4 on all newcomers.
An edit's number is its position among the editor's human edits in time order (`event_timestamp`, then `revision_id`).

## Reverted edit [7]

A human edit that was **identity reverted by someone else within 30 days**.

```sql
revision_is_identity_reverted
and revision_seconds_to_identity_revert < 30 * 86400
-- and the reverting edit (revision_first_identity_reverting_revision_id)
-- was made by someone other than the editor
```

- An identity revert is a later edit that brings the page back to exactly the content it had before this edit.
- A reverting edit by a logged-out editor counts as "someone else".
- The `mw-reverted` tag is not used: it barely exists before 2020.
- 32,878 of 133,976 newcomers (24.5%) had at least one edit from their first day reverted.

## Active editors [9]

Counted per calendar month, for registered accounts' human edits.

| Group | Definition | Median per month, 2008–2025 |
|---|---|---:|
| Editor | At least 1 human edit in the month | 1,089 |
| **Active editor** | At least **5** human edits in the month | 254 |
| **Very active editor** | At least **100** human edits in the month | 33 |

These are the thresholds Wikimedia uses in its own statistics.
