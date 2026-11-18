# Spec delta: post-merge-live-verify-2900

## ADDED Requirements

### Requirement: Post-merge live verification duty

Every landing onto `main` SHALL end with a live-verification read: the newest `main` runs of
`registry-liveness.yml` and `ci-hf-live.yml` are read (run id, trigger event, conclusion) and
both SHALL be green before the landing is recorded as complete. A `ci-hf-live` red whose
failure diff is fixture-vs-live trend drift SHALL open (or link) a trend-refresh issue in the
same breath as the landing record; re-running the battery away, closing it as noise, or
merging further work onto main while the battery is red SHALL be forbidden.

**Reason:** a merge that leaves the vendored trend data behind upstream trending makes main
carry a red live battery indefinitely; without a landing-time read the drift has no owner.

#### Scenario: Landing with both batteries green

- **WHEN** a PR has merged into `main` and the newest `main` runs of `registry-liveness.yml`
  and `ci-hf-live.yml` are both `success`
- **THEN** the landing watch SHALL carry those two verdicts and the
  `make -s check-trend-list-matrix` fingerprint read, and the landing is complete.

#### Scenario: Landing onto a stale trend fixture

- **WHEN** the newest `ci-hf-live` run on `main` is `failure` and its diff names fixture cells
  that disagree with the live trending build
- **THEN** the landing SHALL file (or link) one trend-refresh issue naming the disagreeing
  cells, SHALL record the battery verdict as red in the landing watch, and SHALL NOT proceed
  with further landings until that refresh lane exists.

### Requirement: Replayable post-merge live check target

The Makefile SHALL provide `post-merge-live-check`, implemented by
`scripts/post_merge_live_check.py`. It SHALL print one verdict line per battery — battery name,
newest `main` run id, trigger event, conclusion — plus a fingerprint line carrying the
`check-trend-list-matrix` result. It SHALL exit non-zero when a battery is not `success` or the
fingerprint does not match, and SHALL name the trend-refresh action (issue lane) on a
fingerprint mismatch. A missing or unreadable run stream SHALL exit 2, never a silent zero.

#### Scenario: Green batteries

- **WHEN** both battery workflows' newest `main` runs concluded `success` and the fingerprint
  matches
- **THEN** `make post-merge-live-check` SHALL print three verdict lines and exit 0.

#### Scenario: One red battery

- **WHEN** the newest `ci-hf-live` main run concluded `failure`
- **THEN** `make post-merge-live-check` SHALL print the red verdict, name the trend-refresh
  action, and exit non-zero.

### Requirement: Trend matrix re-pinned to the current trending

The lane SHALL re-pin `tests/fixtures/trend-list-matrix.json` and `tests/fixtures/hub-snapshot.json`
by running the fixed derived-fixture render order (`make -s sync-registry`, `make -s
sync-quant-catalog`, `make -s render-trend-list-matrix`, `make -s render-engine-skill-gap`,
`make -s skills-validate`, then the `check-*` gates, then `make test-unit`), and the committed
fixture SHALL agree with the live trending build for the previously failing cells
(`metal/16/8`, `metal/16/32`, `metal/16/60`, `metal/16/64`). The vendored registry SHALL stay
additive-only. If the sync carries a registry engine that has no skill, the lane SHALL file a
tracking issue per such engine (`make -s spawn-engine-skill-issues`) AND record a dated decision
for it in `data/unsupported-engines.json` in the same batch, leaving
`make -s check-engine-skill-gap` at 0 unresolved.

#### Scenario: A sync carries unskilled engines

- **WHEN** the re-pinned registry adds engines (basalt, edge0, qwen-warp, smolmaxxing) that no
  skill covers and no decision records
- **THEN** the lane SHALL file one tracking issue per engine, SHALL record a dated decision per
  engine in `data/unsupported-engines.json`, and `make -s skills-validate` and
  `make -s check-engine-skill-gap` SHALL exit 0 with 0 unresolved.

#### Scenario: Fresh fixture matches the live battery

- **WHEN** the re-pinned fixture is checked by `make -s check-trend-list-matrix` and exercised
  by `make -s test-unit-network`
- **THEN** both SHALL exit 0 at the lane head.
