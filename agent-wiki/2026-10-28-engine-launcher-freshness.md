# 2026-10-28 — a launcher that lags a pin is now a red gate, not a silent old engine

**Issue:** [#842](https://github.com/asimov-agent/llgenie/issues/842) · **PR:** the pull request that
closes #842 from `feat/check-engine-launchers` · **Found under:** [#178](https://github.com/asimov-agent/llgenie/issues/178)

## What was wrong

`~/bin/llgenie-engine-<engine>` is generated, and its `IMAGE=` line names a content-addressed tag
`:<pin[:8]>-<params_hash8>-<variant>`. `make engine-launchers` writes it once; nothing ever compared
that tag back to the committed params afterwards. So a pin could move (the weekly `engine-bump.yml`)
and the launcher keep naming the previous image — the host then runs last month's engine and
`--version` reports it happily, or a fresh `make engine-launchers` fails on a tag nobody pushed with
the error pointing at GHCR instead of at the pin drift.

Measured on this host, 2026-10-28, before the gate existed:

```
make check-engine-launchers
[launchers] stale launcher names an older pin: llama.cpp-prism launcher pin=e8fd209c params=cb5b6dc0 -> expected pin=c96baf4a params=12ac8d3d
[launchers] stale launcher names an older pin: vllm launcher pin=db9527a4 params=aade39e4 -> expected pin=5df63a72 params=250e7780
[launchers] 2 ok, 2 stale, 8 missing (arch cuda)
```

`c96baf4a` is the committed pin (bump to prism@c96baf4a, #663); `e8fd209c` is the older one (#203).
Same class as #178's "invariant with no gate".

## What changed

- `scripts/check_engine_launchers.py` (new): `expected(arch)` calls
  `install_engine_launchers.install_plan()` — the **writer itself**, not a second copy of the tag
  formula — and `check()` compares each `(engine, variant, tag)` against the `IMAGE="${LLGENIE_IMAGE:-<tag>}"`
  default of the installed launcher. Four outcomes: `OK`, `STALE` (fail, naming both tags and both
  pins, and which of pin/params/variant drifted), `MISSING` (informational — CI's normal state),
  `NOT PUBLISHED` (only with `--check-registry`, the one code path that touches the network).
- `Makefile`: `check-engine-launchers` + `engine-launchers-report`, both declared `.PHONY`, and the
  gate runs inside `ci-unit` right after `check-engine-source`.
- `scripts/issue_bot_gates.py`: `check-engine-launchers` classified in `DEFERRED` with its reason —
  it reads host-local `~/bin` files, which a bot PR cannot change and a CI runner does not have.
- `tests/test_check_engine_launchers.py` (new): 9 cases over a temp bin dir — current launcher passes,
  an older pin fails with both tags in the message, no launcher is informational, a launcher with no
  `IMAGE=` line is stale, `--check-registry` with a stubbed `docker manifest inspect` miss is "not
  published", plus the tag-parsing helpers.
- `docs/ENGINES.md`: the two targets, and an explicit statement of what the gate does **not** prove
  (that the image runs / serves / is published), plus the four inputs the tag hashes.

## Decisions

- **One formula, the writer's.** A re-implemented tag computation would agree today and disagree
  after the next tag-format change — exactly the drift the gate exists to catch.
- **Missing launcher is informational, not a failure.** A clean CI runner has none; failing there
  would make the gate unusable in the job that runs it.
- **Registry check is opt-in.** CI must not depend on GHCR reachability; the default run starts no
  container and opens no socket.
- **The gate is local-truth, so it is red on a host with a stale launcher — by design.** That is the
  defect being reported, and `make engine-launchers ENGINES=<id>` is the fix it names.

## Status

`tests/test_check_engine_launchers.py` → 9 passed in the test image. `make check-wiring`,
`make check-docs`, `make lint` green in the worktree. `make check-engine-launchers` exits 1 on this
host with the two real stale launchers above, and 0 on a tree with no launchers (CI).
