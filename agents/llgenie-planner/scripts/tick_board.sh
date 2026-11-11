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
#   KANBAN_DB     read-only SQLite path of the kanban board (default $HOME/.hermes/kanban.db);
#                 section D reads task_runs.profile from it for the mis-profiled-run check.
#                 Ignored when KANBAN_RUNS_JSON is set.
#   KANBAN_RUNS_JSON an alternative task_runs excerpt already in [{"task_id", "profile",
#                 "status"}] shape; section D reads it instead of the DB (tests / replay).
#   MAIN_OVERRIDE an alternative main sha for section B's staleness comparison
#                 and section F's TIP tag (replay a historical snapshot; defaults
#                 to the freshly-fetched tip). Comparisons are prefix rules, so a
#                 7-, 8-, 9- or 40-char name all denote the same commit (issue #2450).
#   RUN_LIST_JSON an alternative CI run list already in gh run list --json shape;
#                 section F reads it instead of gh (tests / replay of a snapshot).

set -uo pipefail

REPO="${REPO:-$HOME/repository/git/llgenie}"
SLUG="${SLUG:-asimov-agent/llgenie}"
HERMES_BIN="${HERMES_BIN:-$HOME/.hermes/hermes-agent/.hermes/bin/hermes}"
STALL_SWEEP="${STALL_SWEEP:-$HOME/.hermes/profiles/llgenie-planner/cache/scratch/stall_reclaim.sh}"
KANBAN_DB="${KANBAN_DB:-$HOME/.hermes/kanban.db}"
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

# --- B. OPEN PRs: base, staleness vs the freshly-fetched tip, DIRTY ---------
# A DIRTY PR gets NO CI run at all, so nobody is ever notified of it again.
say "B. OPEN PRs (base vs main, staleness, DIRTY, arm state)"
if [ -n "${PR_LIST_JSON:-}" ]; then
  cat "$PR_LIST_JSON"
else
  # autoMergeRequest + reviewDecision are REQUIRED here: omitting them silently
  # reads unarmed for every PR (issue #2182 — a false measurement that looked
  # authoritative). gh pr list returns them only when the field list asks.
  gh pr list --repo "$SLUG" --state open --limit 100 \
    --json number,baseRefOid,mergeStateStatus,mergeable,headRefOid,title,autoMergeRequest,reviewDecision 2>/dev/null
fi \
| python3 -c "
import sys,json
try: d=json.load(sys.stdin)
except Exception: d=[]
main='$MAIN'
def same_commit(a, b):
    # issue #2450: sha names differ by truncation (8-char base vs 9-char main,
    # 40-char baseRefOid vs short-form main). Two names denote the SAME commit
    # when either contains the other; a stale base shares no prefix.
    a = a or ''; b = b or ''
    return bool(a) and bool(b) and (a.startswith(b) or b.startswith(a))
stale=dirty=0
armed=unarmed=inert=0
for p in d:
    base=(p.get('baseRefOid') or '')[:8]
    st=p.get('mergeStateStatus') or '?'
    review=p.get('reviewDecision') or '-'
    is_stale = not same_commit(base, main)
    is_dirty = st == 'DIRTY'
    stale += is_stale; dirty += is_dirty
    am = p.get('autoMergeRequest')
    has_arm = bool(am)
    # four-arm classification (issue #2182): an armed-but-DIRTY/CONFLICTING arm is
    # INERT — it can never merge (DIRTY gets no CI run, queue never sees it) and
    # must never be counted as handled.
    if has_arm and is_dirty:
        arm = 'ARM-INERT (armed+DIRTY, impossible) -> llgenie-pr-merge-conflict'
        inert += 1
    elif has_arm:
        arm = 'ARMED'
        armed += 1
    elif is_dirty:
        arm = 'unarmed DIRTY'
        unarmed += 1
    else:
        arm = 'unarmed'
        unarmed += 1
    tag = ('STALE ' if is_stale else 'fresh ') + ('DIRTY' if is_dirty else st)
    print(f\"  #{p['number']:<5} {tag:<22} base={base} head={(p.get('headRefOid') or '')[:8]} {arm:<28} {review:<15} {p['title'][:30]}\")
print(f'\n  TOTAL open={len(d)}  stale={stale}  dirty={dirty}')
print(f'  ARM armed={armed} unarmed={unarmed} armed-but-DIRTY(inert)={inert}')
print('  ARMED != handled: an armed-but-DIRTY PR is INERT (impossible, not waiting) —')
print('  route it to llgenie-pr-merge-conflict for a rebase. A stale base is ONE')
print('  board-wide sweep, not N tasks. A DIRTY PR has no CI run at all.')
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
# #2353: two ownership/health lines every pass must print. board-ownership is
# measured from `kanban list --json` (assignee+status, no new dependency);
# profiled_mismatch needs task_runs.profile, read read-only from KANBAN_DB (or
# the KANBAN_RUNS_JSON seam, for tests).
say "D. QUEUE (running / ready / blocked, and each READY task)"
if [ -n "${KANBAN_RUNS_JSON:-}" ]; then
  RUNS_SRC=$(cat "$KANBAN_RUNS_JSON")
elif [ -r "$KANBAN_DB" ]; then
  RUNS_SRC=$(KANBAN_DB="$KANBAN_DB" python3 - <<'PY'
import sqlite3, os, json
db = os.environ["KANBAN_DB"]
rows = []
try:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = [{"task_id": r[0], "profile": r[1], "status": r[2]}
            for r in con.execute("SELECT task_id, profile, status FROM task_runs WHERE status='running'")]
except Exception:
    pass
print(json.dumps(rows))
PY
)
else
  RUNS_SRC='[]'
fi
printf '%s' "$KANBAN_SRC" | KANBAN_RUNS_SRC="$RUNS_SRC" python3 -c "
import sys,json,collections,os
try: d=json.load(sys.stdin)
except Exception: d=[]
try: runs=json.loads(os.environ.get('KANBAN_RUNS_SRC','[]'))
except Exception: runs=[]
c=collections.Counter(t.get('status') for t in d)
for s in ('running','ready','blocked'):
    print(f'  {s:9} {c.get(s,0)}')
for t in d:
    if t.get('status')=='ready':
        print(f\"    READY {t['id']} {t.get('assignee') or '':32} {t.get('title') or '':44}\")
# #2353 AC1 — lane-ownership invariant (measured from kanban list --json).
# The planner legitimately OWNS ready cards only for its own orchestration
# domain; a bulk assignee rewrite into llgenie-planner inflates planner
# ready-ownership while collapsing the number of lanes still holding ready work.
PLANNER='llgenie-planner'
ready=[t for t in d if t.get('status')=='ready']
planner_owned_ready=sum(1 for t in ready if t.get('assignee')==PLANNER)
lanes_with_ready=len({t.get('assignee') for t in ready if t.get('assignee') not in (None,'',PLANNER)})
# planner-domain cards: ready cards LLGenie's own orchestration machinery
# created (the planner or its auto-decomposer) and handed to the planner —
# the plausible ceiling for planner ready-ownership. A bulk assignee rewrite
# reassigns LANE-created cards into planner; those are not in this set, so
# planner_owned_ready can never stay under the domain ceiling once it happens.
PLANNER_CREATORS=('llgenie-planner','auto-decomposer')
planner_created=sum(1 for t in ready if t.get('assignee')==PLANNER and (t.get('created_by') or '') in PLANNER_CREATORS)
expect='planner-domain {p} (ready, planner/decomposer-created)'.format(p=planner_created)
status='OK' if planner_owned_ready<=max(1,planner_created) else 'RED'
print(f'  board-ownership: planner_owned_ready={planner_owned_ready} (expect <= {expect}) lanes_with_ready={lanes_with_ready} -> {status}')
# #2353 AC2 — mis-profiled run detection: for every running task compare its
# active run's profile with its assignee. 2026-11-09's 6 planner-profiled runs
# on lane tasks print 6 here; a healthy board prints 0.
run_by_task={r.get('task_id'):r.get('profile') for r in runs if r.get('status')=='running'}
mismatched=[]
for t in d:
    if t.get('status')!='running': continue
    prof=run_by_task.get(t.get('id'))
    ass=t.get('assignee')
    if prof and ass and prof!=ass:
        mismatched.append((t.get('id'), ass, prof))
print(f'  profiled_mismatch={len(mismatched)}' + ('' if not mismatched else '  <-- '+', '.join(f'{i}={a}/{p}' for i,a,p in mismatched)))
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
if [ -n "${RUN_LIST_JSON:-}" ]; then RUNS_SRC=$(cat "$RUN_LIST_JSON"); else RUNS_SRC=$(gh run list --repo "$SLUG" --limit 6 \
  --json databaseId,workflowName,conclusion,status,headSha 2>/dev/null); fi
printf '%s' "$RUNS_SRC" | python3 -c "
import sys,json
try: d=json.load(sys.stdin)
except Exception: d=[]
main='$MAIN'
def same_commit(a, b):
    # issue #2450 (same rule as section B): TIP must hold at any short-sha length.
    a = a or ''; b = b or ''
    return bool(a) and bool(b) and (a.startswith(b) or b.startswith(a))
for r in d:
    same='TIP' if same_commit((r.get('headSha') or '')[:8], main) else 'other'
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
