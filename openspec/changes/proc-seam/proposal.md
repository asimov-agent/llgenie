# proc-seam — proposal

Issue: [#797](https://github.com/asimov-agent/llgenie/issues/797)

## Why

Thirty modules each define their own subprocess helper under five spellings (`_run`, `_sh`, `_gh`,
`run_gh`, `_cmd`), and the wrappers disagree on what a non-zero exit means. Measured per function body:

- **11 of the 30 never inspect `.returncode`** — the call's failure is dropped and the caller receives
  a value as if nothing went wrong.
- **2 of those 11 turn a failed command into `""`** — `detect_server._run` (on timeout) and
  `engine_skills._run` (on OSError/timeout). Both feed **version / hardware detection**, so a probe that
  fails reads "no version", which is the benign branch. That is a silent-failure seam exactly where a
  silent failure is most expensive (the `pipefail`/SIGPIPE class, #616/#605, reads the same code
  optimistically).
- Alongside the wrappers: **142** direct `subprocess.run`/`check_output`/`Popen` call sites in
  `scripts/`, with no single rule for whether a non-zero exit is checked.

## What Changes

1. **`scripts/proc.py`** — one subprocess policy seam exposing exactly three named policies:
   - `run_text(cmd, *, timeout, cwd, env)` → stdout, raises on non-zero;
   - `run_ok(cmd, *, timeout, cwd, env)` → returns rc/stdout/stderr, never raises, caller inspects;
   - `run_checked(cmd, *, timeout, cwd, env)` → raises naming the command and its stderr.
   No defaults: the caller must choose a policy by naming it.
2. **Migrate the two swallowing wrappers first** — `scripts/detect_server.py` and
   `scripts/engine_skills.py` no longer return `""` for a failed command; a probe whose command exits
   non-zero is reported as a failure (a test runs a command exiting 1 on the binary path and asserts the
   loud outcome).
3. **Then the 11 no-exit-code wrappers**, one module per commit, keeping every existing message and exit
   code identical — each call site either states its policy or is deleted.
4. **Then the 16 checking wrappers** collapse onto `run_checked()`.
5. **A gate** — inside `scripts/`, `subprocess.run`/`check_output`/`Popen` are allowed only in
   `scripts/proc.py` or on a line carrying `# proc-allow: <reason>`, checked from `make ci-unit`; plus a
   `# proc-allow:` census printed by `make ci-unit` (a report target) so the remaining direct call sites
   are a visible, shrinking number.

## Not covered

- Migrating all 142 direct call sites in one change — the gate's allowlist is the tracked remainder, and
  it shrinks per module.
- The `gh`-shaped read at the centre of the claim protocol — #799, because the transport there must also
  stay cached per run. This change leaves the claim-path `gh` reads (and the three byte-identical `_gh`
  copies plus `run_failure_reactor._gh_soft`) to #799.
- Makefile inline snippets — they keep their own exit-code handling (`set -e` in the shell); this gate is
  scoped to `scripts/*.py`.

Refs: #797 (this issue), #799 (the claim-path half it defers to), #616/#605 (the pipefail class the
silent-`""` seam belongs to).
