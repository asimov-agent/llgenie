# PR CI verification (is it actually red?)

Before assuming a PR is failing, read the per-job state — a job still
`IN_PROGRESS` is not a failure.

- `gh pr checks <n> --json name,state` and filter OUT `SUCCESS`/`SKIPPED`;
  only what remains is worth acting on. A long hermetic suite (e.g. the macOS
  unit job) can run 20+ minutes after every other job is green, so a PR that
  looks "red" may simply be waiting on one slow job. Do not start fixing
  something that is only running.
- After a squash merge, `git merge-base --is-ancestor <head> origin/main`
  reports NO even though the content IS in main — the individual commits were
  folded into one. Verify content presence (`git show origin/main:<path>` for
the key files), not commit ancestry, before concluding the work is absent.
- A PR's `mergeStateStatus` of `BLOCKED` is often just `REVIEW_REQUIRED` —
  green CI plus no approval. That is the reviewer's gate, not a defect to fix.
