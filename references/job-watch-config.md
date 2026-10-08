# job-watch config.json

`job_watch.py` reads `config.json` from its skill folder. Every regex is a Python regex fragment, matched case-insensitively against the job title or location. Fragments in a list are OR'd. In JSON, a backslash is written `\\` (`"\\bvp\\b"`).

```json
{
  "data_dir": "Job-Search",
  "titles": [
    "product design(er)?",
    "ux[\\s/-]+(designer|lead)",
    "design (lead|manager)",
    "head of design"
  ],
  "exclude_titles": ["intern", "graduate", "graphic", "industrial"],
  "senior_titles": [
    "\\b(head|director|vp|vice president|chief|lead|principal|staff)\\b",
    "^(senior |sr\\.? )?manager\\b"
  ],
  "workday_queries": ["product designer", "ux designer", "design lead"],
  "locations": {
    "anywhere": false,
    "places": ["berlin", "germany", "deutschland"],
    "remote": true,
    "home_countries": ["germany"],
    "remote_regions": ["emea", "europe", "\\beu\\b", "global", "worldwide", "anywhere", "international"]
  },
  "tracker": {"type": "markdown", "file": "Applications.md"}
}
```

| Key | Meaning |
|---|---|
| `data_dir` | The data folder, relative to the workspace root, or absolute. `Job-Watch.md` is written there. |
| `titles` | A posting is a candidate when its title matches any of these. Include every synonym the user gave, and allow for hyphens and plurals (`pre[\\s-]?sales`, `engineer(ing)?`). |
| `exclude_titles` | Dropped even when `titles` matches. Use for wrong-level titles (intern, junior) and look-alikes (e.g. "graphic designer" when the target is "product designer"). |
| `senior_titles` | Optional. Matching roles are split into "Senior / leadership" and "Other" in the note. Omit to use the default (head, director, VP, chief, lead, principal, manager at the start). |
| `workday_queries` | Plain search phrases for Workday boards, which are searched by keyword instead of listed in full. 3–8 phrases covering the titles. |
| `locations.anywhere` | `true` accepts any location. Use only for a fully location-independent search. |
| `locations.places` | Regexes for on-site and hybrid locations the user accepts: cities, regions, countries, local spellings. A posting that mentions any of these matches, whether or not it's remote. Short codes need word boundaries (`\\buk\\b`, `\\bnyc\\b`). |
| `locations.remote` | `true` accepts remote roles that are open to the user (next two keys). `false` means on-site/hybrid in `places` only. |
| `locations.home_countries` | Countries the user can work from, lowercase. A remote role naming one of them matches. Remote roles naming any *other* country ("Remote - Spain") are skipped, even when also tagged Europe, because they usually require residence there. |
| `locations.remote_regions` | Regions that count as open to the user when a remote posting names no country ("Remote - EMEA"). Pick ones that include the user's country. A US user would use `["north america", "\\bus\\b", "americas", "global", "worldwide", "anywhere"]`. |
| `tracker.type` | `markdown` or `gsheet`. A markdown tracker (`tracker.file`, relative to `data_dir`) is re-read automatically on every `fetch`. A Google Sheet is synced by the skill (Step 0) through `applied --json`. |

Check rules with:

```bash
python3 .claude/skills/job-watch/scripts/job_watch.py test "Senior Product Designer" --location "Berlin, Germany"
python3 .claude/skills/job-watch/scripts/job_watch.py test "Lead UX Designer" --location "Remote - Spain" --remote
```

Then `fetch --dry-run` against the real boards. `title_match_wrong_location` shows what the location rules are dropping. Look there first when the user says a role was missed.
