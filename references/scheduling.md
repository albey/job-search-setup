# Scheduling job-watch

Ask the user how often (daily, weekdays, twice a week, weekly, or manual only), then how. Pick a time when the machine or account is likely free; early morning local time means fresh results when they start the day.

| Frequency | Cron |
|---|---|
| Daily 07:00 | `0 7 * * *` |
| Weekdays 07:00 | `0 7 * * 1-5` |
| Mon + Thu 07:00 | `0 7 * * 1,4` |
| Weekly, Monday 07:00 | `0 7 * * 1` |

## Option 1: Cloud routine (recommended when the workspace is a GitHub repo)

Runs in Anthropic's cloud on a schedule, so the computer can be off. Uses the `schedule` skill (`/schedule`) to create a routine.

Requirements:
- The workspace is a git repo pushed to GitHub, **private**: the profile and tracker are personal. The generated skills in `.claude/skills/` and the data folder must be committed.
- A Google Sheet tracker needs the Google Sheets connector attached to the routine. A markdown tracker needs nothing.
- The email check needs the Gmail (or Outlook) connector attached to the routine. Without it, the run skips that step and says so.

Routine prompt:

```
Run the {{WATCH}} skill. This is an unattended run: for the email check, apply only the
clear-cut status changes the skill allows, and never send, reply to, draft or label email.
Then commit the changes to .claude/skills/{{WATCH}}/state.json, .claude/skills/{{WATCH}}/applied.json
and {{DATA}}/Job-Watch.md (and {{DATA}}/Applications.md if the email check changed it) with the
message "{{WATCH}}: scheduled run <YYYY-MM-DD>" and push to the default branch.
In the commit message body, list new roles one per line, then each tracker change from email
(company, role, old -> new status, evidence) so there's a record to revert from.
```

The user sees results after `git pull`, or in Obsidian with the Git plugin's auto-pull. Make sure local edits are committed regularly so the routine's pushes don't conflict.

## Option 2: Local scheduled job

Runs Claude Code headless on this computer. The computer must be on (macOS `launchd` runs a missed job when the Mac wakes; `cron` skips it).

1. Allow the tools the run needs, in `<workspace>/.claude/settings.json` under `permissions.allow` (use the `update-config` skill if available, and show the user the change):
   ```json
   "Bash(python3 .claude/skills/{{WATCH}}/scripts/job_watch.py:*)",
   "WebSearch", "WebFetch",
   "Edit({{DATA}}/**)", "Write({{DATA}}/**)"
   ```
   plus the Google Sheets `get_values` and `update_values` tool names if the tracker is a sheet, and the email connector's search and read tools (Gmail `search_threads` and `get_thread`) if the email check is on. Never allow send, draft or label tools.
2. Find the full path of the `claude` binary (`command -v claude`).
3. macOS: write `~/Library/LaunchAgents/com.<user>.job-watch.plist`:
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0"><dict>
     <key>Label</key><string>com.<user>.job-watch</string>
     <key>WorkingDirectory</key><string><absolute workspace path></string>
     <key>ProgramArguments</key><array>
       <string><path to claude></string><string>-p</string><string>Run the {{WATCH}} skill</string>
     </array>
     <key>StartCalendarInterval</key><array>
       <!-- one dict per run; Weekday 1 = Monday -->
       <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>7</integer><key>Minute</key><integer>0</integer></dict>
     </array>
     <key>StandardOutPath</key><string><absolute workspace path>/.claude/skills/{{WATCH}}/last-run.log</string>
     <key>StandardErrorPath</key><string><absolute workspace path>/.claude/skills/{{WATCH}}/last-run.log</string>
   </dict></plist>
   ```
   Load it with `launchctl load ~/Library/LaunchAgents/com.<user>.job-watch.plist`. For daily, drop the `Weekday` key.
   Linux: a crontab line, `0 7 * * 1-5 cd "<workspace>" && <path to claude> -p "Run the {{WATCH}} skill" >> .claude/skills/{{WATCH}}/last-run.log 2>&1`.
4. Do one manual run of the exact command and check the log before relying on it.

To stop: `launchctl unload <plist>` and delete it, or remove the crontab line.

## Option 3: Script-only job (no AI, no cost)

Runs just `job_watch.py fetch` on a schedule. Covers every company with a job board API, skips the `web` ones, and can't sync a Google Sheet tracker (a markdown tracker still works). New roles appear in `Job-Watch.md`; the next manual `/{{WATCH}}` run covers the web companies.

Same `launchd` / `cron` setup as Option 2, with `/usr/bin/python3 .claude/skills/{{WATCH}}/scripts/job_watch.py fetch` as the program. No permissions needed.

## Option 4: Manual

No schedule. The user runs `/{{WATCH}}` when they want. Suggest a weekly calendar reminder.

## Not suitable

`/loop` only runs while a Claude Code session is open, so it can't serve as a schedule.
