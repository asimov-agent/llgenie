# Wait for the approval to take effect

## Why

The approve-then-merge path (#524/#525) approves the PR and then reads the merge state **the same instant**.
GitHub computes `mergeStateStatus` asynchronously, so that read still says `BLOCKED` and the job abandons the
legitimate path. Measured on PR #530, run
[`39892494540`](https://github.com/asimov-agent/llgenie/actions/runs/39892494540):

```
[auto-merge] PR #530 is green but blocked by a required review — approving as `asimov-agent` (authored by `andyholst`)
[auto-merge] PR #530: approved, but the merge state is still mergeStateStatus is BLOCKED (…)
[auto-merge] PR #530: falling back to --admin (the review cannot be cleared legitimately)
[auto-merge] PR #530 deferred to a human: None; the admin merge was refused too: …
```

Seconds later the PR was `APPROVED`, `CLEAN`, `MERGEABLE` — the approval had landed; the job had moved on.
The deferral text also renders `None` (the successful-approval path leaves the reason variable unset), so the
comment a reviewer reads says nothing useful.

## What Changes

- **`wait_for_merge_state()`** polls the PR (bounded: 6 attempts, 5s apart) until `mergeStateStatus` is
  `CLEAN`, and `_clear_review()` decides against that read instead of the instant one.
- **The deferral names the real reason**: "the approval landed, but the PR did not become mergeable within
  the wait (mergeStateStatus …: …)" — never `None`.
- A PR that does not converge still falls through to the `--admin` fallback and then to the deferral, as today.

## Impact

- A green agent PR merges on the approval the job itself posted, without a second run.
- A genuine deferral is readable on the PR instead of starting with `None;`.
