# The ci-verdict gate contract names the settled-row refusal (issue #2146)

## What changed

`docs/BOTS.md` documents `ci-verdict`'s exit codes and its skip/neutral rules, but never the
settled-row guard — the only way the judge refuses a run at all. A maintainer debugging an exit-2
verdict had no doc that named the refusal. `docs/ARCHITECTURE.md`'s `CI entrypoints` census and its
`ci-verdict.yml` paragraph had the same gap.

Measured 2026-11-08 at `origin/main 287e3135`: `grep -niE "require_settled|mid-upload|not settled"`
in `docs/BOTS.md` returned nothing. The behavioural guard is real and load-bearing — commits
`3871da4b` (#2017) and `648896aa` (#2051) made the judge refuse a jobs listing whose rows are not
all settled — and the guard is additive to the skip/neutral contract the doc already spells out.

This vehicle writes the guard into both prose surfaces:

- **`docs/BOTS.md` `make ci-verdict` block** now states: the judge NEVER judges a mid-upload run —
  `require_settled` refuses (RuntimeError, exit code 2, no check-run posted) any jobs listing with
  a row that is not `status: completed` with a non-empty `conclusion` (issues #2017, #2051).
- **`docs/ARCHITECTURE.md` ci-verdict paragraph** now names the same settled-row prerequisite beside
  the holds-the-run-to-its-decision sentence.

No `scripts/ci_verdict.py`, workflow, or test edited — this lane files and routes, never implements.

## Verification

- `grep -niE "require_settled|mid-upload|settled" docs/BOTS.md` → hits in the `make ci-verdict` block
- `grep -niE "settled" docs/ARCHITECTURE.md` → hit in the `ci-verdict.yml` paragraph
- `make -s lint check-docs check-wiring check-pr-authors check-issue-bodies check-pr-hygiene` → rc 0
  at the head
