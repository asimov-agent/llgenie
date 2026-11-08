# docs/BOTS.md: the rollout-lane hold never applies to a PR or a closed issue (#2128)

**Implements:** issue #2128 — a docs-only refinement of the `docs/BOTS.md` rollout-lane paragraph that
#2088 left one rule behind the code.

The paragraph (measured at `2e04c9c2`, `docs/BOTS.md` lines 818-823) said a `#<n>` the umbrella cites
in its body that is still OPEN and cites the umbrella back is held as `rollout-lane-open` — and no
more. #2088 (PR #2095, squash `89e1b2ec`) changed `scripts/check_pr_acceptance.py` so the gate now
reads each referenced number through `_fetch_issue_meta` (which answers for an issue AND a PR, since
`gh api repos/<repo>/issues/<n>` carries the `pull_request` key) and:

1. **skips a pull request whatever its state** — the PR that implements an umbrella must never
   register as that umbrella's own open lane and hold its own close (measured on PR #1696, run
   `42440654316`, job `128608975606`, head `0d09448b49`, plus #1694);
2. **skips a `closes` target that is already CLOSED** (`stateReason COMPLETED` or a merged PR) as a
   *lane* — a closed lane is not open work, though its unticked criteria are still unproven and
   reported by the other half of the check.

The doc never said either, so a reader of `docs/BOTS.md` would still expect a PR citing the umbrella
to be held. `check-docs` stayed green throughout because the #2088 note trio was complete (note +
`docs/changes.d` row + `CHANGES.md` index) while the prose lagged the code — the exact drift class the
docs lane exists to close (`agent-wiki/` note, not a code change).

## What changed

`docs/BOTS.md`, the rollout-lane sentence, only: it now names the two exclusions (#2088) beside the
#1859 hold, and keeps the "derived from the umbrella's own citations, probed live" tail. No
`scripts/`/`tests/`/workflow change.

Implied by the issue's `How we fix it`; acceptance is the diff shown above and this note trio.
