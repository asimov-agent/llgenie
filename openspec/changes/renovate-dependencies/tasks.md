# renovate-dependencies — tasks

- [x] 1. `renovate.json` with pip_requirements + pip-compile + dockerfile/docker-compose managers, grouped PRs, and the generated/vendored `ignorePaths`
- [x] 2. Conservative automerge: patch/pin/digest only, `automergeType: pr`, `platformAutomerge: false`; container base images never automerge; `github-actions` disabled
- [x] 3. `scripts/check_renovate.py` with `check` / `report`
- [x] 4. `make check-renovate` / `renovate-report`, declared `.PHONY`, `check-renovate` wired into `make ci-unit` and classified in `scripts/issue_bot_gates.py`
- [x] 5. `tests/test_renovate_config.py` (nine rules on fixtures + the real config clean), passing in `make test-unit`
- [x] 6. `docs/RENOVATE.md` written and linked from `README.md`; `make check-docs` green
- [x] 7. `make check-renovate` exits 0; `ci.yml` asserted unfiltered with an engine-image job (a base-image bump builds images)
