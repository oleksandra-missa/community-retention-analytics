# Data decisions

The cleaning rules and metric definitions I chose for this analysis, why, and how many rows, editors or edits each one affects. The notebooks, scripts and other documents refer to them by number.

| # | Decision | Reason | Impact |
|---|---|---|---|
| 1 | Analyze Simple English Wikipedia (`simplewiki`) | English text, so examples are readable; small enough for a laptop (1 GB download) | Covers the whole history, 2001–2026 |
| 2 | **Bots:** an edit is a bot edit if its editor is flagged as a bot, by username or by the bot group, either at the time of the edit or today. Bot edits are excluded from the analysis | Using the flag at the time keeps the normal edits of 34 experienced editors who had a bot flag only for short automated tasks; adding today's flag catches 5 recently approved bots whose older edits have no flag | Removes 2,683,109 of 8,975,240 edits by registered editors (29.9%), from 763 accounts. Bot edits stay in `raw_events` |
