# Tasks: semgrep-refresh-invalid-cron

- [x] 1. Fix the workflow schedule: `1 6 * * 15` → `1 6 15 * *` in
      `.github/workflows/semgrep-rules-refresh.yml` (value + its header comment).
- [x] 2. Add the `workflow-cron` rule to `scripts/check_workflows.py` (stdlib parser over
      GitHub's cron grammar; docstring bullet; findings() wiring; OK line extended).
- [x] 3. Pin the rule in `tests/test_workflows_valid.py`: the shipped bad cron reds the gate;
      valid-grammar fixtures (incl. repo's `*/2`, lists, weekday lists) pass; the repo's own
      crons all pass. (122 tests green across every module touching `check_workflows`.)
- [x] 4. Update `docs/ARCHITECTURE.md` (the two recorded `1 6 * * 15` mentions) to the fixed cron.
- [x] 5. Gates green: `make check-workflows`, `make check-wiring`, `make lint` — all OK;
      `make openspec-validate NAME=semgrep-refresh-invalid-cron` exit 0.
- [x] 6. Measured against GitHub itself on the fixed file: `workflow_dispatch` to the fork head
      ref carrying `1 6 15 * *` is ACCEPTED (no `422 invalid cron`), while the same call against
      the broken fork main still answers `422 invalid cron attribute "1 6 * * 15"` — the gate's
      grammar and GitHub's parser agree in both directions. (Run `43073777356`: a real `refresh`
      job with real steps — the first healthy run this workflow ever produced.)
