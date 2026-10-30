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

### Requirement: the migration must not share mutable module state across test modules

A file migrated to `from scripts import …` keeps the SAME module object a sibling test module already
imports. That is the point of one import root, but it also means a module-level global one test database
mutates (e.g. `scripts.hf_auth._rate_limited`, which `hub_open` increments across 429s and only a non-429
resets) is shared too. A test module whose cases DEPEND on that state MUST reset it per test (a
function-scoped autouse fixture via `monkeypatch`, so pytest restores it), so the whole suite passes in
alphabetical order regardless of which module ran first.

#### Scenario: a retry test does not inherit a sibling module's exhausted budget counter

- **Given** `test_hf_auth` runs first and drives `scripts.hf_auth.hub_open` with an always-429 opener to
  exhaustion, leaving `_rate_limited` at `RATE_LIMIT_WAITS+1`
- **Given** `test_hf_download_retry` imports the same `scripts.hf_auth` and asserts one full 429 budget
- **When** each retry test starts (autouse fixture resetting `_rate_limited` to 0)
- **Then** the chunk download and preflight probe retry tests pass after `test_hf_auth`, in alphabetical
  order
- **Test:** `tests/test_hf_download_retry.py::_fresh_rate_limit_budget` + the alphabetical run of
  `tests/test_hf_auth.py tests/test_hf_download_retry.py` (both 18 pass)

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
