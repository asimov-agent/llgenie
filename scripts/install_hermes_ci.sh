#!/usr/bin/env bash
# Install the Hermes CLI for the bots, and wire the Nous token in the only way that works
# (issues #222/#238/#248).
#
# CI images change; rather than baking one install method in, this tries, in order:
#   1. an already-installed `hermes` on PATH,
#   2. HERMES_INSTALL_URL (an official install script, if the runner has network),
#   3. `uv tool install $HERMES_PACKAGE` (uv is this repo's Python tool runner).
# Anything else is a LOUD failure: a bot that silently runs without an agent would report
# "still red" forever and hide the real problem.
#
# WHY the alias: Hermes's bundled `nous` provider uses OAuth device-code auth, so a bare
# NOUS_API_KEY in the environment is IGNORED and `--provider nous` fails with "not logged into
# Nous Portal". Even `hermes auth add nous --type api-key` does not satisfy its OAuth state
# check. The supported headless path is a CUSTOM provider alias pointed at the Nous
# OpenAI-compatible endpoint with key_env=NOUS_API_KEY, which is what this script writes.
set -euo pipefail

if command -v hermes >/dev/null 2>&1; then
  echo "[hermes-ci] already installed: $(command -v hermes)"
else
  if [ -n "${HERMES_INSTALL_URL:-}" ]; then
    echo "[hermes-ci] installing from HERMES_INSTALL_URL"
    curl -fsSL "$HERMES_INSTALL_URL" | bash
  elif command -v uv >/dev/null 2>&1; then
    echo "[hermes-ci] installing with uv (HERMES_PACKAGE=${HERMES_PACKAGE:-hermes-agent})"
    uv tool install --quiet "${HERMES_PACKAGE:-hermes-agent}"
  else
    echo "[hermes-ci] no uv and no HERMES_INSTALL_URL: cannot install the Hermes CLI" >&2
    echo "[hermes-ci] set HERMES_INSTALL_URL (or install hermes earlier in the job)" >&2
    exit 1
  fi
fi

command -v hermes >/dev/null 2>&1 || { echo "[hermes-ci] hermes is still not on PATH after install" >&2; exit 1; }
echo "[hermes-ci] installed: $(command -v hermes)"

# The alias the bots call by name. Every value is a documented default and every one is
# overridable, because the model id is a pin that moves — but a pin that moves must move in
# every file at once, which is why `make check-agent-model` compares this default with the
# Dockerfile's (scripts/agent_model_pin.py, issue #405).
ALIAS="${HERMES_ALIAS:-nous-deepseek}"
MODEL_ID="${HERMES_MODEL_ID:-deepseek/deepseek-v4.1-flash-1017}"   # provider-prefixed; `-1017` is the SNAPSHOT (2026-10-17) — the unsuffixed id is the older, different model
BASE_URL="${HERMES_BASE_URL:-https://inference-api.nousresearch.com/v1}"
# The snapshot's published budget (context_length 1048576, max_completion_tokens 943718). Written
# literally on purpose: these belong to the MODEL, not to a deployment choice, and leaving them
# unset makes Hermes budget the run from models.dev, which has no entry for this snapshot id.
MAX_TOKENS="${HERMES_MAX_TOKENS:-16000}"
CONTEXT_WINDOW="${HERMES_CONTEXT_WINDOW:-1048576}"

hermes config set "model.aliases.${ALIAS}.model" "$MODEL_ID"
hermes config set "model.aliases.${ALIAS}.provider" custom
hermes config set "model.aliases.${ALIAS}.base_url" "$BASE_URL"
hermes config set "model.aliases.${ALIAS}.key_env" NOUS_API_KEY
hermes config set "model.aliases.${ALIAS}.max_tokens" "16000"
hermes config set "model.aliases.${ALIAS}.context_window" "1048576"

# Loud if the alias did not land: a bot whose alias is missing fails at run time, far from here.
# All three values are checked — a present alias with the wrong model, or with no budget, is the
# half-written state this exists to catch.
for kv in "model=${MODEL_ID}" "key_env=NOUS_API_KEY" "max_tokens=${MAX_TOKENS}" \
          "context_window=${CONTEXT_WINDOW}"; do
  key="${kv%%=*}"; want="${kv#*=}"
  got="$(hermes config get "model.aliases.${ALIAS}.${key}" 2>/dev/null || true)"
  if [ "$got" != "$want" ]; then
    echo "[hermes-ci] alias ${ALIAS}.${key} is '${got}', expected '${want}': the bots would fail at run time" >&2
    exit 1
  fi
done
echo "[hermes-ci] alias ${ALIAS} -> ${MODEL_ID} via ${BASE_URL} (max_tokens=${MAX_TOKENS}, context_window=${CONTEXT_WINDOW}, key_env=NOUS_API_KEY)"
