#!/usr/bin/env bash
# PR fix-bot loop (issue #222): check -> one Hermes repair attempt -> re-check, up to
# FIX_ROUNDS times, then stop.
#
# Exit codes: 0 = green (the workflow may push), 1 = still red after every round (leave
# it for a human), 2 = misconfiguration (nothing was attempted).
#
# It NEVER commits, pushes, merges, rebases or opens anything: the workflow commits and
# pushes ONLY on exit 0, with the owner PAT, and a human still reviews the PR.
#
# Env:
#   FIX_CHECK       the deterministic check command (default: make ci-unit)
#   FIX_ROUNDS      maximum repair attempts (default: 5)
#   FIX_AGENT_CMD   how to run the agent; the prompt is fed on STDIN (default: hermes)
#   The leg preloads the project skills `pr-fix` and `bot-unattended`
#                   (.hermes/skills/<name>/SKILL.md); FIX_AGENT_CMD replaces the whole call.
#   FIX_RULES       the skill file whose presence is required, so a checkout without the
#                   contract fails loudly before a round is spent (default:
#                   .hermes/skills/pr-fix/SKILL.md; its content is PRELOADED, never inlined)
#   FIX_REPORT      the command's captured output (default: /tmp/fix-report.txt)
#   FIX_PROMPT      the assembled prompt (default: /tmp/fix-prompt.txt)
#   FIX_TAIL_LINES  how much of the report to hand the agent (default: 400)
set -uo pipefail

ROUNDS="${FIX_ROUNDS:-5}"
CHECK="${FIX_CHECK:-make ci-unit}"
# The prompt arrives on STDIN, so the default reads it into the one-shot `-z` flag and names
# the image's custom-provider alias (`-m` is the MODEL flag; `--provider nous` cannot work with
# a secret, see scripts/install_hermes_ci.sh).
AGENT_CMD="${FIX_AGENT_CMD:-hermes -z \"\$(cat)\" -s pr-fix,bot-unattended -m ${FIX_AGENT_ALIAS:-nous-deepseek} --reasoning ${FIX_AGENT_REASONING:-medium} --yolo}"
RULES="${FIX_RULES:-.hermes/skills/pr-fix/SKILL.md}"
REPORT="${FIX_REPORT:-/tmp/fix-report.txt}"
# A captured failure log from the RUN that failed (a `workflow_run` trigger, issue #538): the local
# check may not be able to reproduce that failure at all (a macOS-only job, a GPU-only image test), so
# when one is supplied the loop repairs from it and pushes the attempt WITHOUT claiming it is green —
# CI re-runs and re-triggers the bot, up to ROUNDS attempts.
REPORT_FILE="${FIX_REPORT_FILE:-}"
PROMPT="${FIX_PROMPT:-/tmp/fix-prompt.txt}"
TAIL_LINES="${FIX_TAIL_LINES:-400}"

case "$ROUNDS" in ''|*[!0-9]*) echo "[fix-loop] FIX_ROUNDS must be a positive integer, got '$ROUNDS'" >&2; exit 2 ;; esac
[ "$ROUNDS" -ge 1 ] || { echo "[fix-loop] FIX_ROUNDS must be >= 1" >&2; exit 2; }
[ -f "$RULES" ] || { echo "[fix-loop] contract file '$RULES' (the preloaded skill) not found (run from the repo root)" >&2; exit 2; }
command -v "${AGENT_CMD%% *}" >/dev/null 2>&1 || { echo "[fix-loop] agent command '$AGENT_CMD' not found on PATH" >&2; exit 2; }

echo "[fix-loop] check: $CHECK (up to $ROUNDS repair attempt(s), agent: $AGENT_CMD)"

UNVERIFIED=0
if [ -n "$REPORT_FILE" ] && [ -s "$REPORT_FILE" ]; then
  cp "$REPORT_FILE" "$REPORT"
  UNVERIFIED=1
  echo "[fix-loop] repairing from the run's captured failure log ($REPORT_FILE); this runner cannot verify that failure"
fi

run_check() {
  # shellcheck disable=SC2086  # the check is intentionally a command line
  bash -o pipefail -c "$CHECK" >"$REPORT" 2>&1
}

build_prompt() {
  {
    # The contract is a Hermes project skill the leg preloads with `-s`; inlining it again would
    # be the second copy this change removed (issue #577). The prompt carries the run, not the rules.
    echo "Follow the preloaded skills pr-fix and bot-unattended (their contract: ${RULES}). Repair the failing check below."
    echo
    echo "## The failing check"
    echo
    echo '```'
    tail -n "$TAIL_LINES" "$REPORT"
    echo '```'
    echo
    echo "The command was: \`$CHECK\` (exit code shown above). Fix the cause and stop."
  } >"$PROMPT"
}

run_agent() {
  echo "[fix-loop] round $1/$ROUNDS: asking the agent to repair" >&2
  # The prompt is the agent's STDIN: the default `hermes` reads it, and a wrapper that
  # needs a flag can be set through FIX_AGENT_CMD (e.g. "hermes run --prompt-file /dev/stdin").
  bash -o pipefail -c "$AGENT_CMD" <"$PROMPT"
}

for ((round = 1; round <= ROUNDS + 1; round++)); do
  # A failure captured from the RUN cannot be reproduced here (a macOS-only job, a GPU-only image
  # test), so one agent attempt is made from that log and pushed for CI to verify — the attempt
  # counter in the PR's `fix(bot):` commits is what bounds the loop across runs (issue #538).
  if [ "$UNVERIFIED" -eq 1 ]; then
    if [ "$round" -gt "$ROUNDS" ]; then break; fi
    build_prompt
    if run_agent "$round"; then
      echo "[fix-loop] UNVERIFIED: attempt $round/$ROUNDS was prepared from the run's log; CI re-runs to verify"
      exit 0
    fi
    echo "[fix-loop] the agent exited non-zero on attempt $round" >&2
    break
  fi
  if run_check; then
    if [ "$round" -eq 1 ]; then
      echo "[fix-loop] GREEN on the first check — nothing to repair"
    else
      echo "[fix-loop] GREEN after $((round - 1)) repair attempt(s)"
    fi
    exit 0
  fi
  if [ "$round" -gt "$ROUNDS" ]; then
    break
  fi
  echo "[fix-loop] RED (round $round of $ROUNDS) — see $REPORT" >&2
  build_prompt
  if ! run_agent "$round"; then
    echo "[fix-loop] the agent exited non-zero; re-checking anyway" >&2
  fi
done

echo "[fix-loop] still RED after $ROUNDS repair attempt(s) — leaving the PR for a human"
echo "[fix-loop] last output:" >&2
tail -n 40 "$REPORT" >&2
exit 1
