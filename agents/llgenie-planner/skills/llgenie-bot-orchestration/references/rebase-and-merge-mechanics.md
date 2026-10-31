# Rebase, merge, and the traps that silently corrupt both

Depth for "a rebase moves the symptom, a rewrite removes the cause". Every item here produced a red run, a lost commit,
or a comment that never posted.

## Order of operations for a shared-append file

An append-only index (`CHANGES.md` and its kin) is the most common conflict on a busy board. The order is not optional:

```bash
git fetch upstream main
git rebase upstream/main          # 1. land on the new base FIRST
make changes-index                # 2. render AFTER the rebase
git add -A && git rebase --continue
```

**Rendering before the rebase reproduces the exact conflict the rebase exists to escape.** For a multi-commit replay,
write at the **end**: writing the index at commit 2 of 6 bakes a mid-flight state into history. Then assert the property
the gate actually checks, not the CLI's summary:

```python
assert committed_text == ci.render(REPO)     # the rule
# `changes_index.py check` printing "ok: N fragment(s)" describes the FRAGMENTS,
# not the rendered file — it passes while the committed table no longer matches a render.
```

## A rebase that reports success is not a correct file

`git rebase --continue` succeeding says git advanced the commits; it says nothing about the content.

```bash
git show HEAD:<file> | grep -cE '^(<<<<<<<|>>>>>>>)'    # must be 0
git show HEAD:<file> | python3 -c 'import ast,sys; ast.parse(sys.stdin.read())'   # must not raise
python3 -m json.tool <changed>.json                    # for every changed .json
```

A conflict marker can survive a resolution whose pattern matched nothing, get committed, and surface as a `SyntaxError`
several steps later. Run the two checks above **before** the first test run, not after a 60-minute matrix.

## Re-read the live head immediately before any force

`--force-with-lease` protects against strangers, not against your own older knowledge. Re-fetch and compare against the
sha you actually rebased:

```bash
git fetch origin '+refs/heads/<branch>:refs/remotes/origin/<branch>'
git rev-parse origin/<branch>        # must equal the sha you rebased from
git push --force-with-lease --force-if-includes
```

If the head was **replaced** rather than appended (`git merge-base --is-ancestor <old> <new>` is non-zero), abort and
leave the worktree clean. Pushing stale work over an author's newer head is the failure this check exists to stop; a
lane that re-reads this value aborts several attempts and that is the check working, not failing.

## When NOT to rebase

- **Behind-but-mergeable is not a conflict.** `mergeable` is the fact; ancestry is not. A branch one commit behind main
  that still merges cleanly owes no action, and a rebase there costs a push plus the matrix it cancels.
- **Test the merged result, not the diff.** `git merge-tree` is textual: a clean tree can still produce a merged file that
  fails its own invariant. Do the real merge (or merge into a scratch branch), run the affected tests, and only then call
  it clean.
- **Do not chase a moving main.** When the queue is draining several merges a minute, every re-cut lands behind the next
  one and each push cancels the previous matrix — you pay for currency with the evidence the PR needs. Wait for the ref
  to be unchanged for a few minutes, then do **one** rebase, **one** render, **one** push.

## Classify a conflict before you resolve it

| conflict | shape | resolution |
|---|---|---|
| shared append (`CHANGES.md`, an index) | mechanical, one line appended per change | re-render, never hand-merge |
| the same file two changes edited | code | union, or a deliberate choice — never "take ours/theirs" |

"Take ours" on the second row deletes one of two changes, and neither test suite reports it. **A "this file is a superset"
claim is only true against the base you measured** — when main moves, the same file can be older than main's copy while
keeping every function name, so compare **signatures and content, not name sets**. Then prove both sides survived in the
pushed blob rather than the local tree:

```bash
gh api repos/O/R/contents/<path>?ref=<head> -H 'Accept: application/vnd.github.raw' | grep -c '<identifier A>'
```

## Salvage audit: measure, never prune

```bash
git worktree list --porcelain
git merge-base --is-ancestor <tip> origin/main
gh pr list --head <branch> --json number,state
```

- **Dirty worktrees are invisible to ancestry.** `git branch --merged` will call them merged and a prune deletes work
  that exists nowhere else. Report the preserve list instead of deleting anything.
- **Uniqueness is a content property, not a path property.** A branch is not unique because it adds paths no other branch
  adds — those same paths may already sit in an open PR under a different branch name. Compare added content against
  every open PR head and collapse duplicates before quoting a count.
- Keep the audit in a **script under the lane's `agents/` directory**, not in profile scratch: a scratch script is pruned
  and the next lane re-derives the number by hand and repeats the over-count.

## Shell traps that make an announcement silently not happen

- **Backticks in a double-quoted `--body` are command-substituted.** `gh pr comment --body "… `text` …"` runs `text` as a
  command, `gh` exits non-zero, and **nothing posts** — while the next step (a rebase, a push) proceeds as though the
  claim landed. Use single quotes or `--body-file`, and check **both** the exit code **and** that a URL came back.
- **A mis-scoped `jq` returning `0` is indistinguishable from a real zero.** Count with a type test rather than a truth
  test, or the summary line reports "0 armed" for a board carrying eight:

```bash
gh pr list --json autoMergeRequest --jq '[.[]|select((.autoMergeRequest|type)=="object")]|length'
```

- **Quote a nested `jq` filter in single quotes and avoid escaped double quotes inside it** — a half-escaped expression
  fails to parse and reads like an empty result.
