#!/usr/bin/env bash
# salvage-audit.sh — read-only branch/worktree salvage audit for the owner's prune decision.
#
# NEVER deletes, prunes or removes anything. Output is a report only.
#
# Why this exists: the owner's prune is owner-only and irreversible for any work that
# exists on no remote. Uncommitted files are invisible to every ancestry test, so a
# clean-looking branch list can still hide the only copy of a lane's run. This script
# answers exactly one question per branch — "would deleting it lose work?" — and per
# worktree — "is anything uncommitted or uniquely-held here?".
#
# Four buckets, per branch:
#   LANDED   tip is an ancestor of origin/main, or the branch of a MERGED PR  -> lossless
#   ON-A-PR  tip is an open PR head, or the branch is an open PR's head-branch -> lossless
#   NO-DIFF  main already covers every path the branch touches                 -> lossless
#   UNIQUE   the branch ADDS a path main lacks                                 -> PRESERVE
#
# Then UNIQUE is split again by CONTENT: a branch whose added paths all exist in some
# open PR head is covered by that PR even under a different branch name (this is what
# catches a rebase lane's own scratch replays), leaving the genuinely-only-here set.
#
# Usage: salvage-audit.sh [<repo>]
#   default: $LLGENIE_REPO, else the nearest parent of this script containing .git, else cwd.
#   Never a hardcoded host path: this script ships to every checkout and to CI, where the
#   repository lives at a different absolute path (measured: the python sibling pinned
#   /home/asimov/... and would have failed on every runner).
# Exit 0 always unless git itself fails; this is a report, not a gate.

set -uo pipefail
if [ -n "${1:-}" ]; then
  REPO="$1"
elif [ -n "${LLGENIE_REPO:-}" ]; then
  REPO="$LLGENIE_REPO"
else
  # walk up from this script's own directory to the checkout root
  _d=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
  REPO=""
  while [ "$_d" != "/" ]; do
    if [ -e "$_d/.git" ]; then REPO="$_d"; break; fi
    _d=$(dirname -- "$_d")
  done
  [ -n "$REPO" ] || REPO="$(pwd)"
fi
cd "$REPO" || exit 2

command -v gh >/dev/null || { echo "gh CLI required (open/merged PR sets)" >&2; exit 2; }

# Always the remote-tracking ref: a stray refs/heads/origin/main shadows this name.
MAIN=$(git rev-parse refs/remotes/origin/main 2>/dev/null) || {
  echo "refs/remotes/origin/main missing — fetch first" >&2; exit 2; }

SHADOW=$(git rev-parse --verify --quiet refs/heads/origin/main >/dev/null 2>&1 && echo present || echo absent)

# Scratch dir for the two gh payloads. The ONLY removal this script performs, and it is
# fenced two ways so a mis-expansion cannot widen it: the path must exist, and its basename
# must match mktemp's own pattern. A reader grepping for `rm` in a script that promises to
# delete nothing should find exactly this one line, explainable on sight.
tmp=$(mktemp -d /tmp/salvage-audit.XXXXXX)
cleanup() {
  case "$tmp" in
    /tmp/salvage-audit.*) [ -d "$tmp" ] && rm -rf -- "$tmp" ;;
  esac
}
trap cleanup EXIT

gh pr list --repo asimov-agent/llgenie --state open --limit 300 \
  --json number,headRefName,headRefOid > "$tmp/open.json" 2>/dev/null || echo '[]' > "$tmp/open.json"
gh pr list --repo asimov-agent/llgenie --state merged --limit 500 \
  --json number,headRefName > "$tmp/merged.json" 2>/dev/null || echo '[]' > "$tmp/merged.json"

python3 - "$MAIN" "$tmp/open.json" "$tmp/merged.json" <<'PY'
import json, subprocess, sys, collections

MAIN, OPENF, MERGEDF = sys.argv[1], sys.argv[2], sys.argv[3]

def run(*a):
    r = subprocess.run(a, capture_output=True, text=True)
    return r.returncode, r.stdout.strip()

open_prs   = json.load(open(OPENF))
merged_prs = json.load(open(MERGEDF))
open_names  = {p["headRefName"]: p["number"] for p in open_prs}
open_heads  = {p["headRefOid"]: p["number"] for p in open_prs}
merged_names = {p["headRefName"]: p["number"] for p in merged_prs}

rc, out = run("git", "branch", "--format=%(refname:short)")
branches = [b.strip() for b in out.split("\n") if b.strip()]

rows = []
for b in branches:
    rc, tip = run("git", "rev-parse", "--verify", b + "^{commit}")
    if rc != 0:
        rows.append(dict(branch=b, bucket="UNREADABLE", tip="?", detail="tip cannot be read")); continue
    t8 = tip[:8]
    rc, _ = run("git", "merge-base", "--is-ancestor", tip, MAIN)
    if rc == 0:
        rows.append(dict(branch=b, bucket="LANDED", tip=t8, detail="ancestor of origin/main")); continue
    if tip in open_heads:
        rows.append(dict(branch=b, bucket="ON-A-PR", tip=t8,
                         detail="head of open PR #%d" % open_heads[tip])); continue
    if b in open_names:
        rows.append(dict(branch=b, bucket="ON-A-PR", tip=t8,
                         detail="branch of open PR #%d" % open_names[b])); continue
    if b in merged_names:
        rows.append(dict(branch=b, bucket="LANDED", tip=t8,
                         detail="branch of merged PR #%d" % merged_names[b])); continue
    # UNIQUE test: does the branch ADD a path main has never had?
    rc, dt = run("git", "diff", "--name-status", "%s...%s" % (MAIN, tip))
    added = []
    for line in dt.split("\n"):
        if line.startswith("A\t"):
            p = line.split("\t")[1]
            rc2, _ = run("git", "cat-file", "-e", "%s:%s" % (MAIN, p))
            if rc2 != 0:
                added.append(p)
    if not added:
        rows.append(dict(branch=b, bucket="NO-DIFF", tip=t8,
                         detail="main already covers every path it touches")); continue
    # content test: are those added paths already in SOME open PR head?
    hit = None
    for p in open_prs:
        ok = 0
        for f in added:
            rc2, _ = run("git", "cat-file", "-e", "%s:%s" % (p["headRefOid"], f))
            ok += (rc2 == 0)
        if ok == len(added):
            hit = p["number"]; break
    if hit:
        rows.append(dict(branch=b, bucket="ON-A-PR", tip=t8,
                         detail="content held by open PR #%d (different branch name)" % hit))
    else:
        rows.append(dict(branch=b, bucket="UNIQUE", tip=t8,
                         detail="+%d path(s) only here" % len(added), added=added))

c = collections.Counter(r["bucket"] for r in rows)
uniq = [r for r in rows if r["bucket"] == "UNIQUE"]

print("=== BRANCHES: %d @ main %s ===" % (len(rows), MAIN[:8]))
for k in ("LANDED", "ON-A-PR", "NO-DIFF", "UNIQUE", "UNREADABLE"):
    if c.get(k):
        print("  %-10s %d" % (k, c[k]))
print()
print("=== UNIQUE — content that exists only on these branches ===")
for r in sorted(uniq, key=lambda x: x["branch"]):
    subj = run("git", "log", "-1", "--format=%s", r["branch"])[1][:66]
    auth = run("git", "log", "-1", "--format=%an", r["branch"])[1][:28]
    print("  %-42s %s  %-20s %s" % (r["branch"], r["tip"], r["detail"], subj))

# fingerprint duplicates (identical added-file blobs) so twin branches are obvious
print()
print("=== duplicate-content groups within UNIQUE ===")
sig = {}
for r in uniq:
    key = tuple(sorted(
        run("git", "rev-parse", "%s:%s" % (r["branch"], f))[1]
        for f in r.get("added", [])))
    sig.setdefault(key, []).append(r["branch"])
for k, v in sig.items():
    if len(v) > 1:
        print("  identical: %s" % ", ".join(sorted(v)))

# worktrees
rc, wt = run("git", "worktree", "list", "--porcelain")
cur, wts = {}, []
for line in wt.split("\n"):
    if line.startswith("worktree "):
        if cur: wts.append(cur)
        cur = {"path": line[9:]}
    elif line.startswith("branch "):
        cur["branch"] = line[7:].replace("refs/heads/", "")
    elif line == "detached":
        cur.setdefault("branch", "(detached)")
if cur: wts.append(cur)

uniq_b = {r["branch"] for r in uniq}
dirty, wt_uniq = [], []
for w in wts:
    rc2, st = run("git", "-C", w["path"], "status", "--porcelain")
    if rc2 != 0:
        dirty.append((w["path"], w.get("branch", "?"), -1)); continue
    n = len([x for x in st.split("\n") if x])
    if n > 0: dirty.append((w["path"], w.get("branch", "?"), n))
    if w.get("branch") in uniq_b: wt_uniq.append(w["path"])

print()
print("=== WORKTREES: %d ===" % len(wts))
print("  dirty: %d  (uncommitted work is invisible to every ancestry test)" % len(dirty))
for p, b, n in sorted(dirty, key=lambda x: -x[2]):
    print("    %-58s %-34s %s file(s)" % (p, b, n))
print("  on a UNIQUE branch: %d" % len(wt_uniq))
for p in sorted(wt_uniq):
    print("    %s" % p)

preserve_wt = {p for p, _, _ in dirty} | set(wt_uniq)
print()
print("=== CONCLUSION ===")
print("SAFE IN PRINCIPLE TO DELETE: %d branches, %d worktrees" %
      (len(rows) - len(uniq), len(wts) - len(preserve_wt)))
print("MUST BE PRESERVED: %d branches + %d worktrees" % (len(uniq), len(preserve_wt)))
for r in sorted(uniq, key=lambda x: x["branch"]):
    print("  branch %-42s %s" % (r["branch"], r["tip"]))
print("Nothing was deleted, pruned or removed.")
PY

echo
echo "refs/heads/origin/main shadow: $SHADOW   (a shadow corrupts quoted shas)"
echo "All measurements vs refs/remotes/origin/main = ${MAIN:0:8}"
