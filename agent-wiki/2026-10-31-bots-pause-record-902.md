# Record the 2026-10-28 bot pause as data, gate it, and give it a restore measure (issue #902)

## Why
16 bot workflows were `disabled_manually` 2026-10-28T15:50–51Z under runner starvation (#817).
`gh workflow list` cannot tell "deliberately paused for starvation" from "silently broken"; the tree
cannot see `disabled_manually` at all. #874 established that **auto-merge must never be paused**, but
only the tree half (name/fires-by-itself/thresholds) was guarded; the API state half was
*"readable only through the API, so a hermetic ci-unit cannot assert it"* (old docs/BOTS.md).

## What changed
1. **`bots/pause.toml`** — the pause's source of truth: `paused` (16 workflows), `never_pause`
   (`auto-merge.yml`, `ci.yml`, `pipeline.yml`, `published.yml`), `restore_first`/`restore_after`
   (re-enable order), `restore` (N=3, K=10, L=10 — the queue-health measurement).
2. **`scripts/all_pipelines.py`** — the `state == disabled_manually` half of the #874 guard, placed
   where the API IS reachable: `_NEVER_PAUSE` is derived from `bots/pause.toml`, and a never-pause
   workflow the sweep's live read reports disabled is **FORBIDDEN disabled**: it fails the sweep
   loudly instead of a benign `DISABLED` row.
3. **`scripts/bots_restore_health.py` + `make bots-restore-health`** — the #902 restore condition as
   a measurement: `measure` samples the live `/actions/runs` and the queue is healthy when every
   queued `pull_request` run reaches `in_progress` within L minutes; `restore` prints the ordered
   re-enable list from `bots/pause.toml`.
4. **`docs/BOTS.md`** — replaced the "a hermetic ci-unit cannot assert disabled_manually" claim with
   the new API-half guard and the pause-as-data/restore-measurement sections.

## Verified
Unit tests (`tests/test_bots_pause.py`, 9) exercise the real modules with a local stub `gh`
(`BOTS_RESTORE_HEALTH_GH`/CLI `--now`), the accepted external stand-in (not a mock of product logic):
- a never-pause workflow `disabled_manually` → role `forbidden_disabled` → report shows
  `FORBIDDEN DISABLED` and exit 1 (the guard reds on the bug class #874 filed);
- an ordinary paused bot (fix-bot) → still a benign `disabled`/`DISABLED` row, exit 0 (no overreach);
- `restore_order()` == restore_first + restore_after (record-derived), and the cheap bots precede the
  heavy ones;
- a queued run stuck > L min → reading unhealthy (problem named); `in_progress`, or queued but < L
  min, → healthy.
`tests/test_all_pipelines.py` still passes (18 combined) — the new role only fires for names actually
in `_NEVER_PAUSE`, so no existing fixture workflow regressed.

## Restore condition
`make bots-restore-health CMD=measure REPO=owner/repo` until healthy (N consecutive readings, K min
apart, each showing the queue drains within L min), then `make bots-restore-health CMD=restore` and
`gh workflow enable <file>` in order: `fix-bot`, `security-bot`, `registry-sync`, `engine-bump`,
`issue-dedupe`, then `security-scan`, `engine-build`.
