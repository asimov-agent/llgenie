# Tasks

- [x] 1. `openspec/changes/registry-liveness-dispatch` — proposal + `specs/registry-liveness-dispatch/spec.md` (WHEN/THEN, a `- **Test:**` line per scenario) + this checklist
- [x] 2. `.github/workflows/registry-liveness.yml` — after the `ALL=1` hard-fail (kept verbatim), an `always()` step parses each `NOT PUBLISHED <engine>:<pin8>-<hash8>-<variant>` tag, derives engine+arch, and dispatches `engine-build` with `push=true` for every missing cell; grants `actions: write` on the caller workflow
- [x] 3. `scripts/engine_image.py` — new `collect(engine, arch, force, push)` + `collect` CLI subcommand: every enabled CI cell of an engine as one sweep, failure named not fatal, exit 0 only when all succeeded
- [x] 4. `scripts/run_failure_reactor.py` — the pins-publish failure class (`registry-liveness` / `NOT PUBLISHED` / `manifest unknown`) files an issue naming the publish remedy
- [x] 5. `tests/test_engine_build_collect.py` — sweep-collect regression (first cell fails → later cells still attempted, successes built/pushed, failure named) + pinned-unchanged-params-change-still-repins lock
- [x] 6. `tests/test_check_engine_pins_published.py` — workflow-shape test: the dispatch step, `actions: write`, `-f push=true`, arch-deriving parser, and `exit "$rc"` (ALL=1 hard-fail) untouched
- [x] 7. Verification: `tests/test_engine_build_collect.py` 2 passed, `tests/test_check_engine_pins_published.py -m "not network"` 12 passed, `tests/test_run_failure_reactor.py` 29 passed on a fresh worktree cut from `origin/main@8e4e564f`; `make check-pr-agents-line` + `make check-pr-acceptance-form` OK locally
- [x] 8. `make openspec-validate NAME=registry-liveness-dispatch` exits 0 (structure of this change validates)
