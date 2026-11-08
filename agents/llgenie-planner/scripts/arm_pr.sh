#!/usr/bin/env bash
# arm_pr.sh — arm a green + approved + unarmed PR with auto-merge, mechanically.
#
# WHY THIS EXISTS
# ---------------
# The tick prompt never performed the arming it describes. Measured 2026-11-08 at
# origin/main 3e2e64fa: 10 of 18 open PRs had NO autoMergeRequest, so nothing
# merged them even when green; 2 were armed AND DIRTY (an armed DIRTY PR can never
# merge, and the board could not distinguish "armed and waiting" from "armed and
# impossible"). SOUL said "arm when the work is done, then read autoMergeRequest
# back" but no procedure called it. This script makes a single arm mechanical.
#
# THE EXIT CODE IS NEVER PROOF (issue #964). `gh pr merge --auto` exits 0 while
# arming NOTHING when the base is not the default branch. The only proof is an
# autoMergeRequest read back AFTER the arm. This script reads it and refuses to
# claim success without it.
#
# THE FOUR STATES (issue #2182) a PR can be in:
#   armed                    autoMergeRequest present, mergeable      -> nothing to do
#   unarmed                  no arm, not green+approved              -> nothing to do (reported)
#   armed-but-DIRTY (INERT)  autoMergeRequest present but DIRTY/conflict -> arm is impossible;
#                            NEVER counted as handled; dispatch to llgenie-pr-merge-conflict
#   green+approved+unarmed   mergeable, no arm, review=APPROVED      -> ARM NOW
#
# USAGE
#   arm_pr.sh <n>          # arm ONE PR; reads its live state via gh
#   arm_pr.sh --all        # sweep: classify and arm every green+approved+unarmed open PR
#
# ENV (all default to $HOME, never an absolute /home/<user>; issue #2145)
#   REPO      default $HOME/repository/git/llgenie
#   SLUG      default asimov-agent/llgenie
#   PR_STATE  a single PR's gh --json state (for tests / replay; replaces gh pr view)
#   PR_LIST   an open-PR list in gh --json shape (for --all tests; replaces gh pr list)
#   DRY       if 1, classify and print the exact arm command; run nothing
#
# EXIT
#   0  classified; the arm (if any) was read back with autoMergeRequest set
#   2  attempted an arm but the read-back showed NO autoMergeRequest (issue #964; NOT success)
#   1  usage error / PR not found / PR has a live run or is mid-rebase (refused)

set -uo pipefail

REPO="${REPO:-$HOME/repository/git/llgenie}"
SLUG="${SLUG:-asimov-agent/llgenie}"
PR_STATE="${PR_STATE:-}"
PR_LIST="${PR_LIST:-}"
DRY="${DRY:-0}"
say() { printf '[arm] %s\n' "$*"; }

MODE=""
if [ "${1:-}" = "--all" ]; then MODE=all; shift; fi
[ -z "${1:-}" ] && [ "$MODE" != "all" ] && { say "FATAL: PR number or --all required"; exit 1; }
N="${1:-}"

classify() {
  # $1 = PR json. Writes: STATE ARMED=0|1 DIRTY=0|1 REVIEW=... MS=...
  local d="$1"
  printf '%s' "$d" | python3 -c "
import sys,json
try: p=json.load(sys.stdin)
except Exception: sys.exit(3)
arm = bool(p.get('autoMergeRequest'))
ms = p.get('mergeStateStatus') or '?'
mergeable = p.get('mergeable') or '?'
review = p.get('reviewDecision') or '-'
dirty = (ms=='DIRTY')
conflict = (mergeable=='CONFLICTING')
inert = arm and (dirty or conflict)
review_deployed = review=='APPROVED'
if inert: st='inert'
elif arm: st='armed'
elif review_deployed and not dirty and not conflict: st='arm_now'
else: st='unarmed'
sys.stdout.write(f'{st} ')
print(f'ARMED={1 if arm else 0} INERT={1 if inert else 0} DIRTY={1 if dirty else 0} REVIEW={review} MS={ms}')
"
}

arm() {
  # $1 = PR number. Reads state, arms if green+approved+unarmed, reads back.
  local n="$1" state j
  if [ -n "$PR_STATE" ]; then state="$PR_STATE"; else
    state="$(gh pr view "$n" --repo "$SLUG" --json autoMergeRequest,mergeStateStatus,mergeable,reviewDecision,headRefOid,baseRefOid 2>/dev/null || echo "{}")"
  fi
  [ "$state" = "{}" ] && { say "PR #$n: not found / unreadable — refusing"; return 1; }
  j="$(classify "$state")" || { say "PR #$n: malformed state — refusing"; return 1; }
  case "$j" in
    inert*) say "PR #$n: ARMED-BUT-DIRTY (INERT) — the arm can never merge. Route to llgenie-pr-merge-conflict for a rebase. NEVER counted as handled."
            printf '%s\n' "$j"; return 0;;
    armed*) say "PR #$n: already armed — nothing to do."; printf '%s\n' "$j"; return 0;;
    unarmed*) say "PR #$n: unarmed and not green+approved+unarmed — nothing to do."; printf '%s\n' "$j"; return 0;;
    arm_now*) say "PR #$n: green + approved + unarmed -> ARMING";;
  esac
  if [ "$DRY" = "1" ]; then
    say "DRY: gh pr merge $n --repo $SLUG --squash --auto   (then read autoMergeRequest back)"
    printf '%s\n' "$j"; return 0
  fi
  # Refuse a head with a live run or mid-rebase (issue #2069): arming a moving
  # head arms a run that a rebase will destroy. Check statuses are fresh here.
  if gh pr checks "$n" --repo "$SLUG" 2>/dev/null | grep -qE '^(pending|queued|in_progress)'; then
    say "PR #$n: REFUSED — head has a live run (pending/queued/in_progress). Re-read after it lands (issue #2069)."
    return 1
  fi
  gh pr merge "$n" --repo "$SLUG" --squash --auto >/dev/null 2>&1
  rc=$?
  # THE READ-BACK IS THE FACT (issue #964). Exit code is not proof.
  rb="$(gh pr view "$n" --repo "$SLUG" --json autoMergeRequest 2>/dev/null || echo "{}")"
  if printf '%s' "$rb" | grep -q '"enable' ; then
    when="$(printf '%s' "$rb" | python3 -c "import sys,re;d=sys.stdin.read();m=re.search(r'\"enabledAt\":\"([^\"]+)\"',d);print(m.group(1) if m else 'unknown')")"
    say "ARMED #$n — autoMergeRequest read back, enabledAt=$when (the exit code was rc=$rc; the read-back is what counts)"
    printf '%s\n' "$j"
    return 0
  fi
  # gh pr merge exited 0 (or not) but armed NOTHING — issue #964 exactly.
  say "FATAL: PR #$n — armed command ran (rc=$rc) but autoMergeRequest is STILL absent."
  say "       This is the #964 shape: exit-0 with no arm. NOT success. Re-check --repo/base."
  return 2
}

if [ "$MODE" = "all" ]; then
  list="$PR_LIST"
  [ -n "$list" ] && [ -f "$list" ] && list="$(cat "$list")"
  [ -z "$list" ] && list="$(gh pr list --repo "$SLUG" --state open --limit 100 \
      --json number,autoMergeRequest,mergeStateStatus,mergeable,reviewDecision 2>/dev/null || echo "[]")"
  sweep_rc=0
  while read -r n; do
    arm "$n" || { rc=$?; echo "[arm] sweep: PR #$n exit $rc" >&2; [ "$rc" = "2" ] && sweep_rc=2; }
  done < <(printf '%s' "$list" | python3 -c "
import sys,json
for p in json.load(sys.stdin): print(p['number'])
")
  exit "$sweep_rc"
fi

arm "$N"
