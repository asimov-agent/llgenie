# Auto-merge treats cancelled/neutral as non-green (#1423, #1250 Finding B)

2026-11-02. `scripts/auto_merge.py` merged a PR whose CI run was `cancelled` (killed mid-flight) or
whose `ci_verdict` check-run was `neutral` (a superseded head — by design `neutral`, never `success`).
A cancelled run is not a docs-only head: it is a run killed before it could finish, and the `neutral`
verdict explicitly says this head is NOT the one that owns the result. Neither may merge.

`RED_CONCLUSIONS` now includes `cancelled` and `neutral`, so `failing_checks()` defers the PR and
names the non-green conclusion. `skipped` stays the one non-red "no verdict": a docs-only pull
request has no `linux` job (§843, measured #1385). The `enforce_events` scan and the reactor roster
are unchanged; `ci.yml` still gates the merge job on `conclusion == 'success'`.

Measured at main `62d8c60b`. Guard-proofed: the new `test_a_cancelled_or_neutral_check_defers_the_merge`
merged under the pre-fix logic (the exact defect) and defers after the fix; `test_a_skipped_check…`
still merges the docs-only head. Issue: #1423. Related: #1250.
