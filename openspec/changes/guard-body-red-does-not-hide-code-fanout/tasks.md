# guard-body-red-does-not-hide-code-fanout

## Tasks

- [x] Decouple the linux code fan-out from the guard's body-text red (ci.yml `always()` + `if`)
- [x] Fall back `top_tier_rows` to the PR-safe `["none"]` placeholder on a guard with no output
- [x] Classify gate-blocked rows as `blocked` and name the gate in the ci_scope verdict
- [x] Name a RED verdict's failing jobs and keep the #1111 sentence for zero-failure NONE
- [x] Regression tests: negative control (guard-body-red no longer yields NO VERDICT), the
      post-fix code-measured shape, the caller-block attribution, and the green/exit-code guards
      in tests/test_ci_images.py + tests/test_ci_slow_rows.py
- [x] local suites green (test_ci_verdict 57, test_ci_images + test_ci_slow_rows 45)
- [x] `make openspec-validate NAME=guard-body-red-does-not-hide-code-fanout` green
- [x] docs: agent-wiki note + docs/changes.d fragment + CHANGES.md row (same commit)
