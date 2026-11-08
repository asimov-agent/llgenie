# Tasks — engine-build-dispatch-and-live-log

- [x] 1. `.github/workflows/engine-build-pr-trigger.yml`: pass `BRANCH="${{ github.head_ref }}"` (a `pull_request` checkout is detached, so the literal `HEAD` ref was a 422).
- [x] 2. `Makefile`: `engine-build-pr-trigger` forwards `$(if $(BRANCH),--branch "$(BRANCH)",)` into the script.
- [x] 3. `scripts/engine_build_trigger.py`: `_dispatch_ref()` (explicit `--branch` → `GITHUB_HEAD_REF` → the checkout's branch → `""`), and `check()` refuses with a message naming both inputs when the ref is unresolvable.
- [x] 4. `scripts/engine_build_trigger.py`: `_workflow_run_args()` gives every input its own `--field` (the old argv handed `push=true` to `gh` as a positional), and a non-zero `gh workflow run` concludes `dispatch-failed` carrying the CLI's error text, which the failure line prints.
- [x] 5. `scripts/proc.py`: `run_live` (fourth name policy — inherited descriptors, non-raising `rc`) and the module/docstring/test-docstring surfaces that count the policies updated.
- [x] 6. `scripts/engine_image.py`: `_sh_live` wired at BOTH `buildx build` call sites; short `pull`/`tag` calls stay on the capturing `_sh`.
- [x] 7. Tests: `tests/test_proc.py` (streams through, `rc` returned, a line readable before the child exits), `tests/test_engine_build_trigger.py` (detached dispatch at `GITHUB_HEAD_REF`, refusal, one `--field` per input, rejection reason), `tests/test_engine_image_matrix.py` (both build steps reach `run_live`, `_sh` refuses a build).
- [x] 8. Proven against the base: the new build-step tests fail on `origin/main`'s `engine_image.py` (a build routed through the capturing `_sh` trips the fake), and the new dispatch tests fail on `main`'s argv/discovery shape.
- [x] 9. Gates: `make lint`, `make check-wiring`, `make check-docs`, `make check-proc-gate`, `make openspec-validate NAME=engine-build-dispatch-and-live-log`.
- [x] 10. Docs: `agent-wiki/2026-11-08-engine-build-dispatch-and-live-log.md` + `docs/changes.d/` fragment + rendered `CHANGES.md` row.
