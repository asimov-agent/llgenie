#!/usr/bin/env bash
# JEV preflight for the bots' agent container (issue #238). Run it INSIDE the agent image
# before the bot spends model time: it reports whether the JEV decision layer is available
# for THIS run, and puts the provider key where the plugin looks for it.
#
# WHAT THIS IS FOR. The JEV layer is not a gate on the bots and not a substitute for the
# review a PR gets. It is an integration that makes an autonomous run cheaper and more
# correct: the decision layer answers the "is this the right next step" question before the
# model spends a call on it, and the context curation sends the model the part of the repo
# that matters instead of everything. The measurable effect is FEWER LLM CALLS and FEWER
# MISTAKES that would otherwise be caught later, by the reviewer or by CI.
#
# THE RULE THIS FILE EXISTS TO HONOUR: the bots are autonomous. Nothing here may stop a run.
# A missing key, a plugin that is not installed, a provider that does not answer — each is
# reported LOUDLY and the run CONTINUES, because the answer to "JEV is unavailable" is a
# normal (slightly more expensive) agent run, not a stopped bot. `NERVE_REQUIRE=1` turns the
# report into a failure, and it exists for ONE purpose: a CI job that verifies the IMAGE
# carries the layer (see `make agent-jev-preflight NERVE_REQUIRE=1`). No bot workflow sets it.
#
#   TYPESAFE_API_KEY / OPENROUTER_API_KEY / OPENCODE_API_KEY  the provider key (by provider)
#   HERMES_NERVE_PROVIDER      typesafe (default) | openrouter | opencode
#   NERVE_REQUIRE=1            verify-only mode: exit non-zero when the layer is unavailable
#   NERVE_GATE_SKIP_PROVIDER=1 skip the live provider call (offline check only)
set -euo pipefail

HERMES_HOME="${HERMES_HOME:-/root/.hermes}"
export HERMES_HOME
PROVIDER="${HERMES_NERVE_PROVIDER:-}"
if [ -z "$PROVIDER" ]; then
  PROVIDER="$(hermes config get plugins.entries.nerve.settings.jev_provider 2>/dev/null || true)"
fi
PROVIDER="${PROVIDER:-typesafe}"

say()  { echo "[jev-preflight] $*"; }
warn() { echo "[jev-preflight] WARNING: $*" >&2; }

# The key value must never reach a terminal, a log or a step summary. THIS script never prints it,
# but the provider's own smoke does the printing for step 4 — so its output is filtered before it
# goes anywhere: the exact key, and anything key-shaped, come out as REDACTED. The key is passed to
# the filter through the environment (not argv, so it cannot show up in a process list).
redact() {
  _JEV_KEY="${key:-}" "${HERMES_NERVE_PYTHON:-python3}" -c '
import os, re, sys
data = sys.stdin.read()
key = os.environ.get("_JEV_KEY") or ""
if key:
    data = data.replace(key, "***REDACTED-KEY***")
sys.stdout.write(re.sub(r"(?:hf_|sk-|sk_|jev-)[A-Za-z0-9_-]{12,}", "***REDACTED-KEY-SHAPE***", data))
'
}

# A workflow run must be READABLE at a glance: the layer never blocks a run, so a silent "JEV off"
# would only exist in the log. In Actions, annotate the run (the annotation shows on the run and
# the job summary) and write the outcome to the step summary. Locally this stays plain text.
#   `::warning`  the layer is unavailable — this run makes more LLM calls than it needs to
#   `::notice`   the layer is ready — this run is JEV-assisted
annotate() {   # annotate <warning|notice> <message>
  if [ "${GITHUB_ACTIONS:-}" = "true" ]; then
    echo "::$1 title=JEV decision layer::$2"
    if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
      printf '**JEV decision layer (%s):** %s\n' "$1" "$2" >> "$GITHUB_STEP_SUMMARY"
    fi
  fi
}

#: The ONE failure mode: the caller asked to verify the image (`NERVE_REQUIRE=1`).
require() {
  if [ "${NERVE_REQUIRE:-}" = "1" ]; then
    echo "[jev-preflight] ERROR: $* (NERVE_REQUIRE=1, so this is a verification failure)" >&2
    exit 1
  fi
  warn "$*"
  warn "JEV is INACTIVE for this run: the agent still works, autonomously — expect more LLM"
  warn "calls and more mistakes for a reviewer to catch than a JEV-assisted run would make."
  annotate warning "JEV is INACTIVE for this run: $* — the agent continues, with more LLM calls and more mistakes than a JEV-assisted run."
  say "continuing without JEV (the bots never stop for this)"
  exit 0
}

case "$PROVIDER" in
  typesafe)   KEY_VAR=TYPESAFE_API_KEY ;;
  openrouter) KEY_VAR=OPENROUTER_API_KEY ;;
  opencode)   KEY_VAR=OPENCODE_API_KEY ;;
  *) require "unsupported HERMES_NERVE_PROVIDER='${PROVIDER}' (typesafe | openrouter | opencode)" ;;
esac

# 1. the plugin must be in THIS home (plugins are per-home: a copy in another profile or in
#    the repo is invisible to the Hermes that runs the bot).
if [ ! -f "${HERMES_HOME}/plugins/nerve/plugin.yaml" ]; then
  require "the nerve plugin is not installed in ${HERMES_HOME} (plugins/nerve/plugin.yaml is missing) — the agent image was not built with containers/agent/Dockerfile"
fi

# 2. the provider token. Accept the environment (how CI passes it) or an existing
#    ${HERMES_HOME}/.env entry (how the host keeps it), and put it where the plugin's secret
#    scope looks: Hermes resolves credentials per home, not from os.environ.
key="${!KEY_VAR:-}"
if [ -z "$key" ] && [ -f "${HERMES_HOME}/.env" ]; then
  key="$(sed -n "s/^${KEY_VAR}=//p" "${HERMES_HOME}/.env" | tail -n 1)"
  key="${key%\"}"; key="${key#\"}"
  key="${key%\'}"; key="${key#\'}"
  key="${key%${key##*[![:space:]]}}"  # trailing whitespace, without a subshell
fi
if [ -z "$key" ]; then
  require "${KEY_VAR} is not set, so the JEV decision layer cannot answer this run.
       - in CI: add the repo secret ${KEY_VAR} and pass it as 'docker run -e ${KEY_VAR}' (the key never enters the image)
       - locally: export ${KEY_VAR}=... (the same key the host uses)"
fi
if [ -n "${!KEY_VAR:-}" ]; then
  umask 077
  touch "${HERMES_HOME}/.env"; chmod 600 "${HERMES_HOME}/.env"
  if grep -q "^${KEY_VAR}=" "${HERMES_HOME}/.env"; then
    # Portable in-place rewrite: `sed -i` is GNU-only (BSD/macOS sed wants `-i ''`, and this job
    # runs on macOS too). Python is already a dependency of the plugin.
    python3 - "$KEY_VAR" "$key" "${HERMES_HOME}/.env" <<'PYEOF'
import pathlib, sys
var, val, path = sys.argv[1], sys.argv[2], pathlib.Path(sys.argv[3])
path.write_text("".join(f"{var}={val}\n" if line.startswith(f"{var}=") else line
                        for line in path.read_text().splitlines(keepends=True)))
PYEOF
  else
    printf '%s=%s\n' "$KEY_VAR" "$key" >> "${HERMES_HOME}/.env"
  fi
  say "provider key taken from the environment and written to ${HERMES_HOME}/.env (mode 600; the value is never printed)"
fi

# 3. the plugin must be ENABLED in this home: installed but disabled means it is on disk and
#    still doing nothing for the run. Read the machine-readable list, not the Rich table —
#    its columns depend on the terminal width.
if ! command -v hermes >/dev/null 2>&1; then
  require "no hermes on PATH"
fi
plugin_status="$(hermes plugins list --json 2>/dev/null | python3 -c '
import json, sys
try:
    rows = json.load(sys.stdin)
except Exception:
    rows = []
for row in rows if isinstance(rows, list) else []:
    if isinstance(row, dict) and row.get("name") == "nerve":
        print(row.get("status") or "unknown")
        break
')"
if [ "$plugin_status" != "enabled" ]; then
  require "nerve is '${plugin_status:-missing}' in ${HERMES_HOME}: an installed-but-disabled plugin does nothing for the run"
fi

# 4. the provider must answer for real. The plugin ships the smoke; using it means the
#    preflight exercises the same client, provider selection and payload the run will use.
#    A provider that does not answer costs the run its decision layer, not its progress.
if [ "${NERVE_GATE_SKIP_PROVIDER:-}" = "1" ]; then
  say "SKIP: NERVE_GATE_SKIP_PROVIDER=1 — provider not contacted (offline check only)"
else
  smoke="${HERMES_HOME}/plugins/nerve/scripts/live_api_smoke.py"
  if [ ! -f "$smoke" ]; then
    require "the plugin's live smoke is missing at $smoke"
  fi
  say "provider smoke: ${PROVIDER} (model $(hermes config get plugins.entries.nerve.settings.typesafe_model 2>/dev/null || echo '?'), no token echoed)"
  if ! out="$(HERMES_NERVE_PROVIDER="$PROVIDER" "${HERMES_NERVE_PYTHON:-python3}" "$smoke" 2>&1)"; then
    # The plugin redacts the key, and so do we: the smoke's own message is shown through the
    # filter, so a provider that echoes the credential cannot leak it into the run log.
    printf '%s\n' "$out" | tail -n 5 | redact >&2
    require "the ${PROVIDER} provider did not answer a live decision call"
  fi
  printf '%s\n' "$out" | grep -q '"ok": true' \
    || require "the smoke returned no decision payload"
  say "provider OK: a real decision call answered"
fi

say "JEV ready: nerve enabled in ${HERMES_HOME}, provider ${PROVIDER}, token supplied at run time only"
say "the agent runs with the decision layer available — fewer LLM calls, fewer mistakes"
annotate notice "JEV is ON for this run: nerve enabled (${HERMES_HOME}), provider ${PROVIDER} answered a real decision call."
