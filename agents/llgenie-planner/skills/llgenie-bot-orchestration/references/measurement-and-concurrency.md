# Measurement discipline and GitHub Actions concurrency

Hard-won rules from a night where four lanes each reported "done" against a head that had moved, and the fleet's merger starved itself.

## 1. Measure at the branch tip, never at a remembered sha

A PR's head moves without notice (other lanes push to the same branch). Commands that settle it in one line:

```bash
git ls-remote origin refs/heads/<branch> | cut -f1     # the branch tip, now
gh pr view <n> --json headRefOid,isCrossRepository,autoMergeRequest,mergeStateLevel \
                      ,reviewDecision,mergeStateStatus
```

- `isCrossRepository` is a property of the **PR**, fixed at creation and retained after close. It is not a property of the branch. The test for an approvable head is `state=OPEN && cross=false` on the PR you are looking at.
- A closed PR still answers with its history. Reading `cross=true` off a closed PR and acting on it costs whole exchanges.
- Quote the *content* at a sha (`git cat-file -s <sha>:<path>`, `git show <sha>:<file>`), and re-read it in the turn you quote it.

## 2. `cancel-in-progress: false` does NOT protect a pending run

GitHub keeps **one running plus one pending** per concurrency group, and **a newly queued run replaces the pending one regardless of the flag**. The flag protects only the run already executing.

Consequences:

- A per-branch group on a sweeper (e.g. `auto-merge-${head_branch}`) starves it: every event queues a new sweep that kills the pending one before it starts, so runs die with **no job rows at all**. 16 of 25, then 31 of 48 measured.
- Scheduled triggers collapse into the same group as an empty branch name (`auto-merge-`), so cron sweeps cancel each other too.
- The fix for an idempotent, stateless sweeper is **one repo-wide group with `cancel-in-progress: true`**: it re-reads all PRs each run and each merge is one atomic `gh pr merge`, so a cancellation lands before or after a merge, never inside one.
- A repo-wide superseding group is wrong for anything holding state between runs, or for a job whose *side effects* are not atomic. Do not generalise the fix.

## 3. Distinguish supersession from queue-depth cancellation

`cancel-in-progress: true` on `pull_request` predicts **one survivor per push series**: cancelled ≈ pushes − 1, one success per branch.

If successes are near zero (3 in 100 measured) and runs die while still `queued`, the cause is **queue depth**: the next push arrives before GitHub ever schedules the previous run. The flag is benign at a queue of minutes and destructive at a queue of hours. The lever is depth (fewer concurrent runs, more runners), not the flag.

Corollary: **no PR can become green while its run sits queued for hours**, so a board of `BLOCKED/REVIEW_REQUIRED` is often downstream of starvation rather than an approval problem. The tell: one PR reads `CLEAN` while all others read `BLOCKED` — it is the one whose run happened to be scheduled.

The freeze rule follows: **a head only earns a verdict if it stops moving for longer than the queue takes.** A push into a branch whose run is still `queued` is a cancellation, not an iteration.

## 4. The instrument-reports-a-property-it-did-not-check family

Every one of these was found in one night, in code written that same night by careful people:

| Instrument | What it claimed | What it actually checked |
|---|---|---|
| `verified: N identical` | content matched | files existed |
| `run.status` | verdict | a run row exists |
| standing-rule regex `never\s+merge` | the rule is stated | the words appear anywhere — **a quotation satisfies it** |
| profiles-home caveat | a comparison ran | `Path(x).parent` = `/`, which always exists |
| `live-longer` shrink gate | no truncation | live text, which another lane was rewriting in place |
| `replaced an existing file` | which files changed | counted **after** the copy |

Detection habits that worked:

- **Verify the sabotage, not the green.** A sabotage that passes proves the gate; grep for the remaining occurrences instead of trusting exit 0.
- Make a skip **audible in the success line**, not only in stderr: `OK: 3 profile(s) — tree checks only, LIVE NOT COMPARED`. A reader scanning `&&` chains sees the OK line; `EXIT=0` hides the warning.
- Require a home/directory to **hold** the thing it claims (`<base>/<name>/SOUL.md`), not merely to exist.
- Prefer a **manifest match** over a count when deciding whether a directory is a real home — a count is satisfied by junk, a name is not.

## 5. Re-seeding a live profile is a merge, not a copy

`cp` from live → tree (or the reverse) is a **destructive merge performed without a diff**. Measured: the live file was rewritten in place mid-review, dropping the reference below the tree and silently flipping the gate from FAIL to OK, while the tree held 12 lines that existed nowhere else.

- **Live is evidence, not a source of truth.** It is a directory another lane edits without notice.
- What makes a re-seed safe is **not the direction: it is the allowlist plus the byte compare afterwards.** Copy N named paths, then `CHECK=1` must report N files matching; **a file that differs is a decision to make, not a `cp` to run.**
- Guard the write path too: `sync` must refuse to overwrite a live file newer than the source commit without `--force`, naming both times. A read-time caveat cannot catch a silent write.
- Source time must be **the commit that last touched the path** (`git log -1 --format=%ct -- <path>`), never the file's `mtime`: a fresh clone stamps every file with the checkout time, so an mtime comparison says the tree is newer than any live file and the guard disarms on exactly the checkout that runs the sync.

## 7. A host saturated with local full-suite runs cannot produce a baseline

When lanes verify locally instead of on runners, the host accumulates concurrent full-suite pytest
processes, and every number measured there is a **contention sample, not an idle baseline**. Measured
on the planner's host: eight concurrent full suites, oldest at 103 minutes, when one uncontended suite
on the same tree runs ~30–40 minutes — the extra ~65 min is cache-thrash and preemption between runs.

- **Check the population before quoting a wall-time.** `ps -eo etimes,args | grep -E 'python -m pytest|make ci-unit'`
  — if several full suites are live, the number you extract describes the contention, not the code.
- **A negative result is the finding.** "No host wall-time is an idle baseline while N suites compete"
  settles the question; do not keep restarting the measurement hoping for a clean run. The experiment
  that resolves it is one dedicated runner, one job, timed.
- **Your own local probe is not a fleet CI verdict.** The "never cancel a live matrix" rule protects
  CI runs that reviewers are waiting on. Ending your *own* throwaway timing/comparison process — one
  you started, that has answered its question — is legitimate and reduces the contention you are
  complaining about: find its pid (`fuser <log>` / `pgrep -f 'make -s ci-unit'`), `kill`, and confirm
  it is gone. Quote the retired pid and the surviving processes so it is not mistaken for a cancelled
  verdict.

## 6. A larger file is not a safer file

The dangerous direction is a replacement that is **bigger while dropping lines** — 4, 4, 32 and 30 live lines were missing from four "rewrites" that were all *larger* than the files they replaced. Size is the signal an operator and a gate both read first, so it defeats every shrink guard.

Rule: a rewrite of a rulebook is a decision for that lane's owner, lands as its own diff, and must say what it deletes. Never let a sync or a merge prefer the longer file.
