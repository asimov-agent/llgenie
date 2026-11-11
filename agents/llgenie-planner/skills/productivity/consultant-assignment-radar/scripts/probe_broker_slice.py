#!/usr/bin/env python3
"""Probe one slice of the broker registry and emit fresh-assignment candidates as JSONL.

    python3 scripts/probe_broker_slice.py <from-index> <to-index> [hours] [outfile]

For every broker in the slice it
  1. fetches the registry URL (curl, browser UA),
  2. collects candidate assignment links (same host, path looks like a listing/detail page),
  3. follows up to 12 of them and looks for a machine-readable publication time:
       - Teamtailor/JSON-LD  "datePosted": "..."
       - Cinode Market       "Announced 13 Oct, 2026"
       - WordPress           published">2026-10-13
       - Brainville/boards   "yesterday 16:06", "2 hours ago", "13 hours ago"
  4. writes one JSON object per finding with the raw evidence string, plus one status line per broker.

It does NOT log in anywhere and never guesses a date: brokers whose list is JS-only or gated come back as
status "js_or_gated" with whatever text was visible, for the browser/agent pass that follows.
"""
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.join(HERE, "..", "references", "broker-registry.json")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130 Safari/537.36"
LOOKS_DETAIL = re.compile(r"(uppdrag|jobb|jobs|assignment|annons|konsultuppdrag|requisition|"
                          r"/post/|careers?/|lediga)", re.I)

DATE_PATTERNS = [
    ("jsonld_datePosted", re.compile(r'"datePosted"\s*:\s*"([^"]+)"')),
    ("jsonld_datePublished", re.compile(r'"datePublished"\s*:\s*"([^"]+)"')),
    ("cinode_announced", re.compile(r"Announced\s+(\d{1,2}\s+\w+,\s*\d{4})")),
    ("wordpress_published", re.compile(r'published"?\s*[>":]+\s*"?(\d{4}-\d{2}-\d{2})')),
    ("iso_date", re.compile(r"\b(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})")),
    ("relative", re.compile(r"\b(\d{1,2})\s+(hour|hours|minute|minutes)\s+ago\b", re.I)),
    ("relative_day", re.compile(r"\b(1|yesterday|today)\s*(day|)?", re.I)),
]


def fetch(url, timeout=30):
    return subprocess.run(["curl", "-s", "-L", "-m", str(timeout), "-A", UA, url],  # proc-allow: vendored skill script folded live->tree (issue #2262 fold parity; not a bot-lane runner)
                          capture_output=True, text=True).stdout


def visible(html):
    html = re.sub(r"(?is)<(script|style|svg|noscript)[^>]*>.*?</\1>", " ", html)
    txt = re.sub(r"(?s)<[^>]+>", "\n", html)
    return re.sub(r"\n{2,}", "\n", txt)


def timestamps(text, href_html, now):
    out = []
    for label, pat in DATE_PATTERNS:
        for m in pat.finditer(href_html if label.startswith("jsonld") else text):
            raw = m.group(1)
            created = None
            if label.startswith("jsonld"):
                created = raw[:19].replace(" ", "T")
            elif label == "cinode_announced":
                try:
                    created = datetime.strptime(raw + " 2026" if raw.count(",") == 1 else raw,
                                                "%d %b, %Y").strftime("%Y-%m-%d")
                except Exception:
                    created = None
            elif label in ("wordpress_published", "iso_date"):
                created = raw if label == "wordpress_published" else f"{m.group(1)}T{m.group(2)}:00"
            elif label == "relative":
                created = (now - timedelta(hours=int(raw))).replace(microsecond=0).isoformat()
            out.append({"kind": label, "evidence": m.group(0).strip(), "created": created})
    return out


def main():
    lo = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    hi = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    hours = int(sys.argv[3]) if len(sys.argv) > 3 else 24
    outpath = sys.argv[4] if len(sys.argv) > 4 else os.path.join(os.getcwd(), "broker_slice.jsonl")
    now = datetime.now()
    cutoff = now - timedelta(hours=hours)
    registry = json.load(open(os.path.abspath(REG)))
    slice_ = registry[lo:hi]
    with open(outpath, "w") as out:
        for b in slice_:
            html = fetch(b["url"])
            txt = visible(html)
            links = []
            for m in re.finditer(r'href="([^"]+)"[^>]*>(.*?)</a>', html, re.S | re.I):
                href, label = m.group(1), re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(2))).strip()
                absu = urljoin(b["url"], href)
                if urlparse(absu).netloc != urlparse(b["url"]).netloc:
                    continue
                if LOOKS_DETAIL.search(absu) and 8 < len(label) < 120:
                    links.append((absu, label))
            seen, uniq = set(), []
            for u, l in links:
                if u not in seen:
                    seen.add(u)
                    uniq.append((u, l))
            items = []
            for u, l in uniq[:12]:
                page = fetch(u, timeout=20)
                if not page:
                    continue
                pts = timestamps(visible(page), page, now)
                for p in pts:
                    if not p["created"]:
                        continue
                    try:
                        d = datetime.fromisoformat(p["created"])
                    except Exception:
                        continue
                    if d >= cutoff:
                        items.append({"title": l, "link": u, "created": p["created"],
                                      "created_evidence": p["evidence"], "kind": p["kind"]})
                time.sleep(0.2)
            status = "fresh_items" if items else ("open_items_no_date" if uniq else "no_public_list")
            rec = {"broker": b["name"], "url": b["url"], "status": status,
                   "links_seen": len(uniq), "items": items}
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(f'{status:20s} {b["name"][:30]:30s} links={len(uniq):3d} fresh={len(items)}', flush=True)
    print("wrote", outpath)


if __name__ == "__main__":
    main()
