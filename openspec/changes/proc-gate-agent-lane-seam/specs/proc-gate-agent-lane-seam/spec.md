# proc-gate-agent-lane-seam — spec

## ADDED Requirements

### Requirement: Gate — production subprocess confined to the seam

The `subprocess-without-returncode` policy (issue #797) is enforced by `scripts/check_proc_gate.py`
in **scripts/ and agents/**/scripts/** as well as top-level scripts — a bare `subprocess.run` /
`subprocess.check_output` / `subprocess.Popen` in an enforced population is allowed ONLY inside
`scripts/proc.py` (the seam) or on a line carrying a `# proc-allow: <reason>` comment.

#### Scenario: a bare subprocess call in an agent-lane script is refused

Given a file under `agents/**/scripts/` that calls `subprocess.run([...])` with no `# proc-allow:` on
the call line. When `check_proc_gate.py check` runs, the gate exits 1 and names the `file:line` as a
bare site in an enforced population. The seam and `# proc-allow:` remain the only two escapes.

#### Scenario: a `# proc-allow:` site is the tracked remainder

Given a file under `agents/**/scripts/` that reads `.returncode` before use and carries a
`# proc-allow: <reason naming the inspection and #2229>` comment. When `check_proc_gate.py check`
runs, the gate exits 0 and `report` lists the site in the allow-list census.

### Requirement: Tests — the behavior harness is surfaced, not gate-red

The `tests/` population is scanned and enumerated in the census so the class is never invisible, but
a bare subprocess site there is not a gate red: a test's whole job is to spawn subprocess and assert
on its output, and hard-gating it would force a whole-tree carve.

#### Scenario: a bare test subprocess is surfaced, not refused

Given a file `tests/test_x.py` that calls `subprocess.run([...])` in the test body. When
`check_proc_gate.py check` runs, the gate exits 0, and the tests population appears in the output as
a surfaced census count.

### Requirement: Migration — rc-dropping sites route through the seam

The sites that dropped the return code and read `.stdout` unconditionally move onto
`scripts.proc` (`run_text` / `run_ok`), so a git/gh failure raises `ProcError` instead of reading as
`""`.

#### Scenario: a migrated site turns a failure into a loud error

Given `measure_live_admission.py` and `resolve-fleet-triple.py` routing their subprocess through
`scripts.proc.run_text`. When the underlying `git` command fails, the caller sees a `ProcError`
naming the command and exit code — never an empty string consumed as "no data".
