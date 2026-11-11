#!/usr/bin/env python3
"""Stage 2.5 — turn broker captures into *enriched* job-radar/broker_findings.json.

Captures (browser workspace):
  verama_jobs.json          Ework/Verama list (title, ref, comp, loc, age)
  cinode_market.json        Cinode Market cards (title | id | dates | loc | company | Announced ...)
  brainville_links.json     Brainville sample items (href, ctx)
  brainville_details.json   Brainville detail pages per requisition id (skills, location, duration, deadline)

Enrichment: the detail page of every kept assignment is fetched (curl, or taken from the
captures for Tingent/Brainville) and scored with andy_keywords.score_text(), so each finding
carries its own description, requirement bullets, skills, timeline and match evidence.

Usage: python3 build_broker_findings.py <workspace-dir> [hours]
"""
import json
import os
import re
import subprocess
import sys
import html as htmlmod
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from andy_keywords import GROUPS, score_text, coverage  # noqa: E402

WS = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("BH_AGENT_WORKSPACE", ".")
HOURS = int(sys.argv[2]) if len(sys.argv) > 2 else 24
HEREDIR = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.environ.get("JOB_RADAR_DATA") or os.path.expanduser("~/.local/share/consultant-radar")
if not os.path.isdir(OUTDIR):
    OUTDIR = HEREDIR
os.makedirs(OUTDIR, exist_ok=True)
OUT = os.path.join(OUTDIR, "broker_findings.json")
NOW = datetime.now()
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130 Safari/537.36"

DROP_TITLE = re.compile(r"\bSAP\b|COBOL|PHP|\.NET|Test manager|Miljöinspektör|Webbanalytiker|ASIC|ClearCase|"
                        r"Master Planner|Power Electronics|SharePoint|Lean|vatten- och sediment", re.I)
CORE_STOCKHOLM = re.compile(r"stockholm|solna|s[öo]dert[äa]lje|danderyd|nykvarn|sundbyberg", re.I)
REMOTE_ANYWHERE = re.compile(r"^\s*(remote|distans|fully remote)\b", re.I)


def is_stockholm(loc: str) -> bool:
    """Stockholms l\u00e4n, or a posting that is location-agnostic (pure remote) — never 'Sundsvall (90% remote)'."""
    loc = (loc or "").strip()
    return bool(CORE_STOCKHOLM.search(loc) or REMOTE_ANYWHERE.match(loc))

MIN_SCORE, MIN_AREAS = 8, 2      # CV thresholds — same as stage 1
MIN_SCORE_GATED = 3              # title-only sources (description behind a login): Ework/Verama

findings = []


def curl_text(url, keep=None, drop_before=None, limit=6000):
    """Fetch a page and return its visible text (best effort)."""
    try:
        h = subprocess.run(["curl", "-s", "-L", "-m", "30", "-A", UA, url],  # proc-allow: vendored skill script folded live->tree (issue #2262 fold parity; not a bot-lane runner)
                           capture_output=True, text=True).stdout
    except Exception:
        return ""
    h = re.sub(r"(?is)<(script|style|svg|noscript|nav|footer)[^>]*>.*?</\1>", " ", h)
    t = htmlmod.unescape(re.sub(r"(?s)<[^>]+>", "\n", h))
    lines = [l.strip() for l in t.split("\n") if l.strip()]
    txt = "\n".join(lines)
    if drop_before:
        i = txt.find(drop_before)
        if i > 0:
            txt = txt[i + len(drop_before):]
    txt = re.sub(r"\n{3,}", "\n\n", txt).strip()
    # drop the site chrome that every broker page starts with
    chrome = ["Open assignments\nCompanies\nSupport\nApply now\n",
              "Marketplace\nProducts\nPricing\nAbout Brainville\nLogin\nCreate account\nPost an assignment\n",
              "Hoppa till innehåll\n"]
    for c in chrome:
        if c in txt:
            txt = txt.split(c, 1)[1]
    if keep:
        txt = "\n".join(l for l in txt.split("\n") if keep(l))
    return txt[:limit]


def enrich(f):
    """Add keyword match evidence + fit tier to a finding."""
    blob = " ".join(filter(None, [f.get("role"), f.get("client"), f.get("description"),
                                  " ".join(f.get("skills") or []), f.get("engagement")]))
    matched, group_scores, score = score_text(blob)
    core_hit, core_total = coverage(group_scores)
    f.update(matched=matched, group_scores=group_scores, score=score,
             match_count=sum(len(v) for v in matched.values()),
             core_coverage=f"{core_hit}/{core_total}")
    f["fit"] = "high" if score >= 30 else ("medium" if score >= 16 else "low")
    top = sorted(((v, k) for k, v in group_scores.items()), reverse=True)[:4]
    f["fit_note"] = "; ".join(f"{GROUPS[g]['label']} ({s} pts)" for s, g in top) or "no CV keywords found"
    return f


def add(**kw):
    kw.setdefault("description", "")
    kw.setdefault("skills", [])
    kw.setdefault("contact", "")
    kw.setdefault("rate", "")
    f = enrich(kw)
    findings.append(f)
    return f


# ------------------------------------------------------------------ Ework / Verama
p = os.path.join(WS, "verama_jobs.json")
if os.path.exists(p):
    for r in json.load(open(p)):
        m = re.search(r"(\d+)\s+(hour|day)", r["age"])
        if not m:
            continue
        delta = timedelta(hours=int(m.group(1))) if m.group(2) == "hour" else timedelta(days=int(m.group(1)))
        if delta > timedelta(hours=HOURS):
            continue
        if not is_stockholm(r["loc"]) or DROP_TITLE.search(r["title"]):
            continue
        f = add(created=(NOW - delta).replace(microsecond=0).isoformat(),
            source="Ework / Verama (largest Nordic broker)", role=r["title"], client=r["comp"],
            location=r["loc"], engagement=f"Contract job, posted {r['age']}", deadline="",
            link="https://app.verama.com/en/job-requests",
            description=(f"Ework/Verama contract job, reference {r['ref']}, end customer {r['comp']}, "
                         f"location {r['loc']}. Full assignment description and hourly rate are behind the "
                         f"(free) Verama login; the listing itself was published {r['age']}."),
            skills=[], contact="", rate="not public (login required)",
            provenance=f"app.verama.com/en/job-requests guest list, ref {r['ref']}, age \"{r['age']}\"; "
                       f"description + rate gated behind the free Verama login, scored on the title/end customer only")
        if f["score"] < MIN_SCORE_GATED or not f["matched"]:
            findings.pop()

# ------------------------------------------------------------------ Cinode Market
p = os.path.join(WS, "cinode_market.json")
if os.path.exists(p):
    for s in json.load(open(p)):
        m = re.search(r"(\d{4,6}) \|", s)
        rid = m.group(1) if m else ""
        seg = [x.strip() for x in s.split(" ||| ")[0].split("|")]
        ann = next((x for x in seg if x.startswith("Announced")), "")
        if "13 Oct, 2026" not in ann and "14 Oct, 2026" not in ann:
            continue
        loc = next((x for x in seg if re.search(r"onsite|remote|%", x, re.I)), "Stockholm")
        if not is_stockholm(loc):
            continue  # Stockholms län, or a location-agnostic remote posting
        comp = seg[seg.index(ann) - 1] if ann and seg.index(ann) > 0 else ""
        deadline = next((x.replace("Deadline ", "") for x in seg if x.startswith("Deadline")), "")
        dates = next((x for x in seg if re.search(r"\d{4} to |From \d", x)), "")
        link = f"https://cinode.com/market/requests/{rid}"
        body = curl_text(link, drop_before=seg[0], limit=6000)
        reqs = [l for l in body.split("\n") if re.match(r"^(•|-|\*)", l) or len(l) > 120]
        before = len(findings)
        f = add(created="2026-10-13", source=f"Cinode Market / {comp}", role=seg[0], client="",
                location=loc, engagement=dates, deadline=deadline, link=link,
                description=body, skills=reqs[:40],
                rate=next((x for x in seg if "SEK" in x), ""),
                contact="via Cinode Market (broker: %s)" % comp,
                provenance=f"Cinode Market card {rid} (announced {ann.replace('Announced ', '')}) + detail page {link}")
        if f["score"] < MIN_SCORE or len(f["matched"]) < MIN_AREAS:
            findings.pop()   # card passed location+window but the assignment itself is off-CV

# ------------------------------------------------------------------ Brainville
links_p, details_p = os.path.join(WS, "brainville_links.json"), os.path.join(WS, "brainville_details.json")
if os.path.exists(links_p):
    details = json.load(open(details_p)) if os.path.exists(details_p) else {}
    for r in json.load(open(links_p)):
        m = re.search(r"id=(\d+)", r["href"])
        if not m:
            continue
        if not r["ctx"].startswith(("yesterday", "today")):
            continue
        t = re.search(r"(yesterday|today) (\d{2}):(\d{2})", r["ctx"])
        created = (NOW - timedelta(days=1)).strftime("%Y-%m-%d") + f"T{t.group(2)}:{t.group(3)}:00" if t else "2026-10-13"
        if t and datetime.strptime(created, "%Y-%m-%dT%H:%M:%S") < NOW - timedelta(hours=HOURS):
            continue
        parts = [x.strip() for x in r["ctx"].split("|")]
        PLACE = re.compile(r"^(Stockholm|Stockholms l[äa]n|Solna|G[öo]teborg|Sk[åa]ne|V[äa]ster[åa]s|Sundsvall|"
                           r"Karlstad|Remote|Helsinki|Trondheim|Warsaw|Wroclaw|Gdansk|Gdynia|K[øo]benhavn|"
                           r"Lodz|Budapest|Oskarshamn|Lund|Norrk[öo]ping|Uppsala)", re.I)
        loc = next((x for x in parts[1:] if PLACE.match(x)), "Stockholm")
        if not is_stockholm(loc):
            continue          # Stockholms län, or a location-agnostic remote posting
        det = details.get(m.group(1), "")
        skills = []
        sm = re.search(r"\bApply\b(.*?)(?:Want to know more|Create an account|Login\b|$)", det, re.S)
        if sm:
            chunk = sm.group(1)
            if "|" in chunk:
                skills = [x.strip() for x in chunk.split("|")]
            else:
                skills = [x.strip() for x in chunk.split("\n")]
            skills = [x for x in skills if 2 < len(x) < 45]
        days = re.search(r"(\d+)\s+days? left", det) or re.search(r"(\d+)\s+days? left", r["ctx"])
        deadline = (NOW + timedelta(days=int(days.group(1)))).strftime("%Y-%m-%d") if days else ""
        dur = re.search(r"Duration \|\s*([^|\n]{3,40})", det)
        eng_bits = [x for x in parts[3:12] if x and not x.isdigit()]
        eng = "; ".join(eng_bits)[:200] or "see assignment page"
        f = add(created=created, source="Brainville (consultant marketplace)", role=r["title"], client="",
            location=loc, engagement=eng,
            deadline=deadline, link=r["href"],
            description=det or r["ctx"],
            skills=skills, rate=next((x for x in parts if "SEK" in x or "/h" in x), ""),
            contact="apply in Brainville (free account), client posted anonymously",
            provenance=f"Brainville search sample ({r['query']}) + requisition page {r['href']}")
        if f["score"] < MIN_SCORE or len(f["matched"]) < MIN_AREAS:
            findings.pop()

# ------------------------------------------------------------------ Tingent (embedded JSON)
ting = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..")
tmp_candidates = [os.path.join(WS, "tingent.html"),
                  "/home/asimov/.hermes/cache/scratch/brokers/tingent.html"]
tmp = next((p for p in tmp_candidates if os.path.exists(p)), tmp_candidates[0])
if os.path.exists(tmp):
    raw = open(tmp, encoding="utf-8", errors="ignore").read()
    for p in raw.split('"requisition_name"')[1:]:
        name = p.split('"')[1] if '"' in p else "?"
        chunk = p[:200000]
        m = re.search(r'"requisition_publisheddateandtime":"([^"]+)"', chunk)
        if not m or not m.group(1).startswith("2026-10-13"):
            continue
        desc = re.search(r'"requisition_description":"(.*?)","requisition_enddate"', chunk, re.S)
        body = (desc.group(1) if desc else "").replace("\\r", "\n").replace('\\"', '"')
        body = re.sub(r"\\u003c[^>]*\\u003e", "", body)
        sk = re.findall(r'"requisition_skillset":\[([^\]]*)\]', chunk)
        loc = re.search(r'"requisition_locationid":"([^"]+)"', chunk)
        add(created=m.group(1).replace(" ", "T"), source="Tingent (consultant broker)",
            role=name.replace("\\u0026", "&"), client="",
            location=loc.group(1) if loc else "Stockholm",
            engagement="Consultant requisition (Tingent community)", deadline="", link="https://tingent.se/jobs",
            description=body, skills=sk, contact="Tingent consultant community",
            provenance=f"tingent.se/jobs embedded requisition JSON, published {m.group(1)}")

# ------------------------------------------------------------------ KeyMan / Regent / House of Skills
KM = "https://www.keyman.se/sv/data-it/stod-i-dlp-strategi-for-power-platform-till-karolinska-institutet-16516/"
add(created="2026-10-13", source="KeyMan (broker)", role="Stöd i DLP-strategi för Power Platform",
    client="Karolinska Institutet", location="Stockholm", engagement="Consultant contract, published 2026-10-13",
    deadline="", link=KM, description=curl_text(KM, limit=5000), skills=[],
    contact="KeyMan broker (info@keyman.se)", provenance="keyman.se/uppdrag listing date column (2026-10-13) + detail page")

RG = "https://regent.se/uppdrag/1169"
add(created="2026-10-13T12:13:50", source="Regent (broker)",
    role="Dataskyddsspecialist med erfarenhet av One Trust", client="Regent direct customer", location="Stockholm",
    engagement="Uppdrags-id 1169, 100%, start ASAP", deadline="", link=RG,
    description=curl_text(RG, drop_before="Om uppdraget", limit=5000), skills=[],
    contact="Regent (broker)", provenance="regent.se/uppdrag/1169 publishedAt 2026-10-13T12:13:50")

HS = "https://www.houseofskills.se/projektedare-epic-owner-for-lms-initiativ/"
add(created="2026-10-13", source="House of Skills (broker)", role="Projektedare / Epic Owner för LMS-initiativ",
    client="", location="Stockholm", engagement="Consultant assignment, published 2026-10-13", deadline="",
    link=HS, description=curl_text(HS, limit=5000), skills=[], contact="House of Skills (broker)",
    provenance="houseofskills.se/category/konsultuppdrag WordPress published meta 2026-10-13")

findings.sort(key=lambda f: (-f["score"], f["created"]), reverse=False)
findings.sort(key=lambda f: f["created"], reverse=True)
json.dump(findings, open(OUT, "w"), ensure_ascii=False, indent=1)
print(f"enriched broker findings: {len(findings)} -> {OUT}")
for f in findings:
    print(f'  {f["created"][:16]:17s} | score {f["score"]:3d} | {f["match_count"]:2d} kw / '
          f'{len(f["matched"])} areas | {f["source"][:32]:32s} | {f["role"][:44]}')
