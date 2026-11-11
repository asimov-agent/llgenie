# A batch of issue→branch→PR changes in one session

The mechanics that decide whether six reviewable PRs come out of one session, or two good ones and
a pile of conflicts. Everything here is repo-agnostic except where a tool is named.

## One worktree + one branch + one OpenSpec change per issue

```bash
git fetch origin main
git worktree add -b <type>/<kebab> ../<repo>-wt/<kebab> origin/main
cd ../<repo>-wt/<kebab>
```

- Run every edit, gate, commit and push inside that worktree; leave the user's checkout alone (it
  stays on the branch they left it on).
- A container that writes into the tree (an `openspec new`-style CLI, a generator run in a mount)
  leaves the new directory owned by **root**, and the next `write_file` into it fails with
  `Permission denied`. Fix ownership through a throwaway container, not `sudo` (a non-interactive
  shell cannot answer a password prompt):
  `docker run --rm -v "$PWD/<dir>:/c" alpine:3 chown -R "$(id -u):$(id -g)" /c`
- Validate a change in the worktree that OWNS it — a validator pointed at another worktree reports
  the change as missing, which reads like a broken change rather than the wrong cwd.

## Keep each PR's tests in a NEW file

Sibling branches cut from the same base that each append to the same test module conflict by
construction (line-adjacent appends). Give every PR its own `tests/test_<topic>.py` and touch an
existing module only when the change genuinely edits its behaviour. Same for docs: append a section
at a different anchor, not at the end of the same block.

## Update the tests that pin what you are changing

Before editing a Makefile variable, target or recipe, grep the whole test tree for the literal — a
suite that pinpoints the old shape fails on correct code:

```bash
grep -rn "<the literal>" tests/ scripts/ Makefile | grep -v __pycache__
```

Update those assertions to the new contract (both halves of a split variable, the new seam name in a
roster predicate) — never delete the case, and never loosen it to a substring that the old bug would
also satisfy.

## Never run two unit suites at once on one host

A gate that still contains live-network tests (a link crawl, a model download) gets rate-limited by
the second concurrent run: `HTTP 429` reds BOTH branches while both trees are fine, and the flake
looks like a defect in whichever change you are testing at the time.

- Run suites one at a time. Sequence them in one background chain (`run A; run B; run C`) rather than
  starting a suite per worktree and hoping.
- `faulthandler_timeout` prints a stack dump and keeps going, so a stall does not fail the run — grep
  the log for `Timeout (` before believing a green suite, and read the wall-clock time against a
  comparable run.
- If the flake is chronic, the fix is its own PR first (move the live tests out of the gate); the
  other branches then go green on top of it. Say so in each PR body instead of rebasing them onto
  the unmerged fix.

## Sibling PRs must not have to land together

A roster/guard test of the shape "every ignored name is in this list" couples two changes: the second
one cannot add its line without editing the first one's list. Scope such a check so a later leg's
entry is acceptable on its own — "every listed name is ignored AND written by a producer; every
ignored name is listed OR written by a producer" — and then the two PRs are merge-order independent.

## PR bodies for a batch

Each body repeats the three parts (`Issue:` measured symptom, `Fix:` mechanism and why it addresses
the cause, `Benefit:` what it prevents) plus `Technical:` and a `Not covered` list naming every
sibling issue by number. Link the unblocking PR by number rather than by a placeholder, and never
write `closes #N` into a PR that only implements part of the issue.

Opening order: push every branch, open the unblocking PR first (so the others can cite it), then the
rest — `gh pr create --repo <upstream> --base main --head <fork-owner>:<branch> --body-file <file>`.
