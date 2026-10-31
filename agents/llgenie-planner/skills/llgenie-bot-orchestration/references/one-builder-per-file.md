# One builder per file, and prove no duplicate before you dispatch

Split out of `SKILL.md` when that file crossed skill_manage's ~100,000-character cap and
could no longer accept a patch (by `skill_manage`). The text below is verbatim from the
SKILL.md section it replaced; SKILL.md keeps the heading and a one-line pointer so a reader
still finds the rule where it is used.

## One builder per file, and prove no duplicate before you dispatch

When a change needs several lanes (classifier + workflow + tests), **assign by file ownership** and say who owns which
file out loud: the lane that owns the pipeline file edits the pipeline file, the design lane refines and reviews, the
test lane owns the checklist. Three lanes half-working one issue produces a design note, a library and no change.

Before dispatching anything, spend the two commands that catch an existing implementation:

```bash
gh pr list --repo <o>/<r> --state open --limit 100 --json number,title,files \
  --jq '.[]|select(.title+" \([.files[].path]|join(" "))"|test("<keyword>|<path>";"i"))|"\(.number) \(.title)"'
gh api repos/<o>/<r>/branches --paginate --jq '.[].name' | grep -i '<keyword>'
```

A second implementation of the same issue is worse than a late one: it manufactures the very file collision the lanes
were sequenced around. When one lands anyway, **close it as a duplicate with a file-by-file comparison table** (files,
+/−, which behaviours each covers), name the canonical PR, and say explicitly that the diagnosis was correct and
independently reached — a duplicate decision, not a rejection of the work.

**A rewrite is a push; a new PR is a decision.** When a branch needs a fix, the lane force-pushes the branch it already owns — one trail, one review thread. Opening a *fresh* PR for an issue that already has an open one is a decision for the planner, and a lane that does it has manufactured a duplicate by another route. Three vehicles for one issue in a single evening cost more reviewer attention than the change did, and each new branch re-cut the same tree. State it in every brief: *fix the branch you have; do not open a second*.

**Before authorising a fold, check the content is not already in the tree.** "Cherry-pick this commit onto the live branch" is a common ask and often moot: if the assertion or fix already exists under a different name, the authorisation buys a second test of one property plus a push to another lane's branch. Two commands decide it:

```bash
git -C <repo> merge-base --is-ancestor <sha> origin/<branch>; echo $?     # 0 ⇒ already an ancestor
git -C <repo> show origin/<branch>:<path> | grep -c '<the property>'
```

Write authorisations that survive that check — name the **property** to end up on the branch, not a commit to apply — so a lane that finds the property present can return the licence unused. Returning an unused licence with the reason is the correct outcome, not a missed opportunity: it costs nothing, and spending it on a no-op costs a run.

**When both drafts are the same infrastructure, the survivor is the one others stack on.** Two lanes implementing one
issue produce near-identical PRs (same skeleton, same scripts, one file count apart). The tie-break is not merit and not
diff size: count how many open PRs already base on each branch
(`gh pr view <n> --json baseRefName` across the board). Closing the branch four PRs stack on orphans all four and forces
four rebases against a differently shaped manifest — the divergence pattern again — so the stack wins and the duplicate
is closed, with its genuinely better halves (live-profile proof output, an extra make target, disclosed skill texts)
carried over as comments and a small follow-up rather than as a bigger duplicate.

**Pick the survivor by the regression test, not by diff size.** Two PRs that both fix a bug are not equal: the one
whose test *fails when the bug is reintroduced* survives, because the other one's fix lasts until someone tidies the
YAML. Check the guard directly before choosing — grep the new test file for the offending pattern and for the two or
three real paths that were silently skipped — and say which row decided it. Same file count and near-identical diffs
are the normal case; the guard is the only discriminator that matters after merge.

**A lane told to review that ships an implementation is a process finding, not a gift.** Name it in the same message
that accepts the better artifact: the correct move was "this branch cannot meet the criterion, here is why, hand it to
me", not opening a competitor. Otherwise the next pass gets two of everything again.

**But read your own dispatch before you say "unrequested".** Before calling a branch a rival, find the message that
started it: an earlier instruction to *implement* one issue at all costs is an assignment, and a second lane opening a
similar branch later does not retroactively turn the first into a rogue. **And check the authorisation record before
saying a licence never existed** — the grant may be a comment you wrote on that very PR an hour earlier while its inbox
was `queue_full`:

```bash
gh api repos/<o>/<r>/issues/comments/<id> --jq '"\(.issue_url|split("/")|last) \(.user.login) \(.created_at)"'
gh api repos/<o>/<r>/issues/<pr>/comments --jq '.[]|select(.body|test("AUTHORIS|authoris|authoriz";"i"))|"\(.created_at) \(.body[0:80])"'
```

A licence written to a branch by name, hours before a freeze conversation moved on, is exactly the kind of grant a
planner forgets owning — and "you were never authorised" when the comment exists inverts the incident and lets the
real overstep (pushing content other than the authorised commit) go unnamed. Check the ordering — which existed first, the
dispatch or the other PR — and if you got it wrong, correct it **in the PR trail**, not only in a DM: a wrong accusation
left in the record teaches every future lane to ignore a real one. The fair criticism, when it applies, is narrow and
forward-looking ("once the other branch appeared this should have switched to review-only"), never a characterisation of
the whole run.

