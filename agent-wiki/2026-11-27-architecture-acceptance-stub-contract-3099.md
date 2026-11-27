# Document the acceptance draft-stub refusal (issue #3099)

## Change

`docs/ARCHITECTURE.md`'s `## Bots` / Structural gates row for `check_pr_acceptance.py`
now states the behavioural change landed at
`3cea715e3bf891c4e0be2c1f578b32eba7550d42`: a proven clause containing an un-replaced
draft-stub token (`PLACEHOLDER`, `HEADSHA`, `MAINSHA`) is not evidence — both the
acceptance reader (`DRAFT_STUB` in `scripts/check_pr_acceptance.py`) and the commit-
checkbox mirror (`scripts/check_pr_hygiene.py`) refuse the tick. Issue #3075 is named
as the reason, with #3078 as the landing PR. The existing run-conclusion / head-seam,
`acceptance_writeback` verdict-ref sha and `review_finalize` seams are kept verbatim.

## Why this is a docs-only fix

The code already enforces the refusal; the architecture row — the written contract a
reviewer reads to predict which `- [x]` will be accepted — did not name it. No gate,
matcher, test, workflow or script changed.

## Verification

- `grep -n 'DRAFT_STUB'` at the audit reference: definition at line 162, enforced at
  line 236 of `scripts/check_pr_acceptance.py`.
- Before the row, the whole document had no occurrence of `DRAFT_STUB`, `PLACEHOLDER`,
  `HEADSHA` or `MAINSHA` in the `check_pr_acceptance.py` clause. After the row all three
  tokens and the refusal are present.
- `make -s changes-index` rc=0; `make -s check-docs` rc=0; `make -s lint` rc=0;
  `make -s check-workflows` rc=0; `make -s lane-preflight` rc=0.
