# Tasks

- [x] 1. `scripts/check_secret_output.py`: `secrets-in-run-block` also matches GitHub's own `${{ github.token }}` / `${{ github['token'] }}` inside a `run:` block, named in the failure
- [x] 2. `scripts/check_secret_output.py`: new `whole-stdout-into-output-file` rule (`cmd | … >> "$GITHUB_OUTPUT"` and the `$(cmd) >> "$GITHUB_OUTPUT"` substitution form), with the pipe required to be a SINGLE `|` so shell `a || b` chains that end in a redirect are not flagged (measured while porting)
- [x] 3. `scripts/check_secret_output.py`: new `whole-stdout-into-log` rule (`… | tee /dev/stderr` / `/dev/stdout`), with `tee <file>` still allowed
- [x] 4. Docstring rule list updated (the failure message is the fix instruction) and the widened `secrets-in-run-block` wording
- [x] 5. `tests/test_secret_output.py`: one planted fixture per rule plus one safe counter-shape per rule (`env:`-passed `github.token`, the quoted `echo "k=$(…)"` writer, `tee /tmp/out.log`)
- [x] 6. `README.md`: the two new rows in the "No secret value reaches a log (#283)" table and the widened run-block row
- [x] 7. `agent-wiki/2026-10-19-secret-whole-stdout.md`: the work record (issue #361 + the PR it opens)
- [x] 8. Verification: `pytest tests/test_secret_output.py` (28 passed), `make check-secret-output`, `make check-wiring`, `make check-docs`, `make lint`, `make openspec-validate NAME=secret-whole-stdout`
