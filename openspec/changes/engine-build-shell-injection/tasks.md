# Tasks: engine-build-shell-injection

- [x] Move `inputs.producer_run` / `github.triggering_actor` into the step's `env:` block
- [x] Shell reads `$PRODUCER_RUN` / `$TRIGGERING_ACTOR` only (no expressions in `run:`)
- [x] Extend the existing #2578 lock test with the #2622 assertions (no expression in the
      step's shell; both env bindings present)
- [x] Focused battery hermetic: `pytest tests/test_check_engine_pins_published.py` → 30
      passed rc=0 (post-fix tree)
- [x] Semgrep proof: `make security-scan TOOL=semgrep` then parse
      `security-reports/semgrep.json` → 0 run-shell-injection findings at
      `.github/workflows/engine-build.yml` (43 repo-wide findings unchanged otherwise)
- [x] `make check-workflows` rc=0 (after dropping the empty-expression token from the
      step comment, the #330 raw-text parse pitfall)
- [x] `make lint` / `make check-docs` / `make openspec-validate` rc=0
- [x] Pair registered: `agent-wiki/2026-11-13-engine-build-shell-injection-2622.md` +
      `docs/changes.d/2026-11-13-engine-build-shell-injection-2622.md`
- [x] `make lane-preflight` → preflight OK; branch pushed; PR opened vs #2622
