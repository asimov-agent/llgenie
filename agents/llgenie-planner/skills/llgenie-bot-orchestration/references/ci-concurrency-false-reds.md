# CI-concurrency false reds (fleet gate defect)
A red `linux / unit` is not necessarily a branch defect. Before attributing a unit failure to a PR, read the job log and separate code failures from environmental ones.

## The known class: Hugging Face 429 under parallel unit jobs

Every llgenie PR's `linux / unit` job runs `scripts/unit_tests.py run`, which includes real-Hub tests (`tests/test_pick_full_registry.py`, `test_trending_quant_catalog.py`, `test_pick_matrix.py`, `test_trend_pick.py`). When many PRs push in one window, that is **N concurrent unit jobs sharing one Hub rate limit**.

Observed shape (8 CI runs created in a 28-minute window):

```
42 failed, 14987 passed, 13 deselected, 1 error
36 of 42 in tests/test_pick_full_registry.py
dominant message: "<model>/<engine>/<repo> has no files on the Hub"   (assert [])
6 × urllib.error.HTTPError: HTTP Error 429: Too Many Requests
```

Chain: 429 → Hub returns an empty tree → `assert quant_files` fails on `[]` → dozens of assertion errors that read like registry drift.

## THE CONTROL — run it before calling anything environmental

**A failure is environmental only if the control also fails.** Run the same suite on `main` in the same window:

- main **passes**, the PR **fails** ⇒ it is the PR's own change. Do not call it environmental.
- main **and** the PR fail the same rows ⇒ environmental (rate limit, upstream drift).

**A prior run of the same broken code is NOT a control.** "This head failed before the rebase too" proves only that the rebase did not introduce the failure — it says nothing about the environment, because both heads carry the change. The control must differ in the variable under test: a tree **without** the change.

The sharpest version is a same-window trace of how each tree handled the same transient. Real example:

```
main  (passed, 15025 tests): [hf] rate limited (429) on <url>: waiting 115s (wait 1/2)
#932  (failed, 42 tests):    0 429 wait(s) totalling 0s of the 60s budget (HUB_RATE_LIMIT_BUDGET)
```

Same Hub, same 429, same window. Main backed off and completed; the PR backed off zero seconds and failed. The 429 is the trigger; the PR's own retry code is the cause — it replaced working backoff with a budget it never spends. Grep both logs for the backoff line, not just for `429`.

## Name the mechanism at line level, not from run times

A log-derived cause ("it waited 0s of its 60s budget") is a symptom; the fix depends on **why**. Read both copies of the code before prescribing:

```
#932  hub_open, L198:  if _rate_limited > RATE_LIMIT_WAITS or slept + wait > RATE_LIMIT_TOTAL_BUDGET: raise
main  hub_open, L164:  if _rate_limited > RATE_LIMITED_WAITS: raise      then  time.sleep(wait)
constants: #932 RATE_LIMIT_TOTAL_BUDGET = 60 · main: the constant does not exist
```

The zero-wait was **deliberate fail-fast**, not an accounting bug — and the defect was the **threshold** (60 s smaller than the Hub's rate-limit window, so the first 429 trips it). Sizing the budget is the fix; chasing a counter bug is wasted work. Also check whether the failing test was touched by the PR: an untouched test failing means the PR broke an existing guarantee, which is a stronger claim than "its own test is wrong".

Worked example that refuted a wrong call: `main@564e9383` and PR `#932@1bf1eea7` ran the full unit suite concurrently under one Hub rate limit. Main printed `15025 passed, 13 deselected`; #932 printed `42 failed, 14987 passed` with `6 × HTTP 429` and `60 × "has no files on the Hub"`. Same conditions, different outcome ⇒ **#932's own `scripts/hf_auth.py` change was the cause** — it added `HUB_RATE_LIMIT_BUDGET` and its own message read `0 429 wait(s) totalling 0s of the 60s budget`, a budget never spent, so the 429 was never retried. Lesson: 429s in a busy window prove rate limiting *occurred*, not that it *caused* the failure.

## A red job is not a red test — read the failing step

`linux / unit` runs the suite and then several post-suite gates in the same job. In one night, "unit red" meant three different things:

| shape | evidence | real cause |
|---|---|---|
| suite green, gate red | `15036 passed, 13 deselected` then `make check-import-roots` Error 1 | the PR's own import-roots ratchet (bare 52 vs 47, sys-path 32 vs 26) |
| suite never reached | step 6/6 `openspec-tasks-check` → `FAIL <change>: unchecked at lines [8]` | one unchecked openspec box, which also reds `linux/openspec` — two jobs, one cause |
| suite genuinely red | `42 failed, 14987 passed`, 36 in one module | the PR's own retry threshold returning empty trees |

So: pull the job log, find **which step** returned non-zero, and name it. "unit failed" is not a diagnosis, and the three shapes have three different owners and three different fixes.

## How to classify it

1. Get the job log: `gh api repos/<owner>/<repo>/actions/jobs/<job_id>/logs --allow-escape-sequences` after stripping ANSI (the run-level `--log-failed` is unavailable while other jobs in the run are still in progress).
2. Group the failure text. `has no files on the Hub` + `assert []` + `HTTP Error 429` ⇒ environmental.
3. **Check whether the same head already failed before the change** — a rebased head that fails identically to its pre-rebase sha cannot have been broken by the rebase.
4. **Check whether main's unit is green in the same period.** If main passes while N PRs fail the same rows, it is concurrency, not a shared code defect.
5. **Distinguishing test: a serialised re-run.** One unit job, quiet queue. Green ⇒ concurrency. Same rows fail ⇒ genuine registry drift, which is a real issue worth filing.

## Rules

- Never report `unit failure` without reading the log and naming the class.
- Never push a "fix" to a branch for an environmental red; re-run when the queue is quiet.
- Never cancel other people's runs to free rate limit — that is destroying matrices to clear a queue.
- A red job count overstates work: one unchecked openspec line reds **both** `scope` and `linux / openspec` because both paths run `openspec-tasks-check`. Count causes, not jobs.
