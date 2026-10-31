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

## Vehicle supersession — never fork a second vehicle

- When a live PR for an issue is closed unmerged and another PR already implements the same issue, the surviving PR is the vehicle. Re-opening your closed branch under it is a duplicate vehicle (the #824→#832→… cascade).
- The honest completion is: measure that the surviving head actually carries the fix and that its own drift guard passes on its tree; then hold. Do **not** edit the owner's live PR (lane boundary) and do **not** invent a change note / commit to satisfy a generic "no mutation attempted" integrity gate — fabricating a mutation is the violation the gate exists to prevent. State the measured state and hold.
