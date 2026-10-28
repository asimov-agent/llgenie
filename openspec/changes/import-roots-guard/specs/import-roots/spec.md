# import-roots

## ADDED Requirements

### Requirement: a test file does not carry its own import root

`scripts/check_import_roots.py` MUST report a `sys.path.insert`/`append` in any file under `tests/` other
than `tests/conftest.py`, and MUST report a top-level `import <name>` or `from <name> import` where
`<name>` is a module provided by `scripts/`. A file that does not parse MUST be reported as its own
finding rather than skipped.

#### Scenario: a path entry outside the conftest is refused

- **Given** a test file containing `sys.path.insert(0, "scripts")`
- **When** the guard runs
- **Then** it reports a `sys-path` finding naming that file and line, and exits non-zero

#### Scenario: the same module imported through the package is clean

- **Given** a test file containing `from scripts.hf_auth import x`
- **When** the guard runs
- **Then** it reports nothing and exits zero

### Requirement: the guard ratchets instead of blocking on a legacy count

`make check-import-roots` MUST compare the current counts with `tests/fixtures/import-roots-baseline.json`
and fail only when a count **rises**. A missing baseline MUST be a finding. `--update` MUST record the
current counts.

#### Scenario: a new file adding its own root is refused

- **Given** a baseline recorded at the current counts
- **When** a new test file adds a `sys.path.insert`
- **Then** the ratchet reports the increase and exits non-zero

#### Scenario: the migration shrinking the count passes

- **Given** a baseline recorded at 104
- **When** a batch removes ten path entries
- **Then** the ratchet passes without the baseline being edited
