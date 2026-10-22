# Tasks — auto-merge-approve-first (issue #524)

- [x] 1. OpenSpec change: `proposal.md`, `specs/auto-merge-approve-first/spec.md`, this checklist
- [x] 2. `scripts/auto_merge.py`: `_clear_review()` (approve → merge → `--admin` → defer), `try_approve()` wired in with an optional second identity, `_gh(token=)` passing it through the environment
- [x] 3. `.github/workflows/auto-merge.yml` forwards the optional `APPROVER_TOKEN`; `scripts/check_secret_output.py::SECRET_VARS` lists it
- [x] 4. `tests/test_auto_merge.py`: approve-before-merge without `--admin`, self-authored fallback, approver-token path (token never in argv), refused merge defers on the PR
- [x] 5. `README.md` + `agent-wiki/2026-10-22-auto-merge-approve-first.md`
- [x] 6. Verified: `pytest tests/test_auto_merge.py tests/test_secret_output.py` → 63 passed; `make test-unit` → 5016 passed, 6 deselected; `make lint`, `make check-docs`, `make check-wiring`, `make check-workflows` green; `make openspec-validate NAME=auto-merge-approve-first` valid
- [x] 7. PR opened against `asimov-agent/llgenie:main` closing #524
