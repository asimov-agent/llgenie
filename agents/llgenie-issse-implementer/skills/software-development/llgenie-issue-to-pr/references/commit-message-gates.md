# Commit-message and PR-close gate reds

Gates that parse commit subjects and PR bodies. All of these red on TEXT, not code, so the fix is
almost always message/body-only — prove the tree did not move before pushing.

## `make check-pr-closing` — a commit-message PR-number claim

A commit whose subject claims a PR number that disagrees with the PR body's `closes #<n>` reds the
gate with exit 2 and takes BOTH the `scope` and `guard` legs down on the same message (both point at
one defect — do not chase them as two).

Typical bad subject: `ci: <what> (fixes #<pr>, #<issue>)` where the body already says
`closes #<issue>` and the commit has no business naming the PR.

Fix, message-only:

1. `git commit --amend` the subject to end in the SAME adjacent close the body uses —
   `(closes #<issue>)` — and drop any PR-number claim.
2. Prove no content moved: `git diff --stat <old-sha> HEAD` must be EMPTY (an amend that only
   rewords the message leaves the tree byte-identical).
3. Run `make check-pr-closing` LOCALLY at the new head and require rc 0 before pushing.
4. Force-push with the lease pinned to the fetched tip (see the force-with-lease rules in SKILL.md).

Never "fix" this by rewriting the PR body to match a wrong commit message: the body's close target
is the tracker issue and the commit must agree with IT, not the reverse.

## The gate parses SQUASH TEXT, and it applies to EVERY branch

The version on `origin/main` reads the joined commit messages (`COMMIT_MESSAGES`) as well as the PR
body, and it does NOT limit itself to `^agent/` heads — an automated `chore/dep-bump-*` branch that
names an issue in a commit body line (`Issue: #107`) and in the body prose reds exactly like an agent
branch. So a red `guard`/`scope` pair on a branch whose head prefix you assumed was out of scope is
this gate, not a different check: read the job's step output before hunting for a second gate.

## A claim on a CLOSED tracking issue: drop the claim, close nothing

When the issue a batch of PRs claims (`Issue: #<tracker>` in each commit body, `(issue #<tracker>)`
in each PR body) is **CLOSED** and no open issue actually serves the change, the correct edit is to
REMOVE the claim from both surfaces — never invent a `closes #<closed>` (GitHub cannot close it again
and the gate rejects a close on a closed issue):

1. `gh issue view <n> --json state,closedAt` first — the claim's correctness depends entirely on this.
2. Amend the commit to drop the `Issue: #<tracker>` line (`git commit --amend`), and replace the
   `(issue #<tracker>)` prose in the body with a sentence saying the tracker is closed and this change
   closes nothing.
3. `make check-pr-closing` rc 0 locally, with the real body passed in as CI does (the gate reads the
   body, so testing with an empty `PR_BODY` proves only half of it).
4. Prove nothing else moved: `git diff --stat <old-sha> HEAD` shows only the trios/docs files you
   deliberately added.

## Posting comments to satisfy a guard

When a commit message or body correction is pushed via git subprocess, a runtime guard that only
observes file-tool writes will keep demanding "a mutation" and stay red — that is a false negative,
not a reason to edit the tree. Discharge it with ONE finish bookend comment on the PR, then hold. Do
NOT post a near-duplicate "confirmation" comment afterwards for the same push: it is noise on the
PR thread, and the guard re-fires regardless because it never saw the git-subprocess push to begin
with.
