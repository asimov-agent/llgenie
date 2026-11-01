# Fix the un-owned linux/unit main-red — registry-liveness cron + guard (#1407)

The `linux / unit` gate (`make ci-unit`) went red on main and stayed unowned: ruleset 24862727
lists no required status check, so the red (run 41323218791, head 5c5df3d1 — originally the
`openspec-tasks-check` proc-seam red, archived by #1408) was merge-sailed by #1397/#1406 without
a tracker. When this lane claimed it at origin/main 3c12b4de, a full `make ci-unit` exposed the
live head-red as **two unit-test failures**, both introduced by #1397's `registry-liveness.yml`:

- `test_no_workflow_shares_a_minute`: the new workflow claimed cron minutes 11, 29 and 47 —
  already owned by `search-smoke` (11), `rebase-bot` (29) and `architecture-bot` (47), violating
  the "each bot its own odd minute" rule (issues #275/#301).
- `test_every_guard_step_is_byte_identical`: the actor-guard roster is derived to be exactly
  `len(_dispatchable()) + 1` (24 dispatchable + ci.yml = 25 sites). `registry-liveness` has
  `on: schedule + push` only — it is **not** dispatchable — so its copy-pasted guard was a 26th,
  unroster'd site.

Fixed in `.github/workflows/registry-liveness.yml` (one file): moved the three schedule crons to
free odd minutes (35/49/1, verified free on all seven weekdays) and removed the guard job
entirely — a non-dispatchable workflow needs no actor guard, and the roster test pins exactly 25
sites. `tests/test_workflow_guards.py` + `tests/test_bot_pipeline_isolation.py` pass (22 passed);
`make check-workflows` and `make check-wiring` pass. Full `make ci-unit` rc 0 proven by the
`linux / unit` CI run at the fix head (run id quoted in PR body). The change carries its own
`docs/changes.d/<stem>.md` row (issue #934/#1123 discipline).

Not covered: the `check-engine-launchers` stale on the local dev host (host has launchers
installed from an older registry; the CI runner has none and the original CI run passed it) —
not part of this red; and rebasing ongoing PRs is `llgenie-pr-merge-conflict`'s lane.
