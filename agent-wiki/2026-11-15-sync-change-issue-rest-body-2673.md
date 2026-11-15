# 2026-11-15 — sync-change-issue body edits move to REST (issue #2673)

## What was verified

- The failure is real and measured: registry-sync run `43577357338` (2026-11-14) ended with
  `RuntimeError: gh issue edit 2659 ... failed: gh: GraphQL: Resource not accessible by personal
  access token (updateIssue) (HTTP 403)` from the `sync-change-issue` step — so #2659's body has
  been frozen at its creation text on every run since (issue #2659).
- Cause: `scripts/registry_change_issue.py::open_issue` updated the body through
  `gh issue edit --body`, a GraphQL `updateIssue` mutation. The step runs with
  `secrets.BUMP_TOKEN` (fine-grained owner PAT); the same credential creates issues over REST
  without refusal, while GraphQL mutations are rejected — the #775/#826 credential-fact class.
- Fix: new `_edit_body()` seam in `scripts/registry_change_issue.py` — REST
  `gh api -X PATCH repos/<slug>/issues/<n> -f body=...`; after the PATCH the exact body is read
  back over the same transport and a mismatch (a write that claims success but never stuck, the
  #819 silent-drop class) fails the step naming the issue; a refused 403 is reported as one line
  naming issue + endpoint + required capability and `open_issue` returns `update refused for #N`
  so the leg survives and the sync PR step still runs.
- Tests: `tests/test_registry_change_issue.py` — the fake `gh` now RAISES on any `issue edit`
  transport call (pins the REST-only rule); the update test asserts the PATCH, the read-back, and
  stored-body equality; two new tests pin the silent-drop failure and the refused-write report.
  10 passed (`python -m pytest tests/test_registry_change_issue.py` in `llgenie/test:latest`).

## Decisions

- Read-back compares the EXACT body written, not the marker: the marker is the store's identity,
  so an unchanged old body still carries it — equality is the only discriminator.
- The label write stayed REST POST (already proven by #775); the create `--label` flag stays as is.

## Current status

- Out-of-scope recorded as its own linked issue: **#2691** (`registry_review.py::publish` carries
  the same latent GraphQL `--body` transport; no measured failure yet — the lane runs on
  `github.token`).
- AC "a completed registry-sync run where the step exits 0" can only be proven by a dispatched
  registry-sync run on main after this lands (workflow supports `workflow_dispatch`).

Issue: #2673 (PR #2692), #2659, #2691
