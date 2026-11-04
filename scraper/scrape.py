#!/usr/bin/env python3
"""Job Radar scraper. Standard library only.

Pulls remote jobs from free public job APIs and employer ATS boards, filters them
to the roles in config.json, scores them, and writes docs/jobs.json.
A source that fails is skipped and its previous jobs are kept, so one outage
never empties the list.
"""
import hashlib
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CFG_PATH = ROOT / "config.json"
OUT_PATH = ROOT / "docs" / "jobs.json"
UA = "job-radar/1.0 (personal job search tool, runs a few times a day)"
NOW = datetime.now(timezone.utc)


def get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json, application/rss+xml, */*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def strip_html(s):
    s = html.unescape(s or "")
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def to_iso(value):
    """Best effort conversion to an ISO date string, or None."""
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)):
            seconds = value / 1000 if value > 1e11 else value
            return datetime.fromtimestamp(seconds, timezone.utc).isoformat()
        text = str(value).strip()
        try:
            return parsedate_to_datetime(text).astimezone(timezone.utc).isoformat()
        except (TypeError, ValueError):
            pass
        text = text.replace("Z", "+00:00")
        d = datetime.fromisoformat(text)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc).isoformat()
    except Exception:
        return None


def make_job(source, title, company, url, location, posted, pay, desc, remote_hint=False):
    return {
        "title": strip_html(title),
        "company": strip_html(company),
        "url": url,
        "source": source,
        "location": strip_html(location) or "Remote",
        "posted": to_iso(posted),
        "pay": strip_html(pay),
        "desc": strip_html(desc),
        "remote_hint": remote_hint,
    }


# ---------- sources ----------
def fetch_remotive(cfg):
    jobs = []
    for cat in cfg.get("remotive_categories", []):
        data = json.loads(get("https://remotive.com/api/remote-jobs?category=" + cat))
        for j in data.get("jobs", []):
            jobs.append(make_job("remotive", j.get("title"), j.get("company_name"), j.get("url"),
                                 j.get("candidate_required_location"), j.get("publication_date"),
                                 j.get("salary"), j.get("description"), True))
    return jobs


def fetch_jobicy(cfg):
    c = cfg.get("jobicy")
    if not c:
        return []
    url = "https://jobicy.com/api/v2/remote-jobs?count=%s&geo=%s&industry=%s" % (c.get("count", 50), c.get("geo", "usa"), c.get("industry", "hr"))
    data = json.loads(get(url))
    jobs = []
    for j in data.get("jobs", []):
        pay = ""
        if j.get("annualSalaryMin"):
            pay = "%s to %s %s" % (j.get("annualSalaryMin"), j.get("annualSalaryMax", ""), j.get("salaryCurrency", ""))
        jobs.append(make_job("jobicy", j.get("jobTitle"), j.get("companyName"), j.get("url"),
                             j.get("jobGeo"), j.get("pubDate"), pay,
                             j.get("jobDescription") or j.get("jobExcerpt"), True))
    return jobs


def fetch_wwr(cfg, feed):
    root = ET.fromstring(get(feed))
    jobs = []
    for item in root.iter("item"):
        raw = item.findtext("title") or ""
        company, _, title = raw.partition(":")
        if not title:
            company, title = "", raw
        region = item.findtext("region") or ""
        jobs.append(make_job("wwr", title, company, item.findtext("link"), region,
                             item.findtext("pubDate"), "", item.findtext("description"), True))
    return jobs


def fetch_greenhouse(token):
    data = json.loads(get("https://boards-api.greenhouse.io/v1/boards/%s/jobs?content=true" % token))
    jobs = []
    for j in data.get("jobs", []):
        loc = (j.get("location") or {}).get("name", "")
        jobs.append(make_job("greenhouse:" + token, j.get("title"), token, j.get("absolute_url"), loc,
                             j.get("updated_at") or j.get("first_published"), "", j.get("content")))
    return jobs


def fetch_lever(slug):
    data = json.loads(get("https://api.lever.co/v0/postings/%s?mode=json" % slug))
    jobs = []
    for j in data:
        cats = j.get("categories") or {}
        loc = cats.get("location", "")
        hint = (j.get("workplaceType") or "").lower() == "remote"
        jobs.append(make_job("lever:" + slug, j.get("text"), slug, j.get("hostedUrl"), loc,
                             j.get("createdAt"), "", j.get("descriptionPlain") or j.get("description"), hint))
    return jobs


def fetch_ashby(name):
    data = json.loads(get("https://api.ashbyhq.com/posting-api/job-board/%s?includeCompensation=true" % name))
    jobs = []
    for j in data.get("jobs", []):
        comp = (j.get("compensation") or {}).get("compensationTierSummary", "")
        jobs.append(make_job("ashby:" + name, j.get("title"), name, j.get("jobUrl"), j.get("location"),
                             j.get("publishedAt"), comp, j.get("descriptionPlain") or j.get("descriptionHtml"),
                             bool(j.get("isRemote"))))
    return jobs


def all_sources(cfg):
    """Yield (source_name, fetch_callable)."""
    yield "remotive", lambda: fetch_remotive(cfg)
    yield "jobicy", lambda: fetch_jobicy(cfg)
    for feed in cfg.get("wwr_feeds", []):
        yield "wwr", (lambda f=feed: fetch_wwr(cfg, f))
    boards = cfg.get("boards", {})
    for t in boards.get("greenhouse", []):
        yield "greenhouse:" + t, (lambda t=t: fetch_greenhouse(t))
    for t in boards.get("lever", []):
        yield "lever:" + t, (lambda t=t: fetch_lever(t))
    for t in boards.get("ashby", []):
        yield "ashby:" + t, (lambda t=t: fetch_ashby(t))


# ---------- filtering and scoring ----------
def match_role(title, cfg):
    t = title.lower()
    for pat in cfg["exclude_titles"]:
        if re.search(pat, t):
            return None
    for role, pats in cfg["roles"].items():
        if any(re.search(p, t) for p in pats):
            return role
    return None


def eligibility(job, cfg):
    """Return (ok, restricted). Rejects non-US only postings."""
    loc = job["location"].lower()
    has_us = any(t in loc for t in cfg["us_terms"]) or re.search(r"\bus\b", loc) is not None
    if not job["remote_hint"] and "remote" not in loc and "remote" not in job["title"].lower():
        return False, False
    if any(t in loc for t in cfg["non_us_terms"]) and not has_us:
        return False, False
    states = [s for s in cfg["state_names"] if re.search(r"\b" + s + r"\b", loc)]
    restricted = bool(states) and not has_us and cfg["home_state"].lower() not in states
    return True, restricted


def score_job(job, cfg):
    text = (job["title"] + " " + job["desc"]).lower()
    score, why, flags = 50, [], []
    for term, w in cfg["positive_terms"].items():
        if term in text:
            score += w
            why.append(term)
    for term, w in cfg["negative_terms"].items():
        if term in text:
            score += w
            flags.append(term)
    return max(0, min(100, score)), why[:6], flags[:5]


def job_id(url, title, company):
    return hashlib.sha1((url or (title + company)).encode()).hexdigest()[:12]


def build(cfg, previous, fetchers=None):
    prev_by_id = {j["id"]: j for j in previous.get("jobs", [])}
    ok_sources, failed, collected = set(), [], []
    for name, fn in (fetchers if fetchers is not None else all_sources(cfg)):
        try:
            collected.extend(fn())
            ok_sources.add(name)
        except Exception as e:  # keep going, keep old data for this source
            failed.append("%s: %s" % (name, str(e)[:120]))

    cutoff = NOW - timedelta(days=cfg["max_age_days"])
    seen, out = set(), []
    for j in collected:
        if not j["url"] or not j["title"]:
            continue
        role = match_role(j["title"], cfg)
        if not role:
            continue
        ok, restricted = eligibility(j, cfg)
        if not ok:
            continue
        jid = job_id(j["url"], j["title"], j["company"])
        key = (j["title"].lower(), j["company"].lower())
        if jid in seen or key in seen:
            continue
        seen.update([jid, key])
        first_seen = prev_by_id.get(jid, {}).get("first_seen") or NOW.date().isoformat()
        posted = j["posted"]
        if posted and datetime.fromisoformat(posted) < cutoff:
            continue
        score, why, flags = score_job(j, cfg)
        out.append({
            "id": jid, "title": j["title"], "company": j["company"], "url": j["url"], "source": j["source"],
            "role": role, "location": j["location"], "restricted": restricted, "pay": j["pay"],
            "posted": (posted or "")[:10], "first_seen": first_seen, "score": score, "why": why,
            "flags": flags, "snippet": j["desc"][:280],
        })

    # carry over jobs from sources that failed this run
    for old in previous.get("jobs", []):
        if old["id"] in seen:
            continue
        src_ok = old["source"] in ok_sources or (old["source"] == "wwr" and "wwr" in ok_sources)
        if not src_ok:
            age_ok = (not old.get("posted")) or datetime.fromisoformat(old["posted"] + "T00:00:00+00:00") >= cutoff
            if age_ok:
                out.append(old)
                seen.add(old["id"])

    out.sort(key=lambda j: (j["score"], j["posted"] or j["first_seen"]), reverse=True)
    new_ids = [j["id"] for j in out if j["id"] not in prev_by_id]
    return {
        "updated": NOW.isoformat(timespec="minutes"),
        "failed_sources": failed,
        "scoring": {"positive": cfg["positive_terms"], "negative": cfg["negative_terms"]},
        "jobs": out,
    }, new_ids


def notify(new_jobs, cfg):
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    strong = [j for j in new_jobs if j["score"] >= cfg["notify_min_score"]]
    if not topic or not strong:
        return
    lines = ["%s at %s (%d)" % (j["title"], j["company"], j["score"]) for j in strong[:8]]
    req = urllib.request.Request("https://ntfy.sh/" + topic, data="\n".join(lines).encode(),
                                 headers={"Title": "%d new strong job matches" % len(strong)}, method="POST")
    try:
        urllib.request.urlopen(req, timeout=20).read()
    except Exception as e:
        print("notify failed:", e, file=sys.stderr)


def main():
    cfg = json.loads(CFG_PATH.read_text())
    previous = json.loads(OUT_PATH.read_text()) if OUT_PATH.exists() else {"jobs": []}
    result, new_ids = build(cfg, previous)
    OUT_PATH.parent.mkdir(exist_ok=True)
    unchanged = previous.get("jobs") == result["jobs"] and previous.get("failed_sources") == result["failed_sources"]
    if not unchanged:  # avoids an empty commit every run
        OUT_PATH.write_text(json.dumps(result, indent=1) + "\n")
    new_jobs = [j for j in result["jobs"] if j["id"] in set(new_ids)]
    notify(new_jobs, cfg)
    print("%d jobs, %d new, failed sources: %s" % (len(result["jobs"]), len(new_ids), result["failed_sources"] or "none"))


if __name__ == "__main__":
    main()
