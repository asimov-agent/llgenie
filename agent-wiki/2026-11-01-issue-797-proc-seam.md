# 2026-11-01 — issue #797: one subprocess policy seam

Implements #797. `scripts/proc.py` is now the ONE place `scripts/` calls `subprocess.run`; it exposes
exactly three named policies — `run_text` (stdout, raises on non-zero), `run_ok` (rc/stdout/stderr,
never raises, caller inspects), `run_checked` (raises naming the command and its stderr) — and no
policy default, so a caller must state its policy by naming the function.

## What was verified

- `scripts/proc.py` with the three policies + `OSError`/`TimeoutExpired` never swallowed (tests
  `tests/test_proc.py`).
- The two swallowing version-probe wrappers (`detect_server._run`, `engine_skills._run`) delegating to
  `run_checked` — a probe whose command exits non-zero now raises instead of returning `""` (the
  silent "no version" seam). Loud-outcome tests run a command exiting 1 on the binary path.
- The 9 remaining no-exit wrappers (ci_images, engine_image, engine_bump, architecture_bot,
  resolve_run_pr, scanner_image, security_bot, security_bumps, security_issues) delegating to `run_ok`,
  preserving every message and exit code.
- `scripts/check_proc_gate.py` — the gate: `subprocess.run`/`check_output`/`Popen` in `scripts/` is
  allowed only in `scripts/proc.py` or on a line carrying `# proc-allow: <reason>`. `make check-proc-gate`
  reds on a new bare call (proven by a test); `make proc-gate-report` prints the census. Wired into
  `make ci-unit`.
- The remaining direct `subprocess.*` call sites (the tracked remainder of the 142 the issue scopes out)
  each carry a `# proc-allow:` reason, so the gate is green and the census names a shrinking number.
- `make openspec-validate NAME=proc-seam` passes; the challenge has an OpenSpec change with the proposal,
  spec + tasks, all tasks ticked.

## Out of scope (deferred to linked issues)

- The `gh`-shaped claim-path reads — #799 (this change leaves those `_gh` copies + `run_failure_reactor._gh_soft` to that issue).
- Migrating all remaining direct call sites in one pass — the `# proc-allow:` census is the tracked remainder.

PR: #<PR>, issue #797.
