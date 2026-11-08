# Authoring and delivery rules for this lane

Always-on conventions that apply to every doc/issue/PR this lane produces. SKILL.md is at its size
ceiling, so these live here — read this file before writing any artifact or cutting any worktree.

## Write `$HOME`, never `/home/<user>`

In SOUL.md, skills, references, docs, issue bodies, PR bodies, commit messages, and the commands inside
all of them.

A versioned instruction that hardcodes one machine's account name is not reproducible on any other
host, and it contradicts the portability rule the tree itself carries. This applies to prose *and* to
fenced example commands — a `git -C /home/<user>/...` in a code block is the same defect as a
sentence.

**The carve-out is real and narrow.** A context that is *parsed rather than executed* must NOT use
`$HOME`, because nothing expands it there:

- a systemd unit — `ExecStart=`, `EnvironmentFile=`, `WorkingDirectory=`
- a crontab line outside a shell
- a YAML/JSON value a program reads

For those keep an absolute path or the native form (`%h` in systemd). Do not "fix" a unit file into a
form that silently fails. When the literal appears in an `agents/**/*.md` file, fix the prose;
`scripts/*.py` may legitimately build an absolute path from `pathlib.Path.home()`.

**Redact, don't quote, when reporting.** A note or PR body that shows the offending path as evidence
re-commits the defect into the tree. Show it as `<hardcoded-home>/...` and assert the count instead
(`grep -cF` on the literal returns 0).

Verify before committing, on the diff and not the working tree:

```bash
git diff origin/main HEAD | grep '^+' | grep -c '/home/<user>'   # must be 0 on ADDED lines
```

Match on added lines only: a removal legitimately contains the path, and counting the whole diff
reports the fix as a defect.

## Create worktrees under `$HOME`, never `/tmp`

The host `/tmp` is a small tmpfs shared by every lane with a hard **inode** ceiling. When it fills,
`git worktree add` fails without naming the cause, and `make`/docker steps die on scratch files — a
bare `125` from docker is often nothing but a full `/tmp`. Check both axes before a build:

```bash
make check-host-space     # space AND inodes; exits 1 below threshold
df -i /tmp
```

Put new worktrees under `$HOME/...`. Cleaning up your own scratch dirs is fine; a lane's vehicle is
not — never prune another lane's worktree, report it instead.

## A stacked PR dies when its base merges

GitHub **closes** a stacked PR whose base branch merges, and it cannot be reopened
(`reopenPullRequest` fails). The head recorded on the closed PR is also frozen, so pushing to the
branch does not revive it.

Sequence when the base lands:

1. `git fetch origin +refs/heads/main:refs/remotes/origin/main` and rebase the branch onto the new
   `main` — the base's commits are already upstream and drop out.
2. Remove the base's issues from your PR body: they were closed by the base's commits, and now that
   those commits are gone, `check-pr-closing` reds on a closing-set mismatch.
3. Refresh the `AGENTS:` and `BASE:` lines to the new `main` sha.
4. Open a **fresh** PR from the rebased branch; the old one stays closed.

While stacked, say so plainly and do not arm onto `main` — arming a stacked PR lands it into its base,
not into `main`, and merging it alone would carry the base's files with it.
