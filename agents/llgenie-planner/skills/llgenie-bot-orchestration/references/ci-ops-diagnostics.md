# llgenie CI: diagnostics, approval identity, queue capacity

Hard-won operational facts that cost hours to learn.

## 1. Read the failure — the log is one flag away

```bash
gh api repos/asimov-agent/llgenie/actions/jobs/<job-id>/logs --allow-escape-sequences \
  | sed 's/\x1b\[[0-9;]*m//g'
```

- The plain call returns **0 bytes**: `gh` refuses to emit ANSI escapes without the flag. It is a CLI guard, not an API limit. Every lane believed logs were unavailable; they were not.
- `gh run view --log-failed` refuses while the **run** is in flight, even if the **job** already completed — use the per-job endpoint.
- Payoff: six failing tests that read as "six lane bugs" were one stale-assertion class, named by a single log read. Diagnose from the log before dispatching a sweep.

## 2. Approval identity — the author can never approve

- Bots push as the owner's account (`andyholst`), so `gh pr review --approve` fails with *Can not approve your own pull request*, and `--admin` cannot bypass a review rule while the token scope is `write` (not `admin`).
- A second identity already exists: `.github/workflows/auto-merge.yml` holds `secrets.BUMP_TOKEN` (login `asimov-agent`) and calls `make auto-merge … APPROVE=1`; `scripts/auto_merge.py::try_approve()` asserts approver ≠ author.
- So "green ⇒ approved ⇒ merged" is a **token / `allow_auto_merge`** question, never a code change. Do **not** add a second approve step — a duplicate `--approve` reds a green PR with 422.
- Before blaming `reviewDecision`, read the run's `[auto-merge] PR #N` state line. Real causes seen: the sweep itself was queued behind the CI it waits on; or it executed and failed on a non-event ("no open pull request for run …").

## 3. Preflight: name the remote, then the sha

Two main clones with **different remote names**:

| clone | canonical remote |
|---|---|
| `/home/asimov/repository/git/llgenie` | `origin` = asimov-agent |
| `/home/asimov/repository/git/ai-repositories/llgenie` | `upstream` = asimov-agent |

Worktrees inherit the clone that created them, so `git fetch origin main` validates **the fork** in one tree and upstream in the other. Check `cat .git | head -1` → `git remote -v` → `git ls-remote <remote> main` before any fetch or push. Quote the sha **and the ref it was measured on**: a log is evidence about the branch it ran on, not about `main`.

## 4. Capacity is the board's real blocker

- One or two Linux runners serve every PR. A single long matrix (e.g. `linux / unit` with no `timeout-minutes`) holds the pool and everything queues behind it — measured at 46 queued / 2 running.
- Runs belonging to **merged or closed** PRs are pure waste and the cheapest thing to cancel; that single action freed a 41-deep queue. Old `macos/unit` rows on pre-#871 branches are the worst offenders.
- **Never sweep-cancel live matrices.** A job cancelled 21 minutes in is indistinguishable from one that never started, and it destroys the evidence the removal decision needs. Freeing a runner is not fixing a job that will not finish.
- With an empty queue a full PR matrix finishes in minutes — so "slow CI" and "no capacity" are different diagnoses with different remedies.
