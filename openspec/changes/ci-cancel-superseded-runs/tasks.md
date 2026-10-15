# Tasks

- [x] 1. `ci.yml` declares `concurrency: {group: ${{ github.workflow }}-${{ github.ref }}, cancel-in-progress: ${{ github.event_name == 'pull_request' }}}`, with the comment stating why the group is per-ref and why a `push` run is never superseded
- [x] 2. `tests/test_ci_concurrency.py`: the group is per-ref, `cancel-in-progress` is evaluated (true for `pull_request`, false for `push`), every pull-request workflow declares a group, and no workflow cancels every run unconditionally
- [x] 3. `make test-unit` names `tests/test_ci_concurrency.py` (a test file in no target runs in no gate)
- [x] 4. README's CI section states the trigger + cancel behaviour; `agent-wiki/2026-10-15-ci-cancel-superseded.md` records the work and the measured evidence
- [x] 5. Issue #288 reflects the wiring as implemented, and `make openspec-validate NAME=ci-cancel-superseded-runs` exits 0
- [x] 6. Progress: `tests/test_ci_concurrency.py` passes in `llgenie/test:latest` (4 passed) and fails on the pre-fix `ci.yml` (3 failed, no concurrency block), `make lint` exits 0, `make check-wiring` reports no unwired document
- [x] 7. CI on the pushed branch: the PR pipeline's `linux / unit` job passes on the pushed head, and the PR is left open for review (never merged)
