# Tasks — umbrella-open-lane-gate

- [x] Extend `scripts/check_pr_acceptance.py` with a lane-enumeration + open-lane verdict: when a
      PR closes an umbrella, derive referenced issues from its live body, probe each referenced
      issue's live body + state, and emit a `rollout-lane-open` finding for each referenced issue
      that is OPEN and cites the umbrella back; a referenced issue that does NOT cite the umbrella
      back or is CLOSED is not a lane and does not hold.
- [x] Add tests: red on a fully-ticked umbrella with an open backward-citing lane; green when the
      referenced-open issue does not cite the umbrella; green when all referenced lanes are closed;
      green when the umbrella has no open referenced lanes at all.
- [x] Wire the lane probe through the same live-gh seam the gate already uses, so the fake-gh test
      double can answer the per-reference body+state probes.
- [x] Update `docs/BOTS.md` (the `check-pr-acceptance` paragraph) to state that a close is also
      held while a referenced rollout lane is open.
- [x] Change-note triad (agent-wiki + docs/changes.d fragment + CHANGES.md row) per #1123.
- [x] Validate: `make openspec-validate NAME=umbrella-open-lane-gate`, `make check-docs`,
      `make lint`, and the unit suite.
