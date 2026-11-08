# acceptance-gate-pr-not-a-lane

## Why

`make check-pr-acceptance`'s rollout-lane half (#1859) derives an umbrella's candidate lanes from
the umbrella's OWN `#<n>` citations, then holds the close for any referenced number that is OPEN and
cites the umbrella back. It never distinguished an issue from a pull request: GitHub answers the
issues API for both, so `state` is `open` for a PR too. Measured on PR #1696 (run `42440654316` job
`128608975606`, head `0d09448b`, 2026-11-08T02:57:37Z): #1558's body cites `#1696` — the OPEN pull
request whose own body cites `#1558` back — and the gate emitted two `rollout-lane-open` violations
whose evidence named the PR being checked. A PR whose job is to close an umbrella could therefore
never be the thing that closes it; the only escape was closing the PR.

A second, independent instance: #1694 was CLOSED at 2026-11-04T21:09:51Z (`stateReason: COMPLETED`)
yet a 2026-11-08 run still emitted a `rollout-lane-open` finding for it, because the gate iterated
the PR's `closes` targets without asking whether the target was still open. A `closes #N` aimed at an
already-closed issue cannot auto-close anything, so it cannot be a premature close.

## How

`scripts/check_pr_acceptance.py`:

- `_fetch_issue_meta` reads the issue over `gh api repos/<repo>/issues/<n>` and returns
  `(body, state, is_pull_request)` — the REST record carries the `pull_request` key that the
  `gh issue view --json` fields do not expose. A merged PR's `state` is reported as `MERGED`
  (`state: closed` + `pull_request.merged_at`), so both closed and merged targets are named.
- `rollout_lane_findings` `continue`s on a referenced number that is a pull request, whatever its
  state: a PR is the vehicle for an umbrella, never a lane of it.
- `main()`'s `check` loop reads the close target through `_fetch_issue_meta` and short-circuits the
  lane probe when the target is already `CLOSED`/`MERGED`. The `acceptance_verdict` half still runs
  on a closed target — a closed issue's unticked criteria are still unproven, and #2088's scope
  excludes that half.

## Benefits

- A PR can close the umbrella it implements: the umbrella's lane population is what #1859 intended
  (open *issues* doing rollout work), not the PR that lands the result.
- A stale `closes #N` on an already-closed issue stops being fatal, and the gate stops reddening on
  a control that cannot fire.
- No weakening: an OPEN **issue** lane that cites the umbrella back still holds the close (#1859),
  and an unreadable reference still never holds.
