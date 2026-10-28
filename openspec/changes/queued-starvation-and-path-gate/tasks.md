# Tasks — queued-starvation-and-path-gate

- [x] 1. `docs/BOTS.md`: **A queue is not a verdict**, after the generated dispatch table (inside it would be overwritten), with two measuring commands, the #801 distinction and the no-push rule.
- [x] 2. Measured before writing: `runner_name` is `null` for an `in_progress` job and `startedAt` is set at enqueue, so neither discriminates; the doc states the measurement that does.
- [x] 3. `scripts/engine_image.py`: `base_matrix(changed)` compares each backend's rendered `Dockerfile.<backend>` with `git show <ref>:…` and emits one `none` row when nothing changed.
- [x] 4. `make list-engine-base-images` (`.PHONY`, `## help`, documented in `docs/ENGINES.md`) — verified three ways: no ref → 4 rows, `CHANGED=origin/main` on an untouched tree → `none`, one changed backend → that backend.
- [x] 5. `.github/workflows/ci.yml`: `engine-matrix` emits `base` from the same ref; `engine-base` takes `matrix: fromJSON(needs.engine-matrix.outputs.base)` and every step carries `if: ${{ matrix.backend != 'none' }}` — no job-level `if:`, no skipped step.
- [x] 6. `tests/test_ci_images.py`: the allowlist admits the second axis's placeholder idiom, and a new test pins the three `base_matrix` outcomes; `tests/test_engine_image_matrix.py` still passes (the `CHANGED=$before` literal is preserved).
- [x] 7. Evidence for the PR: #786 (security-script PR) queued 28 jobs including four `engine-base-*`; #803 (engine bump) queued 26.
- [x] 8. Gates: `check-workflows`, `check-dispatch-forms`, `check-wiring`, `check-docs`, `lint_linefeeds`, `openspec-validate` exit 0; `pytest tests/test_ci_images.py` 27 passed.
