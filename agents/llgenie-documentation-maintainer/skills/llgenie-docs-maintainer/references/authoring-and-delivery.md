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

## Reconcile live and tree in BOTH directions — the tree can be the truncated side

`make sync-agent-profile PROFILE=<p> CHECK=1` is read-only and compares live
`$HOME/.hermes/profiles/<p>/` against `agents/<p>/`. Read its verdict as a **direction**, not a count:

- **live ahead** — the tree is the truncated side. Copy live→tree, then `cmp` each file to prove
  identity, and fold the result into your branch. A write-mode sync here would have *dropped* the live
  content.
- **tree ahead** — live is stale; sync tree→live, but only after proving every live-ahead sibling is a
  pure superset (line-set diff: each tree-only line is present live, rephrased at most), never a
  whole-profile force.

Never run write-mode `sync-agent-profile` to "fix" a drift you have not classified per file: it
overwrites whichever side it copies over, so a lane whose live is richer loses rules silently. Justify
the direction with a **line-set** diff (`diff <(sort a) <(sort b)`), not byte counts — a file can grow
in bytes while losing a rule (two added paragraphs, one removed rule).

**Live moves mid-session.** The running bot keeps writing its own skills, so a live-ahead set measured
earlier is stale by your final push. Re-measure parity at the end of the task and timestamp the claim;
"live and tree agree" is only true at the moment it was measured.

**A repeatedly-firing verification check means an un-made mutation, not a missing report.** When the
same "prove it" check returns after several passes of more read-only evidence, stop measuring and look
for the tree change you have not made — usually versioning a live-only edit into the tree, or folding a
repaired file into the branch. Another report over the same facts is not the mutation.

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

## Push a rebased branch: fetch by explicit refspec, then read the wire head

`--force-with-lease` refusing after your own push is almost always a **stale local tracking ref**, not
another lane. Do not conclude someone else touched the branch until you have fetched the real tip:

```bash
git fetch origin +refs/heads/main:refs/remotes/origin/main
git fetch origin <branch>
git log --oneline -1 origin/<branch>     # is this your own last push, or a stranger?
```

If the wire head is your own previous push, re-push with `--force-with-lease --force-if-includes` (the wire head is your own last push — an ancestor of an amended head; after a rebase use the plain lease instead). A
plain `--force` here is how a repair another lane made gets silently discarded. After the push, read
the PR's `headRefOid` and `mergeable` back — a push that exits 0 has not necessarily moved the PR.

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
