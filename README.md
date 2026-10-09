# Job Search Setup

A [Claude Code](https://claude.com/claude-code) skill that sets up a personal job-search toolkit. It interviews you about your background and what you're looking for, then generates four skills tailored to you:

| Skill | You say | It does |
|---|---|---|
| **company-fit** | "Should I apply to Acme?" | Researches what the company does, how it's doing and where it's heading, what it hires for, and scores it against *your* ranked priorities. Ends with Apply / Wait / Skip. |
| **job-watch** | "Any new roles?" (or runs on a schedule) | Checks the careers pages of your target companies (30–150, researched with you during setup) for roles matching your titles and locations, and lists what's new. With email connected, each run also checks for replies and moves a tracker status when it's unambiguous (rejection, interview invite, offer), flagging everything else for you. |
| **job-tracker** | "I applied for this: <link>" · "Had a recruiter call with Acme" · "Any replies?" · "Where am I?" | Keeps your application tracker (Google Sheet or markdown file) current, scans your email for replies if connected, and gives you a pipeline view and a follow-up list. |
| **interview-prep** | "Prep me for my interview with Acme" | Builds a prep pack from the job description, the company's culture and values pages and your own stories, then runs a mock interview one question at a time with scored feedback. Debriefs the real interview afterwards. |

Nothing is ever sent or submitted on your behalf. The skills research, track and draft; you apply and reply.

## Install

Clone into the skills folder of the workspace where your job-search notes will live (an Obsidian vault works well):

```bash
git clone https://github.com/albey/job-search-setup.git <workspace>/.claude/skills/job-search-setup
```

or into `~/.claude/skills/job-search-setup` to make it available everywhere.

## Use

Claude Code only picks up new skills when a session starts. If it was already running when you cloned, restart it, or `/job-search-setup` won't be found.

Start Claude Code in your workspace and run:

```
/job-search-setup
```

Setup takes 30–60 minutes, mostly spent building your company list. Claude will:

1. Read your CV or LinkedIn profile and draft your profile: experience, strengths, honest gaps.
2. Ask what you want: roles and their synonyms, seniority, industries, company stage, location and work mode, pay, ranked priorities, where you want to be in 3–5 years, deal-breakers.
3. Research target companies with you, then find each one's job board.
4. Turn your criteria into matching rules and test them against real postings until the results look right.
5. Set up your tracker (Google Sheet or markdown), importing past applications if you have them.
6. Ask how you like to practise interviews.
7. Generate the four skills, schedule job-watch if you want it, and do a first run.

## What you get

```
Job-Search/
  README.md         how it fits together, your criteria, target company table
  Profile.md        your background and what you want: the yardstick for every judgement
  Stories.md        your interview stories (STAR), built up over time
  Job-Watch.md      latest matching roles, refreshed on every run
  Applications.md   your tracker, if you chose markdown
  Companies/        saved company briefs
  Interviews/       prep packs, mock scorecards, real interview debriefs

.claude/skills/
  company-fit/  job-watch/  job-tracker/  interview-prep/
```

Change anything by editing these files or asking Claude ("add Acme to my watch list", "I'd now accept hybrid 2 days", "stop the schedule").

## Requirements

- Claude Code with web search and web fetch.
- Python 3 (job-watch's fetcher uses the standard library only).
- Optional connectors: **Google Sheets** for a sheet tracker; **Gmail** or **Outlook** for reply scanning; **Google Calendar** to pick up interview details.
- For scheduled runs: a private GitHub repo for cloud routines, or a computer that's on for local ones. A no-AI script-only option is also available.

## How job-watch finds roles

Most companies post jobs through an applicant tracking system with a public feed: Greenhouse, Lever, Ashby, SmartRecruiters, Workable, Teamtailor, Pinpoint, Comeet, Workday. job-watch reads those directly, which is fast, complete, and costs nothing. Companies on other systems get a web search on each run. Roles you've already applied for are matched against your tracker and never reported as new.

## Files

| Path | Purpose |
|---|---|
| `SKILL.md` | The setup flow Claude follows |
| `scripts/job_watch.py` | Job board fetcher, matcher and note renderer, copied into the generated job-watch skill |
| `references/job-watch-config.md` | Matching rules (titles, locations) explained |
| `references/ats.md` | Finding a company's job board |
| `references/tracker.md` | Google Sheet vs markdown tracker, email blocks |
| `references/scheduling.md` | Cloud routine, local launchd/cron, script-only, manual |
| `templates/` | Data files and the four skill templates |

## Privacy

Your profile, pay expectations and application history are personal. They stay in your workspace. If it syncs to git, keep the repo private.
