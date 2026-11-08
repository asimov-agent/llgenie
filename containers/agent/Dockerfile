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
# ADDED: the Nous model wiring, as build args with the live defaults, so the pin is
# visible here instead of buried in the install script:
#     --build-arg HERMES_ALIAS=nous-deepseek
#     --build-arg HERMES_MODEL_ID=deepseek/deepseek-v4-flash-0731   (provider-prefixed)
#     --build-arg HERMES_BASE_URL=https://inference-api.nousresearch.com/v1
# The `-0731` suffix is the SNAPSHOT (2026-07-31) of DeepSeek V4 Flash. There is no
# `deepseek-v4.1-flash-0731` on the endpoint. The unsuffixed `deepseek/deepseek-v4-flash`
# is a DIFFERENT model (`canonical_slug …-20260423`) that also answers 200 — so dropping
# the suffix silently runs the bots on the April release (issue #405).
# The pin lives in ONE place too: scripts/agent_model_pin.py, gated by `make check-agent-model`.
# Hermes's bundled `nous` provider is OAuth-only — a bare NOUS_API_KEY is IGNORED and
# `--provider nous` fails with "not logged into Nous Portal" — so the install script writes
# a CUSTOM provider alias (provider=custom, the base_url above, key_env=NOUS_API_KEY), with the
# snapshot's published budget (max_tokens, context_window), and the build asserts every key.
# The alias is why every bot call is `hermes -z ... -m nous-deepseek`.
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
# The repo's test image is hash-tagged on GHCR; locally `make test-image` produces the
# `llgenie/test:latest` alias, and CI passes the resolved hash tag through --build-arg.
ARG TEST_IMAGE=llgenie/test:latest
FROM ${TEST_IMAGE}

# The official installer (docs: hermes-agent.nousresearch.com/install.sh); overridable so a
# maintainer can pin a version without editing this file.
ARG HERMES_INSTALL_URL="https://hermes-agent.nousresearch.com/install.sh"
ARG HERMES_PACKAGE="hermes-agent"
# The model pin and its provider alias (see the header). The model id must stay
# provider-prefixed: the Nous endpoint 404s a bare id.
ARG HERMES_ALIAS="nous-deepseek"
ARG HERMES_MODEL_ID="deepseek/deepseek-v4-flash-0731"
ARG HERMES_BASE_URL="https://inference-api.nousresearch.com/v1"
# The alias's budget: the pinned snapshot publishes context_length 1048576 and
# max_completion_tokens 65536, so this is a deliberate sub-limit pair (the same one the host's
# alias uses). Left unset, Hermes budgets the bot run from models.dev, which has no entry for this
# snapshot id (issue #405).
ARG HERMES_MAX_TOKENS="16000"
ARG HERMES_CONTEXT_WINDOW="1048576"
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
COPY hermes_skills_register.py /usr/local/bin/hermes_skills_register.py
COPY install_nerve_ci.sh /usr/local/bin/install_nerve_ci.sh
COPY nerve_profile_check.py /usr/local/bin/nerve_profile_check.py
COPY agent_jev_preflight.sh /usr/local/bin/agent_jev_preflight.sh
COPY agent_lanes_check.py /usr/local/bin/agent_lanes_check.py
# The fleet's lane profiles (issue #2181). Before this image held NONE: no agents/ reference, no
# profile, so a bot job asking for a named lane resolved against an empty profile home. This tree
# (agents/manifest.json + one <name>/ per lane) is what the lane-install step below installs, and
# scripts/agent_lanes_check.py is the build-time gate that REFUSES the image if any manifest lane
# did not land.
COPY agents /opt/llgenie/agents
ENV HERMES_INSTALL_URL=${HERMES_INSTALL_URL} HERMES_PACKAGE=${HERMES_PACKAGE} \
    HERMES_ALIAS=${HERMES_ALIAS} HERMES_MODEL_ID=${HERMES_MODEL_ID} HERMES_BASE_URL=${HERMES_BASE_URL} \
    HERMES_MAX_TOKENS=${HERMES_MAX_TOKENS} HERMES_CONTEXT_WINDOW=${HERMES_CONTEXT_WINDOW} \
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
    # The install script writes the alias; prove it right here so a bad pin fails the BUILD
    # (an image whose alias is missing or stale only fails later, inside a bot run). All four
    # keys, not just the name: an alias without its budget is budgeted from models.dev, which
    # has no entry for this snapshot id (issue #405).
    && test "$(hermes config get "model.aliases.${HERMES_ALIAS}.model")" = "${HERMES_MODEL_ID}" \
    && test "$(hermes config get "model.aliases.${HERMES_ALIAS}.provider")" = "custom" \
    && test "$(hermes config get "model.aliases.${HERMES_ALIAS}.key_env")" = "NOUS_API_KEY" \
    && test "$(hermes config get "model.aliases.${HERMES_ALIAS}.max_tokens")" = "${HERMES_MAX_TOKENS}" \
    && test "$(hermes config get "model.aliases.${HERMES_ALIAS}.context_window")" = "${HERMES_CONTEXT_WINDOW}" \
    && echo "[agent-image] alias ${HERMES_ALIAS} -> ${HERMES_MODEL_ID} (max_tokens=${HERMES_MAX_TOKENS}, context_window=${HERMES_CONTEXT_WINDOW}, key supplied at run time)"

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

# The llgenie lane profiles (issue #2181). This is the step the issue is about: before it, the
# image carried NO lane — the Hermes CLI was installed but a bot job asking for a named profile
# resolved against an empty profile home. Here each lane declared by agents/manifest.json is
# copied into ${HERMES_HOME}/profiles/<name>/ (its SOUL.md + skills), mirroring how the host's
# `make sync-agent-profile` populates ~/.hermes/profiles/<name>. Then scripts/agent_lanes_check.py
# re-reads that same manifest against the installed profiles and FAILS THE BUILD when a declared
# lane did not land — a container that would run a lane with no rulebook is the failure mode the
# issue names, and it must be visible at build time, not inside a bot run.
RUN set -eux; \
    mkdir -p "${HERMES_HOME}/profiles"; \
    for profile in $(python3 -c 'import json,sys; print(" ".join(p["name"] for p in json.load(open(sys.argv[1]))["profiles"]))' /opt/llgenie/agents/manifest.json); do \
        mkdir -p "${HERMES_HOME}/profiles/${profile}"; \
        cp -r "/opt/llgenie/agents/${profile}/." "${HERMES_HOME}/profiles/${profile}/"; \
    done; \
    python3 /usr/local/bin/agent_lanes_check.py \
        --agents /opt/llgenie/agents \
        --profiles "${HERMES_HOME}/profiles" \
    && echo "[agent-image] llgenie lanes installed into ${HERMES_HOME}/profiles (agent_lanes_check.py passed)"

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
