# The rebase bot runs the squash-close re-check as a hard gate (#1716)

A rebase replays each commit onto `main`, re-authoring each message. `git rebase` can silently drop a
claimed `closes #N` from a rewritten message even when the diff is intact — and this repository's
`check-pr-closing` gate reads the **squash text** (`COMMIT_MESSAGES` merge), so a drop turns the
freshly-rebased PR RED at its new head with no file-level indication. That is exactly what happened
in the 2026-11-04 four-PR rebase batch onto `main 90bab322`: #1697/#1707/#1702 all reddened on
`check-pr-closing` while "patch-intact" was reported. The structural gates the bot already runs only
compare content; they cannot see a message-level close dropping.

## The fix

`scripts/rebase_bot.sh` now runs the squash-close re-check as part of the pre-push gate. After the
structural gates and before the `--force-with-lease` push, it:

1. fetches the **LIVE** PR body (never a snapshot): `gh api "repos/$REPO/pulls/$PR" --jq '.body // ""'`;
2. runs `python3 scripts/check_pr_closing.py check --base "${ORIGIN}/main" --rev HEAD --head "$HEAD_BRANCH"
   --body-file "$CLOSE_BODY" --cwd .`;
3. on a RED (the rebased head's adjacent-close set no longer matches the live body) it reports a
   `gave-up` comment that carries the check's own evidence — the exact `#N` that was dropped — and
   pushes **nothing**, exiting non-zero so the workflow's drain loop counts it as a failure.

The gate script itself is untouched (already correct: adjacency, issue #1329; body-set equals
commit-set, issue #1417). What changed is that the rebase lane now *runs* it, so the lane needs no
memory of the rule to stay safe — a close-drop is reportable red, not a silent pass.

## Prove-the-guard

Three regression tests in `tests/test_check_pr_closing.py` build a **real** git repo and drive the
exact CLI the bot invokes, both arms:

- close kept in the re-authored head message + `Issue:` + body `closes #N` -> **green**;
- head message re-authored to carry only `(#1707)` with no adjacent close while the body still says
  `closes #1707` (the #1697/#1707 defect) -> **red**, naming `1707`;
- no close and no claim -> green (the check is a subset, not a roster).

The actor harness (`tests/test_rebase_bot_sweep.py`) now supplies a deterministic `gh` stub (empty
body, comments swallowed) so the close-dropping actor run exits non-zero with the `#N` named and
nothing published — proving the gate fails closed before any push. Implements #1716.
