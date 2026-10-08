# Job Search

{{USER}}'s job search: {{SEARCH_SUMMARY}}. Set up on {{DATE}} with `job-search-setup`.

## How it works

| Ask Claude | Skill | Writes to |
|---|---|---|
| "Should I apply to Acme?" · `/{{FIT}} Acme` | `{{FIT}}` | Chat; `Companies/<Company>.md` if you ask to save it |
| "Any new roles?" · `/{{WATCH}}` (also runs {{SCHEDULE}}) | `{{WATCH}}` | [Job-Watch](Job-Watch.md) |
| "I applied for this: <link>" · "Had a call with Acme's recruiter" · "Where am I with my applications?" · `/{{TRACKER}}` | `{{TRACKER}}` | {{TRACKER_LINK}} |
| "Prep me for my interview with Acme" · `/{{PREP}}` | `{{PREP}}` | `Interviews/<Company>/` and [Stories](Stories.md) |

- [Profile](Profile.md): background, what I want, priorities. The yardstick for every fit check and interview prep.
- [Stories](Stories.md): STAR stories for interviews.

## Search criteria

Used by `{{WATCH}}` (rules in `.claude/skills/{{WATCH}}/config.json`):

- **Titles:** {{TITLE_CRITERIA}}
- **Location:** {{LOCATION_CRITERIA}}

## Target companies

{{COMPANY_COUNT}} companies. **Board** is the job board `{{WATCH}}` reads; `web` means it's checked by web search each run. To add or remove one, ask Claude, or edit `.claude/skills/{{WATCH}}/companies.json` and this table.

{{COMPANY_TABLES}}
