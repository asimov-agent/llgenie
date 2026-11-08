#!/usr/bin/env bash
# delegate.sh — one dispatch, mechanically, and prove it landed.
#
# WHY THIS EXISTS
# ---------------
# "Dispatch it out loud" was prose in the tick prompt, so a pass could report a
# delegation that never happened. Measured 2026-11-08: a pass reported 8 lanes
# "running" while 7 were idle and 12 of 14 PRs sat stale — every dispatch step
# textually satisfied, nothing created.
#
# A dispatch is four things and all four are required:
#   1. a brief on disk (multi-line; inline heredocs get mangled)
#   2. a kanban task assigned to the owning lane
#   3. a dispatch that actually spawns it
#   4. a confirmation read back from the board  <- this is the only proof
#
# `Spawned: 0` from `kanban dispatch` is NOT a failure: it means capacity is
# full and the task is queued `ready`. That is a different state from running and
# must be reported as such — conflating the two is how an idle board reads busy.
#
# USAGE
#   delegate.sh --lane <lane> --issue <n> --brief <file> [--title T]
#               [--max-runtime N] [--message] [--dry-run]
#
#   --message   DEFAULT ON. REMIND the planner to send the same brief with message_agent.
#               IMPORTANT LIMIT: this script CANNOT send it. `message_agent` is an
#               agent tool, not a shell command, so the delivery must happen in the
#               planner's own turn. The script's job is to make skipping it loud.
#               Task + message are two channels for ONE assignment: the task
#               survives turns, the message makes the lane act in its thread.
#               This defaulted to OFF once and a real dispatch (t_25ec9870) went
#               out with the lane never told - the task sat ready while the
#               planner believed it was delegated. The mandatory path is the
#               default now; skipping it requires --no-message and prints a warning.
#   --no-message  opt out explicitly (rare: only when the lane is already mid-turn
#               on this exact issue and a second message would split its attention)
#   --dry-run   validate the brief and print the exact commands; create nothing
#
# EXIT
#   0  task exists and is running or ready
#   1  bad usage / missing brief
#   2  task was created but could not be confirmed on the board

set -uo pipefail

LANE=""; ISSUE=""; BRIEF=""; TITLE=""; MAXRT=5400; DO_MSG=1; DRY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --lane) LANE="${2:-}"; shift 2;;
    --issue) ISSUE="${2:-}"; shift 2;;
    --brief) BRIEF="${2:-}"; shift 2;;
    --title) TITLE="${2:-}"; shift 2;;
    --max-runtime) MAXRT="${2:-}"; shift 2;;
    --message) DO_MSG=1; shift;;
    --no-message) DO_MSG=0; shift;;
    --dry-run) DRY=1; shift;;
    *) echo "delegate: unknown argument '$1'" >&2; exit 1;;
  esac
done

HERMES_BIN="${HERMES_BIN:-$HOME/.hermes/hermes-agent/.hermes/bin/hermes}"
say() { printf '[delegate] %s\n' "$*"; }

[ -n "$LANE" ]  || { say "FATAL: --lane required"; exit 1; }
[ -n "$ISSUE" ] || { say "FATAL: --issue required"; exit 1; }
[ -f "$BRIEF" ] || { say "FATAL: brief not found: ${BRIEF:-<empty>}"; exit 1; }

# --- gate 1: the brief must carry the things a lane cannot invent ------------
missing=""
grep -q 'AGENTS:'    "$BRIEF" || missing="$missing AGENTS-stamp"
grep -qi '\$HOME'    "$BRIEF" || missing="$missing HOME-rule"
grep -qi 'branch'    "$BRIEF" || missing="$missing branch"
grep -qi 'BOT '      "$BRIEF" || missing="$missing report-line"
if [ -n "$missing" ]; then
  say "FATAL: brief is incomplete — missing:$missing"
  say "       (a brief without these produces a PR that reds its own gates)"
  exit 1
fi

TITLE="${TITLE:-$LANE #$ISSUE: $(head -1 "$BRIEF" | cut -c1-70)}"

# --- gate 2: one vehicle per issue ------------------------------------------
if [ "$DRY" != "1" ]; then
  existing="$("$HERMES_BIN" kanban list --json 2>/dev/null \
    | python3 -c "
import sys,json
try: d=json.load(sys.stdin)
except Exception: d=[]
for t in d:
    if t.get('status') in ('running','ready') and '$LANE' in (t.get('assignee') or '') and '#$ISSUE' in (t.get('title') or ''):
        print(t['id'], t['status']); break
" 2>/dev/null)"
  if [ -n "$existing" ]; then
    say "ALREADY DELEGATED: $existing — not creating a second vehicle for #$ISSUE"
    echo "$existing"
    exit 0
  fi
fi

if [ "$DRY" = "1" ]; then
  say "DRY RUN — would run:"
  say "  $HERMES_BIN kanban create \"$TITLE\" --body-file $BRIEF --assignee $LANE --max-runtime $MAXRT --created-by llgenie-planner"
  say "  $HERMES_BIN kanban dispatch"
  [ "$DO_MSG" = "1" ] && say "  message_agent -> $LANE (same brief)"
  say "brief OK: $(wc -c < "$BRIEF")b, carries AGENTS/, \$HOME, branch, report line"
  exit 0
fi

# --- 1+2: create ------------------------------------------------------------
out="$("$HERMES_BIN" kanban create "$TITLE" --body-file "$BRIEF" \
        --assignee "$LANE" --max-runtime "$MAXRT" --created-by llgenie-planner 2>&1)"
say "$out" | tail -1
TASK="$(printf '%s' "$out" | grep -oE 't_[a-z0-9]+' | head -1)"
[ -n "$TASK" ] || { say "FATAL: no task id in create output"; exit 2; }

# --- 3: dispatch ------------------------------------------------------------
dout="$("$HERMES_BIN" kanban dispatch 2>&1)"
spawned="$(printf '%s' "$dout" | grep -oE 'Spawned:[[:space:]]+[0-9]+' | grep -oE '[0-9]+$')"

# --- 4: CONFIRM from the board — the only proof -----------------------------
status="$("$HERMES_BIN" kanban list --json 2>/dev/null | python3 -c "
import sys,json
try: d=json.load(sys.stdin)
except Exception: d=[]
for t in d:
    if t['id']=='$TASK': print(t['status']); break
" 2>/dev/null)"

case "$status" in
  running) say "CONFIRMED $TASK running -> $LANE" ;;
  ready)   say "CONFIRMED $TASK ready (queued on capacity — spawned=$spawned, all slots busy)" ;;
  blocked) say "CONFIRMED $TASK BLOCKED — it will not run until unblocked"; exit 2 ;;
  "")      say "FATAL: $TASK not found on the board after create"; exit 2 ;;
  *)       say "CONFIRMED $TASK $status" ;;
esac

# --- message channel --------------------------------------------------------
if [ "$DO_MSG" = "1" ]; then
  say "TODO (planner, this turn): send this brief to $LANE with message_agent."
  say "  This script cannot send it — message_agent is an agent tool, not a shell command."
  say "  Quote task id $TASK in the message so the lane can find its task."
  say "  A dispatch is NOT complete until both channels exist: the task here, the message there."
else
  say "WARNING: --no-message given. The task exists but the lane was NEVER TOLD in its own"
  say "         thread, so it may sit idle until its next scheduled turn. This is opt-in, and"
  say "         a lane that received neither a task nor a message must not be reported as busy."
fi

echo "$TASK $status"
