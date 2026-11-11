#!/usr/bin/env python3
"""Merge the broker-sweep JSONL files into job-radar/broker_findings.json.

    python3 scripts/merge_broker_sweep.py [glob] [hours] [outdir]

Input records (one JSON object per line, one line per broker):
    {broker, url, status, evidence, items:[{title, created, created_evidence, location,
                                            link, client, engagement, deadline, snippet}]}
status vocabulary: fresh_items | open_items_no_date | login_gated | no_public_list | blocked | js_or_gated | dead

What it does
  * keeps only items whose created timestamp is inside the window (relative ages must already be absolute),
  * keeps only Stockholm/Solna/Södertälje/Danderyd/Nykvarn/Sundbyberg or location-agnostic remote,
  * scores every item with andy_keywords (>= 8 points and >= 2 CV areas to survive),
  * verifies each surviving link returns HTTP 200 (a link that 404s is dropped, not reported),
  * merges into <outdir>/job-radar/broker_findings.json without duplicating existing links,
  * writes <outdir>/job-radar/sweep_coverage.json — the per-broker status table used in the final report.
"""
import glob
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from andy_keywords import score_text, coverage as cv_coverage  # noqa: E402

PAT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.expanduser("~/.hermes/cache/scratch"),
                                                          "broker_sweep_*.jsonl")
HOURS = int(sys.argv[2]) if len(sys.argv) > 2 else 24
OUTDIR = sys.argv[3] if len(sys.argv) > 3 else os.path.expanduser("~/.local/share/consultant-radar")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130 Safari/537.36"
STOCKHOLM = re.compile(r"stockholm|solna|s[öo]dert[ä]lje|danderyd|nykvarn|sundbyberg", re.I)
REMOTE_ONLY = re.compile(r"^\s*(remote|distans|fully remote)\b", re.I)
MIN_SCORE, MIN_AREAS = 8, 2
MIN_SCORE_GATED, MIN_AREAS_GATED = 3, 1   # login-walled sources: title + end customer only
GATED = re.compile(r"verama|ework", re.I)


def is_stockholm(loc):
    loc = (loc or "").strip()
    return bool(STOCKHOLM.search(loc) or REMOTE_ONLY.match(loc))


def http_ok(url):
    try:
        code = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "-L", "-m", "20",  # proc-allow: vendored skill script folded live->tree (issue #2262 fold parity; not a bot-lane runner)
                               "-A", UA, url], capture_output=True, text=True).stdout
        return code == "200"
    except Exception:
        return False


def read_records(path):
    """Accept JSONL, a pretty-printed JSON array, or pretty-printed consecutive objects —
    subagents produce all three, and silently skipping one format loses a whole slice."""
    txt = open(path, encoding="utf-8", errors="ignore").read()
    dec = json.JSONDecoder()
    i, n = 0, len(txt)
    while i < n:
        while i < n and txt[i] in " \t\r\n,":
            i += 1
        if i >= n:
            break
        try:
            obj, j = dec.raw_decode(txt, i)
        except Exception:
            i += 1
            continue
        if isinstance(obj, list):
            yield from (o for o in obj if isinstance(o, dict))
        elif isinstance(obj, dict):
            yield obj
        i = j


def parse_created(raw):
    """Return (iso_or_date, precision, datetime_or_None). Handles '2026-10-13',
    '2026-10-13 17:01:05', '2026-10-13T09:03:21+02:00' and '2026-10-13 (relative: 19 hours ago)'."""
    raw = re.sub(r"\(.*?\)", " ", (raw or "")).strip()
    m = re.match(r"(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}):?(\d{2})(?::?(\d{2}))?)?", raw)
    if not m:
        return None, None, None
    date = m.group(1)
    if m.group(2) is None:
        return date, "date", datetime.fromisoformat(date)
    iso = f"{date}T{m.group(2)}:{m.group(3)}:{m.group(4) or '00'}"
    return iso, "time", datetime.fromisoformat(iso)


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    target = os.path.join(OUTDIR, "broker_findings.json")
    existing = json.load(open(target)) if os.path.exists(target) else []
    have_links = {(f.get("link"), f.get("role")) for f in existing}
    cutoff = datetime.now() - timedelta(hours=HOURS)

    cov_rows, added, dropped = [], [], {"window": 0, "location": 0, "score": 0, "link": 0}
    accepted_per_broker = {}
    files = sorted(glob.glob(PAT))
    parse_failures = []
    for path in files:
        found = 0
        for rec in read_records(path):
            found += 1
            cov_rows.append({"broker": rec.get("broker"), "url": rec.get("url"),
                             "status": rec.get("status"), "evidence": rec.get("evidence", ""),
                             "fresh": len(rec.get("items") or []), "source_file": os.path.basename(path)})
            for it in rec.get("items") or []:
                created, precision, dt = parse_created(it.get("created"))
                if not created:
                    dropped["window"] += 1
                    continue
                # date-only sources must be judged per day, not thrown out at 00:00
                stale = dt < cutoff if precision == "time" else dt.date() < cutoff.date()
                if stale:
                    dropped["window"] += 1
                    continue
                if not is_stockholm(it.get("location")):
                    dropped["location"] += 1
                    continue
                blob = " ".join(filter(None, [it.get("title"), it.get("snippet"), it.get("client"),
                                              it.get("engagement"), rec.get("broker")]))
                matched, group_scores, score = score_text(blob)
                if score < MIN_SCORE or len(matched) < MIN_AREAS:
                    # short sweep snippets under-score real assignments: fetch the detail page
                    # and judge the full text before rejecting anything.
                    link0 = it.get("link")
                    if link0 and score >= 3:
                        detail = subprocess.run(["curl", "-s", "-L", "-m", "25", "-A", UA, link0],  # proc-allow: vendored skill script folded live->tree (issue #2262 fold parity; not a bot-lane runner)
                                                capture_output=True, text=True).stdout
                        detail = re.sub(r"(?is)<(script|style|svg|noscript)[^>]*>.*?</\1>", " ", detail)
                        detail = re.sub(r"(?s)<[^>]+>", " ", detail)
                        rich, gs2, s2 = score_text(" ".join([blob, detail[:20000]]))
                        if s2 >= MIN_SCORE and len(rich) >= MIN_AREAS:
                            matched, group_scores, score = rich, gs2, s2
                            it["snippet"] = (it.get("snippet") or "") + "  [scored on the full detail page]"
                    gated = bool(GATED.search(f'{rec.get("broker")} {rec.get("url")} {link0 or ""}'))
                    floor, areas = ((MIN_SCORE_GATED, MIN_AREAS_GATED) if gated else (MIN_SCORE, MIN_AREAS))
                    if score < floor or len(matched) < areas:
                        dropped["score"] += 1
                        print(f'    reject(score {score}, {len(matched)} areas, gated={gated}): '
                              f'{str(it.get("title"))[:60]} | {it.get("link")}')
                        continue
                link = it.get("link")
                if not link or (link, it.get("title")) in have_links:
                    dropped["link"] += 1
                    continue
                if not http_ok(link):
                    dropped["link"] += 1
                    continue
                have_links.add((link, it.get("title")))
                accepted_per_broker[rec.get("broker")] = accepted_per_broker.get(rec.get("broker"), 0) + 1
                core_hit, core_total = cv_coverage(group_scores)
                added.append({
                    "created": created, "source": f"{rec.get('broker')} (sweep)",
                    "role": it.get("title"), "client": it.get("client", ""),
                    "location": it.get("location", ""), "engagement": it.get("engagement", ""),
                    "deadline": it.get("deadline", ""), "link": link, "rate": "",
                    "contact": "via the broker", "skills": [],
                    "description": (it.get("snippet") or "")[:1500],
                    "matched": matched, "group_scores": group_scores, "score": score,
                    "match_count": sum(len(v) for v in matched.values()),
                    "core_coverage": f"{core_hit}/{core_total}",
                    "fit": "high" if score >= 30 else ("medium" if score >= 16 else "low"),
                    "fit_note": ", ".join(sorted(matched)) or "no CV keywords",
                    "provenance": f"swept from {rec.get('broker')} ({rec.get('url')}); "
                                  f"timestamp evidence: {it.get('created_evidence')}",
                })

    merged = existing + added
    merged.sort(key=lambda f: f.get("created", ""), reverse=True)
    json.dump(merged, open(target, "w"), ensure_ascii=False, indent=1)
    for c in cov_rows:
        # re-runs see earlier sweeps' findings as duplicates, so count those too
        acc = accepted_per_broker.get(c["broker"], 0) + sum(
            1 for f in merged if str(f.get("source", "")).startswith(f'{c["broker"]} (sweep)'))
        c["cv_matching_accepted"] = acc
        if acc:
            c["status"] = "fresh_matching_items"
        elif c.get("status") == "fresh_items":
            c["status"] = "fresh_but_off_profile"
    json.dump(cov_rows, open(os.path.join(OUTDIR, "sweep_coverage.json"), "w"), ensure_ascii=False, indent=1)

    from collections import Counter
    print(f"merge: {len(files)} sweep files, {len(cov_rows)} brokers reported")
    print(f"  fresh items accepted: {len(added)} | dropped: {dropped}")
    print(f"  broker findings now: {len(merged)} -> {target}")
    print("  statuses:", dict(Counter(c["status"] for c in cov_rows)))


if __name__ == "__main__":
    main()
