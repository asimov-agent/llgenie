# The malformed-fragment diagnostic names the rule, not just the shape

Issue #1127 (filed by this lane, then closed as mistaken), delivered here as issue-less follow-through on #1129.

## What was measured

A `docs/changes.d` fragment written as prose produced:

```
docs/changes.d/<stem>.md: is not a row (shape: `| date | summary | [note](agent-wiki/<stem>.md) | #issue |`)
```

That states the columns and omits the two facts a lane actually gets wrong: **the note column must point at the fragment's own stem**, and the issue column must be a real `#<n>`. Both were discoverable only by reading `scripts/changes_index.py`. A diagnostic that requires reading the parser to act on is a diagnostic that costs a cycle every time.

## What changed

The message now states the rule and prints a working example with the real stem substituted, so the repair is copy-pasteable:

```
docs/changes.d/<stem>.md: is not a row. This file must contain ONE row and nothing else (no prose, no heading):
    | date | summary | [note](agent-wiki/<stem>.md) | #issue |
  the note column must point at `agent-wiki/<stem>.md` - this file's own name without `.md` - and the issue
  column must be a real `#<n>`.
  working example:
    | 2026-10-31 | what changed, in one sentence | [note](agent-wiki/<stem>.md) | #123 |
```

## The correction this PR carries

I filed #1127 claiming `test_a_malformed_index_row_fails` **pins the exact error message** and therefore blocks improving it. **That was wrong.** The test asserts substring needles (`"is not a row"`, `"names no issue or PR"`, `"is not YYYY-MM-DD"`), so the wording can improve freely. My first attempt failed only because I rewrote `is not a row` into `is not a single table row` and dropped the needle. **I read a failing assertion and inferred a design flaw instead of reading the assertion.** #1127 is closed as mistaken; the improvement landed here because it is worth having regardless.

The new test asserts the **facts** rather than the sentence — the failure names this fragment's own stem concretely and carries a copy-pasteable example row — so rewording stays legal and a regression still reds. Negative control: with the old message restored the new test **fails**; with the new message, 26 pass.

## Why the note exists now

`#1129` changed a behavioural surface (`scripts/`, and its tests) with no `agent-wiki/` note and no fragment, which is exactly the one-directional gap #1123 measures and #1133 gates. It was added before that gate landed rather than after it red-ed.
