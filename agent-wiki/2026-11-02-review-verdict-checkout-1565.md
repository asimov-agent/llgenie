# review-verdict's record job checks out before make bot-verdict (#1565)

2026-11-02. The `review-verdict` caller wired by #1562 (closes #1550) could not run its own
producer: its `record` job had **no** `actions/checkout`, so `make bot-verdict` ran in an empty
workspace and died with `No rule to make target 'bot-verdict'` on **every** same-repo review event.
Measured on first real use — PR #1563, run **41418832262** (head `c5f58fa9`, concluded `failure`):

```
make: *** No rule to make target 'bot-verdict'.  Stop.
```

`git show origin/main:.github/workflows/review-verdict.yml | grep -c checkout` → `0`. The #852
bot-verdict marker was therefore never posted by the pipeline half built to post it; the wiring guard
passed on text ("a caller exists") while the caller was broken at runtime.

## Fix

1. **`.github/workflows/review-verdict.yml`** — the `record` job's first step is now the SHA-pinned
   `actions/checkout@11d5960a…` (repo convention, same as `ci-verdict.yml`), checking out
   `pull_request.base.sha` (the repo's own tree, never a fork/PR head) **before** the
   `make bot-verdict` step. The producer now runs from a real tree.
2. **`tests/test_bot_verdict.py`** — the wiring guard is extended past text: a new helper
   `_caller_job_lacks_checkout` parses each workflow caller's YAML and fails when the job that
   invokes `make bot-verdict` has no `actions/checkout@` step. Two new tests pin it: the real tree
   passes, and a copy with the checkout stripped from `review-verdict.yml:record` (the make call
   intact) makes the guard name that caller. Proven at edit time: the extended guard reds
   `('review-verdict.yml', 'record')` on the stripped tree and is green on the real one.

## Tests / acceptance

`test_bot_verdict.py`: 14 passed (12 original + 2 new), including the check that the guard reds a
caller whose job lost its checkout. `make check-workflows` passes. Issue: #1565. The end-to-end
acceptance (a review event posting the marker) is measured by the next real review; this change
unblocks it. scoped in: no change to `scripts/bot_verdict.py` (the producer is fine), no change to
auto_merge, and no re-open of #1550 (already closed by #1562).
