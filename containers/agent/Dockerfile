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
#     --build-arg HERMES_MODEL_ID=deepseek/deepseek-v4.1-flash   (provider-prefixed)
#     --build-arg HERMES_BASE_URL=https://inference-api.nousresearch.com/v1
# Hermes's bundled `nous` provider is OAuth-only — a bare NOUS_API_KEY is IGNORED and
# `--provider nous` fails with "not logged into Nous Portal" — so the install script writes
# a CUSTOM provider alias (provider=custom, the base_url above, key_env=NOUS_API_KEY) and the
# build asserts the alias landed. The alias is why every bot call is `hermes -z ... -m
# nous-deepseek`.
#
# Secrets are NEVER baked: the KEY itself (NOUS_API_KEY), GH_TOKEN and HF_TOKEN arrive at run
# time (`docker run -e ...`, or `container:` + the job's env), exactly as #238 requires. The
# image only knows the NAME of the env var to read (key_env=NOUS_API_KEY).
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
ARG HERMES_MODEL_ID="deepseek/deepseek-v4.1-flash"
ARG HERMES_BASE_URL="https://inference-api.nousresearch.com/v1"

USER root

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

# The CI build context is FLAT (ci_images.context copies each input file to the
# context root), so the COPY path is the file's name, not its repo path.
COPY install_hermes_ci.sh /usr/local/bin/install_hermes_ci.sh
ENV HERMES_INSTALL_URL=${HERMES_INSTALL_URL} HERMES_PACKAGE=${HERMES_PACKAGE} \
    HERMES_ALIAS=${HERMES_ALIAS} HERMES_MODEL_ID=${HERMES_MODEL_ID} HERMES_BASE_URL=${HERMES_BASE_URL}
# `install.sh` puts the CLI in ~/.local/bin and its tree in ~/.hermes; make both stick for
# the runtime user too (a `container:` job does not source a login shell).
ENV PATH="/root/.local/bin:${PATH}"
RUN chmod +x /usr/local/bin/install_hermes_ci.sh \
    && /usr/local/bin/install_hermes_ci.sh \
    && export PATH="/root/.local/bin:$PATH" \
    && hermes --version \
    # The install script writes the alias; prove it right here so a bad pin fails the BUILD
    # (an image whose alias is missing or stale only fails later, inside a bot run).
    && test "$(hermes config get "model.aliases.${HERMES_ALIAS}.model")" = "${HERMES_MODEL_ID}" \
    && test "$(hermes config get "model.aliases.${HERMES_ALIAS}.provider")" = "custom" \
    && test "$(hermes config get "model.aliases.${HERMES_ALIAS}.key_env")" = "NOUS_API_KEY" \
    && echo "[agent-image] alias ${HERMES_ALIAS} -> ${HERMES_MODEL_ID} (key_env=NOUS_API_KEY, key supplied at run time)"

# The repo is checked out by the workflow (the agent edits the working tree); this is only
# the default working dir, and `git config` is left to the workflow so the bot's identity
# is visible in the commits it makes.
WORKDIR /repo

# Same entry shape as the test image: a command, not a daemon.
CMD ["bash", "-lc", "git --version && gh --version && hermes --version"]
