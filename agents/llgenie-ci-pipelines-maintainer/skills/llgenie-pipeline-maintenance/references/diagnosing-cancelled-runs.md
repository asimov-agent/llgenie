# Diagnosing a CI job that ends `cancelled`

A job whose `conclusion` is `cancelled` produced **no verdict**. It is not a test failure to debug in
code, and it is **not green**. Report it as **UNTESTED**. A PR whose current-head suite was cancelled —
or that has no run at its head at all — is untested, and "0 failing checks" is a lie in that state:
`cancel-in-progress` kills each new push's CI, leaving only the sub-minute guards (guard/scope/holds)
completed and green while the matrix that actually proves the PR never ran.

## Step 1 — decide: is it the wall?

**First resolve the CURRENT head's runs — and there may be several.** One head can carry a cancelled
attempt *beside* a live re-run (attempt 2). Aggregate every run whose `head_sha` equals the PR's head:
any run still `status != completed` → **in-progress**; any `completed/success` → **green**; only when
nothing is live and every run at the head was cancelled is it **UNTESTED**. Reading a single
`at_head[0]` reports a false UNTESTED while a re-run is actually testing (or a false green from a stale
attempt) — the mirror of the cancelled-forges-green trap.

```
gh api "repos/<o>/<r>/actions/runs?branch=<ref>&per_page=20" \
  --jq '.workflow_runs[]|select(.name=="CI" and .head_sha=="<head>")|"\(.id) \(.status)/\(.conclusion//"-") attempt=\(.run_attempt)"'
```

Compare `started_at → completed_at` against the job's `timeout-minutes`. If the duration is ≈ the
ceiling **and** the log carries no `N passed / N failed` summary, the suite was killed mid-run at its
own ceiling — a TIMEOUT-cancel, not a failing test.

```
gh api repos/<o>/<r>/actions/jobs/<job-id> --jq '"\(.name) \(.conclusion) \(.started_at)→\(.completed_at)"'
git show <ref>:.github/workflows/pipeline.yml | grep -n timeout-minutes   # the ceiling
```

**Take the duration from the JOB's `started_at → completed_at`, not the run's `created_at → updated_at`.**
The run-level window spans the gap between attempts, so a cancelled attempt-1 followed by a later
attempt-2 reads far longer than either job actually ran — a 44-minute unit job reports as ~85 minutes.
The per-attempt wall is what separates the two kinds of "cancelled": an 18-second supersede (a new push
replaced it) and a 44-minute timeout (it ran and was killed) both read `cancelled`, and only elapsed
tells them apart. Report the attempt-duration pair for a head with several cancelled runs, never a
single run-level number — the run's created→updated is not a job duration.

## Step 2 — find what consumed the clock (progress-gap analysis)

Strip ANSI, then measure the gaps between pytest progress markers `[ NN%]`. A multi-minute gap at a
near-static percentage is a **stall** (a blocking call), not slow tests.

```
gh api repos/<o>/<r>/actions/jobs/<job-id>/logs --allow-escape-sequences | sed 's/\x1b\[[0-9;]*m//g' > log.txt
```

Parse `T hh:mm:ss .*\[ *(\d+)%\]` lines, keep gaps ≥ 2 min, print `gap, pct→pct, t1→t2`, and sum them.
If the gaps dominate the wall (e.g. ~50 of 60 minutes), the clock went to stalls and the ceiling was
never the real problem — raising it only delays the same cancel.

## Step 3 — find the hanging call (faulthandler dump)

pytest's faulthandler prints `Timeout (0:05:00)!` then a thread stack. The **deepest repo frame** is the
blocking call. In the llgenie unit suite this is typically a live HuggingFace Hub request —
`hf_auth.hub_open` reached via `model_engine_pick._hub_open → _hub_json → _tree → _snapshot →
plan_download → offer` — running inside a test the suite *believes* is hermetic (`-m "not network"`).
A test that is not in the network-marker exclusion does live I/O and stalls on a slow/absent network.

## Step 4 — separate the two defects (never let one hide the other)

A wall-cancel usually has two independent causes:

- **A network / hermeticity leak** — live I/O inside the "hermetic" suite (usually the dominant cause).
  Fix: mark/exclude the test or remove the network path. **Raising the ceiling does not fix this.**

### The merge-to-main-only seam for live-HF tests (the routing fix)

When the ask is "move the live-HF tests out so they only run on `main`," the repo already has the
seam — do not build a new one. `@pytest.mark.network` is the routing primitive:

- `ci-unit` (the PR gate) runs `python -m pytest … -m "not network"` — a marked test is **deselected
  from every PR's CI**.
- `.github/workflows/ci-hf-live.yml` runs `make test-unit-network` (which runs `-m network`) **only on
  `push: branches: [main]`** plus a nightly cron + manual dispatch — **never in a pull request**.

So the fix for a leaked test is to add `@pytest.mark.network` to the test(s) that reach the Hub (e.g.
the `_offer()`-based tests in `tests/test_mac_trend_pick.py`, the `_tensorfold_row()`/`mp.offer` tests
in `tests/test_tensorfold_seamless.py`). They leave `ci-unit` and run only on merge-to-main. The
`#1000` routing census (`scripts/` network-marker census) pins each mark — update it in the same
change so a removed/added mark is a named red, and prove the routing with a negative control (marked →
test is `-m "not network"`-deselected; unmarked → it runs and stalls). A test is not "moved" until the
PR-gate selection actually drops it.
- **A ceiling below the max-green** — `timeout-minutes` sits under the suite's measured maximum GREEN
  runtime, so a legitimately-long full suite is cancelled. Fix: raise the ceiling above the max-green
  (below). Raising it *alone* hides the leak.

## Setting the ceiling from the MAX-green, never a fast run

Derive `timeout-minutes` from the **maximum green observation** across many completed runs — never from
a fast run, never from a failing one. Compute max over green unit jobs (the job name has spaces:
`linux / unit`), then set the ceiling above it with headroom, staying below the longer `install` path.

When a test pins the ceiling literal (e.g. `assert unit <= 60`), do **not** delete the assertion — it
encodes real intent (`unit` is the tightest long-job ceiling; `unit < install`). Update the stale
literal to a bound above the measured max-green, state the reason in the docstring, and keep the
`unit < install` invariant. Prove it with a negative control: plant the old value → the test must FAIL;
restore → it PASSES.

## Measure the tree that is actually `main` first

Before any finding, confirm the checkout you are measuring is the freshly-fetched main, not a stale
shadow. A worktree parked on an old branch (or a local `refs/heads/origin/main` that is not the real
remote) answers every question about a tree that is not `main`, and the conclusion is confidently
wrong. Fetch with an explicit refspec, then assert the head you measure against:

```
git -C . fetch upstream main          # the canonical remote is asimov-agent/llgenie
git rev-parse --short HEAD upstream/main   # must match, or check out a clean probe from upstream/main
```

A separate clean `git worktree add /tmp/probe upstream/main` is the cheapest way to measure without
disturbing the checkout you are editing. State the sha every finding was measured at — a finding
without a head is a claim about time, not about the branch.

## A static guard only sees the patterns it enumerates

A "hermetic" leak guard that scans source for network primitives matches only the reach shapes in its
list. A Hub reach through a helper — e.g. `mp.offer(registry, ...)` reaching
`hub_open` deep inside `plan_download → _snapshot → _tree` — passes the scan if `mp.offer` is not in
the entry pattern and no URL literal sits at the call site. So the guard passes while the suite really
reaches the Hub. **Prove the guard catches the bug before trusting it:** plant the reach (spy on the
lowest primitive, or add the symbol to the pattern) and confirm the guard reds; a guard only ever run
on the clean tree has demonstrated nothing.

## Recovery: re-run, never push

To get a verdict on a cancelled head, `gh run rerun <run-id>` — a re-run **keeps the sha** and produces
a verdict. A push cancels the live run again (`cancel-in-progress`), turning one lost verdict into
several; a busy branch can lose every head this way. **Never push "to make CI run",** and never push to
a branch another lane owns while its run is live — hand that lane the sha and let it push on conclusion.

## A mutation must be posted once, verified, never re-issued blind

When a tool/guard blocks your **read-back** (auth, an integrity gate, a hung API) you may be unable to
confirm a comment or issue post landed. That is **not** a reason to re-issue it: each `gh pr comment`
that does land is a duplicate. (A read-block on #1128 once produced **14 identical routing comments**
before the deletes caught up.) Re-issue only after the first attempt's outcome is confirmed — check
`/comments` for your own body before posting again — and a duplicate streak is cleaned by deleting
every copy but the oldest, keeping the one with the most evidence, then verifying the count is exactly
one. Do not add more copies to "fix" a blocked read.
