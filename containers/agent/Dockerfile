# The llgenie agent image (issues #238, #222, #248): the Hermes CLI plus the tooling the
# bot workflows need, so an agent job runs in a pinned container instead of whatever the
# runner happens to have installed.
#
#   FROM the repo's own published test image: python + pytest + gguf/numpy + the repo's
#   test toolchain, published by CI to ghcr.io/asimov-agent/llgenie/test. That keeps the
#   agent's view of the repo identical to the gates it has to pass.
#
#   ADDED: git, gh, curl, ca-certificates and the docker CLI — the bots commit and push
#   with the owner PAT, comment on PRs/issues, and (for the fix loop) drive the same
#   containerised gates the CI runs.
#
#   ADDED: the Hermes CLI, installed at build time through scripts/install_hermes_ci.sh
#   (already-installed → HERMES_INSTALL_URL → `uv tool install`), which fails the BUILD
#   loudly if it cannot install — an agent image without an agent is worse than none.
#   Build-time args let the maintainer pin the source without editing this file:
#     --build-arg HERMES_INSTALL_URL=... --build-arg HERMES_PACKAGE=...
#
# ADDED: the Nous model CHAIN (issue #2929; single-pin history issue #405). The chain is
# declared ONCE in the repo — agents/hermes-base-config.yaml: Nous FREE models first
# (nous-longcat primary, the other free models as the ordered fallbacks), and the paid
# deepseek/deepseek-v4-flash-0731 LAST. There are no model build args anymore: the install
# step runs scripts/apply_hermes_base_config.py, the only writer of the owned keys
# (model.default / model.aliases / fallback_providers), into the global Hermes home, and
# scripts/provision_agent_profiles.py lands the identical chain in every lane profile's
# config.yaml. Every chain entry is a CUSTOM-provider alias (Hermes's bundled `nous` provider
# is OAuth-only — a bare NOUS_API_KEY is IGNORED and `--provider nous` fails), pointed at the
# Nous inference endpoint with key_env NOUS_API_KEY supplied at run time. No bot call carries
# `-m <model>` any more: bots run as their lane profile (`hermes -p llgenie-<lane>`) and load
# the chain from their own config. scripts/agent_model_pin.py (`make check-agent-model`)
# referees the chain, the budgets, and that no `-m` bot call survived in the tree.
#
# ADDED: the Nerve plugin and its settings, installed at build time by
# scripts/install_nerve_ci.sh (issue #238). The host runs Hermes with Nerve enabled — its JEV
# provider is the supervisory layer (DoD checks, nervous challenges, completion auditing, JEV
# telemetry) — and a container that only installed the CLI would run a bot UNSupervised. The
# pin is an immutable 40-char SHA (a tag would make this image's hash tag lie):
#     --build-arg HERMES_NERVE_PLUGIN=keeltrace/hermes-nerve
#     --build-arg HERMES_NERVE_REF=<40-char sha>          (default: the v0.3.1 release commit)
#     --build-arg HERMES_NERVE_GATE_MODE=advisory|off|enforce  (default: advisory, the host's mode)
#     --build-arg HERMES_NERVE_PROFILE=operator|lean|marie_kondo|fat_cat  (default: operator, the host's)
#     --build-arg HERMES_NERVE_WORK_SUPERVISION_MODE=shadow|advisory|enforce  (default: shadow — the
#                    operator profile does not register the work_supervision module)
#
# The PROFILE and the SETTINGS are one decision, not two (issue #611): a named profile takes its module set
# verbatim from the plugin's PROFILES table, so a setting written for a module the profile does not enable
# is configured on paper and off in the run — `context_engine_mode: apply` under `lean` (which has no
# `context_governor`) and `gate_mode: advisory` under `lean` (no `action_gate`) were exactly that. The build
# runs scripts/nerve_profile_check.py against the installed plugin's table and FAILS on a mismatch.
#
# Secrets are NEVER baked: the KEY itself (NOUS_API_KEY), GH_TOKEN, HF_TOKEN and the JEV
# provider key (TYPESAFE_API_KEY) arrive at run time (`docker run -e ...`, or `container:` +
# the job's env), exactly as #238 requires. The image only knows the NAME of the env var to
# read (key_env=NOUS_API_KEY; the plugin reads TYPESAFE_API_KEY from the secret scope).
# scripts/install_nerve_ci.sh REFUSES a build that has a provider key in its environment, and
# scripts/agent_jev_preflight.sh (run at the start of every bot run) reports whether the
# decision layer is available; it never blocks a run, because the bots are autonomous.
# The repo's test image is hash-tagged on GHCR, and EVERY wired build path (ci_images.py
# ensure/_build_local/_buildx_push, via `make agent-image` and every CI leg) passes the exact
# resolved hash tag through --build-arg. There is deliberately NO default here: a bare
# `docker build -f containers/agent/Dockerfile` must fail loudly instead of silently basing the
# agent on the mutable `:latest` alias (trivy ':latest tag used', the last dockerfile misconfig
# on main; issue #2617).
ARG TEST_IMAGE
FROM ${TEST_IMAGE}

# The official installer (docs: hermes-agent.nousresearch.com/install.sh); overridable so a
# maintainer can pin a version without editing this file.
ARG HERMES_INSTALL_URL="https://hermes-agent.nousresearch.com/install.sh"
ARG HERMES_PACKAGE="hermes-agent"
# The Hermes release this image installs, NAMED by the tree (issue #2932). install.sh's
# default `stable` channel floats ("whatever the latest published release is at build
# time"), so two builds of the same llgenie commit could ship different Hermeses and both
# go green. HERMES_INSTALL_COMMIT pins install.sh (--commit) to the peeled commit of the
# upstream annotated tag v0.23.2 (tag object 28f57ed8e3dba4eceb67dfd3e3abda1a7604452d);
# HERMES_VERSION is what the install step must read back from `hermes --version`. PyPI
# cannot deliver this release line (hermes-agent tops out at 0.19.0 there), which is why
# the pin travels through install.sh --commit and not through `uv tool install`
# (HERMES_PACKAGE below stays the documented no-network fallback path).
ARG HERMES_VERSION="0.23.2"
ARG HERMES_INSTALL_COMMIT="ae2a81ccc00e9b7c06301523e5bb09608397149c"   # peeled commit of v0.23.2
# Hermes install args forwarded to upstream install.sh via `bash -s --` (issue #2836):
# the published image ships NEITHER the agent-browser/Playwright toolchain NOR the
# computer-use stack — no llgenie lane uses them, and the Chromium they pull in is a
# 1878-advisory stream the repo can neither fix nor audit. Re-add them with
# --build-arg HERMES_INSTALL_ARGS="". A full override must re-add the --commit pin:
# scripts/agent_model_pin.py (make check-agent-model) refuses an ARGS list that does not
# pass ${HERMES_INSTALL_COMMIT} to install.sh (issue #2932).
ARG HERMES_INSTALL_ARGS="--skip-browser --skip-computer-use --commit ${HERMES_INSTALL_COMMIT}"
# The fetched installer's CONTENT is a pinned input too (issue #2958): the --commit pin
# selects WHICH Hermes install.sh installs, but the script itself arrives over an
# unversioned URL and whoever answers that URL chooses the bytes every build executes.
# scripts/install_hermes_ci.sh verifies the downloaded script against this sha256 before
# running it and fails the build on mismatch. When the upstream installer legitimately
# changes, re-measure with `curl -fsSL <url> | sha256sum` and bump this ARG in the same
# commit — the Dockerfile is a hash input, so the image tag moves with the pin.
ARG HERMES_INSTALL_SCRIPT_SHA="c73dad4dcf7c9ecadb98578e28cc763d23d7be3fa1b513545319038795493214"
# The Nerve plugin pin and the provider it supervises through (see the header, issue #238).
ARG HERMES_NERVE_PLUGIN="keeltrace/hermes-nerve"
ARG HERMES_NERVE_REF="3de7d94982b7a2cb87c829e4b2366ced927d8fed"   # keeltrace/hermes-nerve v0.3.1
ARG HERMES_NERVE_PROFILE="operator"
ARG HERMES_NERVE_PROVIDER="typesafe"
# `shadow` is the default because the `operator` profile does not register `work_supervision`: a
# non-shadow mode would ask a module that is off to do something, which the build's parity check rejects.
# Override to `advisory`/`enforce` only with a profile that enables it (lean, marie_kondo).
ARG HERMES_NERVE_WORK_SUPERVISION_MODE="shadow"

USER root

# The runtime home is created up front and the hermes install chain writes DIRECTLY into it:
# a post-install relocation of a /root-rooted tree is not viable — the installed launcher +
# venv embed the absolute home in 700+ paths (issue #1576). Point HOME/HERMES_HOME/PATH at
# this non-root home now so everything lands where the runtime user (agent) owns it.
RUN useradd -r -m -d /home/agent -s /bin/bash agent \
    && mkdir -p /home/agent/.local/bin /home/agent/.hermes
ENV HOME=/home/agent HERMES_HOME=/home/agent/.hermes

# git/gh: the bots commit, push (owner PAT) and comment. curl/ca-certificates: install and
# API calls. docker CLI: the loop runs the repo's own containerised gates (llgenie/test).
RUN set -eux; \
    apt-get update; \
    # Upgrade the debs INHERITED from the base image: the base's package set is
    # frozen at the base image's build date, and without this line the published
    # image keeps serving them even after Debian pushes fixes (apt 3.0.3,
    # libapt-pkg7.0, zlib1g, tar carried HIGH advisories; issue #2836).
    apt-get upgrade -y; \
    apt-get install -y --no-install-recommends \
        git curl ca-certificates gnupg jq docker.io; \
    rm -rf /var/lib/apt/lists/*; \
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        -o /usr/share/keyrings/githubcli-archive-keyring.gpg; \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list; \
    apt-get update; apt-get install -y --no-install-recommends gh; \
    rm -rf /var/lib/apt/lists/*

# The CI build context is FLAT for the install scripts and Dockerfile (ci_images.context copies
# each input file to the context root), so the COPY path is the file's name, not its repo path.
# The ONE exception is the agents/ tree: it is copied in under agents/ (subdirs preserved) so the
# lane COPY below can reference it by its repo path — a flat copy would collide every profile's
# SOUL.md onto the same basename.
COPY install_hermes_ci.sh /usr/local/bin/install_hermes_ci.sh
COPY apply_hermes_base_config.py /usr/local/bin/apply_hermes_base_config.py
COPY apply_hermes_base_config.py /opt/llgenie/bin/apply_hermes_base_config.py
COPY hermes_skills_register.py /usr/local/bin/hermes_skills_register.py
COPY install_nerve_ci.sh /usr/local/bin/install_nerve_ci.sh
COPY nerve_profile_check.py /usr/local/bin/nerve_profile_check.py
COPY agent_jev_preflight.sh /usr/local/bin/agent_jev_preflight.sh
COPY agent_lanes_check.py /usr/local/bin/agent_lanes_check.py
# The ONE lane installer (issue #2669): the same multi-lane seam the host runs via
# `make provision-agent-profiles` is installed here beside the two modules it imports (it
# sys.path.inserts its own directory), so the image CANNOT install lanes through a different code
# path than the host. The old inline `cp -r` loop is gone: this seam writes, then reads every file
# back byte-for-byte against the tree.
COPY provision_agent_profiles.py /opt/llgenie/bin/provision_agent_profiles.py
COPY agent_profile_sync.py /opt/llgenie/bin/agent_profile_sync.py
COPY check_agent_profiles.py /opt/llgenie/bin/check_agent_profiles.py
# check_agent_profiles.py pulls frontmatter() from check_agent_skills.py at import time
# (scripts/check_agent_profiles.py:74); without this COPY the provisioning step below
# dies with ModuleNotFoundError at build (the latent main breakage caught in issue #2836).
COPY check_agent_skills.py /opt/llgenie/bin/check_agent_skills.py
# The fleet's lane profiles (issue #2181). Before this image held NONE: no agents/ reference, no
# profile, so a bot job asking for a named lane resolved against an empty profile home. This tree
# (agents/manifest.json + one <name>/ per lane) is what the lane-install step below installs, and
# scripts/agent_lanes_check.py is the build-time gate that REFUSES the image if any manifest lane
# did not land.
COPY agents /opt/llgenie/agents
ENV HERMES_INSTALL_URL=${HERMES_INSTALL_URL} HERMES_PACKAGE=${HERMES_PACKAGE} \
    HERMES_INSTALL_ARGS=${HERMES_INSTALL_ARGS} \
    HERMES_INSTALL_SCRIPT_SHA=${HERMES_INSTALL_SCRIPT_SHA} \
    HERMES_VERSION=${HERMES_VERSION} \
    HERMES_NERVE_PLUGIN=${HERMES_NERVE_PLUGIN} HERMES_NERVE_REF=${HERMES_NERVE_REF} \
    HERMES_NERVE_PROVIDER=${HERMES_NERVE_PROVIDER} \
    HERMES_NERVE_PROFILE=${HERMES_NERVE_PROFILE} \
    HERMES_NERVE_WORK_SUPERVISION_MODE=${HERMES_NERVE_WORK_SUPERVISION_MODE}
# `install.sh` puts the CLI in ~/.local/bin and its tree in ~/.hermes; make both stick for
# the runtime user too (a `container:` job does not source a login shell).
ENV PATH="/home/agent/.local/bin:${PATH}"
RUN chmod +x /usr/local/bin/install_hermes_ci.sh \
    && /usr/local/bin/install_hermes_ci.sh \
    && export PATH="/home/agent/.local/bin:$PATH" \
    && hermes --version \
    # The install script applied the chain from its ONE home; the build re-checks this home
    # against the repo's base config so a wrong, missing, or mis-ordered chain fails HERE,
    # not inside a bot run (issue #2929).
    && python3 /usr/local/bin/apply_hermes_base_config.py --check --home /home/agent/.hermes \
        --root /opt/llgenie \
    && echo "[agent-image] chain OK: $(hermes config get model.default) primary, ordered fallbacks + budgets read back identical to agents/hermes-base-config.yaml"

# The supervisory layer (issue #238). HERMES_HOME is explicit because the plugin, its settings
# and the run-time gate must all agree on which home is "this" home — plugins are per-home, and
# a `container:` job never sources a login shell. The install script writes the pinned bundle
# into ${HERMES_HOME}/plugins/nerve, the host's settings under plugins.entries.nerve.settings,
# and fails the BUILD if either did not land. HERMES_HOME is already /home/agent/.hermes (set
# above); the nerve install writes directly into the runtime user's home.
RUN chmod +x /usr/local/bin/install_nerve_ci.sh /usr/local/bin/agent_jev_preflight.sh \
    && /usr/local/bin/install_nerve_ci.sh \
    # Prove the layer is really there and really secret-free, at build time: an image that
    # claims supervision but has no plugin (or has a baked key) is the failure #238 names.
    && hermes plugins list | grep -q 'nerve' \
    && test -f "${HERMES_HOME}/plugins/nerve/plugin.yaml" \
    && test -x /usr/local/bin/agent_jev_preflight.sh \
    && ! env | grep -qE '^(TYPESAFE|OPENROUTER|OPENCODE)_API_KEY=' \
    && echo "[agent-image] JEV layer installed; provider key arrives at run time (scripts/agent_jev_preflight.sh wires it in)"

# The llgenie lane profiles (issue #2181, installer unified by issue #2669). This is the step the
# issues are about: before #2181 the image carried NO lane — the Hermes CLI was installed but a bot
# job asking for a named profile resolved against an empty profile home; and until #2669 this step
# installed the lanes with its own inline `cp -r` loop, a second code path the host's seam
# (scripts/provision_agent_profiles.py) never shared, with a gate that only checked SOUL.md.
# Now the step IS that seam: it writes every lane declared by agents/manifest.json into
# ${HERMES_HOME}/profiles/<name>/, reads every tree file back byte-for-byte, and --resolve proves
# each lane's skills resolve through `hermes -p <lane> skills list --source local`. Then
# scripts/agent_lanes_check.py re-reads that same manifest against the installed profiles,
# reconciles the skills subtree file by file, and FAILS THE BUILD when a declared lane or any of
# its skill files did not land — a container that would run a lane with no rulebook, or with a
# rulebook whose skillbooks cannot load, is the failure mode the issues name, visible at build
# time, not inside a bot run.
RUN set -eux; \
    python3 /opt/llgenie/bin/provision_agent_profiles.py \
        --root /opt/llgenie \
        --dest "${HERMES_HOME}/profiles" \
        --resolve \
    && python3 /usr/local/bin/agent_lanes_check.py \
        --agents /opt/llgenie/agents \
        --profiles "${HERMES_HOME}/profiles" \
    && echo "[agent-image] llgenie lanes installed into ${HERMES_HOME}/profiles through the host's own seam (provision_agent_profiles.py --resolve) and agent_lanes_check.py passed"

# Profile-scoped secrets (issue #2929, measured against Hermes 0.23.2): a profile run resolves
# `model.key_env` from the PROFILE's OWN .env file — a key that only sits in the leg's exported
# environment authenticates nothing. This hook is sourced at the start of every agent leg (the
# Makefile agent legs all boot `bash -lc`, and /etc/profile sources /etc/profile.d/*.sh) and moves
# the leg's NOUS_API_KEY into every llgenie profile home's .env through the SAME script the host
# runs (`make seed-hermes-profile-env`). The image knows only the variable's NAME — the value is
# supplied per-leg by require_env'd legs (AGENTS.md: no secrets baked). The marker export is the
# build-time proof below that a login shell really sources the hook.
COPY seed_profile_hermes_env.py /usr/local/bin/seed_profile_hermes_env.py
RUN chmod +x /usr/local/bin/seed_profile_hermes_env.py \
    && printf '#!/bin/sh\n# llgenie: seed profile-scoped Hermes secrets from the leg environment (issue #2929)\nif [ -n "${NOUS_API_KEY:-}" ]; then\n    python3 /usr/local/bin/seed_profile_hermes_env.py --all >/dev/null 2>&1 || true\nfi\nexport LLGENIE_HERMES_PROFILE_ENV=sourced\n' > /etc/profile.d/llgenie-hermes-profile-env.sh \
    && chmod 0644 /etc/profile.d/llgenie-hermes-profile-env.sh \
    && bash -lc 'test "${LLGENIE_HERMES_PROFILE_ENV:-}" = sourced' \
    && echo "[agent-image] profile-env hook installed: every bash -lc leg seeds profile .env from its own environment"

# The repo is checked out by the workflow (the agent edits the working tree); this is only
# the default working dir, and `git config` is left to the workflow so the bot's identity
# is visible in the commits it makes.
WORKDIR /repo

# Least-privilege runtime epilogue (issue #1576): the install chain above ran as root, but it
# wrote everything into the agent user's home (/home/agent); hand that home to the runtime user
# and drop to it for the whole post-CMD surface (git/gh/hermes), so the container no longer runs
# privileged and the CMD liveness (`hermes plugins list`) still works.
RUN chown -R agent:agent /home/agent \
    && chown -R agent:agent /home/agent/.local /home/agent/.hermes 2>/dev/null || true
USER agent

# Same entry shape as the test image: a command, not a daemon.
CMD ["bash", "-lc", "git --version && gh --version && hermes --version && hermes plugins list | grep -q nerve && echo 'nerve: enabled'"]
