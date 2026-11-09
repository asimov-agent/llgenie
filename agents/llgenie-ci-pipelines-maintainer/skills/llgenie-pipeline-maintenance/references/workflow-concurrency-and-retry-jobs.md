# Workflow concurrency, and the retry job that must survive it

A retry / recheck / recovery job that lives inside the same workflow as the job it retries is the
common shape (a sweep decides, a second job re-decides what the sweep deferred). Two structural
defects make that retry silently useless, and neither shows up as a red check.

**Re-runnable probe:** `scripts/check-workflow-concurrency-shape.py [GLOB ...]` (default
`.github/workflows/*.yml`) reports finding 1 as a hard failure and finding 2 as a note. Run it on the
OLD tree before writing the fix, so the violation count it names is your baseline, and the same
command returning zero on the fixed tree is the proof — a rule only ever run on the fixed tree has
demonstrated nothing.

## 1. Workflow-level `cancel-in-progress` kills the recovery job too

```yaml
concurrency:                       # WORKFLOW level
  group: whatever
  cancel-in-progress: true         # cancels the ENTIRE RUN
jobs:
  decide:  ...
  recheck: ...                     # <- dies with the run the decide job lost
```

A workflow-level `concurrency:` block with `cancel-in-progress: true` cancels **every job in the
run**, including the recovery job. So a cancellation rate on the deciding job is also a cancellation
rate on the net that was supposed to catch it. "A retry that dies with the thing it retries is not
a retry."

The fix is to split the two halves onto their own job-level groups:

```yaml
jobs:
  decide:
    concurrency:
      group: sweep-${{ github.event.workflow_run.conclusion || 'schedule' }}
      cancel-in-progress: true     # superseding an older SWEEP is correct: it re-reads state
  recheck:
    needs: [decide]
    if: always()
    concurrency:
      group: <workflow>-recheck
      cancel-in-progress: false    # the recovery pass queues, it is never killed
```

Job-level `concurrency` overrides the workflow-level block for that job, so no top-level block is
needed at all. Assert the ABSENCE of the top-level block in a test, or a later edit reintroduces it
and nothing complains.

Partitioning the deciding job's group by `github.event.workflow_run.conclusion` is the only filter
`workflow_run.types` cannot express (it offers only `completed`): a failed or cancelled CI run
decides nothing, so it gets its own group and cannot cancel the pending sweep of a run that DID
succeed. A per-branch group is wrong — a scheduled trigger carries no head branch, so all scheduled
sweeps collapse into one empty-name group and cancel each other.

`cancel-in-progress: false` does NOT protect a *pending* run: GitHub keeps one running plus one
pending per group and replaces the pending one whatever the flag says. It protects the *running* one.

## 2. A multi-item retry must not wait per item

If the deciding job decides ONE item and the recheck decides N items (a cap like `MAX_PR=50`), a
bounded per-item wait that is safe in the first becomes fatal in the second:

```
6 attempts x 30 s = 3 min per item
50 items x 3 min = 150 min   vs   the job's timeout-minutes: 10
```

The recheck would be killed by its own patience, mid-sweep, having merged nothing. Pass an explicit
switch so the single-item path waits and the multi-item path takes the fast read:

```python
def run(..., settle: bool = True) -> int:
    not_green = (settle_unfinished_head(...) if settle else no_concluded_green(...))

# every recheck call site:
run(..., settle=False)
```

Also assert the arithmetic itself, so a future bump of the bound or the retry count reds:

```python
def test_the_worst_case_settle_fits_the_merge_job_timeout():
    assert SETTLE_ATTEMPTS * SETTLE_DELAY_S < 10 * 60 / 2
```

## 3. Prove the retry against the real board, not only fixtures

A dry run costs nothing and is the strongest available evidence when a conflicted head means CI
cannot produce a run id. Drive the real script against the real repository and quote how many items
it actually decided:

```bash
GH_TOKEN=$(gh auth token) GITHUB_TOKEN=$(gh auth token) \
  python3 scripts/<sweep>.py recheck --repo <owner>/<repo> --max-prs <cap> --dry
```

Quote the item count it evaluated. "The old cap of 5 would have decided 5; this decided 12" is
production-data evidence; a fixture proves only that the fixture works.

## 4. Mutating the guard must red the test — confirm it does

When you mutation-prove a new rule, a mutation that leaves the suite green means the TEST is inert,
not that the guard is redundant. Two ways a test is inert here:

- The fixture makes the guarded and unguarded paths converge (a read counter consumed by another
  caller, a state that settles the same way either way).
- The item never reaches the guarded code because an earlier filter skips it (a deferral-marker
  requirement, an early `continue`).

Fix by observing the DISPATCH instead of the outcome, then re-run the mutation:

```python
calls = []
monkeypatch.setattr(mod, "slow_read", lambda *a, **k: calls.append("slow") or "blocked")
monkeypatch.setattr(mod, "fast_read", lambda *a, **k: calls.append("fast") or "blocked")
...
assert calls == ["fast"]
```

The mutated run must print the WRONG value (`called: ['slow']`) and red. Only then is the guard proved.

## 5. Moving `concurrency` is a SHAPE change — grep the suite for the old spelling

Tests that locate the block by regex at column 1 (`^concurrency:`) silently stop finding it once the
block moves onto a job. Grep the test tree for the OLD spelling before pushing, and rewrite the
helper to read the new location while pinning the same BEHAVIOUR (supersession, group partitioning):

```python
jm = re.search(rf"^  {re.escape(job)}:\n(.*?)(?=^  [a-z-]+:\n|\Z)", workflow, re.M | re.S)
m  = re.search(r"^    concurrency:\s*\n((?:[ \t]+.*\n)+)", jm.group(1), re.M)
```

Strip comment lines before asserting on the block text — the block carries its own explanation and
prose that quotes a forbidden value would otherwise satisfy the assertion.

## 6. After another lane re-cuts your branch, re-verify your own commit survived

When the rebase lane rebases your branch onto a newer base, a conflict resolution can keep one half
of your change and revert the other (the workflow edit landed, the matching test rewrite was
resolved back to base). The tests then red on your OWN head and it looks like you broke something.

Procedure after syncing to the live head:

1. `git fetch origin <branch>` and `git reset --hard origin/<branch>` — never keep editing on the
   stale local commit.
2. Check each half of your change is still present (`grep -c` the new symbol, the new group name,
   the new helper signature).
3. Re-apply whatever was dropped, re-run the mutation proof, and commit it as the same atomic
   commit.

Do not treat a red at the synced head as CI being wrong: read it, it is usually your own change
half-applied.

## 7. A designed-hold red is not a code red

An acceptance gate that reads the LINKED ISSUE's checkboxes (not the PR body) reds on every bot PR
whose issue still has unchecked criteria. That red names the issue's items and nothing else — it is
the reviewer-verdict gate, not a defect in the change. Report it as such, quote the gate's own log
line, never self-tick the issue boxes, and route the verdict request to the reviewer with the run id
and the evidence. Distinguish it explicitly in the report from any real red in the same run.
