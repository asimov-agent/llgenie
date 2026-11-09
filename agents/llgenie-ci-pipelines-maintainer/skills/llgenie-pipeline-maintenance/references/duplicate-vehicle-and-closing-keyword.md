# One vehicle per fix: sweeping, closing keywords, and stand-down

Applies when a pipeline-fix red surfaces and you are about to open a fix vehicle.

## Sweep the PRs on the target file before opening — not just the issues

A sibling lane may already have the same fix staged in its own payload; two vehicles editing one file is #824 again. A planner may first route an infra red to you ("fix owner = you") then reverse to "HOLD — one vehicle edits that file" once it sees the engine lane's payload carries the same fix staged for a lease-push.

Measure the LIVE reachable head before either closing your PR as a twin or pushing:

- `gh api repos/<o>/<r>/pulls/<n> --jq .head.sha`
- `git log <branch>` for the cited fix commit — a fix "staged" for a push-gated (owner stop) lease-push is often NOT on any reachable head yet
- `git show <head>:<file>` to confirm the defect is still present at the live head

If the fix is staged-but-not-landed, keep the only-live fix open and commit to close-on-landing (the moment the sibling payload lands and proves the same path green). Never close a fix that measurably does not exist on the wire; never open a second one once it lands.

## The closing keyword must name the DEFECT issue, not the issue the red appeared against

When a pipeline-fix red surfaces against a PR that is itself a product change (e.g. a product build PR blocked by the verdict gate), the defect issue is the GATE's issue — matched by root cause ("the judge counts its own posted check-run") — NOT the product PR the red appeared on. Opening your fix with `closes <product-PR>` closes nothing on-wire and mis-scopes the vehicle. The retained vehicle is the one that closes the true defect issue and is reviewer-verdict-gated.

## A sibling landed the identical fix first: the owner keeps one, closes yours

If an implementer lane independently landed the same fix (same function/name, same root cause), the owner closes your PR as a duplicate per one-vehicle-per-issue (#824) even when your diagnosis is correct and your guard-proof green.

- Accept it. Never reopen, never push a competing code path.
- Deliver your verified assets (regression tests, openspec change dir, change-note trio) to the retained PR as an on-issue comment pointer, not stranded on the closed branch.
- Measure the retained head's own diff BEFORE believing an asset is still needed — the sibling's regression test and negative control are often already there, making your offer redundant:

  - `gh api repos/<o>/<r>/pulls/<n>/files --jq '.[]|"\(.filename) +\(.additions)/-\(.deletions)"'`
  - `gh api "repos/<o>/<r>/contents/<file>?ref=<head>" --jq .content | base64 -d` and grep for the function/test name

## Stand down cleanly, don't manufacture work

Once the retained head proves it carries the fix and its guard tests, the task deliverable exists — a further code mutation would either duplicate it (#824) or steal the owning lane's work. State the measured evidence (retained head sha, the fix hunk, the covering test) and stop. Do not fabricate a redundant change to satisfy a progress guard.
