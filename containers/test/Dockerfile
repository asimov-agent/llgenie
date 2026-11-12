# llgenie test container: runs every verification stage containerized so the
# same stages run identically on the dev host (nerdctl/colima) and in CI (docker).
#
#   make test-image        # build
#   make lint / test-unit / test-install / test-health   # any stage
#
# It bundles python + pytest + the locked deps + the hf CLI + the docker CLI.
# Inference servers are NOT in this image: tests start the engine images
# (containers/engines/) through the host docker socket, exactly like `make install`.
FROM python:3.11-slim AS base

# Runtime + test deps (copied from the repo's compiled lockfiles at build).
# These are regenerated from tools/requirements.in + tools/requirements-dev.in
# (source of truth), never hand-edited.
COPY requirements.txt requirements-dev.txt /tmp/
RUN pip install --no-cache-dir \
        -r /tmp/requirements.txt \
        -r /tmp/requirements-dev.txt \
        # `hf` cloud-download CLI (huggingface_hub), used by download_test_model.py
        # with resume/retry. Must be on PATH in the container so the same
        # download command works on CI as on the host.
        "huggingface_hub[cli]>=0.30"

# curl for the health probe; git for diagnostics (linefeed lint uses git ls-files);
# docker CLI so tests in this container start the ENGINE IMAGES through the host's
# docker socket (-v /var/run/docker.sock). No inference server is built or
# installed in this image: llama-server and every other engine run only in their
# own images (containers/engines/), the same images CI publishes (issue #98).
COPY --from=docker:27-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker:27-cli /usr/local/libexec/docker/cli-plugins/docker-buildx /usr/local/libexec/docker/cli-plugins/docker-buildx
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl git lsof make procps \
    && rm -rf /var/lib/apt/lists/* \
    # the repo is bind-mounted from the host (owned by a different uid); mark it
    # safe so `git ls-files` in the lint stage works as root in the container.
    && git config --global --add safe.directory '*'

WORKDIR /repo
CMD ["--help"]
