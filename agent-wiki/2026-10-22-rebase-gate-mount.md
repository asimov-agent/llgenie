# The rebase gate mounts the checkout

Issue: #505. PR: #506.

Run `39727049030` resolved #498's conflict and then aborted. `make lint` expanded to
`docker run -v "asimov-agent/llgenie":/repo`, and docker refused the slug as a volume name. The job
exports `REPO` as the slug; Make treats that as an override of `REPO := $(shell pwd)`.

The mounts now use `$(ROOT)`, an `override` of the checkout path. `make -n lint
REPO=asimov-agent/llgenie` mounts the checkout, and `make -n rebase-bot-sweep` still receives the slug.

Run `39728790390` then reddened `macos / unit` (1 failed, 5023 passed): the
regression test asserted the container shape of the recipe (`-v "<checkout>":/repo:rw` and
`llgenie/test:latest`), but a Darwin host expands `TEST_RUN` to the native 3.11 venv
(`Makefile` `HOST_OS` branch), so its lint recipe carries no volume at all. The test now asserts the
mount invariant where both hosts resolve it (`TEST_OPTS`, via `make -p`) and the recipe against the
shape its own host runs — container on Linux, venv with no volume on macOS.
