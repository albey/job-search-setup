#!/usr/bin/env python3
"""Job watch: pull open roles from company job boards, keep the ones matching the title and
location rules in config.json, track what's new, and render a markdown note.

Usage:
  job_watch.py fetch [--dry-run]          # query all API-backed boards, update state, render note
  job_watch.py add --company C --title T --location L --url U   # record a role found by web search
  job_watch.py webdone --count N          # record how many web-only companies were checked this run
  job_watch.py render                     # re-render the note from state
  job_watch.py applied --json FILE        # snapshot a Google Sheets get_values response into applied.json
  job_watch.py applied --csv FILE         # same, from a CSV export
  job_watch.py applied --md FILE          # same, from a markdown table (automatic on fetch for markdown trackers)
  job_watch.py probe SLUG [SLUG ...]      # find which public job board API answers for each slug
  job_watch.py test TITLE [--location L] [--remote]   # check one title/location against the rules

Files next to this script's skill folder: config.json (rules + paths), companies.json (boards),
state.json (every match ever seen) and applied.json (tracker snapshot).

Standard library only (runs on macOS system python3).
"""
import argparse, csv, datetime, json, re, sys, time, urllib.error, urllib.request, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit

SKILL = Path(__file__).resolve().parent.parent
WORKSPACE = SKILL.parent.parent.parent  # <workspace>/.claude/skills/<skill>
CFG = json.loads((SKILL / "config.json").read_text())
COMPANIES = SKILL / "companies.json"
STATE = SKILL / "state.json"
APPLIED = SKILL / "applied.json"
TODAY = datetime.date.today().isoformat()


def ws_path(p):
    p = Path(p).expanduser()
    return p if p.is_absolute() else WORKSPACE / p


DATA = ws_path(CFG["data_dir"])
NOTE = DATA / "Job-Watch.md"
TRACKER = CFG.get("tracker", {})


def rx(parts):
    return re.compile("|".join(f"(?:{p})" for p in parts), re.I) if parts else None


DEFAULT_SENIOR = [r"\b(head|director|[rsa]?vp|vice president|chief|lead|principal)\b", r"^(senior |sr\.? )?manager\b"]
DEFAULT_REMOTE_REGIONS = ["global", "worldwide", "anywhere", "international"]
# A remote role tied to one country ("Remote - Greece") isn't open to someone elsewhere, even when it's also tagged
# Europe. The user's home_countries are removed from this list.
COUNTRIES = [
    "albania", "austria", "belgium", "bulgaria", "croatia", "cyprus", "czech", "czechia", "denmark", "estonia", "finland",
    "france", "germany", "greece", "hungary", "iceland", "ireland", "italy", "latvia", "lithuania", "luxembourg", "malta",
    "netherlands", "norway", "poland", "portugal", "romania", "serbia", "slovakia", "slovenia", "spain", "sweden",
    "switzerland", "turkey", "ukraine", "united kingdom", "uk", "england", "scotland", "israel", "uae",
    "united arab emirates", "saudi", "egypt", "south africa", "nigeria", "kenya", "india", "pakistan", "singapore",
    "japan", "korea", "china", "hong kong", "taiwan", "philippines", "vietnam", "indonesia", "malaysia", "thailand",
    "australia", "new zealand", "brazil", "mexico", "argentina", "chile", "colombia", "peru", "canada",
    "united states", "usa", "us only"]

TITLE_RE = rx(CFG["titles"])
EXCLUDE_RE = rx(CFG.get("exclude_titles", []))
SENIOR_RE = rx(CFG.get("senior_titles") or DEFAULT_SENIOR)
LOC = CFG.get("locations", {})
HOME = [c.lower() for c in LOC.get("home_countries", [])]
PLACE_RE = rx(LOC.get("places", []))
HOME_RE = rx([rf"\b{re.escape(c)}\b" for c in HOME])
REMOTE_OK_RE = rx(LOC.get("remote_regions", DEFAULT_REMOTE_REGIONS))
COUNTRY_RE = rx([rf"\b{re.escape(c)}\b" for c in COUNTRIES if c not in HOME])
WORKDAY_QUERIES = CFG.get("workday_queries", [])


def http(url, data=None, timeout=30, retries=3):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36",
        "Accept": "application/json, text/html, */*", "Content-Type": "application/json"},
        data=json.dumps(data).encode() if data is not None else None)
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            # boards rate-limit the parallel fetch; back off (honouring Retry-After) and try again
            if e.code not in (429, 503) or attempt == retries:
                raise
            after = e.headers.get("Retry-After", "")
            time.sleep(min(int(after), 30) if after.isdigit() else 2 * 2 ** attempt)


def J(url, data=None):
    return json.loads(http(url, data))


def job(jid, title, location, url, remote=False):
    return {"id": str(jid), "title": " ".join((title or "").split()), "location": location or "", "url": url, "remote": bool(remote)}


# ---- ATS adapters: each returns a list of job dicts ----

def greenhouse(slug):
    return [job(j["id"], j["title"], (j.get("location") or {}).get("name"), j["absolute_url"])
            for j in J(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs")["jobs"]]


def lever(slug, host="api.lever.co"):
    out = []
    for j in J(f"https://{host}/v0/postings/{slug}?mode=json"):
        c = j.get("categories") or {}
        locs = "; ".join(dict.fromkeys([c.get("location") or ""] + (c.get("allLocations") or [])))
        out.append(job(j["id"], j["text"], locs.strip("; "), j["hostedUrl"], j.get("workplaceType") == "remote"))
    return out


def ashby(slug):
    out = []
    for j in J(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")["jobs"]:
        locs = [j.get("location") or ""] + [s.get("location", "") for s in j.get("secondaryLocations") or []]
        country = (((j.get("address") or {}).get("postalAddress") or {}).get("addressCountry")) or ""
        loc = "; ".join(dict.fromkeys(l for l in locs + [country] if l))
        out.append(job(j["id"], j["title"], loc, j["jobUrl"], j.get("isRemote") or j.get("workplaceType") == "Remote"))
    return out


def smartrecruiters(slug):
    out, offset = [], 0
    while True:
        d = J(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100&offset={offset}")
        for j in d["content"]:
            l = j.get("location") or {}
            out.append(job(j["id"], j["name"], l.get("fullLocation") or l.get("city"),
                           f"https://jobs.smartrecruiters.com/{slug}/{j['id']}", l.get("remote")))
        offset += 100
        if offset >= d["totalFound"]:
            return out


def workable(slug):
    out = []
    for j in J(f"https://apply.workable.com/api/v1/widget/accounts/{slug}")["jobs"]:
        locs = [", ".join(x for x in (l.get("city"), l.get("country")) if x) for l in j.get("locations") or []]
        loc = "; ".join(locs) or ", ".join(x for x in (j.get("city"), j.get("country")) if x)
        out.append(job(j["shortcode"], j["title"], loc, j["url"], j.get("telecommuting")))
    return out


def teamtailor(slug):
    root = ET.fromstring(http(f"https://{slug}.teamtailor.com/jobs.rss"))
    out = []
    for it in root.iter("item"):
        locs = [e.text for e in it.iter() if e.tag.endswith("}name") or e.tag.endswith("}city") or e.tag.endswith("}country")]
        remote = (it.findtext("remoteStatus") or "").lower() in ("fully", "remote")
        out.append(job(it.findtext("guid") or it.findtext("link"), it.findtext("title"),
                       "; ".join(dict.fromkeys(l for l in locs if l)), it.findtext("link"), remote))
    return out


def pinpoint(slug):
    out = []
    for j in J(f"https://{slug}.pinpointhq.com/postings.json")["data"]:
        l = j.get("location") or {}
        loc = ", ".join(dict.fromkeys(x for x in (l.get("name"), l.get("city")) if x))
        out.append(job(j["id"], j["title"], loc, j["url"], j.get("workplace_type") == "remote"))
    return out


def comeet(slug):
    # slug: "<company>/<uid>" as in https://www.comeet.com/jobs/<company>/<uid>
    html = http(f"https://www.comeet.com/jobs/{slug}").decode("utf8", "ignore")
    m = re.search(r"COMPANY_POSITIONS_DATA = (\[.*?\]);\s*\n", html, re.S)
    out = []
    for j in json.loads(m.group(1)) if m else []:
        l = j.get("location") or {}
        out.append(job(j["uid"], j["name"], l.get("name"), j.get("url_active_page") or j.get("url_comeet_hosted_page"), l.get("is_remote")))
    return out


def workday(spec):
    # spec: "<tenant>.<wdN>/<tenant>/<site>"; Workday boards are huge, so search by keyword instead of listing all.
    host, tenant, site = spec.split("/")
    base = f"https://{host}.myworkdayjobs.com"
    seen = {}
    for q in WORKDAY_QUERIES:
        for offset in range(0, 100, 20):
            d = J(f"{base}/wday/cxs/{tenant}/{site}/jobs", {"limit": 20, "offset": offset, "searchText": q, "appliedFacets": {}})
            for j in d.get("jobPostings", []):
                seen.setdefault(j["externalPath"], j)
            if offset + 20 >= d.get("total", 0):
                break
    out = []
    for path, j in seen.items():
        loc = j.get("locationsText", "")
        if title_ok(j["title"]) and re.match(r"\d+ Locations", loc):
            try:  # resolve "N Locations" to the real list, only for title matches
                info = J(f"{base}/wday/cxs/{tenant}/{site}{path}")["jobPostingInfo"]
                loc = "; ".join([info.get("location", "")] + info.get("additionalLocations", []))
            except Exception:
                pass
        out.append(job(path, j["title"], loc, f"{base}/{site}{path}", "remote" in j.get("remoteType", "").lower()))
    return out


ADAPTERS = {"greenhouse": greenhouse, "lever": lever, "lever-eu": lambda s: lever(s, "api.eu.lever.co"), "ashby": ashby,
            "smartrecruiters": smartrecruiters, "workable": workable, "teamtailor": teamtailor, "pinpoint": pinpoint,
            "comeet": comeet, "workday": workday}
PROBE_ATS = ["greenhouse", "lever", "lever-eu", "ashby", "smartrecruiters", "workable", "teamtailor", "pinpoint"]


# ---- matching rules ----

def title_ok(t):
    return bool(TITLE_RE.search(t)) and not (EXCLUDE_RE and EXCLUDE_RE.search(t))


def location_ok(j):
    if LOC.get("anywhere"):
        return True
    loc = j["location"]
    if PLACE_RE and PLACE_RE.search(loc):
        return True
    if not LOC.get("remote", True):
        return False
    remote = j["remote"] or re.search(r"remote|anywhere|distributed", loc, re.I)
    if not remote:
        return False
    if HOME_RE and HOME_RE.search(loc):
        return True
    if COUNTRY_RE and COUNTRY_RE.search(loc):
        return False
    rest = re.sub(r"remote|[^a-z]", "", loc.lower())
    return not rest or bool(REMOTE_OK_RE and REMOTE_OK_RE.search(loc))


# ---- application tracker matching ----

TRACKING_PARAMS = re.compile(r"^(utm_.*|src|source|ref|refid|trackingid|gh_src|lever-source.*|lever-origin|currentjobid|eboid|trk.*)$", re.I)


def norm_url(u):
    p = urlsplit((u or "").strip())
    q = urlencode(sorted((k, v) for k, v in parse_qsl(p.query) if not TRACKING_PARAMS.match(k)))
    return (p.netloc.lower().removeprefix("www.") + p.path.rstrip("/").lower() + ("?" + q if q else ""))


def url_ids(u):
    # posting ids (uuids / long numbers / workday R-numbers) survive across URL variants of the same job
    return set(re.findall(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}|\d{6,}|r\d{5,}", (u or "").lower()))


def norm_words(t):
    return re.sub(r"[^a-z0-9 ]", " ", (t or "").lower().replace("&", " and ")).split()


def company_match(tracked, sheet):
    # companies.json names can carry extras: "Acme Group (incl. Widgets Ltd)", "Meta (Facebook / Instagram)"
    a, b = " ".join(norm_words(tracked)), " ".join(norm_words(sheet))
    return bool(b) and (a == b or a.startswith(b) or b.startswith(a) or f" {b} " in f" {a} ")


def title_match(t1, t2):
    w1, w2 = set(norm_words(t1)), set(norm_words(t2))
    return bool(w1 and w2) and len(w1 & w2) / len(w1 | w2) >= 0.75


def load_applied():
    return json.loads(APPLIED.read_text()) if APPLIED.exists() else []


def applied_for(rec, applied):
    ids = url_ids(rec["url"])
    for a in applied:
        if a["link"] and (norm_url(a["link"]) == norm_url(rec["url"]) or (ids & url_ids(a["link"]))):
            return a
        if company_match(rec["company"], a["company"]) and title_match(rec["title"], a["role"]):
            return a
    return None


def md_table(text):
    # the first markdown table whose header has Role and Company columns
    tables, cur = [], []
    for line in text.splitlines() + [""]:
        s = line.strip()
        if s.startswith("|"):
            cells = [c.strip() for c in s.strip("|").split("|")]
            if not all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c):
                cur.append(cells)
        elif cur:
            tables.append(cur)
            cur = []
    for t in tables:
        hdr = [h.lower() for h in t[0]]
        if "company" in hdr and ("role" in hdr or "title" in hdr):
            return t
    return []


def cell_url(v):
    m = re.search(r"\((https?://[^)\s]+)\)|<(https?://[^>\s]+)>|(https?://\S+)", v or "")
    return next(g for g in m.groups() if g) if m else (v or "").strip()


def save_applied(rows):
    hdr = [h.strip().lower() for h in rows[0]] if rows else []
    col = lambda *names: next((hdr.index(n) for n in names if n in hdr), None)
    ci = {"role": col("role", "title", "job title", "position"), "company": col("company"),
          "date": col("date applied", "applied", "date"), "status": col("status"), "link": col("link", "url", "job link", "posting")}
    if ci["role"] is None or ci["company"] is None:
        sys.exit(f"tracker header needs Role and Company columns, got: {rows[0] if rows else 'nothing'}")
    out = []
    for r in rows[1:]:
        get = lambda k: r[ci[k]].strip() if ci[k] is not None and ci[k] < len(r) else ""
        a = {k: get(k) for k in ci}
        a["link"] = cell_url(a["link"])
        if a["role"] or a["link"]:
            out.append(a)
    APPLIED.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return out


def cmd_applied(path, fmt):
    text = open(path, encoding="utf-8-sig").read()
    if fmt == "json":
        # Google Sheets get_values output ({"values": [[...]]}, or wrapped in valueRanges) or a bare list of rows
        d = json.loads(text)
        if isinstance(d, dict):
            d = d.get("values") or ((d.get("valueRanges") or [{}])[0].get("values")) or []
        rows = [[str(c) for c in r] for r in d]
    elif fmt == "md":
        rows = md_table(text)
    else:
        rows = list(csv.reader(text.splitlines()))
    print(f"{len(save_applied(rows))} tracked applications saved to {APPLIED.name}")


def sync_markdown_tracker():
    # markdown trackers live in the workspace, so they're re-read on every fetch with no connector needed
    if TRACKER.get("type") != "markdown":
        return None
    f = DATA / TRACKER.get("file", "Applications.md")
    if not f.exists():
        return f"tracker file {f} not found"
    save_applied(md_table(f.read_text()))
    return None


# ---- state + rendering ----

def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"jobs": {}, "runs": []}


def save_state(st):
    STATE.write_text(json.dumps(st, indent=1, ensure_ascii=False))


def upsert(st, company, j, source):
    key = f"{company}|{j['id']}"
    rec = st["jobs"].get(key)
    if rec is None:
        rec = st["jobs"][key] = {"company": company, "first_seen": TODAY, "source": source}
    rec.update(title=j["title"], location=j["location"], url=j["url"], last_seen=TODAY,
               senior=bool(SENIOR_RE.search(j["title"])))
    return rec["first_seen"] == TODAY


def md_row(r, new):
    loc = (r["location"] or "—").replace("|", "/")
    if len(loc) > 70:
        loc = loc[:67] + "…"
    return f"| {'🆕 ' if new else ''}{r['company']} | [{r['title'].replace('|', '/')}]({r['url']}) | {loc} | {r['first_seen']} |"


def render(st):
    last = st["runs"][-1]["date"] if st["runs"] else TODAY
    open_ = sorted((r for r in st["jobs"].values() if r["last_seen"] == last),
                   key=lambda r: (r["first_seen"] != last, r["company"].lower(), r["title"]))
    closed = sorted((r for r in st["jobs"].values() if r["last_seen"] != last), key=lambda r: r["last_seen"], reverse=True)[:15]
    applied = load_applied()
    done = [(r, a) for r in open_ for a in [applied_for(r, applied)] if a]
    done_keys = {id(r) for r, _ in done}
    open_ = [r for r in open_ if id(r) not in done_keys]
    L = ["# Job Watch", "",
         "Generated by the `job-watch` skill. Criteria and the company list are in [README](README.md). "
         "Edits to this file are overwritten on each run.", "",
         f"**Last run:** {last} · {len(applied)} applications in the tracker", ""]
    if not APPLIED.exists():
        L += ["> TODO: tracker not synced yet, so roles already applied for aren't filtered out.", ""]
    hdr = ["| Company | Role | Location | First seen |", "|---|---|---|---|"]
    for label, rows in (("Senior / leadership roles", [r for r in open_ if r["senior"]]),
                        ("Other matching roles", [r for r in open_ if not r["senior"]])):
        L += [f"## {label} ({len(rows)})", ""]
        L += (hdr + [md_row(r, r["first_seen"] == last) for r in rows]) if rows else ["None open."]
        L.append("")
    if done:
        L += [f"## In your tracker ({len(done)})", "", "Open roles that match a row in the application tracker.", "",
              "| Company | Role | Status | Applied |", "|---|---|---|---|"]
        L += [f"| {r['company']} | [{r['title']}]({r['url']}) | {a['status'] or '—'} | {a['date'] or '—'} |"
              for r, a in sorted(done, key=lambda x: x[0]["company"].lower())] + [""]
    if st["runs"]:
        run = st["runs"][-1]
        if run.get("errors"):
            L += ["## Fetch errors (last run)", "", "> TODO: check these boards. The slug or ATS may have changed.", ""]
            L += [f"- {c}: {e}" for c, e in run["errors"].items()] + [""]
    if closed:
        L += ["## Recently closed / no longer listed", "", "| Company | Role | Last seen |", "|---|---|---|"]
        L += [f"| {r['company']} | [{r['title']}]({r['url']}) | {r['last_seen']} |" for r in closed] + [""]
    L += ["## Run log", "", "| Date | New | Open matches | Boards checked | Web-checked |", "|---|---|---|---|---|"]
    L += [f"| {r['date']} | {r['new']} | {r['open']} | {r['boards']} | {r.get('web', 0)} |" for r in reversed(st["runs"])]
    NOTE.parent.mkdir(parents=True, exist_ok=True)
    NOTE.write_text("\n".join(L) + "\n")


def fetch_all(api):
    def run(c):
        try:
            return c, ADAPTERS[c["ats"]](c["slug"]), None
        except Exception as e:
            return c, [], f"{type(e).__name__}: {e}"[:150]

    # Workable rate-limits bursts from cloud IPs, so its boards go one at a time after the parallel batch
    serial = [c for c in api if c["ats"] == "workable"]
    with ThreadPoolExecutor(16) as ex:
        results = list(ex.map(run, [c for c in api if c not in serial]))
    for c in serial:
        time.sleep(3)
        results.append(run(c))
    return results


def cmd_fetch(st, dry_run=False):
    companies = json.loads(COMPANIES.read_text())["companies"]
    api = [c for c in companies if c["ats"] != "web"]
    results = fetch_all(api)
    if dry_run:
        # for tuning the rules: what would match now, without touching state or the note
        hits = [f"{c['name']} — {j['title']} ({j['location']})" for c, jobs, _ in results for j in jobs
                if title_ok(j["title"]) and location_ok(j)]
        title_only = [f"{c['name']} — {j['title']} ({j['location']})" for c, jobs, _ in results for j in jobs
                      if title_ok(j["title"]) and not location_ok(j)]
        print(json.dumps({"matches": hits, "title_match_wrong_location": title_only[:40],
                          "errors": {c["name"]: e for c, _, e in results if e}}, indent=1, ensure_ascii=False))
        return
    tracker_err = sync_markdown_tracker()
    new, errors, matches, applied = [], {}, 0, load_applied()
    for c, jobs, err in results:
        if err:
            errors[c["name"]] = err
            # keep previously seen roles from a failing board open, so an outage doesn't mark them closed
            for r in st["jobs"].values():
                if r["company"] == c["name"] and st["runs"] and r["last_seen"] == st["runs"][-1]["date"]:
                    r["last_seen"] = TODAY
            continue
        for j in jobs:
            if title_ok(j["title"]) and location_ok(j):
                matches += 1
                if upsert(st, c["name"], j, c["ats"]) and not applied_for(st["jobs"][f"{c['name']}|{j['id']}"], applied):
                    new.append(f"{c['name']} — {j['title']} ({j['location']})")
    # a same-day re-fetch replaces today's run but keeps roles already recorded from web checks
    prev = next((r for r in st["runs"] if r["date"] == TODAY), {})
    web_today = [r for r in st["jobs"].values() if r["source"] == "web" and r["last_seen"] == TODAY]
    web_new = [r for r in web_today if r["first_seen"] == TODAY and not applied_for(r, applied)]
    st["runs"] = [r for r in st["runs"] if r["date"] != TODAY]
    st["runs"].append({"date": TODAY, "new": len(new) + len(web_new), "open": matches + len(web_today),
                       "boards": len(api) - len(errors), "web": prev.get("web", 0), "errors": errors})
    save_state(st)
    render(st)
    # boards that failed get web-checked instead, so their roles aren't missed this run
    web = [{"name": c["name"], "careers": c.get("careers", "")} for c in companies if c["ats"] == "web" or c["name"] in errors]
    print(json.dumps({"new": new, "open_matches": matches, "errors": errors, "web_check": web,
                      "tracker_error": tracker_err, "note": str(NOTE)}, indent=1, ensure_ascii=False))


def cmd_add(st, a):
    j = job(a.url, a.title, a.location, a.url)
    is_new = upsert(st, a.company, j, "web")
    tracked = applied_for(st["jobs"][f"{a.company}|{j['id']}"], load_applied())
    is_new = is_new and not tracked
    run = next((r for r in st["runs"] if r["date"] == TODAY), None)
    if run:
        run["open"] += 1
        run["new"] += int(is_new)
    save_state(st)
    render(st)
    label = f"already applied ({tracked['status'] or 'no status'}): " if tracked else ("NEW: " if is_new else "already seen: ")
    print(label + f"{a.company} — {a.title}")


def cmd_probe(slugs):
    def run(pair):
        ats, slug = pair
        try:
            jobs = ADAPTERS[ats](slug)
            return ats, slug, len(jobs), [j["title"] for j in jobs[:3]]
        except Exception:
            return ats, slug, 0, []

    with ThreadPoolExecutor(16) as ex:
        res = list(ex.map(run, [(a, s) for s in slugs for a in PROBE_ATS]))
    # boards with zero open jobs are dropped: unclaimed slugs on some ATSs answer with an empty list
    out = {s: [{"ats": a, "jobs": n, "sample": t} for a, s2, n, t in res if s2 == s and n] for s in slugs}
    print(json.dumps(out, indent=1, ensure_ascii=False))


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--dry-run", action="store_true")
    sub.add_parser("render")
    w = sub.add_parser("webdone")
    w.add_argument("--count", type=int, required=True)
    ap = sub.add_parser("applied")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--csv")
    src.add_argument("--json")
    src.add_argument("--md")
    a = sub.add_parser("add")
    for k in ("company", "title", "location", "url"):
        a.add_argument(f"--{k}", required=True)
    pr = sub.add_parser("probe")
    pr.add_argument("slugs", nargs="+")
    t = sub.add_parser("test")
    t.add_argument("title")
    t.add_argument("--location", default="")
    t.add_argument("--remote", action="store_true")
    args = p.parse_args()
    if args.cmd == "probe":
        return cmd_probe(args.slugs)
    if args.cmd == "test":
        j = job("x", args.title, args.location, "", args.remote)
        print(json.dumps({"title_ok": title_ok(j["title"]), "senior": bool(SENIOR_RE.search(j["title"])),
                          "location_ok": location_ok(j)}))
        return
    st = load_state()
    if args.cmd == "fetch":
        cmd_fetch(st, args.dry_run)
    elif args.cmd == "applied":
        fmt, path = next((k, v) for k, v in (("json", args.json), ("md", args.md), ("csv", args.csv)) if v)
        cmd_applied(path, fmt)
        render(st)
    elif args.cmd == "add":
        cmd_add(st, args)
    elif args.cmd == "webdone":
        for r in st["runs"]:
            if r["date"] == TODAY:
                r["web"] = args.count
        save_state(st)
        render(st)
    else:
        render(st)


if __name__ == "__main__":
    sys.exit(main())
