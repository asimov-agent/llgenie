# Measure which bot lanes are idle, and which issues are genuinely dispatchable.
#
# Usage:  python3 measure_lane_idleness.py [owner/repo]
#
# Prints every workflow with keyword in its path, its newest run state and age in hours,
# then every open `agent:implement` issue that has NO assignee, NO claim comment and NO
# open PR — i.e. the intersection of "idle lane" and "unowned work" is what you route.
#
# Why the shape:
#  * match workflows on .path, never .name — a bot workflow's display name differs from
#    its filename, so name-based lookups 404 and you conclude a lane never ran.
#  * the runs payload is {"workflow_runs": [...]} at the root, not a bare array.
#  * a lane is idle when its newest run is far older than its own cron slot, or every
#    recent run is `skipped` — not when the workflow list simply looks short.
import json, re, subprocess, sys, datetime

REPO = sys.argv[1] if len(sys.argv) > 1 else "asimov-agent/llgenie"
KEYS = ("bot", "sync", "bump", "refine", "rebase", "guard", "scan", "merge",
        "arms", "holds", "reactor", "audit", "review")
CLAIM_RE = re.compile(r"\b(claim|bot-claim|claimed for implementation)\b", re.I)


def api(path):
    p = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if p.returncode != 0:
        return {}
    try:
        return json.loads(p.stdout or "{}")
    except json.JSONDecodeError:
        return {}


now = datetime.datetime.now(datetime.timezone.utc)
rows = []
for wf in api(f"repos/{REPO}/actions/workflows?per_page=100").get("workflows", []):
    path = wf.get("path", "")
    if not any(k in path.lower() for k in KEYS):
        continue
    runs = api(f"repos/{REPO}/actions/workflows/{wf['id']}/runs?per_page=1")
    runs = runs.get("workflow_runs", []) if isinstance(runs, dict) else []
    if not runs:
        rows.append((path, "NEVER", None))
        continue
    r = runs[0]
    created = datetime.datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
    rows.append((path, f"{r['status']}/{r.get('conclusion') or 'na'}",
                 (now - created).total_seconds() / 3600))

rows.sort(key=lambda x: (x[2] is None, -(x[2] or 0)))
print(f"== newest run per workflow ({REPO}) ==")
print("idle-est first; compare each age against the workflow's own cron slot")
for path, state, age in rows:
    print(f"  {path:52s} {state:22s} age={('%.1fh' % age) if age is not None else 'NA'}")

print("\n== open agent:implement issues with no assignee, no claim, no open PR ==")
issues = api(f"repos/{REPO}/issues?state=open&per_page=100&labels=agent:implement")
if isinstance(issues, dict):
    issues = []
for it in issues:
    if "pull_request" in it:
        continue
    n = it["number"]
    if it.get("assignees"):
        continue
    comments = api(f"repos/{REPO}/issues/{n}/comments?per_page=100")
    if isinstance(comments, dict):
        comments = []
    if any(CLAIM_RE.search(c.get("body") or "") for c in comments):
        continue
    prs = api(f"repos/{REPO}/pulls?state=open&per_page=100&head={REPO.split('/')[0]}:agent/issue-{n}")
    if isinstance(prs, list) and prs:
        continue
    print(f"  #{n}  {it['title'][:88]}")

print("\nReminder: a refined-but-unclaimed issue is dispatchable; a vague one is a REFINE task.")
print("A lane may be 'idle' by run-age yet still hold an open PR — check its vehicles first.")
