# Cleaning up a finished worktree: the test image leaves root-owned `__pycache__`

Companion to the "OpenSpec change dirs are root-owned after `make openspec-new`" section in SKILL.md —
same root cause (a container runs as root over a mounted repo), different victim.

## Symptom

```
$ git worktree remove /home/asimov/repository/git/llgenie-wt/<name> --force
error: failed to delete '/home/asimov/repository/git/llgenie-wt/<name>': Permission denied
$ git branch -D fix/<name>
Deleted branch fix/<name> (was <sha>).        # this part works
```

The branch and the git registration are gone, but a ~3 MB directory with the repo's files is left behind.
A later `git worktree list` no longer shows it, so the cleanup *looks* finished.

## Why

`make test-unit` runs `python -m pytest` inside `llgenie/test:latest` with the worktree bind-mounted. The
container's Python writes `__pycache__/` owned by `root:root`. `git worktree remove` deletes as your user
and cannot unlink root-owned files or the directory containing them.

## Diagnose first (do not just retry)

```bash
find <worktree> ! -user "$(id -un)" -printf '%u:%g %m %p\n' 2>/dev/null | head
ls -d <worktree>            # does it still exist at all?
git worktree list | grep <name>
```

- Root-owned paths listed → the directory is the blocker; delete it as root (below).
- Nothing root-owned and the path does not exist → the worktree was already removed; the error was a stale
  registration or a race with another agent's cleanup. Nothing to do.
- `git worktree prune --verbose` prints nothing in either case — prune only drops admin entries for
  directories that no longer exist, so it does NOT clean a leftover directory whose registration is gone.

## Fix: delete through the image (no sudo needed)

Mount the PARENT of the worktree, not the worktree itself:

```bash
docker run --rm -v /home/asimov/repository/git:/w -w /w llgenie/test:latest \
  rm -rf /w/llgenie-wt/<name>
```

Then confirm: `find /home/asimov/repository/git -maxdepth 3 -name '<name>'` must print nothing.

## Related cleanup that IS yours

- `git branch -D fix/<name>` — the local branch, after the PR merged (squash merge ⇒ `-D`, not `-d`).
- The remote branch: `git ls-remote origin '<branch>'` and `git ls-remote fork '<branch>'` should both be
  empty after the merge deleted it. This clone pushes to `fork` and PRs to `origin` (see SKILL.md).
- Leave the sibling worktree container (`llgenie-wt/`) and other agents' worktrees alone — one agent, one
  worktree.
