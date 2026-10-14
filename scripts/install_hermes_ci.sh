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
# overridable, because the model id is a pin that moves.
ALIAS="${HERMES_ALIAS:-nous-deepseek}"
MODEL_ID="${HERMES_MODEL_ID:-deepseek/deepseek-v4.1-flash}"   # provider-prefixed (the endpoint 404s a bare id)
BASE_URL="${HERMES_BASE_URL:-https://inference-api.nousresearch.com/v1}"

hermes config set "model.aliases.${ALIAS}.model" "$MODEL_ID"
hermes config set "model.aliases.${ALIAS}.provider" custom
hermes config set "model.aliases.${ALIAS}.base_url" "$BASE_URL"
hermes config set "model.aliases.${ALIAS}.key_env" NOUS_API_KEY

# Loud if the alias did not land: a bot whose alias is missing fails at run time, far from here.
if ! hermes config get "model.aliases.${ALIAS}.key_env" 2>/dev/null | grep -q NOUS_API_KEY; then
  echo "[hermes-ci] the alias ${ALIAS} was not configured: the bots would fail at run time" >&2
  exit 1
fi
echo "[hermes-ci] alias ${ALIAS} -> ${MODEL_ID} via ${BASE_URL} (key_env=NOUS_API_KEY)"
