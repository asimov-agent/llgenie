# Tasks: restamp bump commit text before the lane pushes

## 1. Spec first

- [x] OpenSpec change `engine-bump-commit-restamp-3076` created with `make openspec-new` and a
      proposal/spec/tasks delta before the code edit (proven: `make openspec-validate
      NAME=engine-bump-commit-restamp-3076` rc=0, `Change ... is valid`).

## 2. Producer seam

- [x] `scripts/engine_bump_restamp.py` gains `--commit-in/--commit-out/--engine/--run/--image-run`
      and a block-scoped `restamp_commit_text()`: measured run-stamped clauses from the SAME
      composer, subject/tail byte-preserved, refuse to write when a stub survives (proven:
      `make -s engine-bump-commit-restamp ENGINE=ollama RUN=12345 COMMIT_FILE=... COMMIT_OUT=...`
      rc=0; `grep -c PLACEHOLDER <out>` = 0).
- [x] `.github/workflows/engine-bump.yml` calls the seam between `git commit` and `git push`, and
      amends only when the message differs (proven: `make -s check-workflows` rc=0,
      `[workflows] OK`).
- [x] Hermetic tests cover stub replacement, no-heading messages, image runs and the CLI refusal
      (proven: `python3 -m pytest tests/test_engine_bump_restamp.py -q -p no:cacheprovider` rc=0
      42 passed).
- [x] The change note and one-row `docs/changes.d/` fragment are present and indexed in
      `CHANGES.md` (proven: `make -s check-docs` rc=0).
