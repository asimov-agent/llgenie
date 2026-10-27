# Tasks

- [x] 1. `tools/requirements.in`: pin the direct runtime deps exactly (`numpy==2.4.6`, `gguf==0.19.0`, `huggingface_hub[cli]==1.30.0`) and state the scan's own fixed versions as annotated floors (`certifi>=2026.10.18 # GHSA-6q48-6c7w-9gw2`, `filelock>=4.2.1 # CVE-2026-112940`, `urllib3>=2.8.0 # CVE-2026-97687, CVE-2026-97689`)
- [x] 2. `tools/requirements-dev.in`: the same three annotated floors, so the test image's combined install compiles above them
- [x] 3. Regenerate `tools/requirements.txt` and `tools/requirements-dev.txt` through `make -C tools generate-requirements` / `generate-requirements-dev` — never by hand
- [x] 4. `tests/test_requirements_pins.py`: exact direct pins, annotated floors, compiled pins at or above every floor in both files — discovered by `make test-unit`
- [x] 5. `agent-wiki/2026-10-27-security-requirements-pins.md` + a `CHANGES.md` index row (issue #754 + the PR it opens)
- [x] 6. Verification: every package the report names is compiled at or above its `fixed` version in both compiled files (measured: `certifi==2026.10.23`, `filelock==4.2.4`, `urllib3==2.8.0`; the run-40537601445 artifact is a snapshot of the OLD image, so re-running the verdict on it can only restate its findings — the next scheduled scan re-scans the new pins), `make check-security-bumps`, `make check-docs`, `make lint`, `make test-unit` green, `make openspec-validate NAME=security-requirements-pins` valid
