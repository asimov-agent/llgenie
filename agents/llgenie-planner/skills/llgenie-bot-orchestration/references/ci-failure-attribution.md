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

**The cheap discriminator is a two-sided count**, e.g. `notes 222 / rows 222` on `origin/main` against `222 / 221` on the branch — one missing artefact, not a broken feature. Quote both sides; a one-sided count is an opinion.

And when the missing artefact is generated or indexed, **rebase, never edit**: adding the row or file in the PR diff duplicates it after the rebase. Batch the affected set onto one fresh base in a single pass (one matrix instead of N staggered 20-minute ones), and report `base sha · PR# · head before → after` per PR. A rebase is legal only where the failure is *shared*; where the PR owns the red, the owning lane fixes it and the sweeper says so.

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

## 8. A rebase is a re-measurement, not a replay

Rebasing a branch that sat for hours is not a mechanical conflict resolution: `main` changed the *premises* the branch encodes. Expect to find, and to re-derive rather than trust:

- a **baseline recorded at the cut** (a ratchet count, a file census, a snapshot of accepted findings) that no longer matches what `main` produces — re-measure it against an export of the new base and record what the branch *actually* produces, or the guard reds on `main` itself;
- an **index/record model that changed** (one file per change instead of one row in a table) — the old shape is wrong in kind, not in content, so the fix is regeneration, not a merge of both sides;
- a **lint or format rule that did not exist at cut** — a "keep both sides" resolution glues a heading onto the previous paragraph and reds `lint`.

State the base sha in every rebase report, and when the branch predates a model change, say **"stale in kind, needs rebase"** instead of "missing row": the two need different fixes.

## 8.5 A consumer job that polls for a DISABLED producer's artifact

When a job fails with "<artifact> was never published within N minutes / no producer cell state" or a `manifest unknown` on a tag it waited for, the defect is usually NOT the consumer: some other workflow is supposed to PUBLISH that artifact, and it is `disabled_manually`. A job that `gh ci-wait-engine-images`-style polls GHCR for an image can burn its whole budget waiting for a producer that no enabled workflow drives.

Discriminate producer-disabled from consumer-broken before attributing:
- check the producer's workflow state: `gh api repos/<o>/<r>/actions/workflows —page` and grep the named producer for `disabled_manually`;
- confirm the artifact truly is absent: `docker manifest inspect ghcr.io/<o>/<r>/<image>:<tag>` → `manifest unknown`;
- note that an ACTIVE sibling (`publish-agent-image`) may publish a DIFFERENT artifact (the agent image, keyed by hash) and is NOT a substitute producer for the engine/router image the consumer waits on.

This reds every PR's job (not one lane), so it is a base defect, and the fix is an OWNER re-enable decision (or a build-in-band `needs:` redesign so the consumer consumes the artifact the same run built instead of polling a remote), NOT a code fix in the PR. Frame it as "the producer that workflow X's gate depends on is disabled" rather than "a bot forgot to publish" — the producer cannot publish while disabled, so the unblock is the owner's, and the failed install is the symptom to report, not the thing to edit.

**The structural fix is to make the consumer test a leg of the producer.** Once you have diagnosed a decoupled poll (consumer waiting on a tag some other workflow may or may not publish), the durable remedy is not just re-enabling the producer but *moving the consumer's test into the producer*: each producer matrix row already does `build-engine -> verify -> push`; append the install/dry-run/author its own just-published image after the push. Then "the artifact exists" and "the artifact installs" are properties of the one pipeline that builds it, the 30-minute poll disappears from the consumer, and a disabled producer can no longer red a consumer — there is nothing left to poll. Frame the request as one pipeline owning both the publish and the acceptance of what it published, not as N files to touch.

## 8.6 `openspec-tasks-check`: one unticked checkbox reds TWO jobs, and `validate` is not `tasks-check`

A PR whose `openspec/changes/<change>/tasks.md` still contains `- [ ]` lines fails `openspec-tasks-check` with
`[openspec-tasks] FAIL <change>: unchecked task checkbox(es) at lines [...]`, and `ci-openspec` exits 2. Because
`scope` runs `check-docs`, which runs `openspec-tasks-check`, **that one cause reds both `linux / openspec` AND
`scope`** — two red job names, one defect. Do not report the pair as two independent problems, and do not assume a
`scope` red is the census.

- **`openspec-validate <name>` green means the spec TEXT parses; it says nothing about the checkboxes.** A lane citing
  validate as proof the tasks are done is citing the wrong gate.
- The tasks file is the **author's** content. A rebase/sweep lane must not tick another lane's boxes — that fabricates
  progress and is the failure the gate exists to catch. Route the named line numbers to the owning lane.
- Tick a line only with the evidence that line names. A task reading "`make test-unit` … exit 0" requires **that
  target**, not a hand-rolled `pytest tests/` — the target is what CI runs and what the checkbox asserts. A task whose
  proof does not exist stays unchecked and is reported by name; a falsely ticked box is worse than an unticked one.
- Timing: work the tick only after the head's in-flight runs conclude, then push one commit — never cancel a matrix to
  land a checkbox.

## 8.7 A live-network test inside a hermetic gate shows up as slow, then timeout-at-low-percent

A hermetic CI gate (unit job running `-m "not network"` over `tests/`) that still contains a test reaching a real
live service — the HF Hub, GHCR, any remote — is not a flake and not "slow hardware". It is a **misclassification**:
the test belongs to the `network`-marked set (a separate main-merge/scheduled pipeline), not the hermetic PR gate.

Attribution fingerprints, in order:

- **`Timeout (N:MM:SS)!` at a low progress % restarts nothing**: a per-test timeout firing early in the run (e.g. at
  14%) with the suite otherwise sailing past means one specific test is hanging on I/O, not the suite being slow.
- **Per-test timeout duration equals the ceiling budget** (e.g. `pytest-timeout` 5:00): the test is spending its whole
  budget on one upstream wait (HTTP 429 rate-limit under concurrency, a dropped connection, a hub that never answers).
  A remote service under rate-limit 429s: the fail is *the test's own network reach*, independent of the branch.
- **A hermetic-local contract is broken**: `make test-unit` without `HF_TOKEN` should be offline-runnable; if it
  genuinely reaches the Hub it violates that. "Green in CI with the token, red offline" is the tell.
- **Progress lines separate by minutes** (23:31 → 23:35 → 23:40 → 23:45): those gaps are remote stalls/retries.

Consequence and fix: *moving the test to the network-marked set is a fix, not a workaround* — it is what `-m network`
exists for, and it changes *where* the test runs (main-merge/scheduled pipeline), not *whether* it runs. Classify fast:
find every un-marked scope that reaches a live hub (`grep` for `hub_open`/`hub_json`/ranged GETs to `huggingface.co`,
and check the network-marker pin actually asserts no un-marked scope reaches the Hub), mark them `@pytest.mark.network`,
and let the pin (`test_network_marker.py`'s AST reach check) catch the class, not the instance. Verify by running the
*selection* — `make test-unit` must deselect the marked tests and `make test-unit-network` must still collect them —
do not hand-pick one marked file and call the class fixed.

## 9. Failure shapes worth naming in the report

Write the verdict as a sentence a merger can act on: *green at `<sha>`, run `<id>`, N success / 0 failure / 0 cancelled, mergeable* — or *not green, because X*. Name cancelled jobs explicitly; never summarise a run with cancelled rows as "green modulo timeouts".

## 10. A gate failure at a head that exists nowhere is fabricated, and verifying is cheap

Three lanes in one session attributed red checks to heads that were reachable on **no** remote or local ref
(`913049ee` for #1138, `5a62dd08` for #1117): the architect reported a phantom new-head, the rebase lane then relayed
it as a diagnosed "guard FAILURE" with invented authors (`architect@llgenie.local`), and another lane re-stated the
same phantom for a different PR. Checking costs three commands and settles it in seconds:

```bash
git ls-remote origin | grep -i <short-sha>        # on a real ref?
git for-each-ref | grep -i <short-sha>            # a local ref?
gh api repos/<o>/<r>/commits/<PR-head>/check-runs --jq '.check_runs[]|"\(.name): \(.status)/\(.conclusion)"'
```

- A sha cannot be called a phantom on reachability alone. **A run that carried it as `head_sha` is authoritative proof the branch was there** — force-pushing past it makes it unreachable *now*, not fabricated *then*. Before calling any reported sha a phantom, query `actions/runs?head_sha=<sha>`; a match ends the question. Reachability is absence-of-evidence-now, not evidence-of-fabrication. (Cost a lane a retracted false accusation: a real `913049ee` guard FAILURE I labelled fabricated because I measured the PR's current head instead of the run's head.)
- **A gate verdict is bound to the head it ran at.** A lane may truthfully report a failure at an intermediate head that has since advanced past it; measuring only the current head then calling the report "fabricated" is precisely the measurement-error class this rule exists to stop. To adjudicate, read the run's `head_sha` + `jobs[]` log, then the current head's check-runs — both, in that order.
- Gate verdicts travel: a phantom head diffuses across lanes within minutes, each attribution sounding more authoritative than the last. Break the chain by insisting the head exists before believing the verdict.
- A **fabricated finding is worse than a stale one**: stale says "I measured earlier", fabricated says "I measured something that is not there". Paste the check-runs at the reachable head as the floor for any future "failure".

## 11. A lane's self-diagnosis of its own author identity can be inverted against the allowlist

`scripts/check_pr_authors.py` derives `ALLOWED` from `ALIASES` (email -> name frozenset) and gates on **names**, so
an allowlisted address can look like a "typo" to the lane that authored through it. Measured: a lane reported its own
PR `support@docondee.com` as a one-extra-letter typo needing re-author, when that address is the canonical `ALIASES`
entry for "Asimov Agent"/"Mr. Asimov" and `check-pr-authors` passes it. Verify against the gate's real allowlist,
never against a lane's narrative about it:

```bash
git show <base>:scripts/check_pr_authors.py | sed -n '/^ALIASES/,/^}/p'    # the email->name map
gh api repos/<o>/<r>/pulls/<n>/commits --jq '[.[].commit.author.email]|unique[]'
```

Before dispatching a re-author (which rewrites commits on a branch), read the map: if the claimed offending address
is in `ALIASES`, the gate is green and the re-author destroys a correct identity. Re-author only on a real
`ALLOWED`-ban. Same rule that stops me re-correcting numbers: cite the gate's own output, not the lane's gloss.
