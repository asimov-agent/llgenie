#!/usr/bin/env python3
"""Stage 3 — write one *detailed* markdown file per assignment finding.

Input (job-radar/, override with JOB_RADAR_DATA):
  platsbanken_matches.json  CV-matched Platsbanken ads (full detail + match evidence)
  broker_findings.json      enriched broker/marketplace findings (full detail + match evidence)
Output:
  ~/assignments/<created-timestamp>-<slug>.md

Each file carries: created timestamp, source, end customer, location, engagement, rate,
deadline, contact, the assignment page link, the matched CV keywords per area with points
and core coverage, the ad's requirement lists, the full description, and provenance.

Usage: python3 emit_assignments.py [hours]
"""
import json
import os
import re
import subprocess
import sys
import unicodedata
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from andy_keywords import GROUPS, score_text, coverage  # noqa: E402

HEREDIR = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("JOB_RADAR_DATA") or os.path.expanduser("~/.local/share/consultant-radar")
if not os.path.exists(os.path.join(DATA, "platsbanken_matches.json")):
    DATA = HEREDIR
OUTDIR = os.path.expanduser("~/assignments")
HOURS = int(sys.argv[1]) if len(sys.argv) > 1 else 24
MIN_SCORE = 8                     # weighted CV points needed to be written out
EXCLUDE_HEAD = re.compile(
    r"(ios|android|frontend|front-end|\.net|automotive|autosar|embedded|asic|biostatistik|"
    r"spelutveckl|unity|säljare|account manager|rekryterare|kock|undersköterska|"
    r"\btestare\b|\btester\b|\bQA\b|sjuk|vård)", re.I)


def slugify(s, maxlen=60):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    return s[:maxlen].strip("-") or "assignment"


def created_stamp(created):
    created = (created or "").strip()
    m = re.match(r"(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}):?(\d{2})(?::?(\d{2}))?)?", created)
    if not m:
        return created, "unknown-time"
    date, hh, mm, ss = m.group(1), m.group(2), m.group(3), m.group(4)
    if hh is None:
        return date, f"{date}T000000-unknown-time"
    iso = f"{date}T{hh}:{mm}:{ss or '00'}"
    return iso, iso.replace(":", "").replace("-", "")


def within(iso, cutoff):
    try:
        d = datetime.fromisoformat(iso)
    except Exception:
        return True
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d >= cutoff


def clean(txt, limit=6000):
    txt = re.sub(r"[ \t]+\n", "\n", txt or "")
    txt = re.sub(r"\n{3,}", "\n\n", txt).strip()
    return txt[:limit] + ("\n\n_(truncated)_" if len(txt) > limit else "")


def match_block(matched, group_scores, score, core_coverage):
    lines = [f"**{score} points** — {sum(len(v) for v in matched.values())} CV keywords in "
             f"{len(matched)} of the CV's areas · core areas covered: **{core_coverage}**", ""]
    for g, kws in sorted(matched.items(), key=lambda kv: -group_scores.get(kv[0], 0)):
        label = GROUPS[g]["label"]
        pts = group_scores.get(g, 0)
        lines.append(f"- **{label}** ({pts} pts): " + ", ".join(sorted(kws)))
    missing = [GROUPS[g]["label"] for g in GROUPS
               if GROUPS[g]["weight"] == 3 and g not in matched]
    if missing:
        lines += ["", "Not mentioned in this ad: " + ", ".join(missing)]
    return "\n".join(lines)


def bullets(items, empty="_none stated_"):
    items = [re.sub(r"^[•\-*\s]+", "", str(x)).strip() for x in (items or [])]
    items = [x for x in items if x]
    return "\n".join(f"- {x}" for x in items) if items else empty


UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130 Safari/537.36"


def link_alive(url, tries=2):
    """200/3xx/403 = the page exists (403 is just bot protection); 404/410 = the assignment is gone."""
    for _ in range(tries):
        code = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "-L", "-m", "25",  # proc-allow: vendored skill script folded live->tree (issue #2262 fold parity; not a bot-lane runner)
                               "-A", UA, url], capture_output=True, text=True).stdout.strip()
        if code != "000":
            return code
    return "000"


def write(path, body):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").write(body)
    return path


def platsbanken_body(r):
    iso, stamp = created_stamp(r["pub"])
    loc = ", ".join(filter(None, [r.get("city"), r.get("municipality"), r.get("region"), r.get("postcode")]))
    scope = r.get("scope") or {}
    scope_txt = f"{scope.get('min') or ''}–{scope.get('max') or ''}%" if scope else ""
    apply = r.get("apply") or {}
    contacts = r.get("contacts") or []
    contact_lines = []
    for c in contacts:
        contact_lines.append(" ".join(filter(None, [c.get("name"), c.get("description"),
                                                    c.get("email"), c.get("telephone")])))
    mh, nh = r.get("must_have") or {}, r.get("nice_to_have") or {}
    mh_lines = [f"{k}: " + ", ".join(v) for k, v in mh.items() if v]
    nh_lines = [f"{k}: " + ", ".join(v) for k, v in nh.items() if v]
    body = f"""# {r['headline']}

- **Posted:** {iso}
- **Source:** Arbetsförmedlingen Platsbanken (job ad, id {r.get('id')})
- **Assignment page:** {r['url']}
- **Employer / end customer:** {r.get('employer')}{f" (org.nr {r['employer_orgnr']})" if r.get('employer_orgnr') else ''}{f" — {r['employer_url']}" if r.get('employer_url') else ''}
- **Workplace:** {r.get('employer_workplace') or '—'}
- **Location:** {loc or '—'}{f" ({r['workplace_model'].get('label') if isinstance(r['workplace_model'], dict) else r['workplace_model']})" if r.get('workplace_model') else ''}
- **Occupation (taxonomy):** {r.get('occupation') or '—'} / {r.get('occupation_group') or '—'} / {r.get('occupation_field') or '—'}
- **Engagement:** {r.get('employment_type') or '—'}{f", {r.get('working_hours')}" if r.get('working_hours') else ''}{f", scope {scope_txt}" if scope_txt else ''}{f", duration: {r.get('duration')}" if r.get('duration') else ''}
- **Salary:** {r.get('salary') or 'not stated'}
- **Vacancies:** {r.get('vacancies') or '—'}{f", experience required: {r.get('experience_required')}" if r.get('experience_required') else ''}
- **Apply by:** {(r.get('deadline') or 'not stated')[:10]}
- **Apply via:** {apply.get('url') or apply.get('email') or 'see assignment page'} {('(via Arbetsförmedlingen)' if apply.get('via_af') else '')}
- **Contact:** {'; '.join(contact_lines) or 'see ad'}

## CV match (Andy Holst)

{match_block(r['matched'], r['group_scores'], r['score'], r['core_coverage'])}

## Requirements in the ad

**Must have**
{bullets(mh_lines)}

**Nice to have**
{bullets(nh_lines)}

## Full ad text

{clean(r.get('description')) or '_no description returned by the API_'}

## Provenance

- Window: last {HOURS} h · region Stockholms län · fetched from JobTech Search API (jobsearch.api.jobtechdev.se)
- Publication timestamp source: ad `publication_date` ({iso}); ad id {r.get('id')}
- Matched with job-radar/andy_keywords.py (weighted CV keyword profile)
"""
    return body, stamp


def broker_body(b):
    iso, stamp = created_stamp(b["created"])
    skills = b.get("skills") or []
    skill_lines = [s for s in skills if isinstance(s, str)][:40]
    cov = b.get("core_coverage") or "{}/{}".format(*coverage(b.get("group_scores", {})))
    eng = re.sub(r"\s*\|\s*", " · ", (b.get("engagement") or "not stated")).strip(" ·")
    body = f"""# {b['role']}

- **Posted:** {iso}
- **Source / broker:** {b['source']}
- **Assignment page:** {b['link']}{f"  \n- **Link check:** {b['link_note']}" if b.get('link_note') else ''}
- **Client / end customer:** {b.get('client') or 'not stated'}
- **Location:** {b.get('location') or 'not stated'}
- **Engagement:** {eng}
- **Rate:** {b.get('rate') or 'not stated'}
- **Deadline:** {b.get('deadline') or 'not stated'}
- **Contact / how to apply:** {b.get('contact') or 'via the broker'}

## CV match (Andy Holst)

{match_block(b.get('matched', {}), b.get('group_scores', {}), b.get('score', 0), cov)}

## Requirements / skills listed on the page

{bullets(skill_lines)}

## Assignment description (from the broker page)

{clean(b.get('description')) or '_the broker does not publish the description without a login_'}

## Provenance

- Window: last {HOURS} h · Stockholms län (fully remote counted) · captured with the consultant-assignment-radar skill
- Posting time source: {b.get('provenance') or 'broker page timestamp'}
"""
    return body, stamp


def main():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=HOURS)
    os.makedirs(OUTDIR, exist_ok=True)
    matches = json.load(open(os.path.join(DATA, "platsbanken_matches.json")))
    brokers = json.load(open(os.path.join(DATA, "broker_findings.json")))

    written, skipped = [], {"headline": 0, "score": 0, "window": 0, "location": 0}
    for r in matches:
        if EXCLUDE_HEAD.search(r["headline"]):
            skipped["headline"] += 1
            continue
        et = (r.get("employment_type") or "")
        if not et or not re.search(r"frilans|egen konsult|underkonsult|konsultuppdrag|uppdrag", et, re.I):
            skipped["employment"] = skipped.get("employment", 0) + 1
            continue
        matched, group_scores, score = score_text(" ".join(filter(None, [
            r["headline"], r.get("description"), (r.get("employer") or ""),
            " ".join(sum((r.get("must_have") or {}).values(), []))])))
        if score < MIN_SCORE:
            skipped["score"] += 1
            continue
        if not within(r["pub"], cutoff):
            skipped["window"] += 1
            continue
        r.update(matched=matched, group_scores=group_scores, score=score,
                 match_count=sum(len(v) for v in matched.values()),
                 core_coverage="{}/{}".format(*coverage(group_scores)))
        body, stamp = platsbanken_body(r)
        written.append(write(os.path.join(OUTDIR, f"{stamp}-{slugify(r['headline'])}.md"), body))

    for b in brokers:
        loc_b = b.get("location") or ""
        if not (re.search(r"stockholm|solna|södertälje|danderyd|nykvarn|sundbyberg", loc_b, re.I)
                or re.match(r"^\s*(remote|distans|fully remote)\b", loc_b, re.I)):
            skipped["location"] += 1
            continue
        if b.get("score", 0) < MIN_SCORE and "login" not in (b.get("description") or "").lower():
            pass  # broker findings are already curated upstream; keep them
        if not within(b["created"], cutoff) and b["created"].count("-") == 2 and len(b["created"]) > 10:
            skipped["window"] += 1
            continue
        code = link_alive(b["link"])
        if code in ("404", "410"):
            skipped["dead_link"] = skipped.get("dead_link", 0) + 1
            print(f"    dropped (assignment page {code}): {b['role'][:60]} | {b['link']}")
            continue
        if code == "000":
            # 000 from curl usually means the site's WAF refused the automated request, not a dead page
            b["link_note"] = ("automated check blocked by the site (WAF) — open this page manually to confirm "
                              "it is still open")
        body, stamp = broker_body(b)
        path = os.path.join(OUTDIR, f"{stamp}-{slugify(b['role'])}.md")
        i = 2
        while os.path.exists(path):
            path = os.path.join(OUTDIR, f"{stamp}-{slugify(b['role'])}-{i}.md")
            i += 1
        written.append(write(path, body))

    print(f"assignments written: {len(written)} -> {OUTDIR}")
    print(f"skipped: {skipped}")
    print(f"window start: {cutoff.isoformat()}")


if __name__ == "__main__":
    main()
