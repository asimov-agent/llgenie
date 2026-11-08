# Dispatched defect turns out to be already fixed — ship the regression guard, never a phantom fix

## The situation

You claim a "fix X / improve Y" issue, read the failing producer log, and find that the root
cause was ALREADY fixed by a prior commit that is in `origin/main` and in every head you would
branch from. The naive moves are both wrong:

- **Phantom re-fix** — re-implement (or tweak) the already-correct production code so the diff
  looks like "work". This ships churn that can itself regress the fix and misleads the reviewer.
- **Empty PR / close the issue** — "already fixed, nothing to do" produces no reviewable artifact
  and leaves the defect unprotected against the NEXT change that reintroduces it.

## The rule

When the documented defect is already remedied but the remedy has **no test coverage**, the
reviewable deliverable is a **hermetic regression test that locks the fix in**. The mutation is
the test, not the production code.

1. **Prove the fix is present and where it came from.** `git log -S '<symbol>'` / read the
   commit that introduced the fix, and confirm it is an ancestor of the head you are branching
   from (`git merge-base --is-ancestor <fix-sha> origin/main`). Quote the commit and the sha you
   branched from in your START comment so the reviewer sees the premise.
2. **Prove the coverage gap.** `grep -rn '<fix-symbol>' tests/` returning nothing, or the symbol
   appearing only in production, is the evidence the fix is unprotected. That gap IS the issue.
3. **Write a hermetic regression test** that exercises the REAL repo artifact (the real
   Dockerfile / config / fixture), not a hand-rolled mock of the old shape — a mock reimplements
   the pre-fix behaviour and passes while the real path stays broken. Assert the post-fix
   invariant (e.g. "no bare base `FROM`, no `docker.io` ref, exactly one `AS <base>`"), and
   sweep every real instance so a future per-engine/param addition is caught too, not just the
   one cell that reddened.
4. **Frame the OpenSpec change as the guard.** proposal.md states "the production fix already
   landed in <commit>; this change adds the missing hermetic regression coverage" — so the
   reviewer is not tricked into thinking you re-fixed it.
5. **Pin the specific reddened cell by name** in one named test, and sweep the class in a
   second, so both "the exact blocker" and "the whole failure class" are covered.

## Pitfalls

- **Do not copy the failing run's error as if it were still live.** A failing producer cell you
  read may predate the fix (check the fix commit's date vs the run's commit). Say plainly: "the
  documented failure predates <fix-sha>; the post-fix failure at the anchor is unreadable because
  the run is still in_progress." Never assert the defect is live at the current head without a
  readable post-fix log.
- **A regression test that re-tests a pure helper in isolation passes even when the real
  Dockerfile diverges.** Drive the test off the actual committed file so it reds if someone
  changes the file's `FROM` back to a registry reference.
- **Name the test without a leading underscore** — `_test_foo` is not collected by pytest; it
  silently never runs.
- **Mirror the failing cell's EXACT code path — a different flag is a different branch.**
  The reddened cell may be a push build (`if push and REGISTRY:`) while the existing regression
  test only exercised `push=False`. A test on the wrong path passes green while the real branch
  stays uncovered. Drive the test with the same kwargs/flags the failing invocation used (e.g.
  `_buildx(tag, ctx, True, cache_ref)`) and assert the distinguishing flag (`"--push" in build`)
  so the test provably exercises the branch under review.
- **Cover BOTH sides of a tolerance, not just the suppression.** A "missing precondition → skip
  the flag" fix tested only on the absent case proves suppression, not that the flag is STILL
  emitted when the precondition holds. Add the symmetric test (present cache → `--cache-from` /
  `--cache-to` still present) so a future change cannot silently drop the write entirely while
  the suppression test stays green.
- **A helper extracted into a SINGLE shared probe needs a DIRECT contract test, not just
  indirect coverage through its callers.** When a refactor collapses two call sites onto one
  helper (a shared "does X exist" probe, a shared arg-builder), tests that exercise it only via
  the callers prove the callers, not the helper's own contract — and a future change to the helper
  can regress the exact behaviour (return mapping, the command it issues, the unconfigured
  short-circuit) while every caller test stays green because a caller's branch masks it. Add one
  test that pins the helper directly: the successful case (return value AND the exact command it
  issues, asserted with `==` on the recorded call list), the failure case (non-zero rc -> the
  absent/false result), and the no-config case (empty config -> the helper issues NO command at
  all and returns the safe default). One helper, one direct test; caller tests are additional, not
  a substitute.
- **In a recorded-subprocess-call test, never assert on `calls[-1]` — the target command is not
  always last.** After a successful operation the code runs FOLLOW-UP calls (a push build runs
  `buildx build … --push`, then `docker pull`, then `docker tag`), so `calls[-1]` is the tag, not
  the build. Select by a distinguishing flag: `build = next(c for c in calls if "--push" in c)`
  (or by the `buildx build` subcommand), then assert on `build`. Asserting on `calls[-1]` fails
  with an AssertionError naming the wrong command and reads as "the fix is missing" when the
  build was actually cold as intended.
