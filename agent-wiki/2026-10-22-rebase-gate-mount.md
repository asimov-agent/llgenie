# The rebase gate mounts the checkout

Issue: #505. PR: #506.

Run `39727049030` resolved #498's conflict and then aborted. `make lint` expanded to
`docker run -v "asimov-agent/llgenie":/repo`, and docker refused the slug as a volume name. The job
exports `REPO` as the slug; Make treats that as an override of `REPO := $(shell pwd)`.

The mounts now use `$(ROOT)`, an `override` of the checkout path. `make -n lint
REPO=asimov-agent/llgenie` mounts the checkout, and `make -n rebase-bot-sweep` still receives the slug.
