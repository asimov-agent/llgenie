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
    # HERMES_INSTALL_ARGS is word-split on purpose: it is a flag list for install.sh,
    # not one quoted string. The agent Dockerfile defaults it to
    # `--skip-browser --skip-computer-use --commit ${HERMES_INSTALL_COMMIT}` (issues
    # #2836, #2932) — the --commit is what makes the installed Hermes a named release.
    curl -fsSL "$HERMES_INSTALL_URL" | bash -s -- ${HERMES_INSTALL_ARGS:-}
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

# The Hermes release the image must run (issue #2932). install.sh's `stable` channel floats,
# so the Dockerfile pins it with --commit <peeled v0.23.2> and names HERMES_VERSION; this is
# the read-back. Whichever install path ran, `hermes --version` must agree with the pin —
# the first version token only, so a drift suffix (`0.23.1+6066`, a checkout that is not the
# pinned tag) is a failure too. A build that installed a different Hermes fails HERE, not a
# bot run ninety minutes later. Same discipline as the skills-dir registration below.
HERMES_VERSION="${HERMES_VERSION:-0.23.2}"
hermes_reported="$(hermes --version 2>/dev/null | head -1 || true)"
hermes_got="$(printf '%s\n' "$hermes_reported" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)"
if [ "$hermes_got" != "$HERMES_VERSION" ]; then
  echo "[hermes-ci] installed Hermes is '${hermes_got:-<unreadable>}' (reported: ${hermes_reported:-nothing}), expected ${HERMES_VERSION}: the install drifted from the pinned release" >&2
  exit 1
fi
echo "[hermes-ci] hermes ${hermes_got} == pinned release ${HERMES_VERSION}"

# The model chain, installed from its ONE home (issue #2929; referee issue #405).
# `agents/hermes-base-config.yaml` declares the chain — Nous FREE models first
# (`nous-longcat` primary), the other free models as the ordered fallbacks,
# `deepseek/deepseek-v4-flash-0731` LAST — and scripts/apply_hermes_base_config.py is the only
# writer of its owned keys (model.default, model.aliases, fallback_providers). The single-alias
# MODEL_ID/ALIAS build ARGs are gone: this home gets the chain, and scripts/provision_agent_profiles.py
# gives every lane profile the identical chain. Bots carry no `-m` flag; they run as their lane
# profile and load the chain from its config.yaml. The write is followed by a read-back --check:
# a chain that did not land fails the BUILD, not a bot run ninety minutes later.
HERMES_HOME_RESOLVED="${HERMES_HOME:-$HOME/.hermes}"
HERMES_CHAIN_ROOT="${HERMES_CHAIN_ROOT:-/opt/llgenie}"
if [ ! -f "${HERMES_CHAIN_ROOT}/agents/hermes-base-config.yaml" ]; then
  HERMES_CHAIN_ROOT="$(cd "$(dirname "$0")/.." && pwd)"   # a repo checkout running this script (tests, host dry-runs)
fi
APPLY_SEAM="/usr/local/bin/apply_hermes_base_config.py"   # the image path the Dockerfile COPYs
[ -f "$APPLY_SEAM" ] || APPLY_SEAM="$(dirname "$0")/apply_hermes_base_config.py"   # a repo checkout
python3 "$APPLY_SEAM" --home "$HERMES_HOME_RESOLVED" --root "$HERMES_CHAIN_ROOT"
python3 "$APPLY_SEAM" --check --home "$HERMES_HOME_RESOLVED" --root "$HERMES_CHAIN_ROOT"

# The bots' contracts are Hermes PROJECT skills: `.hermes/skills/<name>/SKILL.md` in the checkout,
# preloaded by each leg with `hermes -s <name>` (issue #577). Hermes reads skills from its own home
# and from `skills.external_dirs`, so the checkout's directory is registered here, once, at build
# time — every bot leg mounts the checkout at `/repo`, so that is the path registered.
# The registration is written as a real YAML LIST (`scripts/hermes_skills_register.py`), because
# `hermes config set` takes a list on a newer CLI and silently stores a string on the pinned
# `hermes-agent==0.19.0` — a string that resolves to no directory at all. The read-back makes a
# registration that did not land fail the BUILD instead of a bot run ninety minutes later.
HERMES_SKILLS_DIR="${HERMES_SKILLS_DIR:-/repo/.hermes/skills}"
HERMES_SKILLS_HOME="${HERMES_HOME:-$HOME/.hermes}"
python3 /usr/local/bin/hermes_skills_register.py --home "$HERMES_SKILLS_HOME" --dir "$HERMES_SKILLS_DIR"
python3 /usr/local/bin/hermes_skills_register.py --home "$HERMES_SKILLS_HOME" --dir "$HERMES_SKILLS_DIR" --check
