# inline-check-all-steps — tasks

Issue: [#305](https://github.com/asimov-agent/llgenie/issues/305)

## 1. Extract every step

- [x] 1. Fix `_steps()` in `scripts/code_review.py`: end a `run:` block at the first non-blank line
      indented at or below the `run:` line, so every step is returned (measured 13 → 105 blocks over
      the committed workflows).
- [x] 2. Measure the real tree: `_steps()` per workflow vs. real `run:` count — 13 vs 105 pre-fix.

## 2. Do not trade a false negative for a false positive

- [x] 3. Add `_code_only()`: strip quoted prose from a `run:` block but keep `$( ... )` and backtick
      substitutions, so `fix-bot.yml`'s quoted commit message is not filed while a script run in a
      substitution still is.
- [x] 4. Run the check over the real tree: 0 findings, and the two prose false positives gone.

## 3. Pin both directions

- [x] 5. Add `test_a_violation_in_a_step_that_is_not_last_is_still_a_finding` (the false negative).
- [x] 6. Add `test_a_script_name_in_a_quoted_message_is_prose_not_a_command` (the false positive).
- [x] 7. Add `test_a_script_in_a_substitution_is_still_a_command` (the guard on the fix).
- [x] 8. Prove 5 and 6 fail against the pre-fix code and pass against the fix.

## 4. Verify

- [x] 9. `tests/test_code_review.py` → 29 passed in `llgenie/test:latest`.
- [x] 10. `make lint`, `make check-wiring`, `make check-docs`, `make check-dispatch-forms` and
      `make openspec-validate NAME=inline-check-all-steps` exit 0.
- [x] 11. `make test-unit` green (see the PR's checks).
