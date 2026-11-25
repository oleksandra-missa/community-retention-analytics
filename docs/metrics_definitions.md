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
community health and are not newcomers. The bot rule applies to them too: 4,121 anonymous edits have a bot flag
and are removed. Edits where none of `event_user_is_permanent`, `event_user_is_anonymous` and
`event_user_is_temporary` is true are excluded (6,546 edits).

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

## Page deleted [11]

A human edit whose **page was deleted within 30 days** of the edit.

```sql
revision_is_deleted_by_page_deletion
and revision_deleted_by_page_deletion_timestamp < event_timestamp + interval 30 day
```

- Edits on pages that were later deleted are kept in every other count. This includes pages that were deleted
  and later restored, whose edits keep the deletion mark.
- 25,385 of 133,976 newcomers (18.9%) had at least one edit from their first day whose page was deleted within 30 days.
  This counts every first-day edit, not only the first edit: 25,013 newcomers made their very first edit on a page
  that was deleted at any time later, and the two groups overlap but neither contains the other.

## First-day experiences [12]

A newcomer's **first day** is the 24 hours from their first human edit. Two experiences are measured over the
first-day edits, on every part of the wiki:

- **Reverted on the first day:** at least one first-day edit is a [reverted edit](#reverted-edit-7).
  32,878 newcomers (24.5%).
- **Page deleted on the first day:** at least one first-day edit's [page was deleted](#page-deleted-11) within 30 days.
  25,385 newcomers (18.9%).
- **Started on mobile [15]:** the first human edit has the `mobile edit` tag, which covers the mobile website and the
  Wikipedia apps. Measured for the cohorts 2014–2025, since mobile editing for registered users began in 2013.
  25,531 of 97,170 newcomers (26.3%).

Both happen within 31 days of the first edit, so they always come before the main retention window (days 60–180).
The **number of first-day edits** is used in groups: 1, 2–4, 5–9 and 10+.

Drivers of retention are compared in two ways [13]: within groups of newcomers with the same number of first-day
edits, cohort period or creation method, and with a logistic regression that holds all these factors fixed at once
(see `analysis/notebooks/02_first_experiences.ipynb`).

## Active editors [9]

Counted per calendar month, for registered accounts' human edits.

| Group | Definition | Median per month, 2008–2025 |
|---|---|---:|
| Editor | At least 1 human edit in the month | 1,089 |
| **Active editor** | At least **5** human edits in the month | 254 |
| **Very active editor** | At least **100** human edits in the month | 33 |

These are the thresholds Wikimedia uses in its own statistics.

## Concentration of work [14]

Per calendar year, registered editors are ranked by their number of human edits that year, on every part of the
wiki. Ties are broken by account ID, so the ranking is the same every run.

| Measure | Definition | 2008–2025 |
|---|---|---:|
| **Top 1% share** | Share of the year's edits made by the first 1% of the ranking (rounded up) | 73.2–84.6% |
| **Editors making half** | How many editors, counting down the ranking, it takes to reach half of the year's edits | 7–26 |

Logged-out editors aren't ranked, since they can't be counted as people; their edits are reported as a share of all
human edits.

## Cleaned tables

`pipeline/build_tables.py` builds these tables in `data/wiki.duckdb` from `raw_events`, applying the definitions above.

### `edits`: one row per edit by a registered human or a logged-out editor (8,330,211 rows)

| Column | Meaning |
|---|---|
| `revision_id` | Edit ID |
| `event_timestamp` | When the edit was made |
| `editor_type` | `registered` (6,153,960 edits) or `logged_out` (2,176,251) |
| `user_id` | Account ID; empty for anonymous editors |
| `page_id`, `page_namespace` | The page, and which part of the wiki it was in at the time |
| `text_bytes_diff` | How much the page grew (+) or shrank (−), in bytes |
| `revision_tags` | Labels the software added, as comma-separated text |
| `is_reverted` | A [reverted edit](#reverted-edit-7) |
| `page_deleted_within_30_days` | The edit's [page was deleted](#page-deleted-11) within 30 days |

### `accounts`: one row per registered account (1,761,982 rows)

| Column | Meaning |
|---|---|
| `user_id` | Account ID |
| `created_at` | When the account was created (the account-creation event's time) |
| `created_by` | `self`, `peer` (another user), `system` (automatically) or `unknown` |
| `first_edit_at` | The account's first human edit; empty if it never made one |

### `newcomers`: one row per [newcomer](#newcomer-4-5) of 2008–2025 (133,976 rows)

| Column | Meaning |
|---|---|
| `user_id`, `cohort_year`, `first_edit_at` | The newcomer, their cohort and when their clock starts |
| `account_created_at`, `created_by` | When and how the account was created |
| `first_edit_namespace` | Where the first edit was made |
| `edits_total` | All their human edits, at any time |
| `retained_months_3_to_6` | The [main retention metric](#retained-main-metric-6) |
| `retained_second_month` | The [secondary retention metric](#retained-in-the-second-month-secondary-metric-6) |
| `fifth_edit_within_180_days`, `fiftieth_edit_within_180_days` | Funnel steps 3 and 4 |
