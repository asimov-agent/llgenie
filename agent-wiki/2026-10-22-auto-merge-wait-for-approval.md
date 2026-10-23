# 2026-10-22 — wait for the approval to take effect (#531)

**Issue:** [#531](https://github.com/asimov-agent/llgenie/issues/531) · **PR:** the PR that closes it

## What was wrong

`_clear_review()` (from #524/#525) approves the PR and then reads `pr_state()` **in the same instant**. GitHub
computes `mergeStateStatus` asynchronously, so that read still reports `BLOCKED`; the job concludes the approval
did not work, falls back to `--admin`, and defers. Measured on PR #530, run
[`39892494540`](https://github.com/asimov-agent/llgenie/actions/runs/39892494540):

```
[auto-merge] PR #530 is green but blocked by a required review — approving as `asimov-agent` (authored by `andyholst`)
[auto-merge] PR #530: approved, but the merge state is still mergeStateStatus is BLOCKED (…)
[auto-merge] PR #530: falling back to --admin (the review cannot be cleared legitimately)
[auto-merge] PR #530 deferred to a human: None; the admin merge was refused too: …
```

Seconds later the PR was `APPROVED` / `CLEAN` / `MERGEABLE`. The deferral also rendered `None` — the
successful-approval path left the reason variable unset, so the comment said nothing.

## What changed

- `wait_for_merge_state()`: bounded poll (6 attempts, 5 s apart) until `mergeStateStatus` is `CLEAN`.
- `_clear_review()` decides from that read, so the approval the job just posted is allowed to take effect.
- A PR that never converges keeps today's behaviour (admin fallback → deferral), but the comment now reads
  "the approval landed, but the PR did not become mergeable within the wait (mergeStateStatus …: …)".

## Verified

- `pytest tests/test_auto_merge.py` in `llgenie/test:latest` → 36 passed, including a fake `gh` that holds
  `BLOCKED` for two reads after the approval (merged without `--admin`) and one that never settles (deferral
  names the wait, no `None;`).
- `make test-unit` → 5025 passed, 6 deselected; `make lint`, `make check-docs`, `make check-wiring`,
  `make check-workflows`, `make openspec-validate NAME=auto-merge-wait-for-approval` → green.

## Related

The third blocker seen in that run is not code: `secrets.BUMP_TOKEN` carries no `workflow` scope, so a PR that
touches `.github/workflows/**` cannot be merged with it at all
(`refusing to allow a Personal Access Token to create or update workflow … without workflow scope`). PR #530 is
such a PR; it needs the scope added to the PAT, or a human merge.
