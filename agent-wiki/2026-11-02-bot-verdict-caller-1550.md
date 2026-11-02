# The bot-verdict producer is CALLED, never definition-only (#1550)

2026-11-02. `#852` shipped the producer (`make bot-verdict`), the consumer (`auto_merge` reads the
marker), the docs and the tests — and no caller: its own `## Not covered` said *"No lane posts a
verdict yet"*. A reviewer completes a review; the one machine-readable verdict the merge decision
reads is never written. Measured at `main@27e2f4fa`: `grep -rn "make bot-verdict"` over
`.github/workflows/`, `agents/` and `scripts/` found only the definition, the Makefile target, and
the docs.

## Fix

1. **`review-verdict.yml`** is the pipeline-half caller. It triggers on `pull_request_review`
   (`submitted`), resolves the EXACT head the review judged and the newest concluded `pull_request`
   run at that head, and runs `make bot-verdict VERDICT=approve|changes HEAD=<head> RUN=<run id>
   REPO=asimov-agent/llgenie PR=<n>` — posting as the workflow's own token (`github-actions[bot]`,
   a trusted verdict author), so `reviewer == author` and the no-impersonation rule holds by
   construction. A commented review is not a verdict; a head with no concluded run is not posted
   (#1551). Only a same-repo head is recorded here: a fork review event carries a read-only token
   and no secrets, and those heads are covered by the reviewer lane's own (separately-routed) posting.
2. **The wiring guard.** `tests/test_bot_verdict.py` now greps `.github/workflows/`, `agents/` and
   `scripts/` for a caller of `make bot-verdict VERDICT=… HEAD=… RUN=… REPO=… PR=…` and fails when
   none exists — and proves that failure by scanning a caller-less copy of the workflows. The
   producer can never again exist with no caller.
3. **The reviewer lane's own posting** (running the same target from the host, its SKILL/SOUL) is
   the reviewer lane's own artifact and is routed separately by the planner when the code lands; it
   covers the fork heads this read-only workflow event cannot.

## Tests / acceptance

`test_bot_verdict.py`: the real tree has at least one caller; a caller-less tree makes the same
assertion fail. `test_auto_merge.py`: `make auto-merge-explain` on a verified head reporting a
`changes` verdict names the reviewer who holds it. check-workflows passes (the new workflow is in
the run-failure-reactor roster; it is not dispatchable, so it needs no owner guard and no dispatch
row). check-wiring, lint pass. Issue: #1550; closes the `#852` follow-up the follow-up was filed as.
