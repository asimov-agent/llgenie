# Tasks: ci-scope-base-ref-behavior

## 1. Baseline

- [x] 1.1 Measure on the current tree: the `classify the diff` step has the `if [ -z "$BASE" ]`
  fallback and no test executes it (grep `tests/` for a behavioural fallback test).

## 2. The harness

- [x] 2.1 A helper extracts the `run:` body of scope.yml's ci-scope step and substitutes the
  `${{ github.base_ref }}` / `${{ github.event_name }}` expressions for a given event shape.
- [x] 2.2 A stub bin dir records `make` and `git` argv (each call appended to a record file) and the
  body is executed under `bash` with that dir first on PATH.

## 3. The behavioural pins

- [x] 3.1 Empty base_ref ⇒ recorded make invocation names `BASE=origin/main`.
- [x] 3.2 Empty base_ref ⇒ stdout contains the "No github.base_ref" fallback line.
- [x] 3.3 A real base_ref ⇒ recorded invocation names `BASE=origin/<ref>` and the fallback line is
  absent.

## 4. Negative controls

- [x] 4.1 Planted variant without the `if [ -z … ]` block ⇒ resolution property reports failure
  (recorded ref `BASE=origin/`).
- [x] 4.2 Planted variant without the `echo` line ⇒ visibility property reports failure while
  resolution still holds.

## 5. Gates

- [x] 5.1 `pytest tests/test_ci_scope.py tests/test_ci_scope_trigger.py` exits 0.
- [x] 5.2 `make lint` and `make check-docs` exit 0.
