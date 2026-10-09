# Tracker blocks

The generated skills share one tracker. Pick the blocks for the user's backend and paste them into the templates where the placeholder sits. Fill `<...>` values; don't leave them in.

Standard columns (an existing sheet may use other header names: map them, and write the user's headers into `{{TRACKER_SPEC}}` instead):

| Col | Header | Content |
|---|---|---|
| A | Role | Job title as the posting states it |
| B | Company | Company name, properly capitalised |
| C | Date Applied | ISO `YYYY-MM-DD` |
| D | Status | One of `Saved`, `Applied`, `Interviewing`, `Offer`, `Rejected`, `Withdrawn` |
| E | Stage | Current step when interviewing: `Recruiter screen`, `Hiring manager`, `Technical`, `Case / presentation`, `Panel`, `Final` |
| F | Pay | Only if the posting states it, e.g. `80-95k`, with the currency symbol when it isn't the user's home currency; add ` base` when only base is stated |
| G | Work Mode | `Remote`, `Hybrid`, `Hybrid – 3 days office`, `In office`, or `Not stated` |
| H | Link | Job posting URL, the company's own page in preference to LinkedIn |
| I | Notes | Referral, recruiter name, next step, short history |
| J | Last Update | ISO date of the last change to the row |

---

## Google Sheet

### {{TRACKER_SPEC}}

```markdown
The tracker is the Google Sheet **<sheet name>**:
- ID: `<sheet id>`
- Link: https://docs.google.com/spreadsheets/d/<sheet id>/edit
- Tab: `<tab>`. Row 1 is the header. Data starts on row 2.

<the columns table above, with the user's actual headers>
```

### {{TRACKER_READ}}

```markdown
Read `'<tab>'!A:J` with the Google Sheets connector's `get_values` (load it with ToolSearch if it only appears as a deferred tool). If the connector isn't available or not authenticated, say so in one line (the user can run `/mcp` to connect it) and carry on without the tracker.
```

### {{TRACKER_WRITE}}

```markdown
Writing needs the **Google Sheets** connector (`get_values`, `update_values`, `append_values`). Drive alone can read the sheet but not edit it. If the Sheets tools aren't available after a ToolSearch, stop and tell {{USER}} to connect Google Sheets. Never create a copy of the sheet or a separate file.

If a `google-workspace` skill is available, load it before the first write. In any case:
- Read `'<tab>'!A:J` right before writing. Rows move when {{USER}} edits by hand.
- Prefix text that Sheets could parse as a number or date with `'` (except column C, which should be a real date).
- Re-read after writing to check the result.
```

### {{WATCH_TRACKER_SYNC}}

```markdown
## Step 0: Sync the application tracker

1. Read `'<tab>'!A1:J1000` including the header row, with the Google Sheets connector's `get_values` (fall back to the Google Drive connector's CSV export). Load the tools with ToolSearch if they're deferred.
2. Save the result to the scratchpad directory exactly as returned, then run one of:
   ```bash
   python3 .claude/skills/{{WATCH}}/scripts/job_watch.py applied --json <path>
   python3 .claude/skills/{{WATCH}}/scripts/job_watch.py applied --csv <path>
   ```
3. If the sheet can't be read, carry on with the previous `applied.json` and say the tracker snapshot is stale, with the file's modified date. Don't skip the run.
```

---

## Markdown file

### {{TRACKER_SPEC}}

```markdown
The tracker is the markdown table in `{{DATA}}/Applications.md`. {{USER}} may edit it by hand too. The first table in the file is the tracker; `{{WATCH}}` reads it by its column headers, so never rename or reorder them.

<the columns table above>
```

### {{TRACKER_READ}}

```markdown
Read `{{DATA}}/Applications.md`.
```

### {{TRACKER_WRITE}}

```markdown
- Read `{{DATA}}/Applications.md` right before editing; {{USER}} may have changed it.
- One row per application, one line per row. Replace any `|` inside a cell with `/`. Write links as plain URLs.
- Add new rows at the bottom of the table, never below the status legend.
- Re-read after editing to check the table still has the same number of columns in every row.
```

### {{WATCH_TRACKER_SYNC}}

```markdown
## Step 0: Tracker

The markdown tracker `{{DATA}}/Applications.md` is read automatically by `fetch`. If `fetch` returns a `tracker_error`, report it and carry on.
```

---

## Email

### {{EMAIL_STEP}}: Gmail

```markdown
Search Gmail for each company, in parallel, with `search_threads`: the company name and its domain where known, limited to mail since a few days before the application date, e.g. `(Acme OR acme.com) after:2026/09/25`. ATS senders count: `greenhouse.io`, `ashbyhq.com`, `lever.co`, `myworkday.com`, `smartrecruiters.com`, `workablemail.com`, `teamtailor.com`, LinkedIn job messages. Open matching threads with `get_thread`. Ignore marketing and job-alert newsletters.
```

### {{EMAIL_STEP}}: Outlook

```markdown
Search Outlook mail for each company, in parallel, using the connected Outlook/Microsoft 365 tool's message search: the company name and its domain where known, since a few days before the application date. ATS senders count: `greenhouse.io`, `ashbyhq.com`, `lever.co`, `myworkday.com`, `smartrecruiters.com`, `workablemail.com`, `teamtailor.com`, LinkedIn job messages. Open the matching messages. Ignore marketing and job-alert newsletters.
```

### {{EMAIL_STEP}}: no email connector

```markdown
No email connector is set up. Ask {{USER}} to paste or summarise any replies they've had since the last clean-up (one line per company is enough). If they later connect Gmail or Outlook, re-run `/job-search-setup` or ask Claude to add an email step here.
```

---

## Job-watch email check

### {{WATCH_EMAIL_CHECK}}: with an email connector

Paste this into job-watch when Gmail or Outlook is connected. Use the Gmail or Outlook search wording from `{{EMAIL_STEP}}` above for the tool names.

```markdown
## Step 0b: Check email for application news

This often runs unattended on a schedule, so it applies only clear-cut changes and leaves everything else for {{USER}}. It needs the <Gmail / Outlook> connector (load it with ToolSearch if deferred). If it isn't available, skip this step and say so in one line of the report.

**Window:** mail since the day before the previous run (the last `runs` date in `.claude/skills/{{WATCH}}/state.json`), or the last 14 days if there's no previous run.

**Rows in scope:** every tracker row whose Status isn't `Rejected`, `Withdrawn` or `Offer`, including rows with an empty status. {{TRACKER_READ}}

1. **Search**, in parallel:
   - One search per in-scope company: the company name, plus its domain where known, since the window start.
   - One sweep of job-board senders, which often send rejections from no-reply addresses that don't name the company: `greenhouse.io`, `ashbyhq.com`, `lever.co`, `myworkday.com`, `smartrecruiters.com`, `workablemail.com`, `teamtailor.com`, `pinpointhq.com`, `linkedin.com`.
   Open the matching messages. Ignore job alerts, newsletters and marketing.
2. **Match** each relevant email to one row by company, and by role title when the company has several rows. If it's unclear which row, change nothing and list it under "Needs you".
3. **Classify and apply.** Only these moves happen automatically, and only when the email says so explicitly:

   | Email says | New Status | Allowed from |
   |---|---|---|
   | Rejection: "not moving forward", "pursuing other candidates", "position filled" | `Rejected` | empty, `Saved`, `Applied`, `Interviewing` |
   | Interview invite, scheduling link, a booked call with a recruiter or hiring manager | `Interviewing` (and Stage) | empty, `Saved`, `Applied` |
   | Written offer, or a verbal offer confirmed in writing | `Offer` | empty, `Applied`, `Interviewing` |

   For each change, prepend a short dated entry to Notes, keeping what's there (`2026-10-09: rejected after hiring manager round (email from Jane Doe); `), and set Last Update to today. When the row is already `Interviewing` and a new round is booked, update only Stage, Notes and Last Update.
   Never move a status backwards. Never change Role, Company, Date Applied, Pay, Work Mode or Link. Never add or delete rows.
4. **Leave for {{USER}}** (no change, list in the report under "Needs you"): "thanks for applying" confirmations, recruiters asking for information or availability, anything waiting on {{USER}}'s reply, emails from companies with no tracker row (new recruiter outreach), and anything ambiguous.
5. **Write safely.**
{{TRACKER_WRITE}}
   Locate rows again by company and role right before writing, not by position from the first read.
6. **Never** send, reply to, draft, label, archive or mark as read any email.

If this step changed the tracker, sync it again before Step 1 so the snapshot is current (a markdown tracker is re-read by `fetch` automatically).
```

### {{WATCH_EMAIL_CHECK}}: no email connector

Replace the placeholder with nothing.

### {{WATCH_EMAIL_REPORT}}

With an email connector:

```markdown
- **Tracker updates** from Step 0b: each change as company, role, old → new status, and evidence (sender, date, one-line gist), so {{USER}} can revert any that are wrong. Then **Needs you**: emails awaiting a reply, interviews to schedule, recruiter outreach from companies not in the tracker, and anything ambiguous. Say "no application news" if there was none, or that the email check was skipped and why.
```

Without one: replace the placeholder with nothing.
