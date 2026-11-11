# Repairing an agent-opened PR's OpenSpec bookkeeping

The implementation commit is usually fine; what reds `validate` is the bookkeeping the
implementer skipped. Work in this order — each step unblocks the next, and one of them
(the every-change gate) fails in a way that looks like a test regression but is your own
unticked box.

## 1. Read the change off the PR head, not off the body

```bash
git show origin/<branch>:openspec/changes/<name>/tasks.md
git show origin/<branch>:openspec/changes/<name>/proposal.md
git show origin/<branch>:openspec/changes/<name>/specs/<cap>/spec.md | grep -n '\*\*Test:\*\*'
```

- Every `- **Test:** <path>::<test>` must name a symbol that exists
  (`grep -n "def <test>" <path>`). `openspec validate` checks structure only, so a
  scenario can cite a test that was never created and the structural gate stays green.
- Every doc-only task (the §8 guard row, the ARCHITECTURE/description row, the
  human-facing skill paragraph) is the box most agent PRs leave genuinely undone. Write
  those before ticking, never after.

## 2. The proposal's `Issue:` line is a machine field

The generated index row's Issue column is parsed from the proposal header:
`^(Issue|PR):\s*(.+?)$`. A prose value there ("this run's `issue.md` — the input carried
no issue number") becomes a garbage cell that no reviewer can resolve to a number.

- Brain-instinct fix: `Issue: #<n>` matching the branch's closing issue, then regenerate.
- Do not invent a `PR:` line — no other change carries one; the column renders `—`.

## 3. `findings.md` fields are LIST ITEMS

The checker parses `^\s*[-*]\s+\*\*(?P<name>…)\*\*`, so a field written as a bare
`**Evidence:** …` line is invisible and the run fails with "missing Evidence, Why, Done
when" even though the text is right there.

- Correct shape per finding: `## <title>` then
  `- **Evidence:** <file:line / command output / data point>`,
  `- **Why:** …`, `- **Done when:** …`.
- A field's detail runs to the next field / heading / BLANK line — a blank line inside
  one field truncates it into the issue body.
- `- none` is the valid "found nothing" answer and files nothing.
- After the PR is green (or after it merged without the implementer's filing step),
  file them: `make file-findings PR=<n> ISSUE=<n>`, then read back that each issue is
  open WITH the `tech-debt` label — a label the repo lacks is silently dropped and the
  issue starves the bot queues.

## 4. Tick, regenerate, then run the gates — and expect the every-change gate

```bash
make openspec-index                      # never hand-edit the generated index
make openspec-tasks-check                # bare: per-change OK/FAIL
make openspec-check                      # validate + tasks + index currency
```

**The task gate inspects EVERY active change in the tree**, including the one you are
editing, and its own module (`tests/test_check_openspec_tasks.py`) asserts the real repo
is fully ticked. So the full suite fails on your own unticked verification box, which
reads exactly like a test regression:

```
[test] 13 module(s) passed, test_check_openspec_tasks.py FAILED
[openspec-tasks] FAIL <change>: unchecked task checkbox(es) at lines [10]
```

Order that avoids the loop: run the real verification (fast gates, the affected module in
the test container, `make validate`), tick the verification box WITH that evidence in it,
regenerate the index, then run the full suite.

## 5. A verification box carries its evidence, not a tick

Tick a box only when the work it names exists, and put the proof in the same line:
command + result (`make validate → QA PASSED`, `PASSED 133 | FAILED 0`), and the RED
control (`fails on the pre-change base with …`). A bare `- [x]` on a docs box is the
claim the next reviewer has to re-verify by hand.

## 6. When a protected file's write is refused, the box is BLOCKED, not ticked

If the change owes a row in a protected rule file and the write is refused (an approval
gate that times out is a refusal — silence is not consent, and the file may hold other
unrelated edits you must not clobber), there are two mechanical states and only one is
honest:

- `- [~] <task text> — blocked: <who/why>` — the gate ACCEPTS this and reports it as
  review-required (`9/10 · 1 blocked` in the index row). A bare `- [~]` with no
  `blocked:` reason FAILS.
- Never tick it, and never route the same edit through another tool (`terminal`,
  `execute_code`) to get past the refusal.

Deliverable in that case: the exact row/section text in the PR body (or the report) so a
human can paste it, plus the blocked box naming that. The rest of the change still lands.
