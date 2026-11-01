# Judging acceptance at a moving PR head

An acceptance verdict is a statement about one sha. A lane that re-pushes after your measurement voids
your verdict — the criterion may now hold, may now fail, and either way the branch you measured no longer
exists at the head. Never repeat "acceptance met" / "acceptance not met" from a head you did not just fetch,
and never let a lane's re-push turn your standing correction into a contradiction on the thread.

## Procedure

1. Fetch the head fresh, every time, before any acceptance claim:

```bash
gh pr view <n> --json headRefOid,state,updatedAt --jq '{head:(.headRefOid[0:8]),state,updatedAt}'
```

   Compare against the sha your last verdict names. Same sha ⇒ restate; different sha ⇒ your verdict is
   void and the branch must be re-measured (step 2). A lane folding your correction and force-pushing is
   the common case, not an anomaly. When a lane *quotes* a head in a report, do not trust the quote —
   the tip is `headRefOid`; confirm the relationship with

```bash
git -C <planner-tree> merge-base --is-ancestor <quoted-sha> <tip> ; echo $?   # exit 1 = quoted sha is not even behind
```

   A quoted sha that is not an ancestor sits on an abandoned line: a "final" naming a non-ancestor is
   stale by inheritance, however confidently it is stated — treat it as no head at all and measure the tip.

2. Measure at that sha in a clean detached worktree off a freshly fetched ref:

```bash
git -C <planner-tree> fetch origin <full-sha>
git -C <planner-tree> worktree add --detach /tmp/wt-<n>-<short> <full-sha>
```

   Run `worktree add` as its **own** command, then `cd` in the next call. A fused chain
   (`cd /tmp/wt-new && python3 ...`) fails because the working directory is resolved when the shell command
   starts — the directory does not exist yet, so the `cd` errors and every step after it never runs, while
   a `| tail -1` on the end hides it. Same for `rm -rf <dir>; git worktree add ...; <measure>` chains: keep
   delete, add and measure in separate calls so a failure is visible instead of swallowed.

   If `worktree add` keeps refusing (`fatal: '<dir>' already exists`) and you only need to READ the tree,
   skip worktree registration entirely and extract exactly that sha:

```bash
git -C <planner-tree> archive <full-sha> | tar -x -C /tmp/arch-<short>
```

   It is a read-only copy of the committed tree, immune to stale worktree metadata, and safe to `rm -rf`
   and redo when a measurement needs a clean slate.

3. Scope the measurement to the criterion, not to the whole gate. A fleet-wide run reports every lane's
   residual and cannot answer "did this PR meet ITS acceptance":

```bash
python3 scripts/check_agent_profiles.py check --only <scopes> 2>&1 | grep -ci '<your-lane>'
```

   Take the count twice in two separate invocations and require agreement before reporting the number.
   Report the un-scoped total separately as context ("fleet residual fell 69 → 65"), never as the verdict.
   **When the criterion is "zero rows for my lane", the authoritative measurement is the NO-ARGS gate
   counting that lane's rows — never a `--only` subset.** A filter that omits one class the gate also
   emits (e.g. `live-edited-not-tree` sitting alongside `live-longer`) reports a false `0` while the
   no-args gate reads several rows; a lane quoting "0 rows via `--only <classes>`" is therefore not
   evidence that the criterion holds. Read the full gate output and count lane rows yourself.

4. Post the verdict where the work and the tracker both live — the PR **and** the issue it closes — and read
   back that your comment is newest (`.comments[-1].id`). When the new verdict supersedes your own earlier
   correction, say so explicitly ("supersedes <old comment>; the correction is resolved by measured
   counter-evidence at <sha>") so the thread does not read as two planners contradicting each other.

## Binding a contract is not verifying it

Posting an acceptance line that names the issue's criteria ("this PR is the sole vehicle, acceptance =
these four clauses") is a **contract**, not a verdict. The verdict is owed separately and is the mutation
the pass still needs — read the diff at the head and check each clause names a real artifact:

```bash
gh pr view <n> --json files --jq '.files[]|{path:.path,additions:.additions,deletions:.deletions}'
gh pr diff <n> | grep -nE '^\+.*(def |^\+[a-z0-9-]+: |schedule|cron|uses:)'   # the product, not the prose
```

- A clause "a `make` target reads field X" is met only when the Makefile hunk adds that target **and**
  the reader module reads that field. A body sentence naming the issue is not evidence for any clause.
- Walk the criteria in order and attach the artifact that satisfies each (file + function/target name).
  Report clause 4 ("green at head") separately from an **ambient red** inherited from another tracked
  issue — the PR introduced no new red even when the leg reads `failure`.

## Pitfalls

- **"Acceptance contract bound" is not "acceptance met".** After posting the criteria, the remaining owed
  fact is *does the diff satisfy them*; skipping it leaves the reviewer to re-derive the only thing that
  matters and is exactly where a lane's confident body text gets repeated as a planner verdict.
- **A lane's diagnosis is a claim about a FILE, not a story.** Before accepting a claimed root cause,
  read the cited file at the cited sha:

```bash
gh api repos/<o>/<r>/contents/<path>?ref=<sha> --jq .content | base64 -d | grep -nE '<symptom>'
```

  Accept when those lines actually show the defect (the colliding cron minutes, the stray guard job and
  its `needs:` edge); a well-written diagnosis that the file does not corroborate is still unverified.
- **Gate scripts are repo-root relative.** Run them from the worktree at the PR head, never from the
  long-lived primary clone — a stale clone reports false drift and you will publish it as a finding.
- **`gh pr checks` is a display, not a verdict.** It renders `pending`/`in_progress`/`cancelled` in a column
  people read as pass/fail, and grepping it misses legs entirely (a leg that has not started shows under a
  different row). Read the rollup JSON (`gh pr view <n> --json statusCheckRollup`) when one job's state
  decides your claim.
- **A green scoped gate is not a green PR.** Acceptance at the gate level can be met while a tracked red
  leg from another issue still blocks the head. Report the two separately — "fold acceptance met; CI still
  pending on <tracked red>" — instead of compressing them into one word.
- **No acceptance claim without the sha in the sentence.** "It passes now" without a sha is a claim about
  time, not about the branch.
- **A verdict change on the PR must be mirrored on the tracker in the same pass.** Re-enabling a re-cut, or
  flipping met↔not-met, on only one surface leaves the issue tracker stating the superseded state; the owner reads
  the tracker, sees "wait for freeze / no re-cut owed" next to a PR comment that says "re-enabled", and reads two
  planners in contradiction. Post the new state to the PR and the issue it closes together, each naming the
  comment it supersedes. Three consistent surfaces (PR, issue tracker, ledger) is the deliverable — one correct
  post next to one stale post is not.
- **A fold whose target is a growing live file cannot be accepted until it stops growing, and no new fold
  may be dispatched while it is still growing.** Measure the target's freeze (stable size + mtime, two
  samples apart) before judging the head; a red gate caused by live drifting *after* the fold snapshot is
  not an implementer defect and does not justify a new vehicle — and cutting another re-cut before the
  freeze just yields a fold that is overtaken seconds later, a loop that cannot land. Close only when the
  no-args gate reads zero lane rows at a pushed head; until the live set holds still, hold and re-measure
  rather than re-cutting. See `references/agent-profile-sync.md`.
