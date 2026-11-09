# The run-failure reactor dispatches the fix-bot with github.token (#2091)

## What changed

The reactor's Route A dispatch carried `DISPATCH_TOKEN: ${{ secrets.BUMP_TOKEN }}`
(`.github/workflows/run-failure-reactor.yml`), an owner PAT scoped for pushing a branch but **not**
for the workflow-dispatch endpoint. Every real dispatch was refused `HTTP 403 Resource not
accessible by personal access token` on `/dispatches` (measured run `42442836444`, job `react`
`128615515251`, head `e51f2fd0`). #2086 made the refusal loud and non-blocking, so the board read
*no repair* — but **no repair happened**: the reactor's whole Route A leg was dead in a tested repo.

Now the credential is the job's own `github.token` (the repository convention, `docs/BOTS.md`):

- One credential for the dispatch: `GH_TOKEN: ${{ github.token }}`, and a job-level `permissions:
  actions: write` already declared. A `github.token` dispatch is exactly the write `actions: write`
  grants, so the endpoint accepts it.
- The old refusal premise is gone: fix-bot's guard admits `github-actions[bot]` on a
  `workflow_dispatch` of this repository (issue #1571), so the dispatched run no longer needs an
  owner-identity PAT to pass it.
- The `DISPATCH_TOKEN` env plumbing is gone entirely — no second credential, no fallback that could
  silently change identity while the doc says `github.token`.

The #2086 refusal path is untouched: a dispatch that is still refused (HTTP 403) is posted on the
PR as `repair unavailable` and releases the claim, rather than reddening the reactor.

## Why

A red PR now actually wakes the fix-bot that exists to repair it (acceptance criterion 1 of #2086),
instead of the reactor reporting "repair unavailable" as the normal outcome. It also stops the
document (`docs/BOTS.md`'s token table), the fix-bot guard, and the workflow from contradicting each
other — the three now agree that a dispatch uses `${{ github.token }}`.

## What to test

- `make run-failure-reactor REPO=asimov-agent/llgenie RUN_ID=<red PR run> DRY=1` still previews and
  prints the dispatch as `github.token`.
- `tests/test_bot_write_tokens.py::test_the_run_failure_reactor_dispatch_uses_github_token_not_a_secret`
  locks the decision (GH_TOKEN == `${{ github.token }}`, no `DISPATCH_TOKEN`/`secrets.*` on the step).
- A red same-repo PR run dispatched through the reactor spawns a `fix-bot` run at the PR's head and
  the reactor posts the dispatched run id on that PR.
