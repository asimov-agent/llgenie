# proc-seam

## ADDED Requirements

### Requirement: one subprocess policy seam with exactly three named policies

`scripts/proc.py` MUST be the ONE place `scripts/` calls `subprocess.run`/`check_output`/`Popen`, and it
MUST expose exactly three named policies, each with NO policy default (the caller states its policy by
naming the function):

- `run_text(cmd, *, timeout=None, cwd=None, env=None) -> str` — returns stdout; raises on a non-zero exit.
- `run_ok(cmd, *, timeout=None, cwd=None, env=None) -> subprocess.CompletedProcess` — never raises on a
  non-zero exit; returns the completed process so the caller inspects `rc`/`stdout`/`stderr`.
- `run_checked(cmd, *, timeout=None, cwd=None, env=None) -> str` — returns stdout; raises on a non-zero
  exit, naming the command and its stderr.

`scripts/proc.py` MUST NOT define any other subprocess-wrapping policy.

#### Scenario: the three policies answer "what happens when the command fails"

- **Given** `scripts/proc.py`
- **When** each of `run_text`, `run_ok`, `run_checked` is called with a command that exits non-zero
- **Then** `run_text` and `run_checked` raise, `run_checked` naming the command and its stderr, while
  `run_ok` returns a `CompletedProcess` whose `returncode` is non-zero
- **And** `make check-wiring` reports `scripts/proc.py` wired and its test module tested
- **Test:** `tests/test_proc.py` exercises all three policies against a command that exits 1

### Requirement: a failed version/hardware probe is loud, never an empty string

`scripts/detect_server._run` and `scripts/engine_skills._run` MUST no longer return `""` for a failed
command. A probe whose underlying command exits non-zero MUST be reported as a failure (raised), so the
caller never reads a silent `""` as "no version".

#### Scenario: a probe whose command exits 1 is loud

- **Given** a probe path that runs a command which exits 1 on the binary path
- **When** `detect_server` / `engine_skills` runs the probe
- **Then** the probe raises (a loud failure), never returning `""`
- **Test:** runs a command that exits 1 on the binary path and asserts the loud outcome

### Requirement: the 11 no-exit-code wrappers state their policy or are deleted

None of the 11 wrappers that previously never inspected `.returncode` MUST survive: each call site either
MUST state its policy (via a `proc.*` call or an allowed direct `subprocess.*` with
`# proc-allow: <reason>`) or MUST be deleted, with every existing message and exit code preserved.

#### Scenario: a no-exit-code wrapper either states a policy or is gone

- **Given** one of the 11 modules that previously defined a `_run`/`_sh`/`_gh`/`run_gh` wrapper that
  never read `.returncode`
- **When** the gate scans `scripts/` for a `subprocess.*` call at the old wrapper site
- **Then** the call is either inside `scripts/proc.py`, on a `# proc-allow:` line, or absent — never a
  bare un-policied `subprocess.*` call
- **Test:** the proc gate + `tests/test_proc_seam_gate.py` name any surviving site

### Requirement: the 16 checking wrappers collapse onto run_checked

Each of the wrappers that read the exit code and raised on non-zero MUST now delegate to `run_checked()`,
MUST preserve the existing message (naming the command and its stderr) and MUST preserve the exit code.

#### Scenario: a checking wrapper's failure names the command and its stderr

- **Given** a checking wrapper whose original body ran `subprocess.run` and raised on non-zero naming
  the command and stderr
- **When** it is called with a command that exits non-zero
- **Then** it raises with the same exit code and a message naming the command and its stderr
- **Test:** the module's existing failure-path test stays green; the message assertion is unchanged

### Requirement: a gate confines subprocess.* in scripts/ to the seam

Inside `scripts/`, a `subprocess.run`/`check_output`/`Popen` call is allowed ONLY in `scripts/proc.py` or
on a line carrying a `# proc-allow: <reason>` comment. The gate MUST run from `make ci-unit`, and a NEW
bare `subprocess.run` in any other `scripts/*.py` MUST red the gate (proven by a test).

#### Scenario: a new bare subprocess.run in scripts/ reds the gate

- **Given** a `scripts/*.py` file containing a `subprocess.run` call with no `# proc-allow:` and not in
  `scripts/proc.py`
- **When** the gate is run
- **Then** it fails, naming the file:line
- **Test:** a test adds such a file to a scratch tree and asserts the gate fails

### Requirement: the proc-allow census is printed

`make ci-unit` (or a report target) MUST print a census of the remaining direct `subprocess.*` call
sites in `scripts/`, each named with its `# proc-allow:` reason, so the tracked remainder is a visible,
shrinking number rather than an invisible count.

#### Scenario: the census names the remaining direct call sites

- **Given** `scripts/` contains at least one `# proc-allow:`-tagged `subprocess.*` site outside
  `scripts/proc.py`
- **When** the census report target is run
- **Then** it prints each remaining site's `file:line` with its reason and a total count
- **Test:** `tests/test_proc_seam_gate.py` runs the report against a fixture tree

Refs: #797; #799 defers to this seam for the claim-path `gh` reads.
