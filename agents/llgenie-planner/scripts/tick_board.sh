#!/usr/bin/env bash
# tick_board.sh — one measurement pass for the orchestrator tick (issue #2159).
#
# WHY THIS EXISTS
# ---------------
# The tick prompt was prose: 13 numbered steps of which only 2 named a runnable
# command. Every pass therefore interpreted the words differently, and a pass
# could satisfy a step by asserting it ("I measured quiescence") with nothing
# behind the claim. Measured 2026-11-08: a pass dispatched three lanes onto new
# backlog issues while 13 of 14 open PRs sat on stale bases and 7 lanes were
# idle — every step textually satisfied, the board untouched.
#
# The fix is not more words. It is a command per step: this script performs the
# deterministic measurements ONCE and prints them under fixed section headers
# A. ... G., so the prompt can say "act on section C" instead of describing
# what to look for. A step now either has output here or it did not run.
#
# USAGE
#   tick_board.sh            # human report (sections A-G in fixed order)
#   tick_board.sh --json     # machine report (for follow-up scripting)
#
# ENV (all default to $HOME, never an absolute /home/<user>; issue #2145)
#   REPO        default $HOME/repository/git/llgenie
#   SLUG        default asimov-agent/llgenie
#   HERMES_BIN  default $HOME/.hermes/hermes-agent/.hermes/bin/hermes
#   STALL_SWEEP default $HOME/.hermes/profiles/llgenie-planner/cache/scratch/stall_reclaim.sh
#                (the versioned stall sweep, when it lands under agents/, overrides this)
#   PR_LIST_JSON  an alternative PR list already in gh --json shape (for tests /
#                 replay of a captured snapshot); section B reads it instead of gh.
#   KANBAN_JSON   an alternative kanban list already in hermes kanban --json shape;
#                 sections C and D read it instead of hermes kanban list.
#   MAIN_OVERRIDE an alternative main sha for section B's staleness comparison
#                 (replay a historical snapshot; defaults to the freshly-fetched tip)

set -uo pipefail

REPO="${REPO:-$HOME/repository/git/llgenie}"
SLUG="${SLUG:-asimov-agent/llgenie}"
HERMES_BIN="${HERMES_BIN:-$HOME/.hermes/hermes-agent/.hermes/bin/hermes}"
STALL_SWEEP="${STALL_SWEEP:-$HOME/.hermes/profiles/llgenie-planner/cache/scratch/stall_reclaim.sh}"
JSON=0
[ "${1:-}" = "--json" ] && JSON=1

# A section header, numbered as the ACs specify.
say() { printf '\n===== %s =====\n' "$*"; }

# --- A. PREFLIGHT -----------------------------------------------------------
# A verdict read against a remembered sha is a claim about the past: main moves
# roughly every 26 minutes here. Everything below is measured at THIS sha.
say "A. PREFLIGHT"
git -C "$REPO" fetch origin main -q 2>/dev/null
MAIN="${MAIN_OVERRIDE:-$(git -C "$REPO" rev-parse --short origin/main 2>/dev/null)}"
FETCHED_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
AGENTS_B="$(git -C "$REPO" show origin/main:AGENTS.md 2>/dev/null | wc -c)"
AGENTS_L="$(git -C "$REPO" show origin/main:AGENTS.md 2>/dev/null | wc -l)"
printf 'main_sha: %s\n' "$MAIN"
printf 'fetched_at_utc: %s\n' "$FETCHED_UTC"
printf 'agents_md: %sb %sl   <- cite this sha and size in every brief\n' "$AGENTS_B" "$AGENTS_L"

# --- B. OPEN PRs: base, staleness vs the freshly-fetched tip, DIRTY, arm state -
# A DIRTY PR gets NO CI run at all, so nobody is ever notified of it again.
# The measurement is only as good as the --json field list: WITHOUT
# autoMergeRequest,reviewDecision every PR below reads `unarmed` silently — the
# false-measurement bug of #2182. Any field a row prints MUST be in the list.
say "B. OPEN PRs (base vs main, staleness, DIRTY, arm state)"
if [ -n "${PR_LIST_JSON:-}" ]; then
  cat "$PR_LIST_JSON"
else
  gh pr list --repo "$SLUG" --state open --limit 100 \
    --json number,baseRefOid,mergeStateStatus,mergeable,headRefOid,title,autoMergeRequest,reviewDecision 2>/dev/null
fi \
| python3 -c "
import sys,json
try: d=json.load(sys.stdin)
except Exception: d=[]
main='$MAIN'
stale=dirty=0
narm=0; inert=0
for p in d:
    base=(p.get('baseRefOid') or '')[:8]
    st=p.get('mergeStateStatus') or '?'
    is_stale = base != main
    is_dirty = st == 'DIRTY'
    stale += is_stale; dirty += is_dirty
    armed = bool(p.get('autoMergeRequest'))
    narm += armed
    # armed-but-DIRTY is the INERT state: DIRTY gets no CI run and the merge
    # queue never sees it, so the arm can never fulfil. Report it as impossible,
    # NEVER as handled — an armed-DIRTY PR read as 'handled' is a hold whose
    # reason expired and a merge that cannot happen.
    inert_state = armed and is_dirty
    inert += inert_state
    if inert_state:      arm = 'ARM-INERT'        # armed AND DIRTY -> impossible
    elif armed:          arm = 'ARMED'            # merge-queued and waiting
    elif (p.get('reviewDecision') == 'APPROVED' and p.get('mergeable') == 'MERGEABLE'
          and not is_dirty): arm = 'green+appr+unarm'  # ready to arm now
    else:                arm = 'unarmed'
    rev = p.get('reviewDecision') or '-'
    tag = ('STALE ' if is_stale else 'fresh ') + ('DIRTY' if is_dirty else st)
    print(f\"  #{p['number']:<5} {tag:<22} {arm:<17} rev={(rev or '-')[:15]:<15} mrg={(p.get('mergeable') or '-')[:11]:<11} base={base} head={(p.get('headRefOid') or '')[:8]}  {p['title'][:24]}\")
print(f'\n  ARM   armed={narm}  unarmed={len(d)-narm}  armed-but-DIRTY(inert)={inert}')
print('  ARM-INERT is NOT handled: dispatch llgenie-pr-merge-conflict for the rebase.')
print(f'  TOTAL open={len(d)}  stale={stale}  dirty={dirty}')
print('  A stale base is ONE board-wide sweep, not N tasks. A DIRTY PR has no CI run at all.')
"

# --- C. LANES: running count per lane, idle named ---------------------------
say "C. LANES (running counts per lane -- any 0 non-planner lane is idle)"
if [ -n "${KANBAN_JSON:-}" ]; then KANBAN_SRC=$(cat "$KANBAN_JSON"); else KANBAN_SRC=$("$HERMES_BIN" kanban list --json 2>/dev/null); fi
printf '%s' "$KANBAN_SRC" | python3 -c "
import sys,json,collections
try: d=json.load(sys.stdin)
except Exception: d=[]
c=collections.Counter(t['assignee'] for t in d if t.get('status')=='running')
lanes=['llgenie-planner','llgenie-architect','llgenie-issse-implementer','llgenie-pr-reviever',
 'llgenie-ci-pipelines-maintainer','llgenie-documentation-maintainer','llgenie-engine-improver',
 'llgenie-pr-merge-conflict','llgenie-security','llgenie-tester','llgenie-product-manager',
 'llgenie-business-analyst','llgenie-status-keeper']
idle=[]
for l in lanes:
    n=c.get(l,0)
    if n==0 and l!='llgenie-planner': idle.append(l)
    print(f'  {l:34} {n}' + ('   <-- IDLE' if n==0 and l!='llgenie-planner' else ''))
print(f'\n  idle_non_planner={len(idle)}')
print('  Every idle lane with an ownable red PR means the pass is NOT finished.')
"

# --- D. QUEUE: running / ready / blocked, with every READY task -------------
say "D. QUEUE (running / ready / blocked, and each READY task)"
printf '%s' "$KANBAN_SRC" | python3 -c "
import sys,json,collections
try: d=json.load(sys.stdin)
except Exception: d=[]
c=collections.Counter(t.get('status') for t in d)
for s in ('running','ready','blocked'):
    print(f'  {s:9} {c.get(s,0)}')
for t in d:
    if t.get('status')=='ready':
        print(f\"    READY {t['id']} {t.get('assignee') or '':32} {t.get('title') or '':44}\")
" 2>/dev/null

# --- E. STALLED WORKERS (kanban tasks + DM waiters) --------------------------
say "E. STALLED WORKERS (both classes: kanban tasks, DM waiters)"
if [ -x "$STALL_SWEEP" ]; then
  bash "$STALL_SWEEP" 2>&1 | tail -6 | sed 's/^/  /'
  echo "  quote both lines: tasks: stalled=... ; dm: stalled=... "
else
  echo "  MISSING $STALL_SWEEP -- cannot measure stalls (versioned sweep not yet installed)"
fi

# --- F. recent CI conclusions at THIS tip -----------------------------------
say "F. CI AT THE TIP (tagged TIP vs other by headSha==main; never a remembered red)"
gh run list --repo "$SLUG" --limit 6 \
  --json databaseId,workflowName,conclusion,status,headSha 2>/dev/null \
| python3 -c "
import sys,json
try: d=json.load(sys.stdin)
except Exception: d=[]
main='$MAIN'
for r in d:
    same='TIP' if (r.get('headSha') or '')[:8]==main else 'other'
    print(f\"  {str(r.get('workflowName') or '?')[:34]:34} {str(r.get('status') or '?'):10} {str(r.get('conclusion') or '-'):9} {same:5} run={r.get('databaseId')}\")
print()
print('  A failure whose headSha != main is NOT a main-tip red. Re-read at the tip before reporting.')
"

# --- G. LANE DRIFT: the exact CHECK=1 command per lane -----------------------
say "G. LANE DRIFT (tree vs live -- measure, never sync blind)"
if [ -d "$REPO" ] && git -C "$REPO" rev-parse --git-dir >/dev/null 2>&1; then
  echo "  run: make -C $REPO sync-agent-profile PROFILE=<lane> CHECK=1   (per lane)"
  echo "  and: make -C $REPO check-agent-profiles"
  echo "  never run it WITHOUT CHECK=1: several tree copies are the truncated side."
else
  echo "  repo missing"
fi

echo
echo "===== END (every section above is a measurement, not a claim) ====="
