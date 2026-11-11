# Makefile and container seams that bite when adding a target

Concrete traps hit while adding a prune/audit target and iterating its tests. Read this
before adding a make target that shells out to `gh`, or before debugging a write that
fails `Permission denied` inside a fresh worktree.

## `REPO` is the checkout path, not a slug

`Makefile` defines `REPO := $(shell pwd)`. A recipe that needs `OWNER/REPO` for `gh`
MUST use its own variable (`SLUG=`), never `$(if $(REPO),$(REPO),owner/name)` — that
fallback can never fire, because `REPO` is always set, and `gh` answers
`expected the "[HOST/]OWNER/REPO" format, got "/abs/path"`. `issue-cleaner-scan`,
`issue-cleaner-apply` and `queued-alarm` all pass `$(REPO)` and fail on their own
documented invocation for this reason; a new target must not copy them. Pin it in a
test that reads the recipes: fail when a `gh`-facing `--repo` carries `$(REPO)`.

## `.PHONY:` is a backslash-continued block

A test asserting "target X is declared phony" cannot filter lines by
`startswith('.PHONY:')` — the block spans many lines, so the target sits on a
continuation. Walk the block while the current line ends with `\`, or ask `make -pn`.
(`make check-wiring` enforces phony-ness for every parsed target; a missing entry
bites at run time as `make: '<target>' is up to date.`)

## `make openspec-new` leaves a root-owned change directory

The target runs the OpenSpec CLI in a container as `-u root`, so the scaffolded
`openspec/changes/<name>/` is owned by root and the first `write_file` into it fails
`Permission denied` (same fate as `openspec/changes/archive` and `openspec/specs`).
Chown it from a throwaway container before writing anything:

    docker run --rm -v "$PWD:/w" -w /w alpine:latest \
        sh -c 'chown -R 1000:1000 openspec/changes/<name>'

## Fast test iteration without waiting for `make test-unit`

`make test-unit` runs the whole discovered suite (~20 min). To iterate one file, run it
in the SAME test image, as the invoking user:

    docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp \
        -v "$PWD:/repo" -w /repo llgenie/test:latest \
        python -m pytest tests/test_<name>.py -q -p no:cacheprovider; echo "REAL EXIT=$?"

- `--user` + `-e HOME=/tmp` keep the worktree free of root-owned `__pycache__`/
  `.pytest_cache`; without them the container writes as root and the checkout becomes
  partly undeletable later (see `development/git-maintenance`, "Stale worktrees").
- Print the exit status explicitly: piping a run through `tail` reports the pipe's
  status, so a red suite can read as `exit_code: 0` and be reported green.
- Fixture git repos need an identity passed in (`GIT_AUTHOR_NAME`/`GIT_COMMITTER_*`
  plus `GIT_CONFIG_GLOBAL=/dev/null`), otherwise `git commit` fails inside the image.

## A recipe that runs pytest must run it through a seam

The runner's `/usr/bin/python3` has **no pytest**. A recipe line like `python3 -m pytest tests/x.py` is
therefore an always-red step on every CI job that reaches it (`No module named pytest`), and it can stay
latent for weeks when the job that would run it has no matrix rows. Recipes may only invoke pytest through a
seam that provides it:

| seam | what it is |
|---|---|
| `$(TEST_RUN)` | the test image in CI, the venv on a dev host |
| `$(call engine_test,ENV=…)` | the test image with an engine's env; the shape `test-engine-image` uses |
| `$(ENGINE_TEST_RUN)` | the older engine-smoke form |
| `$(PY)` / `$(VENV_GUARD)` / `$(NATIVE_GUARD)` | the gguf venv, which carries pytest (host + Metal-only targets) |
| `.../bin/python -m pytest` | an explicit venv interpreter |

Verify without running: `make -n <target> ENGINE=<id> ARCH=<arch>` must render `docker run …
llgenie/test:latest` (plus the env vars the test needs, e.g. `LLGENIE_TEST_ENGINE`,
`LLGENIE_PUBLISHED_PULLED=1`). Then run the target end to end when it is affordable — one published-image
target takes minutes and proves pull + digest + flags + serve at once.

Lock it with a text test over the Makefile: join `\`-continuations, skip recipe comments, and fail any
recipe line that runs pytest without a seam; expose the rule as a function so a synthetic Makefile proves
both directions (a bare `pytest tests/x.py` is caught and named, a container/venv call is not). A guard that
only runs against today's clean Makefile proves nothing.

## An empty matrix means the target has no CI coverage at all

A job whose name prints unexpanded (`test-published-${{ matrix.engine }}-${{ matrix.variant }}`), ends
`-none-none`, shows `skipping`, or has 0 jobs is a placeholder: the matrix resolved to nothing. When the
matrix is derived from **changed** files, a Makefile/harness-only push runs zero rows, so an end-to-end target
edited in that PR is never exercised until an unrelated engine change re-populates it — exactly how a broken
recipe line survives review. Fixes are cheap: run the target locally against the real artefact, and keep a
hermetic text test on the recipe itself.

## Checkout debris after merged PRs

`make worktree-prune` is the sanctioned cleanup; run `DRY=1` first and read the kept
reasons. Eligibility is a MERGED PR whose `mergeCommit` is an ancestor of the base —
never a name pattern, a commit date, or `git branch --merged` (this repo squash-merges,
so a merged branch's tip is never an ancestor). Branches with no PR, a CLOSED PR, a
dirty worktree, a detached worktree or the main checkout are kept by design: a bulk
`git branch -D` over a guessed pattern deletes unreviewed work. Report counts
(branches, worktrees, `du -sh ../llgenie-wt`) before and after — "pruned" without
numbers is not evidence.
