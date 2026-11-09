# Scheduled engine/registry maintenance jobs get bounded ceilings + a gate (#2317)

ATS = main@5cc544cf via f99be26e, measured 2026-11-09.

## What changed

The four scheduled engine/registry maintenance **step** jobs carried no `timeout-minutes`,
so a hang inherited GitHub's 360-minute default. This change bounds each from its observed
wall time and adds a `make check-workflows` rule that reds whenever a `schedule`-triggered
workflow's job (any job that runs steps — a `uses:` caller cannot hold a ceiling, #882)
declares no `timeout-minutes`.

| workflow | job | ceiling | measured wall time (real run) |
|---|---|---|---|
| `engine-bump.yml` | `plan` | 20 | 12–27s (42495434034, 41483337124, 41455039526) |
| `engine-bump.yml` | `bump` | 30 | tensorfold 5m01s (42495434034) |
| `engine-bump-rebase.yml` | `rebase` | 20 | 15s (42478956638) |
| `registry-sync.yml` | `sync` | 60 | 32–40m (40682255828, 40414178202, 40402053825) |

## Verification

- `make check-workflows`: Green (0 violations) on the fixed tree.
- Negative control (sabotage): removing `sync`'s `timeout-minutes: 60` reds
  `make check-workflows` (rc=1, `[workflows] 1 violation(s)` naming
  `registry-sync.yml`/`sync`) and fails the tree-scope test
  `test_every_scheduled_job_in_this_repository_declares_a_ceiling`; restoring it
  returns Green (rc=0, all 31 `test_workflows_valid.py` + 107 in the touched suites pass).
- `test_workflows_valid.py` adds five resident cases: scheduled-no-timeout → report,
  scheduled-with-timeout → pass, non-scheduled → out of scope, scheduled `uses:` → skipped,
  repro-tree → green.

Implements issue #2317. See PR <pr-in-body>.
