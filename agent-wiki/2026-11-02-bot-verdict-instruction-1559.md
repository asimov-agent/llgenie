# The review verdict posts the bot-verdict marker with a run= slot (#1559)

2026-11-02. The reviewer lane's own skill (`agents/llgenie-pr-reviever/SKILL.md`) instructed
`gh pr review -a` / `gh pr review -r` for a verdict and, when the review-state seat was identity-blocked
("Can not approve your own pull request"), fell back to a plain `gh pr comment` — but neither path wrote
the `<!-- bot-verdict: head=<sha> run=<run id> verdict=… reviewer=<login> -->` marker that
`scripts/auto_merge.py::decide()` reads. Measured at `main@91ef9b5a`: `git grep -n bot-verdict
origin/main -- agents/llgenie-pr-reviever/*` returned nothing, while #1551/#1556 had made the run= slot a
required part of the producer and #1557 was the first real consumer.

## Fix

1. `agents/llgenie-pr-reviever/SKILL.md` — the verdict instruction now opens with the marker posted via
   `make bot-verdict VERDICT=approve|changes HEAD=<full sha> RUN=<run id> REPO=asimov-agent/llgenie
   PR=<n> [REVIEWER=<login>] [NOTE="<evidence anchor>"]`, naming `head=`, `run=`, `verdict=` and
   `reviewer=`, with the run-id rule (a verdict is only valid at the head the run concluded; `auto_merge`
   accepts a marker only at the PR's current `headRefOid`).
2. The identity-blocked fallback is the marker itself: `make bot-verdict` still posts it when `gh pr
   review -r` / `-a` is refused, so a plain comment without the marker is no longer the load-bearing
   step. The evidence anchor (failing criterion, head sha, run id) and the route-to-planner stay.

## Tests / acceptance

`make lane-preflight` and `make check-docs` pass at the PR head; the SKILL.md verifies with
`grep bot-verdict` non-zero on `agents/llgenie-pr-reviever/skills/software-development/
llgenie-pr-review/SKILL.md`. Issue: #1559. Closed by the #1559 PR.
