---
name: worktree-branch-hygiene
description: Use when pruning stale git worktrees or merged branches.
version: 1.0.0
author: Hermes Agent
license: CC-BY-4.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [git, worktree, branches, squash-merge, cleanup, containers]
---

# Worktree and branch hygiene

## When to Use

A checkout has accumulated dozens of worktrees or local branches and nobody knows which hold
unlanded work; a repo's per-agent workflow creates `feat/<kebab>` worktrees and the agent stops at the
PR; or a prune attempt fails with `Permission denied` / `cannot remove working tree`. Also load it
before writing cleanup automation, so the eligibility rule is proven rather than guessed.

## Rule 0 — the default is report, never delete

Audit output is the deliverable; deletion needs an **explicit owner instruction**, not an inference from
the audit. Ship the report target first (`git worktree list --porcelain` + the PR map, one table, counts
and `du -sh`) and treat the destructive target as unbuilt until someone asks for it in words. A report
that cannot delete is the supported operation.

The trees that make this rule load-bearing are a specific class: **merged tip + no open PR + dirty**.
They look prunable by every ancestry signal and hold the only copy of the work. On a real fleet a survey
found four of nine in exactly that state, plus the main checkout itself — which is the argument for the
rule, measurable before any prune runs.

## Rule 0b — "ahead N commits" is not evidence of unique work

A worktree ten commits ahead of its remote is usually an **older base**, not unpublished work: a diff
between an older and a newer base is non-empty by construction. Before moving or resetting any branch,
compare **per-file blob equality** against three sources — the base branch, the target PR's remote, and
the branch's own remote. A file matching one of the three is older; a file matching none is worth
reporting. Only after that proof may the worktree be re-pointed, and re-pointing never force-pushes.

Corollary: `git reset --hard` is never part of a sweep. `git status --porcelain` and
`git log --oneline <remote>..HEAD` first — anything listed is work on no remote, invisible to every
check, and destroyed silently by a reset.

## Rule 1 — ancestry cannot prove a branch landed in a squash-merging repo

A squashed branch tip is **never** an ancestor of the base, so every ancestry signal lies:

| signal | verdict on squash-merged work | why |
|---|---|---|
| `git branch --merged` | says unmerged | the squashed commit is a new commit |
| `git merge-base --is-ancestor <tip> main` | false | same |
| `git branch -d` | refuses | same |
| `git cherry main <branch>` | shows `+` patches | patch-ids differ after the squash |
| `git diff --stat main...<branch>` | often empty | tree identical — useful, but not proof of a merge |

Eligibility comes from the **pull request**, and only from it: the branch is the head of a MERGED PR
**and** that PR's `mergeCommit.oid` is on the base.

```bash
gh pr list --repo OWNER/REPO --state all --limit 500 \
  --json number,state,headRefName,mergeCommit      # state per head, one call
git worktree list --porcelain                       # path, HEAD, branch|detached, bare
```

## Procedure — audit, then prune

1. **Classify every local branch** (`git for-each-ref --format='%(refname:short)' refs/heads`) against
the PR map: PR MERGED with its merge commit on the base → prunable; PR OPEN/CLOSED-unmerged → keep; no
PR at all → keep. Print the reason for every kept branch; a silent omission is unauditable.
2. **Report before acting**: counts of prunable / closed / no-PR / dirty, plus `du -sh` of the worktree
root, so the user sees the size of the decision.
3. **Dry run first** (`DRY=1` / `--dry`): the plan must print every keep reason and mutate nothing.
4. **Remove**: `git worktree remove <path>` (no `--force` — a dirty worktree must stop you), then
`git branch -D <branch>`. If the worktree removal fails, **keep the branch**: deleting it first strands
a directory with no ref.
5. **Prune refs**: `git fetch --all --prune`, then re-count branches and worktrees and re-measure disk.
6. **Only then delete leftover directories** whose branches are gone (container recipe below).
7. **Re-run the prune after clearing those directories.** A `worktree remove` that failed on
permissions still unregistered the worktree, so the branch it held is deletable — but only once the
directory is out of the way. The second pass is what turns "117 prunable, 30 removed, 87 kept" into
"117 removed"; the prune is idempotent, so just run it again and re-count. `scripts/audit-and-prune.sh`
does all seven steps in one call (`DRY=1` audit, `DRY=0` prune with both passes):
`bash scripts/audit-and-prune.sh` — run the audit first and quote its numbers.

## Rule 2 — never prunable, whatever history says

- the repository's **main checkout** (`git worktree list` lists it first);
- the worktree the run is **executing in** — git refuses to remove the directory it stands in
  (`fatal: validation failed, cannot remove working tree`), so exclude it up front instead of failing;
- any **detached-HEAD** worktree (it holds no branch, so no merge licenses deleting it);
- any **dirty** worktree (report the files);
- a worktree a **live session is using** — a merged PR's tree can still be open in another agent's
  shell. Before removing one, look for a process under it and for files touched in the last half hour:
  `ps -eo pid,args | grep '<worktree root>'` and
  `find <path> -newermt '-30 minutes' -type f | grep -v -E '__pycache__|\.pytest_cache|/\.git/'`.
  Hold back the tree that hits, and say so — the eligibility rule licenses deleting merged work, not
  interrupting a run;
- a branch whose PR is closed-unmerged, or that names no PR — that is a human decision.

## Rule 3 — root-owned files a containerized run leaves behind

Running tests/CLI stages in a container with `-u root` and the repo bind-mounted leaves
`__pycache__` / `.pytest_cache` owned by root. `git worktree remove` then fails with
`error: failed to delete '<path>': Permission denied` **after** unregistering the worktree: the git
side is gone (it no longer appears in `git worktree list`), the directory stays with hundreds of MB
in it, `du` never moves — and the BRANCH still exists, so a single prune pass reports it as kept.
Assume no passwordless sudo, and plan for **two passes** (step 7 below).

```bash
# iterate locally as yourself, so nothing root-owned is created
docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD:/repo" -w /repo IMG \
  python -m pytest tests/test_x.py -q -p no:cacheprovider

# clear leftovers through a container as root
docker run --rm -v "$PWD:/w" -w /w alpine:latest sh -c 'chown -R 1000:1000 <dirs>'
docker run --rm -v "<root>:/wt" -w /wt IMG sh -c 'rm -rf -- <dir> <dir>'
```

Count them first with `find <root> -not -user "$(id -un)" | wc -l`, so the report is a number.

Two things follow from the same seam and both cost a round trip if missed:

- **A hand-run container test must carry the same mounts the repo's make target uses.** A worktree's
`.git` file points into the MAIN checkout (`…/repo/.git/worktrees/<name>`), so a bare
`-v "$PWD:/repo"` makes every git-touching test fail with
`fatal: not a git repository: …/.git/worktrees/<name>` — a false red that looks like a broken test.
`make -n <target>` prints the exact `docker run` line (the repo's runs mount both paths); copy its
`-v` flags into the one-off command.
- **A container stage that CREATES a directory leaves it root-owned too** — an openspec scaffold, a
code generator, an installer. `chown -R "$(id -u):$(id -g)"` the new directory through a root container
BEFORE you write into it, or the first edit fails with `Permission denied` on a file that does not
exist yet (the editor's temp-file write is what is refused, so the error names a path you cannot see).

## Rule 4 — every quoted number comes from the command

Before reporting a prune (or writing it into a PR body or work record), re-read the counts from the
tool output: branches before/after, worktrees before/after, bytes reclaimed, keep-reason breakdown. A
remembered breakdown is how a body ends up stating "36" where the plan printed 38.

## Pitfalls

- **A batch edit by RELATIVE path lands in the session's start directory, not in the worktree you just
  created.** `cd ../llgenie-wt/<kebab>` inside one `terminal` call does not move a separate code-execution
  kernel, and every new call starts in the invocation cwd — so a `pathlib.Path('.github/workflows')` loop
  rewrote thirteen files in the USER's main checkout while the worktree stayed clean and `git status` there
  reported nothing. Address the worktree by ABSOLUTE path in the script
  (`WT = Path('/abs/.../llgenie-wt/<kebab>')`, then `WT / '.github/workflows'`), and after any batch edit
  check BOTH trees (`git -C <worktree> status --short`, `git -C <user checkout> status --short`); undo a
  stray edit in the user's checkout with `git -C <checkout> checkout -- <paths>` before anything is
  committed or pushed. A sweeping scan (a grep, a file listing) over a relative path misleads the same way
  — a "distinct bodies: 1" result taken from the wrong tree is evidence about the wrong files.
- **`git stash` is repo-wide, not worktree-local — do not use it to falsify a change.** The stash list is
  shared by every worktree of the repo, so `git stash push <path>` in one tree and a later `git stash pop`
  can apply ANOTHER agent's entry: `UU` conflicts on files you never touched, with
  `Recorded preimage for …` as the tell. And a push of an already-COMMITTED path silently creates no entry,
  so the "reverted" run tests the fixed source and passes — the guard looks broken when it is not. To prove
  a test catches a defect, edit the file, run the test, then `git checkout -- <path>`, and confirm
  `git status --short` shows only your intended edits. If a pop already landed someone else's work:
  `git reset -q HEAD -- <files>`, `git checkout -- <files>`, restore any tracked file you deleted while
  cleaning up, and leave `git stash list` untouched — that entry belongs to another branch, not to you.
- **Prove a new test reds on the OLD code in a detached throwaway worktree — not by stashing, and not
  by `checkout --`.** `git checkout -- <path>` cannot falsify a test you are ADDING, and the stash is
  repo-wide: `git worktree add --detach ../wt/<probe> origin/main`, copy ONLY the new/changed test file
  into it, run that one test there (`3 failed`), run the same test in the feature worktree
  (`3 passed`), then `git worktree remove --force` the probe. That is the red-first evidence for a
  change that is already committed, and it never touches the user's checkout or another agent's stash.
- **Never read a prune's exit code through a pipe.** In a piped invocation the call reports the
  LAST command's status, not the prune's, so a target that failed prints
  `*** [Makefile:<n>: worktree-prune] Error 2` while the shell exits 0. Redirect and read the real
  status
  (`make worktree-prune > /tmp/p.log 2>&1; echo EXIT=$?`), then grep the log. A first pass that prunes
  worktrees and then errors is usually the removal race the two-pass rule covers — re-run it bare,
  confirm the counts moved, and only investigate if the second pass fails too.
- **`git branch -D` cannot delete a branch a worktree holds**, even one shown as `detached` in
  `git worktree list`; remove that worktree first or the branch survives a "successful" prune.
- **`git worktree list --porcelain` is block-structured** (`worktree`, `HEAD`, `branch`|`detached`,
  `bare`); parse blocks, not lines.
- **A stale worktree is not inert**: a resumed agent that attaches to a merged branch's worktree wastes
a whole run, and the branch may already be gone.
- **Do not delete a no-PR branch to "tidy up"**: where agents cut several branches per task, those are
usually second attempts at work that landed under another name — say so, keep them, let a human decide.
- **Automate it in the repo, not in a shell alias**: target + tests on a real squash-merging fixture
repo + docs, so the eligibility rule is executable.
- **When the user says a PR "is not working", find the real edge before blaming CI.** Re-read the
implementation for the case it got wrong (here: running the prune from inside the worktree it wanted to
remove) and fix that; then rebase onto the latest upstream, force-push with lease, and only then
report which red jobs were external flakes.
- **After the PR merges, prove it on the pulled base, not on your branch.** `git fetch --all --prune`,
`git pull --ff-only` in the main checkout, confirm the PR's `mergeCommit.oid` is an ancestor of the
pulled `HEAD` (`gh pr view <n> --json mergeCommit`), then run the suite in a **fresh detached
worktree** off `origin/main` — never in the user's checkout, which accumulates the container's
root-owned artifacts. Then dogfood: the merged target's own `DRY=1` run over the real repo is the
cheapest end-to-end proof that what shipped does what it promised.
- **A flake is not a closed file.** Before writing one up, and before leaving it open, read the suite
roster's `deselect`/`excluded` entries: a live-network check moved out of the hermetic gate erases the
impact the issue claimed, and a stale open issue then misleads the next reader. Measured evidence (the
roster line, the target that now runs it) plus a close beats a vague "still open".

Repo-specific commands and gate order for llgenie: `references/llgenie-repo-notes.md`.
