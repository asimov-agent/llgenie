# main-ruleset gate (#1400)

The repository's only branch protection is the `main` ruleset (id 24862727, enforcement active), and
its full rule list was exactly two: `deletion`, `non_fast_forward`. There was **no**
`required_status_checks` rule and no merge queue, so a red CI run could land on `main` entirely
authorised at the platform layer (#1309's "main stays green" was a promise, not a guarantee). The gap
rotted silently because nothing read the ruleset and alarmed.

Verified against the spec (2026-11-07, origin/main @ 58e10771):

- `make check-main-ruleset` (scripts/check_main_ruleset.py) reads the live `main` ruleset and exits 1
  when `required_status_checks` is missing or a pinned context is not listed; exits 2 (UNKNOWN, never
  clean) when the ruleset cannot be read. The pinned floor is the 10 contexts a real merged PR emits
  (guard, ci-images, scanner-images, the seven `linux / *` jobs minus top-tier, ci-verdict); the pin is
  additive, so a legitimate pipeline addition never reds it. `linux / top-tier` is deliberately not
  pinned: its check-run spelling depends on the `ci:slow` label (measured `(none)` vs `(run)`), and
  pinning either would deadlock the other side.
- `main-ruleset.yml` is the consumer (daily-except-Monday 07:31 UTC, minute 31 owned by no other bot —
  issue #275; plus `workflow_dispatch`), and its red completion is routed by `run-failure-reactor` (its
  name is in that workflow's `workflow_run.workflows` roster), so the failure files/updates a deduped
  issue instead of being a definition nobody runs. It never runs in a PR and never mutates.
- `main-ruleset-apply` (APPLY=1) is the owner-admin-only add-only PUT: it appends
  `required_status_checks` to the existing rules and keeps `deletion`/`non_fast_forward`. DRY prints the
  body; a non-admin ruleset PUT returns 404 (measured), so the flip is the owner's one command.
- 8 unit tests prove the guard catches the bug: the live gap fixture is RED, the covered fixture
  (the scripted apply's outcome) is GREEN, a partial list names exactly the missing context, an extra
  context is not a finding, report exits 0, apply is add-only and DRY. `make openspec-validate
  NAME=main-ruleset-status-checks` passes; `check-workflows`, `check-wiring`, `check-docs`,
  `check-dispatch-forms`, `test_bot_pipeline_isolation` all green.

What remains owner-admin-only (stated on #1400, never hidden): running `make main-ruleset-apply APPLY=1`
with an admin token and then re-verifying acceptance criterion 1/2/3 (the live rule present, a red PR
reads BLOCKED on a throwaway, a green PR reads clean). This change ships the measure-and-alarm control
and the exact scripted update; the platform mutation is outside a non-admin lane's reach.
