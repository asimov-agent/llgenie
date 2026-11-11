# Writing assertions that survive legitimate change, and guarding a whole class

## Assert the invariant, not the literal spelling

A test that pins a contiguous command string — `"scripts/pre.sh && scripts/run.sh" in recipe` — reds a
legitimate edit that inserts an argument or an env assignment between the two commands, while the
behaviour is still correct. In a CI gate that reads as a code defect and blocks the PR.

- Assert **order**: `recipe.index("scripts/pre.sh") < recipe.index("scripts/run.sh")`.
- When the two must stay chained in one shell invocation, assert the stronger form deliberately: both
  appear inside the same `bash -lc '…'` segment (split on `bash -lc '` and `';`).
- Keep a comment at the assertion saying which edit it must tolerate, so the next reader does not "tighten"
  it back into a spelling check.

## Guard the class with a test over the file's TEXT, not just today's state

When the lesson is "no recipe may do X again", the guard is a small hermetic test that parses the Makefile
and can be pointed at a synthetic sample:

- Join `\`-continuations, skip recipe comments (a `#` line inside a recipe is documentation), and key by the
  target header (a line matching `^name:` that is not tab-indented).
- Extract the rule as a function of the file text (`offenders(text) -> [(target, command)]`), assert it is
  empty for the real file, AND assert both directions on a synthetic Makefile — a clean real file proves
  nothing about whether the rule fires. Include the negative case the rule must allow (the venv seam, a
  container seam) or the guard becomes noise and gets disabled.
- A new test file needs no roster edit: `scripts/unit_tests.py` discovers `tests/test_*.py`. Only deliberate
  exclusions belong in the roster.

## Falsify before you call the test good

Revert only the source fix, run the new test, confirm it fails with the symptom you are claiming, restore.

- Do it by editing the file back and `git checkout -- <file>` — NOT `git stash`. A stash stack is
  repository-global, shared by every worktree of the clone, so a `stash push` that matches nothing followed
  by `stash pop` can apply ANOTHER worktree's in-progress work into yours (and leave conflict markers).
- State the falsification in the commit/PR (`falsified: without the fix the test fails with …`); an assertion
  nobody saw fail is not evidence.
