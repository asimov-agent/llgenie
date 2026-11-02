# ci: engine-bump commit must not claim issue #107 (generated-template fix, #1588)

- **Issue:** #1588 (red check-pr-closing on automated engine-bump PR)
- **Change:** `.github/workflows/engine-bump.yml` — the generated bump commit message no longer
  begins with `Issue: #107 — …`. That line was a genuine `check-pr-closing` claim (issue #1329/#1417)
  to a **closed** meta-issue (#107, COMPLETED 2026-10-11) that a rolling engine-bump PR never closes,
  so the gate demanded an adjacent `closes #107` generated bumps never emit → every automated bump red.
  The commit now reads `Automated engine pin bump (weekly rolling pin; closes no issue): …`; the
  informative Fix/Benefit/Technical body is unchanged, and no gate is weakened (the adjacent-keyword
  check stays exactly as it is).
- **Test:** `tests/test_engine_bump_pr_body.py` —
  `test_generated_commit_message_does_not_trip_the_closing_gate` parses the workflow's `msg=$(printf` line,
  renders it through bash, and asserts the generated commit claims no issue and passes `check_squash`.
  Guard-proven both directions: the planted OLD wording makes the test red (claims `#107`); the fix
  restores green (0 claims).
- **Lane:** ci-pipelines-maintainer (gate source; the finding was dispatched to this lane).
- **Status:** fix lives in the generated-commit template, not in `check_pr_closing.py`; the body's
  `(issue #107)` prose is a reference, not a claim, and stays.
