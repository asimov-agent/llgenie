# Card-aware engine ranking (rank_engines / pick / matrix)

Durable domain for llgenie work that orders or labels a model's engines:
`scripts/model_engine_pick.py` (`rank_engines`, `rank_models`, `recommend`,
`trend_list_matrix`), plus `llgenie_serve._tps_label`. `data/models.json` stays a
VERBATIM upstream copy — never add fields to it; every field the ranking reads
is already in it (`hardware`, `tps`, `backend`, optional `measured_on`).

## The ranking rule (mirror trending-local-llms' README)

A measurement on a bigger card does not qualify a smaller tier (what it needed
there is unknown), and datacenter parts never count. Rank by the evidence that
describes THIS host's card, not raw t/s within a backend class. On a host whose
card class cannot be detected (Apple Silicon, CPU) the card class does not apply
and the backend-only rule ranks, as before.

Parse the card a measurement ran on from the registry's own `hardware` string:
- upstream's `_CARD_VRAM` table + `hardware_vram_gb(hardware)` -> card GB (also
  parse explicit "NGB Card" forms); a DGX node names no card -> card unknown.
- `_DATACENTER_HW` list -> datacenter hardware (A100/H200/MI300X/GB200/B300/TPU/
  ...), which never counts for a consumer-card host.
- a measurement with no named card is a box (e.g. DGX Spark), NOT evidence
  about any card class.

Ranks, lowest first: `0` proven on this card (same backend AND card_gb <= host
card), `1` same backend on a bigger card, `2` same backend with no card named,
`3` another backend, `4` datacenter, `5` supported with no figure. The ranks
guarantee a datacenter t/s never outranks a consumer card. When writing or
verifying the order, sync the live registry to a temp file
(`sync_registry.sync(UPSTREAM, tmp, UPSTREAM_README)`) and print
`rank_engines(m, 'cuda', gb=N)[0]` for N in (16, 48) before hardcoding figures.

Labels come from ONE rule shared by the data model and the serve label
(`tps_label`): "N t/s (CUDA, 48 GB card)" / "(CUDA, card unknown)" /
"(CUDA, datacenter)". Never keep a second, divergent label formatter.

## Ripples when the ranks change

Refactoring the rank order renumbers every engine-id pin in the same work:
- `tests/fixtures/trend-list-matrix.json` is GENERATOR-OWNED: regenerate with
  `make render-trend-list-matrix`, never hand-edit, and commit the new golden
  rows; a stale fixture is the diff that trips `make check-trend-list-matrix`.
- acceptance tests (`test_trend_list_acceptance.py`, `test_registry_sync_trend.py`,
  `test_trend_pick.py`, `test_model_engine_pick.py`) pin exact per-arch/card
  engine ids + t/s + variants and break together; update them in the SAME
  change. When a helper gains a parameter (`test_registry_sync_trend._same_hw`
  gains a card arg), grep the whole test tree for the symbol before widening its
  signature; every hand-rolled copy of the old shape fails on a shard you did
  not run.
- live-sync tests download upstream at runtime: run the containerized pytest
  with `--network host`, and READ the real generated figures before hardcoding
  any assertion — the old snapshot's pin can be superseded by a next-rung figure
  you did not predict.
- a full `make test-unit` run is container-cached and slow (~15+ min): run it in
  the background only after edits are final, and disregard a run that started
  before the last edit — it fails on the very assertions you just rewrote and is
  a stale run, not a regression. See also `references/loop-gate-background-run.md`.

## Verification gates

`make lint`, `make ci-unit` (test-unit + check-trend-list-matrix + registry/skill/
quant), `make check-wiring`, `make check-docs`, `make openspec-validate NAME=<change>`;
commit the OpenSpec change + agent-wiki entry + README in the same batch as the code.

### `ci-openspec` fails on an unticked task, not on a bad spec

The CI `openspec` job (linux AND macos) runs `make ci-openspec` = `make
openspec-validate NAME=ci-pipeline` + **`make openspec-tasks-check`**, which fails
any ACTIVE change whose `tasks.md` still has a `- [ ]`. A PR whose only defect is
its last, honest task (`- [ ] PR opened … CI monitored green`) therefore goes RED
with no local signal: run `make openspec-tasks-check` (container, fast) before
pushing, tick the PR task with its real PR number, and expect the follow-up push to
re-run the whole pipeline. Green CI cannot be reached while the box is unticked, so
tick it and let the re-run confirm — do not leave the task open "until green".

### `make openspec-new` writes the change dir ROOT-owned

The openspec image runs as root, so `proposal.md`/`specs/`/`tasks.md` cannot be
written afterwards (Hermes' `write_file` returns `Permission denied: …/.hermes-tmp…`,
and `sudo` needs a password on this host). Fix ownership through a root container
instead:

```bash
docker run --rm -v "$PWD:/repo" alpine:3 chown -R 1000:1000 /repo/openspec/changes/<name>
```

(`make openspec-validate` at the end may re-create root-owned files; chown again
before committing. See also `references/worktree-cleanup-root-owned.md`.)
