# 2026-11-09 — ci-verdict's OWN final line says RED, never "no verdict" (issue #2222)

#2279 fixed the `ci_scope.py` summary sentence that misstated a real RED as `0 failures`, but the
`ci-verdict` judge's FINAL stderr line still fired `FAILED: run <id> has no verdict — see the
summary line above` for EVERY red exit — including a genuinely-red verdict that IS a verdict.
Measured on run 42454987236 (issue #2222): `linux/unit FAILED`, summary `verdict=red success=9
failure=1`, and the last line still read `has no verdict`. A board quoting the LAST line of a red
verdict got the #2061 confusion back one layer lower.

`scripts/ci_verdict.py::main`'s exit line is now verdict-aware: a `red` verdict ends with
`FAILED: run <id> is RED — … FAILED job(s); a red verdict HAS a verdict, and it is red`, a `none`
verdict keeps the #1111 wording (where "no verdict" is exactly the point), and a green judged run
the head's unjudged reds force RED names the UNJUDGED RED cause. Exit code, `verdict`, `counts`,
summary lines and the check-run payload are untouched. Regression test pins the new RED line and
the unchanged NONE line (tests/test_ci_verdict.py 60 passed).
