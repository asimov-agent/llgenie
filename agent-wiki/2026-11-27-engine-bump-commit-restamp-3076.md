# Engine-bump commit text restamp (issue #3076)

## Change

The producer side now restamps the bump lane's COMMIT acceptance block before it pushes.
`scripts/engine_bump_restamp.py` gained a commit-text mode (`--commit-in/--commit-out/--engine/
--run/--image-run`), exposed as `make engine-bump-commit-restamp`; `.github/workflows/
engine-bump.yml` calls it between `git commit` and `git push` and amends in place only when the
message changed.

## Measured

- `make -s engine-bump-commit-restamp ENGINE=ollama RUN=12345 COMMIT_FILE=<scratch>/commit.md
  COMMIT_OUT=<scratch>/restamped.md` rc=0; one `PLACEHOLDER` token replaced; `grep -c PLACEHOLDER
  <out>` = 0.
- `python3 -m pytest tests/test_engine_bump_restamp.py -q -p no:cacheprovider` rc=0, 42 passed.
- `make -s check-workflows` rc=0; `make openspec-validate NAME=engine-bump-commit-restamp-3076`
  rc=0.

## Why no head sha in the commit proof

A self-amending commit cannot name its own final sha; stamping the pre-amend sha would be stale at
the live head (issue #2288). The commit mirror therefore cites `rc=0 run=<id>` (the reader gates
accept the run-id form), while the PR body keeps the head-stamped clauses the composer already
renders.
