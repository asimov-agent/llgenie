---
name: bulk-mechanical-migration
category: software-development
description: "Use when migrating many files mechanically."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [refactor, migration, codemod, tests, guards]
    related_skills: [containerized-repo-verification, simplify-code, systematic-debugging]
---

# Migrating many files mechanically

<!-- host-bot-tools:begin -->

## Tools

This lane's chat session is pinned to these Hermes toolsets and no others: `clarify`, `code_execution`, `file`, `memory`, `session_search`, `skills`, `terminal`, `todo`.

Skills that stay enabled: `bulk-mechanical-migration`, `github`, `github-issue-triage`, `github-workflow-admission`.
Every other installed skill is listed in `skills.disabled`.
The pin is `tests/fixtures/host-bot-capabilities.json` in asimov-agent/llgenie (issue #1038).
<!-- host-bot-tools:end -->

## When to Use

Use when ONE change has to be applied to dozens or hundreds of files the same way — collapsing many
import bootstraps into one root, renaming a helper across a tree, deleting boilerplate — and the repo has
(or should have) a gate that can see the leftover shape. Skip the ratchet for fewer than ~10 files: there
an edit-per-file pass with the normal gates is faster than building a checker.

A change that touches dozens or hundreds of files with the same shape: one import root instead of many,
`from x import y` instead of bare imports, a renamed helper, boilerplate deleted. The defining risk is
that **a partial migration is worse than none** — a half-migrated tree has two conventions, so the next
reader cannot tell a leftover from a decision, and the suite can stay green while the tree is wrong.

## Order of work: guard, then batches

1. **Write the guard first, as a RATCHET.** The tree already violates the rule N times, so a plain gate
   would red the suite on the commit that adds it, and no gate lets violation N+1 in unseen. Record the
   current counts in a fixture (`tests/fixtures/<name>-baseline.json`) and fail only when a count RISES:

   ```
   check   -> every finding, exit 1                              (the honest report)
   ratchet -> counts vs the baseline, exit 1 only on an increase  (what CI runs)
   --update -> record the current counts
   ```

   The baseline is data in the tree, so progress is a number falling, and a missing baseline is a finding
   rather than a pass.
2. **Batch ~15 files, never all of them.** Rewrite, then run the batch's own tests before touching the
   next batch. An automated pass that produces unparseable output must be **reverted**, not repaired in
   place — revert and redo the batch with an explicit rule per file.
3. **Update the baseline after each batch** (`--update`) and let the ratchet prove the direction is down.

## A refusal must not talk like a success

A guard that shrinks a file and then prints `verified: 3 file(s) read back identical` is the same lie with
a non-zero exit. Two rules, both testable:

- **Pin the message, not just the return code.** A test asserting `rc != 0` passes on a tool that
  refuses *and* still prints its success line. Assert the sentence: `rc != 0`, both sizes present (computed
  from the fixture, never hardcoded), the word `smaller`/`shrank` present, and **`verified` absent**:

  ```python
  assert rc != 0
  assert f"{tree_bytes} b" in msg and f"{live_bytes} b" in msg
  assert "smaller" in msg.lower()
  assert "verified" not in msg.lower()          # the assertion that exists for the lie
  ```

- **A success line states what was compared, not a reassurance.** `verified: N copied and read back as
  written, M replaced an existing file` is true; `verified: N file(s) read back identical` claims the
  destination was already right when the tool only checked that it wrote what it copied. Verifying your own
  write is not verifying what was there.

## Refuse on CONTENT, not on a size ratio

A seed that is a **prefix** of the real file — every line it carries also appears in the destination, which
has more — is a truncation even when it is 98 % of the size. A `tree < live * 0.75` floor passes that case
happily. The predicate that works is set-theoretic:

```
subset  = tree_lines != live_lines and set(tree_lines) <= set(live_lines)
refuse  = subset or (live and tree < live * SHRINK_FLOOR)      # floor stays as the second signal
```

- Build the fixture to defeat the size check (a rule dropped from a near-identical file), not to trip the
  obvious half-size case.
- **Add the opposite control**: a destination whose rules differ entirely is an *edit*, not a truncation,
  and the guard must let it through. A guard with only negative controls eventually blocks real work.
- **Read both sizes at run time.** A number captured from a brief, a message or an earlier measurement is
  stale before it is used; `stat` the destination and the source inside the check.

## Compare against the authoritative copy, never the nearest one

When the same content lives in two places (a repo copy and the installed/live copy), the live one is
`stat -c %s <live path>` and the repo one is `git cat-file -s <sha>:<path>`; comparing a *worktree's* files
compares neither, and the worktree may be on any branch. Two consequences for the gate:

- Fail when the **live** copy is longer than the in-tree one: that is the direction that loses content,
  because the sync copies tree over live. A presence-only check ("3 files present, 1 profile") is green
  over a large deletion — presence says *a file is here*, the comparison says *it is the file*.
- When the live copy does not exist at all (a CI runner has no `$HOME/.hermes/profiles/`), **skip the
  comparison rather than fail**: a gate that cannot see both sides must say nothing instead of pretending
  it compared them.

## Select statements with the AST, not with line regexes

A line-anchored pattern cannot tell a module-level bootstrap from a statement inside a test body, and
`$` anchors are defeated by a trailing comment:

- `sys.path.insert(0, str(home / "plugins" / "x"))` **inside a test** points at a temporary tree that
  test just built. Stripping it breaks the test (`No module named 'x'`), not the seam. Walk
  `ast.parse(text).body` and match `Expr(Call(Attribute(...)))` at module level only.
- An import regex anchored with `$` silently skips `import thing  # noqa: E402`; strip the trailing
  comment scaffolding FIRST, then rewrite imports, then delete the now-orphaned path line. Doing it in
  the other order leaves a bare import with no path entry — an `ImportError` per file.
- Re-`ast.parse` every rewritten file and drop the batch entry that fails, rather than writing it and
  discovering it at test time.

## The single root belongs in the test conftest — and it covers the scripts dir too

Removing a test's `sys.path.insert(… / "scripts")` breaks the *product* when a scripts module imports its
siblings bare (`scripts/auto_merge.py` doing `import verify_closure`). That is the seam, and it belongs
in `tests/conftest.py`, once, for the whole suite: insert the repo root AND the scripts directory there.
Then a test file needs no bootstrap of its own, and the scripts keep resolving their siblings.

## The dual module object — the trap that stops a file mid-batch

`from scripts import engine_skills as es` and a scripts module doing `import engine_skills` create **two
distinct module objects**. A test that patches `es.SKILLS_DIR` patches the package one while the code
under test reads the bare one, so the patch silently misses and the write lands in the real repo:

```
FileNotFoundError: /repo/skills/engines/fixture/SKILL.md     # the temp fixture was never used
```

- **Before migrating a test that monkeypatches a scripts module, grep that module for bare sibling
  imports** (`grep -n '^import ' scripts/<module>.py`). If it has them, the fix is on the scripts side
  (`from scripts import sibling`), not in the test — leave that file out of the batch and say why.
- The same hazard is why a count-based gate is not enough: both conventions import fine, and only a
  behavioural test that patches one side exposes the split.

## Verify a batch, and prove a failure is yours

- Run the batch's files through the project's own harness selection (`python scripts/unit_tests.py run
  --group fast`, or the aggregator's `argv`), not an ad-hoc `pytest` list — the roster knows which files
  are excluded for environmental reasons (a live-network or venv-only module failing in the test image is
  not your batch).
- When a file fails after migration, run **the same file on a pristine detached checkout of the base**.
  Passing there and failing on your tree is the only proof the failure is yours; failing on both means it
  is environmental and belongs in the "not mine" column of the report.
- Quote both numbers in the PR body: the baseline before/after (`104/141 -> 69/107`) and the batch's test
  count. "Migrated" without a falling baseline is a claim, not progress.

## Report what is left

State the remaining count and how many batches that implies, and name every file deliberately left out
with its reason. An issue whose acceptance is "no bare imports remain" is not closed by the guard plus two
batches; closing it then is the same defect the ratchet exists to prevent.
