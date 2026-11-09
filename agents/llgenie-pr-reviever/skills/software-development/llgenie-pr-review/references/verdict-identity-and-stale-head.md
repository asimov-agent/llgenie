# Verdict identity, stale heads, and derived-echo reds

Three failure modes measured on live PRs; each cost a wrong verdict once.

## 1. `gh pr review -r/-a` is rejected when reviewer identity == PR author identity

On agent-authored PRs the token used by this lane (`andyholst`) is the same
identity that opened the PR, so GitHub refuses the review state:

> Can not request changes on your own pull request

Do not retry with flags, do not switch account. Post the **same load-bearing
verdict as a PR comment** — failing gate name, head sha, run id/job id, and the
exact fix — and report it to @llgenie-planner. Say in the comment that the
`-r`/`-a` state was mechanically unavailable due to self-review prohibition, so
the next reader does not think the verdict state was skipped by choice.

Check `gh pr view <n> --json author` against `gh api user --jq .login` **before**
composing the review command when the PR looks agent-authored.

## 2. A verdict measured at a head that has since moved is moot, not wrong-but-standing

Before posting any verdict, re-read in the same breath:

```bash
gh pr view <n> --repo asimov-agent/llgenie \
  --json state,mergedAt,headRefOid,mergeCommit \
  --jq '{s:.state,m:.mergedAt,h:.headRefOid[0:9]}'
```

- `state != OPEN` → no verdict exists to post; if a verdict was already posted,
  **retract it in the PR** quoting the sha judged and the closure/merge time.
- `headRefOid != sha you measured` → the measurement no longer describes the
  branch; re-measure at the new head (a force-push burst can leave 4+ heads
  between dispatch and verdict).
- A PR closed with `mergedAt: null` is *not* merged; a closed-without-merge
  verdict is a ghost frame — withdraw it the moment it is discovered.

### Re-anchor vs re-judge: compare the PR's OWN contribution, never head-to-head

A moved head means the old verdict no longer describes the branch, but it does not automatically mean the
code changed. Decide with the PR-relative diff, not `git diff <old-head> <new-head>`:

```bash
# what the PR proposed at the head you judged
git diff --stat <judged-head>^ <judged-head> -- <graded files>
# what the PR proposes now, measured against ITS OWN new base (post-fetch main)
git diff --stat <new-base> <new-head> -- <graded files>
```

- **Identical contribution → re-anchor.** Re-cite the verdict at the new head with the new sha/run id;
  do not re-run every gate for a pure rebase that only absorbed other merged PRs' base content.
- **Different contribution → re-judge.** Run the graded tests and the acceptance gate at the new head and
  post a fresh verdict that says it supersedes the old one.
- A raw head-to-head diff **inflates**: after a rebase onto a newer main, other PRs' merged changes to the
  same files show up as "the branch changed" when the PR's own contribution is byte-identical. Reading
  182 added lines off the head-to-head diff is the wrong measurement; the PR-relative one is the fact.
- The converse also happens: a rebase lane's **conflict union** (keeping both sides' fixtures) is a real
  content change to graded test files even though it "only rebased" — that one is a re-judge, and the lane
  saying "rebased, green" is not proof the contribution still matches what you judged.

## 3. A dispatch's premise is a claim, not a measurement — falsify each anchor before acting

An inbox/planner dispatch routinely arrives anchored to a board snapshot that is already superseded. Each anchor it names is a **claim to verify**, and a verdict or a write-back that acts on an unverified anchor is a fabricated state. The three anchors to re-measure in the same breath, every pass:

- **"Fresh run in progress at `<head>` with `<legs>` pending."** List the runs filtered on that `head_sha` and read their `created_at`; a run can only be *fresh* if it was created **after** the merge that moved main to the head you are judging. Runs whose `created_at` predates that merge are the old concluded ones (their check-set already has a conclusion, not "pending"). No run created after the head-chaining merge ⇒ **no run at this head ⇒ no verdict** (absent/in-progress is never a verdict).
- **"6 unticked criteria / the designed self-red."** Re-read the linked issue's box marks and `updated_at`; a verdict-gated seam tick that already landed shows every box `- [x]` carrying its `(proven: … comment=<id>)` marker and the acceptance gate green. If the boxes are ticked, no re-tick and no "unblock" verdict is owed — post a correction naming the seam's produced comment id, and say "no re-tick" explicitly.
- **"base == live main, base-race cleared."** Verify with `merge-base(<head>, fresh origin/main) == origin/main tip`, not the PR's `base` field (see `branch-base-and-rebase.md`).

When any anchor contradicts the live wire, trust the wire (PR head sha, run `created_at` vs the head-chaining merge, each issue box mark, merge-base) over the dispatch's text, and **post the measured-state correction on the PR** (facts, "no verdict / no tick owed") — a correction anchored to command output is the deliverable, not a re-posted verdict. Report the correction back to the planner on the same wire so the board unwinds on true state.


## 4. A post-merge "verdict red" can be a derived log echo, not a regression

After a merge, aggregator jobs that fetch logs by job id can 404 on the old
run and re-emit the pre-merge red. Distinguish before attributing a regression:

- Read the gates at the **merge commit / current main** (`guard`, `recheck`,
  `ci-images`, `install`, `lint`, `openspec`). Green there + red only in the
  aggregator echo = derived echo (seen on #1714 and #1732).
- Attribute a main red to a tracked issue class (e.g. `test_top_tier_acceptance.py:321`
  `ccore picks must be high->lower` is the #1713/#1723 per-provider ordering
  class) and record it against a **fresh run id**, never the stale one.
- Never call main green from job totals alone; main is green only when the
  longest gate concludes green **at base==main**.
