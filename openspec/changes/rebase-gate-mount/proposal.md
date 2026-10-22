# The rebase gate mounts the checkout, not the repo slug

## Why

Run `39727049030` rebased #498, the agent resolved the conflict in `scripts/architecture_bot.py` and
`tests/test_architecture_bot.py`, and then the structural gate failed:

```
docker run --rm -u root -v "asimov-agent/llgenie":/repo:rw ...
docker: Error response from daemon: create asimov-agent/llgenie: "asimov-agent/llgenie" includes
invalid characters for a local volume name
make[1]: *** [Makefile:1194: lint] Error 125
[rebase-bot] gates failed
```

The rebase job exports `REPO: ${{ github.repository }}` so the sweep and the push know the slug. Make
treats an environment variable as an override of `REPO := $(shell pwd)`, so `make lint` mounts the
slug. Docker refuses it, the rebase is aborted, and the resolved conflict is thrown away.

## What Changes

- **`Makefile`** — the container mounts use `$(ROOT)`, an `override` of `$(shell pwd)`, so an
  exported slug cannot become a volume source. `$(REPO)` stays the slug for the bot targets.
- **`tests/test_rebase_bot_gates.py`** — `make -n lint REPO=asimov-agent/llgenie` mounts the checkout,
  and `make -n rebase-bot-sweep` still receives the slug.

## Impact

- A resolved rebase survives its own gate.
- The sweep and the push still talk to `asimov-agent/llgenie`.
