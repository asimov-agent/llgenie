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
#   FIX_ROUNDS      maximum repair attempts (default: 3)
#   FIX_AGENT_CMD   how to run the agent; the prompt is fed on STDIN (default: hermes)
#   FIX_RULES       the rules file handed to the agent (default: scripts/fix_bot_rules.md)
#   FIX_REPORT      the command's captured output (default: /tmp/fix-report.txt)
#   FIX_PROMPT      the assembled prompt (default: /tmp/fix-prompt.txt)
#   FIX_TAIL_LINES  how much of the report to hand the agent (default: 400)
set -uo pipefail

ROUNDS="${FIX_ROUNDS:-3}"
CHECK="${FIX_CHECK:-make ci-unit}"
# The prompt arrives on STDIN, so the default reads it into the one-shot `-z` flag and names
# the image's custom-provider alias (`-m` is the MODEL flag; `--provider nous` cannot work with
# a secret, see scripts/install_hermes_ci.sh).
AGENT_CMD="${FIX_AGENT_CMD:-hermes -z \"\$(cat)\" -m ${FIX_AGENT_ALIAS:-nous-deepseek} --reasoning ${FIX_AGENT_REASONING:-medium} --yolo}"
RULES="${FIX_RULES:-scripts/fix_bot_rules.md}"
REPORT="${FIX_REPORT:-/tmp/fix-report.txt}"
PROMPT="${FIX_PROMPT:-/tmp/fix-prompt.txt}"
TAIL_LINES="${FIX_TAIL_LINES:-400}"

case "$ROUNDS" in ''|*[!0-9]*) echo "[fix-loop] FIX_ROUNDS must be a positive integer, got '$ROUNDS'" >&2; exit 2 ;; esac
[ "$ROUNDS" -ge 1 ] || { echo "[fix-loop] FIX_ROUNDS must be >= 1" >&2; exit 2; }
[ -f "$RULES" ] || { echo "[fix-loop] rules file '$RULES' not found (run from the repo root)" >&2; exit 2; }
command -v "${AGENT_CMD%% *}" >/dev/null 2>&1 || { echo "[fix-loop] agent command '$AGENT_CMD' not found on PATH" >&2; exit 2; }

echo "[fix-loop] check: $CHECK (up to $ROUNDS repair attempt(s), agent: $AGENT_CMD)"

run_check() {
  # shellcheck disable=SC2086  # the check is intentionally a command line
  bash -o pipefail -c "$CHECK" >"$REPORT" 2>&1
}

build_prompt() {
  {
    cat "$RULES"
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
