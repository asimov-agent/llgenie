# fix-engine-bump-pr-body-newlines — Tasks

Checklist of record. Each step maps to a spec requirement in
`openspec/changes/fix-engine-bump-pr-body-newlines/specs/engine-bump-pr-body/spec.md`.
Ticked the moment the work is verified with real tool output.

## Fix

- [x] 1.1 Rewrite the base PR-body assignment in
      `.github/workflows/engine-bump.yml` to use `printf '…%s…'` so `\n`
      becomes a real newline (REQ-1).
- [x] 1.2 Rewrite the hard-fail append to use `printf '%b'` so the warning
      lands on its own paragraph after a blank line (REQ-2).
- [x] 1.3 Add `tests/test_engine_bump_pr_body.py` that extracts the run block
      from the workflow, validates it with `bash -n`, and asserts real newlines
      + the hard-fail append for a simulated shell (REQ-1/REQ-2/REQ-3).
- [x] 1.4 `engine_bump.bump` rewrites the unit suite's hardcoded pin asserts
      (full sha, 8-char prefix, tag, tag without `v`) in `tests/` and
      `README.md`, and a Strata bump regenerates `data/strata_models.json`.
      The workflow commits those files (REQ-4).
- [x] 1.5 `tests/test_engine_bump.py::test_bump_rewrites_hardcoded_pin_asserts`
      locks the rewrite against the same assert shapes the bump PRs fail on.
- [x] 1.5b A same-size file that is not a readable GGUF is removed and fetched
      again before the download fails
      (`tests/test_llama_ai.py::test_unreadable_gguf_is_removed_and_refetched`).

## Verify

- [x] 1.6 `make lint` green (REQ-3).
- [x] 1.7 `make test-unit` green (REQ-1/REQ-2/REQ-4 via the new tests).
- [x] 1.8 `make openspec-validate NAME=fix-engine-bump-pr-body-newlines`
      exits 0.
- [x] 1.9 Sync to latest `main`, commit, push, and open the PR to upstream main
      referencing issue #144.
