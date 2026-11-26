# A/B test design: a message after a newcomer's first revert

A plan for an experiment a product team could run on Simple English Wikipedia. The choices behind it are
decision 16 in the [Data decisions](data_decisions.md) table. The numbers are calculated in
[analysis/notebooks/05_ab_test_power.ipynb](../analysis/notebooks/05_ab_test_power.ipynb) and
[analysis/profiling/profile_ab_test.py](../analysis/profiling/profile_ab_test.py), from the cohorts 2021–2025.

## Summary

| | |
|---|---|
| **Treatment** | A friendly message on the newcomer's talk page, sent when an edit from their first day is reverted |
| **Who** | Newcomers whose first-day edit is reverted by someone else: about 2,566 a year |
| **Split** | 50% treatment, 50% control (nothing changes), at random by account |
| **Primary metric** | Retained in the second month: at least one edit in days 30–60 after the first edit. Baseline 2.78% |
| **Smallest effect to detect** | +1 percentage point (2.78% → 3.78%) |
| **Settings** | Two-sided test, 5% significance level, 80% power |
| **Sample size** | 4,945 newcomers per group, 9,890 in all |
| **Duration** | 46 months of enrolment, result after 48 months on this wiki alone |

## 1. Why this test

[Notebook 02](../analysis/notebooks/02_first_experiences.ipynb) found that newcomers whose first-day edit is reverted stay
much less often. With activity, cohort year, account type and place of the first edit held fixed, a revert goes with
0.37 times the odds of staying. But that is a correlation. Newcomers who get reverted may differ in ways the data
can't see, for example by being vandals who never meant to stay.

An experiment answers the causal question. Reverting a good-faith edit is often right, so the test doesn't change
whether edits are reverted. It changes **how a revert feels**: does an explanation and an invitation to try again
make reverted newcomers more likely to come back?

## 2. Hypothesis

- **Null hypothesis:** the message doesn't change second-month retention among reverted newcomers.
- **Alternative hypothesis:** it does, up or down. The test is two-sided because a message could also backfire,
  for example by drawing attention to the rejection.

## 3. The treatment

- **Trigger:** the first time an edit from a newcomer's first day (the 24 hours from their first edit) is reverted
  by someone else. In 2021–2025, about half of these reverts came within 10 minutes of the first edit, 68.2% within an
  hour and 87.8% within a day, so most newcomers would still be on the site.
- **Treatment group:** gets a short message on their talk page. It says that edits are often undone and that this
  is normal, explains how to see why (the page history and the reverter's edit summary), links to a page with
  help for new editors, and invites them to try again or ask a question.
- **Control group:** the current experience. Both groups may also get whatever message the reverting editor leaves,
  since that is part of the current experience.

## 4. Who is in the test, and how they are split

- **Eligible:** a registered account, not a bot, whose first-day edit is reverted by someone else (decisions 2, 4
  and 7). Each account enters the test once, at its first such revert.
- **Unit of randomization:** the account. Each eligible account is assigned at the trigger by a random 50/50 draw,
  for example a hash of its account ID with a salt unique to this test, and stays in its group.
- **Randomization** is what makes the comparison fair: chance decides who gets the message, so the two groups are
  alike in everything else (activity, account type, device, good or bad faith), and a difference in retention is
  caused by the message.
- **Everyone assigned is analyzed** in the group they were assigned to, even if they never read the message or were
  later blocked. Leaving such newcomers out would make the groups unlike each other again. This is called
  intention-to-treat analysis.

## 5. Metrics

| Role | Metric | Definition | Baseline |
|---|---|---|---:|
| **Primary** | Retained in the second month | At least one human edit in days 30–60 after the first edit (decision 6) | 2.78% |
| Secondary | Retained in months 3–6 | At least one human edit in days 60–180 (decision 6) | 2.96% |
| Guardrail | Retained in months 3–6 | Must not be lower in the treatment group | 2.96% |
| Guardrail | Later edits reverted | Share of the group's human edits in the 30 days after the trigger that are reverted by someone else (decision 7) | measured in the test |

The second month comes first because its result is known 4 months sooner, and for reverted newcomers the two
metrics are almost equal (2.78% and 2.96%), so it needs about the same sample. The guardrails make sure the message
doesn't buy a short-term rise at the cost of long-term retention, or bring back newcomers whose next edits get
reverted too, which would add work for the editors who review them.

## 6. Sample size and duration

The **minimum detectable effect** is the smallest effect the test is built to find. It is set at +1 point, a
36% relative rise. A rise of 2 points (72%) is a lot to expect from one message; 0.5 points is more realistic but
would take far longer.

The **significance level** (5%) is the chance of a false alarm, and **power** (80%) is the chance of detecting a
real effect of +1 point.

| Smallest effect | Per group | In all | Months to the result |
|---:|---:|---:|---:|
| +0.5 point | 18,390 | 36,780 | 174 |
| **+1 point** | **4,945** | **9,890** | **48** |
| +1.5 points | 2,347 | 4,694 | 24 |
| +2 points | 1,401 | 2,802 | 15 |

The months count enrolment at 214 reverted newcomers a month, plus 2 months for the last newcomer's second month to
end. A simulation of 2,000 experiments of this size confirmed the settings (4.5% false alarms and 78.8% detection,
against the planned 5% and 80%). Splitting the real reverted newcomers of 2021–2025 into random halves gave 4.9%
false alarms, so the calculation holds on real data.

## 7. Analysis plan

Decided before the test starts, so the result can't be shaped after seeing the data:

1. **Check the split:** the two groups should be close to 50/50. A significant imbalance (a chi-square test at 1%)
   means the assignment or the logging is broken, and the result can't be trusted.
2. **Compare the primary metric** with a two-proportion z-test, two-sided, at 5%. Report the difference in points
   with its 95% confidence interval, not only whether it is significant.
3. **Check the guardrails** and the secondary metric.
4. **Look at the result only once, at the planned size.** Checking every month and stopping at the first
   significant result raises the real chance of a false alarm well above 5%.

## 8. Risks and limits

- **It takes about 4 years on this wiki alone.** Simple English Wikipedia is small: about 2,566 reverted newcomers
  a year.
- **Vandals are in both groups.** The message can't help someone who never meant to stay, so they dilute the effect.
  Targeting only good-faith newcomers would need good-faith labels for their edits in real time, and would shrink the group even
  more.
- **Retention changes from year to year** (2.02–3.56% in 2021–2025). This doesn't bias the test, because the control
  group is measured at the same time, but over 4 years the baseline used for sizing may drift.
- **The community has to agree.** Messages from an automated account need the community's approval, and the
  message text should be written with experienced editors.

## 9. How to make it shorter

| Option | Effect on the duration |
|---|---|
| **Run the same test on several wikis at once** (recommended) | With 5 times as many reverted newcomers in total, 11 months; with 10 times as many, 7 months |
| Accept a larger smallest effect | +2 points: 15 months, but a smaller real effect would likely be missed |
| Adjust for what is known before the message (creation method, first edit place, mobile, edits before the revert) | Only 2.2% fewer newcomers needed: these explain little of who stays |

**Recommendation:** run the test on several language editions at once, with the same message translated and the same
analysis per wiki and pooled. On Simple English Wikipedia alone, run it only if a large effect is the one worth
finding.
