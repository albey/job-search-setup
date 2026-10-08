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
