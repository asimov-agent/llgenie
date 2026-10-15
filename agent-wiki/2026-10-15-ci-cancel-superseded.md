# A push to a PR terminates the run it supersedes (#288)

## Why

`ci.yml` is the only workflow this repo triggers on a pull request, and it carried **no
`concurrency:` block** — while every bot workflow carried one (`cancel-in-progress: false`, on
purpose). So a second push to a PR branch started a second run **beside** the first instead of
replacing it.

Measured 2026-10-15 on `main` `9675c1fa`:

| branch | runs live at the same time |
|---|---|
| `feat/bot-pipeline-isolation` | `38680205632` (sha `345e7eb8`, 04:11Z) **and** `38683422700` (sha `846d4ed8`, 04:48Z) |
| `feat/dispatch-forms` | `38677283875` (sha `85a38612`, 03:38Z) **and** `38677403882` (sha `28e5b51`, 03:39Z) |
| `main` | `38681207155` (sha `9509628b`, 04:23Z) **and** `38682751248` (sha `9675c1fa`, 04:41Z) |

One superseded run costs the linux suite (`make ci-unit` measured at 11–20 min: 4356 passed in 673 s,
4330 in 1170 s), the macOS job, and the `engine-image-*` matrix plus `test-published-*` — and a
same-repo PR run **publishes**: `make push-engine` is an unconditional step of every `engine-image-*`
job (measured: run `38121659510` pushed `llama-cpp:23b0202a-021e11d2-cuda` on a PR run), so both live
runs were building and pushing the same images. The queued leftovers also sat in the same
`macos-15-intel` queue that blocks every open PR (#254), and `gh pr checks` kept reporting a verdict
for a commit that was no longer the head.

There is no repo-level switch for this: GitHub has no "cancel superseded runs" setting, so the
mechanism is the per-workflow `concurrency` key.

## What landed

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}
```

- **Per-ref group**: `github.ref` for a `pull_request` run is `refs/pull/<n>/merge`, so one PR
  cancels its own predecessor and two different PRs never cancel each other. The group lives in
  `ci.yml` (the workflow the event triggers), not in the `workflow_call` files
  (`pipeline.yml`/`published.yml`).
- **`cancel-in-progress` is true for `pull_request` only**: a `push` to `main` is never cancelled —
  a main run mid-publish to GHCR must finish, since a cancelled publish leaves the content-hash image
  tag half-pushed and the next run republishes all of it.
- **The bots are untouched**: `cancel-in-progress: false` stays everywhere a bot hands an agent up to
  180 minutes of work.

## Verification

`tests/test_ci_concurrency.py` (wired into `make test-unit`) — a YAML key is invisible to every other
gate, so the contract is pinned:

1. the group is per-ref and is not an unconditional literal;
2. `cancel-in-progress` is **evaluated** for `github.event_name == 'pull_request'` **and** `push` —
   true for the PR, false for the push (a `true` copied for every event fails);
3. every workflow triggered on a pull request declares a group (a new PR workflow cannot silently
   re-introduce the leak);
4. no workflow declares the literal `cancel-in-progress: true`.

The test fails on the pre-fix `ci.yml` (no `concurrency` block → the group assertion fails), which is
the proof it is a gate rather than a description of the file.

## Related

- #288 — the issue this closes.
- #254 — the `macos-15-intel` queue; cancelling superseded runs shortens it but does not fix it.
- #275 / #287 — the bot half (per-bot concurrency groups, unique cron slots); this is the CI half,
  where the same ref deliberately supersedes itself.
