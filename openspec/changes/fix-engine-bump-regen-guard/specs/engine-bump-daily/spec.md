# fix-engine-bump-regen-guard — spec

## MODIFIED Requirements

### Requirement: regen guard
`make generate-engine-params` after a bump MUST change only
`containers/engines/params/<id>.json` and `containers/engines/dockerfiles/<id>/*`
for the bumped engine. The regen MUST write only that engine
(`make generate-engine-params ENGINE=<id>`): rewriting every engine fails the
guard and no bump PR opens. The guard MUST read the working tree (`git status
--porcelain`), not make's stdout. A diff anywhere else (including another
engine's params) MUST fail the job. Make's own directory lines MUST NOT fail it.

#### Scenario: bump of A cannot change B's params
- **Given** a bump of engine A whose regen changes engine B's params
- **When** the regen guard reads the working tree
- **Then** the job fails naming B's file
- **Test:** `tests/test_engine_bump.py::test_regen_guard_isolates_engine`

#### Scenario: make directory lines are not changed files
- **Given** `make generate-engine-params` prints `make[1]: Entering directory ...` and changes only the bumped engine's params
- **When** the regen guard runs
- **Then** it does not fail, and the allowed path is the bumped engine's params file
- **Test:** `tests/test_engine_bump.py::test_regen_guard_ignores_make_directory_lines`
