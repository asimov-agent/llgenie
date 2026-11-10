# Hermetic test runs, census gate, and vehicle-supersession quirks

Measured in real sessions; each line is a rule with its reason.

## Hermetic test runs leave root-owned artifacts

- Run the suite in the pinned image: `docker run --rm -u root -e PYTHONPATH=/repo/scripts -v "$PWD":/repo:rw -w /repo -e HOME=/root llgenie/test:latest python3 -m pytest tests/<file>.py -q -p no:cacheprovider`.
  `-p no:cacheprovider` keeps cache/`--durations` crashes out of the run; the image is the CI-exact env, so a host venv green proves little.
- `-u root` writes `__pycache__/*.pyc` owned by root inside the mounted worktree. Consequences, all measured:
  - `git worktree remove <dir>` fails with `Permission denied`; plain `rm -rf` fails the same way.
  - Clean up with `sudo rm -rf <dir>` before declaring the temp worktree gone. A worktree whose parent refs were deleted (`git update-ref -d`) also breaks its `.git` gitfile — read files via `git show <sha>:<path>` against the main object store, not from that worktree's git.

## The architecture census pointer (`measured at <sha>`)

- `docs/ARCHITECTURE.md` carries a `measured at \`<40-hex>\`` census pointer; `make check-docs` (Makefile census gate, `[census-gate]`) fails when that sha is not a reachable ancestor of the head.
- This is a **shared red**: it reds `scope`/`linux unit` on every docs and code PR whose tree still carries a stale pointer, and on `main` itself. Before blaming a PR's diff, check whether the pointed sha resolves (`git -C <main> cat-file -t <ptr>`) and is an ancestor (`git merge-base --is-ancestor <ptr> <head>`). A red identical on main is the tracked census defect, not the PR's fault — route it to the census vehicle, do not fix it inside an unrelated PR.
- A rebase re-slots commits, so a census re-point commit's needle can name a sha the rebase renumbered; the re-point must follow the needle to the new sha or the gate reds. Disclose that reconciliation on the PR when a rebase lane does it.

## A worktree bind-mount makes the census gate read UNREADABLE

Running the gate battery in the image with `-v <worktree>:/repo` against a `git worktree` checkout makes
`check_architecture_census.py` print `[census-gate] UNREADABLE: git could not read this checkout` and
fail `make check-docs`, even on a clean tree. Mechanism: a linked worktree's `.git` is a **file** naming
the main repo's `.git/worktrees/<name>` path, which is NOT mounted at that path inside the container, so
git inside the container cannot resolve the checkout. This is a bind-mount artifact, not a defect in the
change — CI runs on a full clone and checks the census. Do not chase it and do not edit the pointer to
"fix" it; judge the census leg from a full clone or from CI, never from a worktree-mounted container run.

## A git-ls-files scan reads ZERO tracked files in a worktree-mounted container

The same bind-mount artifact that makes the census gate `UNREADABLE` breaks any test that discovers files
via `git ls-files`: inside `docker run -v <worktree>:/repo`, the linked worktree's `.git` file points at a
path outside the mount, so `git ls-files` returns **0 files**. The symptom is a batch of failures like
`<path> must be in the lint scan list (got 0 files)` — the harness's tracked-file set is empty, not the
change being wrong. `tests/test_lint_linefeeds.py::test_extension_less_file_is_in_tracked_scan` in
particular fails this way (8 parametrized cases, all `got 0 files`) even on a clean tree. The container
also reports `HAS_GIT` — git is present; it just cannot see the repo. Judge any git-ls-files-dependent
scan on the HOST (real git tree) or from CI, never from a worktree-mounted container run, and never edit
the tree to "fix" the empty scan.

## Vehicle supersession — never fork a second vehicle

- When a live PR for an issue is closed unmerged and another PR already implements the same issue, the surviving PR is the vehicle. Re-opening your closed branch under it is a duplicate vehicle (the #824→#832→… cascade).
- The honest completion is: measure that the surviving head actually carries the fix and that its own drift guard passes on its tree; then hold. Do **not** edit the owner's live PR (lane boundary) and do **not** invent a change note / commit to satisfy a generic "no mutation attempted" integrity gate — fabricating a mutation is the violation the gate exists to prevent. State the measured state and hold.
