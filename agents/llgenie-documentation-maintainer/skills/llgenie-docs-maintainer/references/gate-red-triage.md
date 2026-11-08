# Is this gate red YOURS, or is `main` already red?

A docs gate failing on your branch is not evidence your branch caused it. Answer the question with a
command before editing anything, because the two answers have opposite remedies: a branch defect is
yours to fix, while a red `main` is an **issue to file** — and it silently disables the gate for every
PR cut from main.

## Step 1: reproduce the red on a CLEAN base, with no local changes

```bash
git worktree add --detach "$SCRATCH/wt-base" <origin/main sha>
cd "$SCRATCH/wt-base" && make check-docs   # the gate, unpiped, so you read the real rc
echo "rc=$?"
```

- **Same failure at clean base → `main` is red.** Do not fix it inside your branch as a drive-by; file an
  issue with the measurements, then a separate doc-only PR that closes it. Two reasons: your branch's
  scope claim becomes false, and the fix needs its own note trio.
- **Green at clean base → the red is yours.** Fix it in the branch.
- Run the gate **unpiped**. `make … | tail -2` returns the pipe's rc, not make's, and a "pass" that way is
  not a pass.

Do the same for `linux / unit` and for any gate a dispatch named — the base comparison is the only thing
that separates "my change" from "main's baseline", and it turns an unexplained red into a reportable
fact.

## Step 2: a gate red on main is an EMERGENCY for that gate's whole surface

When `check-docs` is red on main, **every docs gate is unenforced** on every PR cut from main: the
change-note trio, the README target sweep, the `CHANGES.md` index and the census itself all stop being
checked. That is why a docs audit run against a red gate cannot report "clean" — the instrument was off.
Say this explicitly when filing: it converts a one-line fix into a priority, and it explains why earlier
audits were green-but-wrong.

## The census-pointer class (the one that reds `check-docs` on main)

`docs/ARCHITECTURE.md` carries a census sentence with a `measured at `<sha>`` pointer, and
`scripts/check_architecture_census.py` requires that sha to be **a real commit AND an ancestor of
`HEAD`**. When it is not:

```
[census-gate] the census has no usable referent — census measured at `605f1a2e`
  (tracked=3730, …); no usable referent; HEAD is 2e04c9c2
```

Diagnose it with git, not by eye — the pointer is often a **pre-squash commit on the PR branch**, which
is a real commit but not in main's history:

```bash
git merge-base --is-ancestor <ptr> HEAD && echo ancestor || echo NOT-an-ancestor
git branch -r --contains <ptr>                 # -> origin/agent/issue-N-… (an unmerged PR branch)
gh pr view <n> --json headRefOid,mergeCommit   # PR head != squash commit
```

### Repoint **and re-measure** — never repoint alone

The numbers in the census were counted at the bad pointer's tree, so they are wrong for main too. A
pointer-only fix swaps one false census for another and passes the gate while stating untrue counts.
Re-count every gate-parsed value at the new sha with the tool:

```bash
git ls-tree -r --name-only <new-sha> | wc -l                                   # tracked
git ls-tree -r --name-only <new-sha> | grep -c '^tests/test_.*[.]py$'          # testspp
git ls-tree -r --name-only <new-sha> | grep -E '^openspec/changes/[^/]+/' \
  | cut -d/ -f3 | sort -u | wc -l                                             # openspec changes
```

Then confirm from the gate itself — its OK line restates the parsed values, so it is the read-back:

```
[census-gate] OK — census measured at `<sha>` (tracked=N, testspp=N, changes=N);
  referent `<sha>` is an ancestor of HEAD (<sha>)
```

### It is a recurring class; the durable fix is the code lane's

This has been fixed by editing the document several times and each recurred, because the **generator**
still pins the PR branch head. The durable fix — derive the pointer from the landing squash commit — is
`scripts/` work: name it in the issue for the code lane and land only the document half. Do not silently
absorb a code fix into a docs PR, and do not claim the class is closed when you fixed the instance.

## Step 3: shipping the fix cleanly (the scratch-file trap)

Redirecting gate output **into the worktree** and then `git add -A` commits your log files. This happens
repeatedly and silently:

```bash
make check-docs > .g1 2>&1     # .g1 now lives in the worktree
git add -A                     # commits .g1, .g2, .g3 — a scope violation in the diff
```

- Write gate logs **outside** the worktree (`$SCRATCH/…` or the session scratch dir), never as a
dotfile beside the tree you are about to stage.
- Before every commit, read the staged set and assert it is exactly what you intend:
  `git diff --cached --name-only`. A file count you expected (e.g. 4) versus what you got (7) is the
  signal; `git commit --amend` after `git rm --cached <f>` is the repair, and re-check the count after.
- Verify the delivered scope with the comparison that will be reviewed:
  `git diff --name-only <base> HEAD` — not the staged list, which is gone after commit.

## A red `ci-verdict` is usually DOWNSTREAM — trace the publication chain before re-judging

`ci-verdict` is a judge, not a detector: it reads the `ci-scope-decision` artifact that `ci.yml`'s
**guard** job publishes, and reds with `NO DECISION: this run published no scope decision` when that
artifact is absent. A guard that died on an earlier step never publishes it, so one upstream red shows
up as three:

```
ci.yml guard fails on check-pr-acceptance  (reviewer-gated tick, do not self-tick)
  -> guard never uploads ci-scope-decision
  -> GET /actions/runs/<id>/artifacts -> total_count: 0
  -> ci-verdict reads no decision -> "NO DECISION" -> red
```

So before treating a `ci-verdict` red as its own defect, read the guard's failing step and the run's
artifact count:

```bash
gh api repos/<org>/<repo>/actions/runs/<id>/jobs \
  --jq '.jobs[]|select(.conclusion=="failure")|"\(.name): "+([.steps[]|select(.conclusion=="failure")|.name]|join(";"))'
gh api repos/<org>/<repo>/actions/runs/<id>/artifacts --jq '.total_count'
```

One root cause, three symptoms — say that, do not list them as three problems.

**Re-judging cannot manufacture a decision.** The manual `workflow_dispatch` of `ci-verdict` re-reads
the same run; a run whose guard never published a decision re-posts the same `NO DECISION`. Re-judge
is the right move for a verdict that is *stale or judged against a superseded measure* — not for one
whose judged run genuinely holds no decision. Running it anyway is not diligence; it is a red you
spend a run to reproduce.

**Do not correct into a second wrong.** When the re-judge re-reds, reading `NO DECISION` as a *new,
independent cause* is the easy next mistake — it is downstream of the same gate. Verify the chain (which
job publishes the artifact this one reads) before you write either "same verdict" or "distinct cause"
on the wire. Both phrasings have shipped as confident fact and both were wrong.

## Report the triage, not just the verdict

When the red was main's, the report is: the base sha, the gate's own error line, the ancestor check's
answer, the issue filed, and the PR that closes it. "check-docs was red" without which-sha-and-why is a
claim about time, and the next reader cannot tell it from a stale one.
