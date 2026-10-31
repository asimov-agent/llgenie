# Verifying a control, and rebuilding on a base that moved

Two failure classes that look like success: a negative control that never landed, and a branch whose
content was replaced or dropped by a rewrite. Both end with a green you cannot trust.

## 1. Verify the sabotage before you trust the green

A sabotage that patches the wrong occurrence — or the wrong function — leaves the suite exactly as it was,
and an unchanged suite reads identically to a passing control. Check the mutation landed **first**.

```bash
# phrase removed from a document: the count must be 0 before the suite means anything
grep -c '<the exact phrase you deleted>' <file>

# a function neutered: call it and see the wrong value, do not infer from the edit
python3 -c 'import sys; sys.path.insert(0,"scripts"); import <mod> as m; print(m.<fn>(...))'

# a line deleted from a list of similar lines: count the removal
python3 - <<'EOF'
lines = open(p).read().splitlines(keepends=True)
kept = [l for l in lines if not l.startswith('<prefix>')]
print("removed:", len(lines) - len(kept))
open(p, 'w').write("".join(kept))
EOF
```

Rules of thumb:

- Anchor the sabotage on a **unique, structurally complete** unit (the whole line, the whole function
  body), never on the first occurrence of a phrase — prose repeats.
- A sabotage that reds the *wrong* count of tests is also informative: one test per carrier means one red
  per deletion; four reds means the rule is asserted by neighbours you did not know about.
- Restore from a copy taken before the edit (`cp <file> /tmp/<name>.bak`), never `git checkout -- <file>` —
  that restores HEAD and silently discards your own uncommitted work in the same file.

## 2. A rewrite can keep the checks and delete what they check

Rebases and force-pushes by other lanes are described in commit titles as cleanups. Measure the carriers,
not the diff summary:

```bash
git fetch origin <branch> --quiet
git diff --stat origin/<base> origin/<branch>      # files you expect, plus anything unexpected
git show origin/<branch>:<path> | grep -c 'def <symbol>'   # the implementation still present
git show origin/<branch>:<tests> | grep -c 'def test_<name>' # the test still present
```

Signature seen twice: the test file survived and the implementation was gone, with the PR reading
`MERGEABLE/CLEAN`. The tell is that the suite is **red** at the head — which is only visible if you run it.
So after any head change you did not make: `git diff --stat` (shape), `grep -c` for each carrier's symbol
(content), and run the gate and the suite (behaviour). An empty `git diff <old> <new>` means only the sha
moved; a non-empty one means someone else built there.

When the missing half is code, re-apply it against the base's **current** text — messages and detail strings
move. A patch built from an older cut will silently fail to apply its string replacement while the function
wrapper lands, producing a half-restored file whose tests fail on the message, not the logic.

## 3. Rebuilding on a moved base: copy only what you own

| what you are changing | how to rebuild |
|---|---|
| a file only this lane edits (your SOUL, your skill) | `git show <old-branch>:<path> > <path>` is fine |
| a shared file (the test module, the manifest, the exemption list) | never copy wholesale — **patch by insertion**, appending or inserting after the neighbour's block |
| a file another lane is actively rewriting | patch the smallest region, and message that lane with your sha first |

Enforcement, run before every commit:

```bash
git diff --stat origin/<base> HEAD
```

Deletions outside the lines you wrote are the failure: a copy taken from an older tip deletes every line the
base gained since, which reads as "this PR removes other lanes' tests". When the diff shows deletions you
did not intend, the rebuild is wrong even if every gate is green.

## 4. Fetch the branch you are cutting from, not just main

`git fetch origin main` is the wrong fetch when the branch you cut from is a feature branch that carries the
tree. Fetch and record in the same breath:

```bash
git fetch origin <base-branch> main --quiet
git rev-parse --short origin/<base-branch> origin/main     # both go into the start comment
```

A worktree cut from a tip fetched minutes earlier is a census of the past as soon as that tip moves, and
the damage is not subtle — every file the base gained renders as a deletion in your diff.

## 5. A census taken in a worktree you have edited is a census of your own edits

Before reporting the base's state ("the block is 15 of 16", "the gate is red here"), measure it in a
**detached worktree of the base** with `git status --short` empty. Hand edits made during the previous
attempt corrupt the count, and the wrong conclusion ("the base drifted") is indistinguishable from a real
finding until the worktree is clean.

## 6. A finding whose path cannot be opened is a defect in the reporter

Probe the reporter, not the tree:

```bash
mkdir -p /tmp/<odd-name>/agents/<profile>   # and a manifest + canonical rules file
python3 scripts/check_agent_profiles.py check --root /tmp/<odd-name> --agents-dir agents
```

If the printed `where:` starts with `<odd-name>/agents/...`, the path is computed one parent too high
(`agents.parents[1]` is above the repository). Findings must be repo-relative and openable from the repo
root; two path conventions in one output is how a reviewer stops trusting paths and starts grepping.

When you grep a document to confirm a phrase is present, remember prose wraps: a raw `grep` on a 70-character
phrase returns 0 for text that is present across a line break. Grep a short unique fragment, or compare
whitespace-normalised (`" ".join(text.split())`).
