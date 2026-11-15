# Proposal: registry-sync-change-issue-rest-edit

## Why

The registry-sync `State what changed in ONE issue` leg (`make sync-change-issue`, `scripts/registry_change_issue.py::open_issue`) updates the existing change issue with `gh issue edit --body` — a GraphQL `updateIssue` mutation. The leg's credential (`secrets.BUMP_TOKEN`, a fine-grained owner PAT scoped for push/PR work) is refused by that mutation: measured on run 43577357338 (registry-sync schedule, 2026-11-14) with

`RuntimeError: gh issue edit 2659 ... failed: GraphQL: Resource not accessible by personal access token (updateIssue)`

and this class was seen before on the same script's label path (`addLabelsToLabelable`, issue #775; fixed there by REST + warn-and-defer). The same credential CAN write issues over REST — it CREATED #2659 via `gh issue create` (REST `POST /repos/.../issues`, author `asimov-agent`, 2026-11-14T04:36Z) — so the transport, not the capability, is the break. With every store diff since, the leg dies at the EDIT and #2659's body is frozen at its creation text: the change analysis for 11-14 onward never lands on the issue, and the step is a recurring red in `registry-sync` (#2665 records 44 reds in its last 100 runs; this leg reds on top of the store gate).

## What Changes

- **REST body edit.** `open_issue`'s update branch replaces `gh issue edit --body` (GraphQL) with `gh api -X PATCH repos/<slug>/issues/<n> -f body=...` — the same REST seam class #826/#775 established for label writes on this credential. The gate (`scripts/registry_keys.py` / `make check-registry-keys`) is NOT touched: this is transport/wiring only (issue #2673 AC3).
- **Read-back proof.** After the PATCH, the marker is read back from `GET repos/<slug>/issues/<n>` (`--jq .body`, same REST transport). A write that claims success but never stored the new body `SystemExit`s, naming the issue — the #819/#724 silent-drop rule.
- **Loud refusal report.** If the PATCH is refused outright (HTTP 403 / `not accessible by personal access token`), the leg prints one stderr line naming the issue number, the endpoint, and the capability (`issues write`), returns `update refused for #<n>` and survives (the #775 credential-fact rule: the sync PR step must still run). No more bare `gh issue edit ... failed` tracebacks.
- **Tests pinned.** The fake-`gh` in `tests/test_registry_change_issue.py` gains the PATCH/read-back pair, a silent-drop body test (read-back fails → step fails naming the issue), and a refused-body test (stderr names issue + endpoint + capability, step survives). The update test pins `api -X PATCH` and asserts `issue edit` is NEVER called.

## Scope guard

- `scripts/registry_review.py:311` carries the identical GraphQL `--body` edit but runs on `github.token` (registry-sync-review.yml), which GraphQL accepts — no measured failure. Filed as its own linked issue (latent same-class transport).
- The `--add-label` GraphQL sites (`issue_dedup.py`, `issue_implementer.py`, `issue_refiner.py`) are untouched: they run on lanes whose token accepts them, and #2673 demands no gate/behavior change beyond this leg.
- `secrets.BUMP_TOKEN` scopes stay the owner's to set (established rule, agent-wiki 2026-10-20); this change stops *depending* on GraphQL capability it never had.

## Impact

- Affected specs: `registry-sync-change-issue` (new capability: REST transport + read-back + loud refusal for the change-issue leg)
- Affected code: `scripts/registry_change_issue.py`, `tests/test_registry_change_issue.py`
- Issue: #2673 (AC1 identity+cause recorded; AC2 proven by a completed registry-sync run whose step exits 0 with the body updated; AC3 gate unchanged; AC4 refusal report pinned by test)
