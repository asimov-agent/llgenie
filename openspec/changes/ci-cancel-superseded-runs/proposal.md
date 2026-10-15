# ci-cancel-superseded-runs — proposal

Issue: [#288](https://github.com/asimov-agent/llgenie/issues/288)

## Why

`ci.yml` is the only workflow this repo triggers on a pull request, and it declared **no
`concurrency:` block** — while every bot workflow declared one (with `cancel-in-progress: false`,
deliberately, so a bot run is never killed by its own next tick). So a second push to a PR branch
started a second run **beside** the first instead of replacing it.

Measured on 2026-10-15 (`main` `9675c1fa`):

- `feat/bot-pipeline-isolation` had run `38680205632` (sha `345e7eb8`, 04:11Z) and run
  `38683422700` (sha `846d4ed8`, 04:48Z) **both live at the same time**;
- `feat/dispatch-forms` had two queued runs one minute apart (`38677283875` sha `85a38612` 03:38Z,
  `38677403882` sha `28e5b51` 03:39Z);
- `main` had two queued runs (`38681207155` sha `9509628b` 04:23Z, `38682751248` sha `9675c1fa`
  04:41Z).

One superseded run costs the linux suite (`make ci-unit` is measured at 11–20 min: 4356 passed in
673 s, 4330 in 1170 s), the macOS job, and the whole `engine-image-*` build matrix plus
`test-published-*` — and a same-repo PR run **publishes**: `make push-engine` is an unconditional
step of every `engine-image-*` job (measured: run `38121659510` pushed
`llama-cpp:23b0202a-021e11d2-cuda` on a PR run), so two live runs of one branch both build and push
the same images. The waste is worst exactly where it hurts: the superseded runs sit in the same
jammed `macos-15-intel` queue that blocks every open PR (#254), and `gh pr checks` keeps reporting a
verdict for a commit that is no longer the branch head.

There is no repo-level setting for this — GitHub has no "cancel superseded runs" switch — so the
mechanism is the per-workflow `concurrency` key.

## What Changes

- **`ci.yml` gains a `concurrency:` group** keyed to the workflow **and the PR ref**:

  ```yaml
  concurrency:
    group: ${{ github.workflow }}-${{ github.ref }}
    cancel-in-progress: ${{ github.event_name == 'pull_request' }}
  ```

  `github.ref` for a `pull_request` run is `refs/pull/<n>/merge`, so **one PR supersedes its own
  predecessor** and two different PRs never cancel each other. The group belongs to the caller:
  `pipeline.yml` and `published.yml` are `workflow_call` files, and `ci.yml` is the workflow the
  `pull_request`/`push` event actually triggers.

- **`cancel-in-progress` is TRUE for `pull_request` only.** A `push` to `main` must never cancel a
  `main` run that is mid-publish to GHCR: a cancelled publish leaves the content-hash tag
  half-pushed and the next run has to republish all of it. Superseding is for the PR path.

- **The bots are untouched**: their `cancel-in-progress: false` stays (a repair/rebase that is 40
  minutes into a 180-minute agent job must never be killed), and the PR's `cancel-in-progress: true`
  is forbidden everywhere in this repo.

- **`tests/test_ci_concurrency.py`** pins the contract, because a YAML key is invisible to every
  other gate: the group is per-ref, and `cancel-in-progress` is **evaluated** for both event names
  (true for `pull_request`, false for `push`) rather than grepped as a string — a `true` copied for
  every event fails the test. Two table-driven cases keep it durable: every workflow that triggers on
  a pull request must declare a group, and no workflow may cancel every run unconditionally.

- **README** states the CI trigger and cancel behaviour, and **`agent-wiki/`** records the work
  (AGENTS.md README-sync + record-of-work rules).

## Not covered

- **#254** — the `macos-15-intel` queue with no matching runner. Cancelling superseded runs shortens
  that queue but does not fix it; it stays its own issue (and a repo-settings/coverage decision).
- **Backfill** — runs already superseded today need a manual/API cancel; the workflow change governs
  runs started after it lands.
- **The bot workflows' own concurrency** — already shipped by #275/#287
  (`tests/test_bot_pipeline_isolation.py`); this change neither adds nor relaxes a bot group.
