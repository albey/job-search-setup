# Finding a company's job board

Most companies post jobs through an applicant tracking system (ATS) with a public JSON feed. job-watch reads those feeds directly: fast, free, and complete. Companies without one get a web search each run instead.

## companies.json

```json
{"companies": [
  {"name": "Acme Robotics", "segment": "Robotics", "ats": "greenhouse", "slug": "acmerobotics", "careers": "https://acmerobotics.com/careers"},
  {"name": "Big Corp", "segment": "Enterprise", "ats": "workday", "slug": "bigcorp.wd5/bigcorp/External", "careers": "https://bigcorp.com/careers"},
  {"name": "Small Co", "segment": "Startups", "ats": "web", "careers": "https://smallco.io/jobs"}
]}
```

`name` is shown in the note and matched against the tracker's Company column, so use the name the user would write. `segment` groups the README table. `careers` is always worth filling: it's the fallback when the API fails.

## Probing

1. For each company, guess 1–3 slugs: the name lowercased without spaces (`acmerobotics`), with hyphens (`acme-robotics`), the domain without TLD, and common suffixes (`acmeinc`, `<name>hq`, `<name>careers`).
2. Run them in batches of 20–40 slugs:
   ```bash
   python3 .claude/skills/<watch>/scripts/job_watch.py probe acmerobotics acme-robotics acmeinc ...
   ```
   Output maps each slug to the boards that answered, with the job count and three sample titles. Empty means nothing answered.
3. **Check the sample titles** belong to the company you meant. A short slug like `bolt` can belong to a different company on each ATS. Some ATSs also serve demo boards with placeholder jobs for unclaimed slugs.
4. For companies with no hit, open their careers page (WebFetch, or WebSearch `"<company>" careers greenhouse OR lever OR ashby OR workday`) and look at where the "Apply" links go:

| Link looks like | ats | slug |
|---|---|---|
| `boards.greenhouse.io/<slug>`, `job-boards.greenhouse.io/<slug>`, `?gh_jid=` on their own site | `greenhouse` | `<slug>` (if only `gh_jid` shows, search the page source for `boards-api.greenhouse.io/v1/boards/<slug>`) |
| `jobs.lever.co/<slug>` | `lever` | `<slug>` |
| `jobs.eu.lever.co/<slug>` | `lever-eu` | `<slug>` |
| `jobs.ashbyhq.com/<slug>` | `ashby` | `<slug>` |
| `jobs.smartrecruiters.com/<slug>` | `smartrecruiters` | `<slug>` |
| `apply.workable.com/<slug>` | `workable` | `<slug>` |
| `<slug>.teamtailor.com` | `teamtailor` | `<slug>` |
| `<slug>.pinpointhq.com` | `pinpoint` | `<slug>` |
| `comeet.com/jobs/<company>/<uid>` | `comeet` | `<company>/<uid>` |
| `<tenant>.wd<N>.myworkdayjobs.com/<site>` (sometimes with a locale like `/en-US/` before `<site>`) | `workday` | `<tenant>.wd<N>/<tenant>/<site>` |
| Anything else (custom site, iCIMS, Taleo, SuccessFactors, Personio, Recruitee, BambooHR) | `web` | none, set `careers` |

Workday: test with `curl -s -X POST -H 'Content-Type: application/json' -d '{"limit":1,"offset":0,"searchText":"","appliedFacets":{}}' https://<tenant>.wd<N>.myworkdayjobs.com/wday/cxs/<tenant>/<site>/jobs`. A JSON reply with `total` means the slug is right.

A company with zero open jobs looks the same as a wrong slug in `probe`. If the careers page clearly links to an ATS but nothing is open right now, use that ATS anyway.

## Keeping it working

ATS migrations are common. When `fetch` reports the same company failing two runs in a row, re-probe it and update `companies.json`.
