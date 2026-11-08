# 2026-11-08 — ci-verdict RED names its failing jobs (issue #2061, PR #2278)

The `ci-verdict` judge's summary line said `NO VERDICT: N job(s) unaccounted for — 0 failures is
not a verdict` even when the run's own `guard` job FAILED (`counts["failure"] = 1`) — the exact
#1111 sentence written for a run with *zero* failures, repeated beside a real `guard FAILED` line.
Measured live on run 42505834364 (judged 42505814856 @ 1238c15e): `success=0 failure=1
no-verdict=9` and the summary still claimed `0 failures`. `scripts/ci_scope.py::verify()` now
splits the non-green sentence by cause: a RED verdict names the failing job(s)
(`RED: 10 job(s) unaccounted for — 1 FAILED (guard), 9 unaccounted, 0 pending`), a NONE verdict
keeps the #1111 wording unchanged, and a GREEN verdict adds nothing. `verdict`, `counts` and the
exit code are untouched; regression tests pin the new RED line, the unchanged NONE line and the
unchanged green case (local suites green: test_ci_verdict.py 55, scope/bot/publish 68).
