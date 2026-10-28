# Reading and attributing a red CI run

Depth for when a PR or `main` reports a failing check. Ordered: read the failure, attribute it to the right ref, then decide whose fix it is.

## 1. Read the actual failure text — it is available

```
gh api repos/<owner>/<repo>/actions/jobs/<job_id>/logs --allow-escape-sequences \
  | sed 's/\x1b\[[0-9;]*m//g'
```

`gh` refuses the raw body with *"the response contains terminal escape sequences; pass --allow-escape-sequences"* and the refusal reads like an empty response (≈99 bytes of message, or 0 through a jq filter). Do not conclude "logs are unavailable": strip ANSI and the whole job log is there, including `FAILED tests/...` lines and the assertion body.

`gh run view <id> --log-failed` only refuses while the **run** is in flight, even when the **job** has completed. Retry it after the run concludes; do not use it as the primary source.

## 2. Attribute before fixing: which ref did that run test?

A log is evidence about **the ref it ran on**. Quoting a branch log as a claim about `main` turns a PR defect into a repo defect and sends a lane after the wrong fix.

- Quote all three: **run id, head sha, and the ref/branch the run belongs to**.
- A repo-wide red must be proven on `main` itself: check out a pristine detached worktree of `origin/main`, run the same test files, and compare counts. Identical failures there mean no PR is at fault and the fix belongs to one `main` commit, not to N branches.
- A PR-level red on a *queued or cancelled* run is not a red — `cancelled` is never a pass, and `queued` owes no verdict.

## 3. One stale edit, many red PRs

When the same N tests fail across several unrelated PRs, suspect a shared base change (a workflow group deleted, a job renamed, a list grown) rather than N lane bugs. Grep the tests for the removed symbol, fix it once on `main`, then re-check each PR: a PR that goes green **with no code change** is the proof, and that sentence belongs on the PR.

## 4. A shape change has a spelling — find who asserted it

Before pushing a change that moves a shape (inline command → make target, `needs` list, `.PHONY` keys, a status field, a manifest), grep the suite for that shape's literal text:

```
grep -rn '<old spelling>' tests/ scripts/
```

A correct fix reds when another test pins the *spelling* rather than the behaviour. Recurring instances: an inline `python3 scripts/x.py` replaced by `make x`; a `needs:` list gaining a new upstream job; a target declared in `.PHONY` but no longer having a recipe; a status field that reports a derived state.

## 5. Assert behaviour; assert lists as subsets

- Pin what the code must do, not how it is written: an assertion on one spelling of a shell fallback false-reds a correct rewrite.
- For anything the tree is meant to extend (workflow sets, manifests, job rosters, profiles), assert **`expected <= actual`**, never equality. Equality reds on the next legitimate addition and teaches the next person to edit the test.
- Keep both directions: a subset check on membership plus a referent check that each listed name resolves to something real.

## 6. Ceilings, and the field that lies

- A job with no `timeout-minutes` inherits the 6-hour default: "hung" and "slow" are indistinguishable for hours. Give each job a budget of **≥2× its slowest observed successful run**, and never set a caller's ceiling below its callee's (a tight caller kills a healthy callee and looks like a red).
- `run.status` can report `queued` for tens of minutes while its jobs hold runners. For a stall, read **job-level** `status`/`started_at`/`runner_name` — an alarm keyed on `run.status` sleeps through a hang.
- `runner_name` empty + `cancelled` means no machine was ever assigned; a job that ran and was then cancelled has a runner name. Starvation and cancellation have different remedies; measure which one it is before cancelling anything.

## 7. Queue economics

- `concurrency: <wf>-${{ github.ref }}` with `cancel-in-progress: true` means every push cancels the verdict the previous head was earning. **One push per head, then freeze until its run concludes.**
- A **queued** run owes no verdict, so superseding it costs nothing; a **running** matrix is 20+ paid minutes, so cancelling it needs a reason. Cancel only matrices whose verdict no longer matters (closed or merged PRs, stale heads).
- Distinguish **starvation** (many queued, nothing in progress — capacity/plan) from **churn** (queue deep but the oldest entry is minutes old — one runner against many pushes). Churn's fix is fewer runs per PR, not more cancels.

## 8. Failure shapes worth naming in the report

Write the verdict as a sentence a merger can act on: *green at `<sha>`, run `<id>`, N success / 0 failure / 0 cancelled, mergeable* — or *not green, because X*. Name cancelled jobs explicitly; never summarise a run with cancelled rows as "green modulo timeouts".
