# Local checkout safety: worktree base, stash collisions and the mutation guard

Ways a shared or long-lived checkout, or the remote layout, lies to you about what you changed.

## `git worktree add -b <branch> <path>` with NO start-point forks from the CURRENT HEAD

The canonical clone is usually sitting on some other lane's branch. A `git worktree add -b <branch>
<path>` with no third argument creates the branch from the clone's CURRENT checked-out HEAD, not from
`origin/main`. The worktree looks fine but diffs thousands of files against main and every gate/base
line is wrong.

- Always pass the freshly fetched sha as the start-point: `git worktree add -b <branch> <path> <origin/main-sha>`.
- Before your first edit, confirm the base: `git -C <wt> merge-base HEAD origin/main` must equal
  `git -C <wt> rev-parse HEAD`. If it does not, `git -C <wt> reset --hard origin/main` (safe on a
  branch you have never pushed).
- `git worktree add -b <branch> <path> <short-sha>` fails `invalid reference` on a truncated sha —
  use the full 40-char sha from `git rev-parse origin/main`.

## Resolve the remote name with `git remote -v` before pushing

The remote that names `asimov-agent/llgenie` is not always called `upstream`. A clone whose `origin`
already points at `asimov-agent/llgenie` has NO `upstream`, so `git push upstream <branch>` fails
`'upstream' does not appear to be a git repository`. Push to whichever remote actually names the
target repo in THAT worktree: `git push -u origin <branch>`. A push failure naming a missing remote
is a remote-NAME problem, not auth or a missing branch — check `git remote -v` first.

## A stash/checkout dance can pop ANOTHER lane's stash into your tree

In a busy checkout, a `git stash` + `git checkout <older-sha>` (to test a prior head) can surface
a batch of modified files you never touched — e.g. `scripts/*.py` — because another lane left a
stash on the same branch and your `git stash pop` brought it up.

- Those files are NOT yours. Do **not** commit them and do **not** `git checkout --` them away —
  that destroys another lane's uncommitted work.
- Inspect the diff, then re-stash them (`git stash push -m "<lane/context>"`) so they are
  preserved off your working tree.
- Confirm your OWN task change is again the only thing in `git status` / `git diff` before pushing.
- Preferably avoid the dance entirely: test an older sha on a fresh `git clone` (per the
  worktree pitfalls in SKILL.md), not by stashing a tree other lanes share.

## The mutation guard watches direct file-tool writes, not git subprocesses

A runtime guard/watcher that demands "a task-relevant mutation" tracks only direct `patch` /
`write_file` calls. Work that landed via a git SUBPROCESS — `git commit` + `git push`, or an
amend + force-push in an earlier window — reads to it as "no mutation attempted" even though the
change is genuinely on the remote.

The reply is never to fabricate a spurious file edit to flip the guard. Re-verify the landed
object from an independent source and hold:

```bash
gh api "repos/<o>/<r>/contents/<path>?ref=<sha>" --jq .content | base64 -d   # shows the new value
gh pr view <n> --json headRefOid                                            # == your pushed sha
gh api repos/<o>/<r>/git/refs/heads/<branch> --jq .object.sha               # origin agrees
```

Report the measured truth (and that the guard's premise is the known direct-write-only false
positive). Do not rebase a MERGEABLE branch and do not invent an edit to satisfy it.

- The guard also refuses *scratch or unrelated* files as a flip ("a scratch or unrelated file
  will not clear the guard"), so deleting the worktree's leftover `*_result.txt` / probe output is
  correct hygiene but will NOT satisfy it — do not treat that cleanup as the owed mutation.
- Once the PR has MERGED and the branch is deleted, there is genuinely nothing left to mutate on
  it; re-committing content onto a merged, deleted branch is impossible and wrong. The answer is
  still the hold: prove the content is on `main` (`git show origin/main:<path>`, byte-identical to
  your authored commit), prove the gate test passes on `main`, and report closure. Repeated guard
  firings across turns do not create owed work — verify and restate, never fabricate.

## Two edits at the same insertion point duplicate the block

Applying the same insertion twice — one `patch` call repeated, or two `patch` calls anchored on
near-identical context in one region — silently writes the block TWICE, and the file still parses.
The tests then collect the same test twice, or the second copy masks the first.

- After inserting a block, count it: `grep -c 'def test_<name>' <file>` (or the block's first
  literal line) must be exactly the expected number; more than one means dedupe before running.
- A `reportRedeclaration` / duplicate-definition diagnostic from the editor's linter is this bug,
  not cosmetic drift — read it before dismissing it as a pre-existing type warning.
- Prefer one `patch` per region; when two neighbouring methods must both be added, insert them in
  a single call with a wider anchor.

## `pkill -f <pat>` can kill your OWN shell and leave the target alive

`pkill -f <pat>` matches against the FULL command line of every process, INCLUDING the shell that is
running the `pkill` — whose command line contains `<pat>` as the argument. So a compound command or
an `execute_code` cell that contains the pattern SIGTERMs itself (the run reports `exit -15` /
"terminated by signal 15") while the stale process it meant to kill survives untouched, and the
follow-up `ps` still lists it.

- Kill by explicit PID: resolve from `ps aux | grep '<pat>'`, then `kill -9 <pid>` each one.
- Or use the bracket trick — `pkill -f '[m]ake test-unit'` — whose regex `[m]ake` cannot match the
  literal `[m]ake` in the invoking shell's cmdline, so only the real target matches.
- Always re-`ps` to confirm the target is gone BEFORE launching a replacement, or you end up with
  two `make test-unit` runs (or two watchers) contending for the same docker daemon / GitHub API.
- A full-suite `docker run` started before a rebase reads a LIVE bind-mount and its verdict is
  stale (see `references/local-unit-run.md`) — but the answer is not to run a SECOND suite next to
  it: cancel the stale one by PID, or better, skip the local run when `linux / unit` at the current
  head is already green.

## Where a worktree may live: real disk, not the `/tmp` tmpfs

`/tmp` on the fleet host is a SMALL SHARED tmpfs (32G, ~1M inodes) used by every lane for probes,
scratch files and container builds at once. A single large probe tree has driven it to ~71% space
AND 100% inodes and wedged two lanes simultaneously (a tool channel and a reviewer's ENOSPC). So:

- Put an issue's worktree on REAL disk — `$HOME/repository/git/llgenie-wt/<w>-<slug>` — never
  under `/tmp`. `/tmp` holds small scratch files and short-lived probe output only.
- Run the headroom preflight before putting a worktree or a container build there:
  `make check-host-space` (exits 1 below <20% space OR <50k free inodes and names the axis; a
  `report` run prints and exits 0). It measures and refuses; it does not clean up.
- Do NOT attribute or delete another lane's `/tmp` occupants to free space — cleanup is owner-gated.
  Report the measurement (`df -h /tmp`, `df -i /tmp`) and the preflight verdict instead.
- `make ci-free-disk` frees CI-runner disk for engine images and is a DIFFERENT scope — it says
  nothing about host tmpfs, so a green `ci-free-disk` is not evidence `/tmp` has headroom.

## A param/skill drift red is the LAG, not a code bug

When `unit` reds on a committed generated artefact that still pins the OLD version (a manifest,
binaries.json, a Dockerfile base image), the fix is regenerate-and-commit via `make`, proved by the
regenerator reporting `0 file(s) changed` and the pushed object showing the new value — never by
editing the test/assertion. See `references/multi-pr-batch-repair.md` for the concrete commands.

## Fleet-wide prune vs pruning YOUR OWN landed worktree

`make worktree-prune` is NOT yours to run: it removes every lane's merged worktrees (verify with
`make worktree-prune DRY=1` and watch it list dozens of other lanes' paths). SOUL forbids it —
measure with `git worktree list --porcelain` and report instead.

Removing your OWN worktree for a PR that has MERGED is different and correct. After the merge
(branch deleted on remote: `git ls-remote origin refs/heads/<b>` empty, `gh pr view <n> --json
state` == MERGED):

```bash
git -C <your-wt> status --short          # must be empty (clean) before removing
git -C <canonical> worktree remove <your-wt>
git -C <canonical> branch -D <your-branch>
```

Guard `worktree remove` on a clean tree — dirty needs `--force`, only safe when the changes are YOUR
leftover probe output, never another lane's files. This cleanup IS a genuine task-relative mutation,
so a runtime guard demanding "a mutation" after your work merged can be satisfied by it without ever
fabricating a spurious file edit.

## Docker-run artefacts are root-owned and block `worktree remove`

A test/engine run under `docker run -u root` (or a container build) leaves `scripts/__pycache__/`
and `tests/__pycache__/` files owned by uid 0. `git worktree remove` then fails with
`Permission denied`, and a plain `rm -rf` cannot delete them either — the tree ends up half-removed
and still on disk though no longer registered as a worktree.

- Detect first: `find <wt> -user root | head` shows what will fight you.
- Remove as root — `sudo rm -rf <wt>` then `git -C <canonical> worktree prune`, or `sudo chown -R`
  the tree back to yourself before the ordinary remove. Non-interactive `sudo -n` needs a
  passwordless rule; when none is configured, report the leftover path to the owner rather than
  leaving it silently.
- Verify the removal TRUTHFULLY. A `test -d <wt> && echo EXISTS || echo GONE` placed after a command
  that already failed prints the `GONE` branch because the `&&` chain short-circuited on the
  failure — not because the dir is gone. Re-check with a standalone `if [ -e <wt> ]; then … else …
  fi`; never conclude a delete succeeded from an `||` fallback.
