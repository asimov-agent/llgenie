# 2026-11-15 — registry review publish body edits move to REST (issue #2691)

## What was verified

- Latent defect, not a measured failure: `scripts/registry_review.py::publish` body-updated its
  review issue through `gh issue edit --body` (GraphQL `updateIssue`) — the exact transport issue
  #2673 measured as REFUSED for the registry lane's runner credential (registry-sync run
  `43577357338`: `GraphQL: Resource not accessible by personal access token (updateIssue)`). This
  lane runs on `github.token` today (GraphQL accepts it), so nothing had broken yet; the sibling
  lane proves what one credential re-point does (issue body frozen forever).
- Fix: `_edit_body()` / `_gh_api` / `repo_slug` / `_REFUSED` added to `registry_review.py`
  (mirroring the proven `registry_change_issue.py` seam from PR for #2673): REST
  `gh api -X PATCH repos/<slug>/issues/<n> -f body=...`, exact-body read-back (a silent drop —
  the #819 class — fails the step naming the issue), refused 403 → one stderr line naming issue +
  endpoint + `issues write` capability and `publish` returns `update refused for #N`.
- Tests: `tests/test_registry_review.py` — fake `gh` raises on any `issue edit` transport call;
  update test asserts PATCH + read-back + stored-body equality; two new tests pin the silent-drop
  failure and the refusal report. **15 passed** in `llgenie/test:latest`.

## Decisions

- No workflow wiring change: the lane stays on `github.token`; the fix is transport-only so a
  future credential change (the #136/#2121/#2264 class) no longer freezes review bodies.
- Read-back compares the EXACT body written (the marker alone cannot discriminate — same store →
  same marker, learned on #2673).

## Current status

- Origin of this issue: #2673's out-of-scope rule (filed as #2691 at #2673's PR time).
- Post-merge: the next registry-sync-review run exercises the new seam on a live store.

Issue: #2691, #2673
