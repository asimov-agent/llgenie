#!/usr/bin/env python3
"""Stage 1 — Platsbanken (Arbetsförmedlingen) 24 h scan, matched against Andy's CV keywords.

Fetches every ad published inside the window in Stockholms län from the JobTech Search API,
scores it with andy_keywords.score_text(), and writes two artefacts:

  job-radar/platsbanken_raw.json      every ad in the window (full API payload)
  job-radar/platsbanken_matches.json  CV-matching ads, with full detail for the emitter

Usage:
    python3 scan_platsbanken.py [hours] [outdir] [region-concept-id]

Notes
  * curl is used instead of urllib: the API occasionally answers 400 to urllib requests.
  * `offset` hard caps at 2000 -> the remaining ads are fetched by re-sharding on
    occupation-field with the same region + window filter.
"""
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from andy_keywords import NOISE, score_text, coverage  # noqa: E402

API = "https://jobsearch.api.jobtechdev.se/search"
MAX_OFFSET = 2000
STOCKHOLM = "CifL_Rzy_Mku"
REGION_LABEL = {"CifL_Rzy_Mku": "Stockholms län", "zo5Q_ap1_kvS": "Västra Götalands län",
                "o2Cg_3Ap_qvK": "Skåne län"}
# an assignment is "interesting" from 2 matched areas / 8 weighted points upward
# ---- employment-type gate -------------------------------------------------
# Andy takes consultant assignments, not employment positions: drop every ad that
# offers a job (fast anställning, provanställning, tillsvidare, vikariat, säsong,
# trainee, lärling, praktik). Only assignment-like engagement types survive.
# ANY form of employment goes — "anställning" of every kind (fast, tillsvidare, heltid,
# provanställning, behovs-, tidsbegränsad, tim-, vikariat, säsong, trainee, lärling, praktik).
# Only genuine assignment/freelance engagement types survive.
EMPLOYMENT_DROP = re.compile(
    r"anställning|vikariat|säsongsarbete|sommarjobb|feriejobb|extraarbete|trainee|lärling|praktik|"
    r"arbetsmarknadsutbildning|arbetspraktik|tillsvidare", re.I)
EMPLOYMENT_KEEP = re.compile(
    r"frilans|egen konsult|underkonsult|konsultuppdrag|uppdrag|uppdragsanställning", re.I)


def is_assignment(employment_type: str) -> bool:
    """True only for assignment-like engagement types (never permanent employment)."""
    et = (employment_type or "").strip()
    if not et:
        return False
    if EMPLOYMENT_DROP.search(et):
        return False
    return bool(EMPLOYMENT_KEEP.search(et))

MIN_GROUPS, MIN_SCORE = 2, 8


def fetch(params, tries=5):
    q = "&".join(f"{k}={v}" for k, v in params.items())
    for i in range(tries):
        r = subprocess.run(["curl", "-s", "-m", "60", "-H", "accept: application/json", f"{API}?{q}"],  # proc-allow: vendored skill script folded live->tree (issue #2262 fold parity; not a bot-lane runner)
                           capture_output=True, text=True)
        try:
            d = json.loads(r.stdout)
            if "hits" in d:
                return d
        except Exception:
            pass
        time.sleep(2 * (i + 1))
    return None


def paged(since, region, extra=None, sink=None):
    off, last = 0, None
    while True:
        p = {"limit": "100", "offset": str(off), "sort": "pubdate-desc",
             "published-after": since, "region": region}
        p.update(extra or {})
        d = fetch(p)
        if not d:
            break
        last = d
        for h in d["hits"]:
            sink[h["id"]] = h
        n = len(d["hits"])
        off += n
        if n < 100 or off >= min(d["total"]["value"], MAX_OFFSET):
            break
        time.sleep(0.6)
    return last


def ad_text(a):
    parts = [(a.get("description") or {}).get("text") or "", a.get("headline") or ""]
    for key in ("occupation", "occupation_group", "occupation_field"):
        parts.append((a.get(key) or {}).get("label") or "")
    for level in ("must_have", "nice_to_have"):
        blk = a.get(level) or {}
        for field in ("skills", "work_experiences", "education", "languages"):
            parts += [x.get("label", "") for x in (blk.get(field) or [])]
    return " ".join(parts)


def detail(a):
    """Everything the emitter needs — no second lookup against the raw dump."""
    addr = a.get("workplace_address") or {}
    emp = a.get("employer") or {}
    mh, nh = a.get("must_have") or {}, a.get("nice_to_have") or {}
    return {
        "id": a["id"],
        "headline": a.get("headline"),
        "pub": a.get("publication_date"),
        "last_pub": a.get("last_publication_date"),
        "deadline": a.get("application_deadline"),
        "url": a.get("webpage_url"),
        "logo": a.get("logo_url"),
        "employer": emp.get("name"),
        "employer_url": emp.get("url"),
        "employer_orgnr": emp.get("organization_number"),
        "employer_workplace": emp.get("workplace"),
        "city": addr.get("city"), "municipality": addr.get("municipality"),
        "region": addr.get("region"), "postcode": addr.get("postcode"),
        "country": addr.get("country"), "street": addr.get("street_address"),
        "workplace_model": a.get("workplace_model"),
        "occupation": (a.get("occupation") or {}).get("label"),
        "occupation_group": (a.get("occupation_group") or {}).get("label"),
        "occupation_field": (a.get("occupation_field") or {}).get("label"),
        "employment_type": (a.get("employment_type") or {}).get("label"),
        "working_hours": (a.get("working_hours_type") or {}).get("label"),
        "scope": a.get("scope_of_work") or {},
        "duration": (a.get("duration") or {}).get("label"),
        "salary": a.get("salary_description") or (a.get("salary_type") or {}).get("label"),
        "vacancies": a.get("number_of_vacancies"),
        "experience_required": a.get("experience_required"),
        "access": a.get("access"),
        "must_have": {k: [x.get("label") for x in (mh.get(k) or [])] for k in
                      ("skills", "work_experiences", "education", "education_level", "languages")},
        "nice_to_have": {k: [x.get("label") for x in (nh.get(k) or [])] for k in
                         ("skills", "work_experiences", "education", "languages")},
        "apply": a.get("application_details") or {},
        "contacts": a.get("application_contacts") or [],
        "description": ((a.get("description") or {}).get("text") or "").strip(),
    }


def main():
    hours = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    outdir = sys.argv[2] if len(sys.argv) > 2 else os.path.expanduser("~/.local/share/consultant-radar")
    region = sys.argv[3] if len(sys.argv) > 3 else STOCKHOLM
    region_label = REGION_LABEL.get(region, region)
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S")
    datadir = outdir          # data lives in the XDG dir, never inside a source/repo tree
    os.makedirs(datadir, exist_ok=True)

    ads = {}
    d = paged(since, region, sink=ads)
    total = d["total"]["value"] if d else 0
    for cid in {((h.get("occupation_field") or {}).get("concept_id")) for h in list(ads.values())} - {None}:
        paged(since, region, {"occupation-field": cid}, ads)
    key = region_label.split()[0].lower()[:7]
    ads = {k: a for k, a in ads.items()
           if key in ((a.get("workplace_address") or {}).get("region") or "").lower()}

    rows = []
    dropped_employment = 0
    for a in ads.values():
        matched, group_scores, score = score_text(ad_text(a))
        if not matched or NOISE.search(a.get("headline") or ""):
            continue
        core_hit, core_total = coverage(group_scores)
        if len(matched) < MIN_GROUPS or score < MIN_SCORE:
            continue
        row = detail(a)
        if not is_assignment(row.get("employment_type")):
            dropped_employment += 1
            continue
        row.update({
            "matched": matched,
            "group_scores": group_scores,
            "score": score,
            "core_coverage": f"{core_hit}/{core_total}",
            "match_count": sum(len(v) for v in matched.values()),
        })
        rows.append(row)
    rows.sort(key=lambda r: (-r["score"], -r["match_count"]))

    json.dump(list(ads.values()), open(os.path.join(datadir, "platsbanken_raw.json"), "w"))
    json.dump(rows, open(os.path.join(datadir, "platsbanken_matches.json"), "w"),
              ensure_ascii=False, indent=1)
    print(f"window since {since} (UTC) | region: {region_label} | ads in window: {total} | collected: {len(ads)}")
    print(f"CV matches: {len(rows)} -> {os.path.join(datadir, 'platsbanken_matches.json')}")
    print(f"dropped {dropped_employment} CV-matching ads that offer employment "
          f"(vanlig/tillsvidare/provanställning/vikariat/…) rather than an assignment")
    for r in rows[:15]:
        print(f'  {r["score"]:3d} | {r["pub"][:16]} | {r["headline"][:54]:54s} | {(r["employer"] or "")[:24]:24s} | '
              f'{r["match_count"]} kw / {len(r["matched"])} areas')


if __name__ == "__main__":
    main()
