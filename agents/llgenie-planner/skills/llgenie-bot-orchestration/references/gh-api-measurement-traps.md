# gh API measurement traps that masquerade as "no evidence"

Before repeating or refuting a lane's claim, get the measurement right. Each trap below
produced a wrong conclusion in practice because the query, not the repo, was wrong.

## 1. `.../actions/runs?head_sha=` needs the FULL 40-char oid

A 7-char prefix returns an empty list, which reads as "no runs at this head" and invites a
false "nothing is running / nothing was ever run" report.

```bash
FULL=$(gh pr view <n> --json headRefOid --jq '.headRefOid')
gh api "repos/asimov-agent/llgenie/actions/runs?head_sha=$FULL&per_page=20" \
  --jq '.workflow_runs[]?|"\(.created_at) \(.status)/\(.conclusion // "-") run=\(.id) \(.name)"'
```

## 2. An empty `git ls-remote origin refs/heads/<branch>` does not mean the branch is gone

Lane PRs are frequently pushed to a per-clone fork remote, so the canonical `origin` legitimately
has no such ref. Read `git remote -v` first, and treat the PR object as authoritative:

```bash
gh pr view <n> --json headRefName,headRefOid
```

If `headRefOid` matches the tip the lane quoted, the work exists — a missing remote ref is a
remote-naming artefact, not an abandoned branch.

## 3. `statusCheckRollup` is the per-check verdict at the head, and it carries the RERUN conclusion

A lane citing "unit pending" or "ci-verdict FAILURE" from a run created before a publish or a
rerun-watcher pass is stale. The same head can read all-SUCCESS once the rerun concludes.

```bash
gh pr view <n> --json statusCheckRollup \
  --jq '.statusCheckRollup[]?|"\(.status // .state) | \(.context // .name) | \(.conclusion // .state)"'
```

Never route a residual red to an owner issue, and never repeat a lane's residual-red claim,
without a rollup read at that exact head. A run whose `created_at` predates the fix (a published
tag, a merged dependency) but whose jobs ran after it is normal — `created_at` is the run's first
creation, not its last attempt.

## 4. Post-merge gate workflows run with `head_branch=main`

Do not hunt the PR branch for a `ci-verdict`-style workflow run — its run list will show only
`main` rows, which reads as "no verdict exists". The PR's own rollup already carries that check's
per-PR row, so read the rollup, not the workflow's run list.

## 5. `mergeable`/`mergeStateStatus` read `UNKNOWN` transiently after a push or rerun

GitHub re-computes mergeability asynchronously; immediately after a push or rerun both fields
can read `UNKNOWN` even with `reviewDecision=APPROVED`. Re-poll on a later pass; `UNKNOWN` is
neither a verdict nor a defect, and must not be reported as BLOCKED or as merge-ready.

## 6. jq syntax that silently empties a live read (looks like "no data")

Three filters that fail or return empty and read as "nothing on the board":

- **`-q` is not `--jq`.** `gh api` takes `--jq`; a bare `-q` is silently ignored on some
  subcommands and prints the raw JSON (or nothing useful). Use `--jq`.
- **The optional-`?` operator inside a filter can parse-error** (`?.foo` on a projected object)
  and return empty. Drop the `?` once you have selected the array.
- **A `;` between two jq filters is a shell splice, not a jq separator.** `'A; B'` breaks the
  filter. Run two separate `--jq` calls (or one filter with `,`), never `;`.

A boolean filter that mixes `select()` with a bare `and` on a projection also errors — filter to
the list first, then project. When a read returns empty, suspect the query before concluding
"no runs / no checks / nothing landed".

## 7. Reading a failing job's log reliably

`gh api .../actions/jobs/<job_id>/logs` is the source of truth for *why* a check reds. Get the
`job_id` from the check-run's `details_url` (last path segment) or the run's `jobs` list.

**The log endpoint fails closed on ANSI, and the failure reads as an empty log.** Without
`--allow-escape-sequences` the response is a ~99-byte message ending "...pass --allow-escape-sequences
to output it anyway" — a 0-byte redirect to a file, i.e. exactly what "the log is empty" looks like.
Check the byte count before concluding a log is missing; a tiny non-zero file is a refusal, not an
empty log. The flag PERMITS the escape bytes; it does not strip them, so strip colour codes yourself:

```bash
gh api "repos/<o>/<r>/actions/jobs/<job>/logs" --allow-escape-sequences > /tmp/job.log 2>/dev/null
sed 's/\x1b\[[0-9;]*m//g' /tmp/job.log | grep -iE "::error|Error 1|ERROR|FAILED|assert" | tail -20
```

Read the failing STEP, not the job name. Prefer the step-level API over log text when both are
available — it is immune to the empty-read above:

```bash
gh api "repos/<o>/<r>/actions/runs/<run>/jobs" \
  --jq '[.jobs[]|select(.conclusion=="failure")|"\(.name): \([.steps[]|select(.conclusion=="failure")|.name]|join(","))"]'
```

Never infer an empty queue from an empty grep — widen the grep or read the whole log tail before
reporting "no evidence".

## 8. `gh run view <id> --json jobs` returns the run's `jobs` array WITHOUT a `total_count` key

A script that reads `jobs.get("total_count")` to decide "did this run instantiate any jobs?" gets
`None` for EVERY run, because the run-view projection is `{"jobs": [...]}` — the key simply is not
present. `int(None or 0)` can be the true count, so "ZERO JOBS" is reported for runs with live
compiles (real total_count = 3). This silently made a False-Positive monitor (2026-11-06).

The field DOES exist on `gh api .../actions/runs/<id>/jobs`'s top level. For a job-presence count
use that endpoint (`.total_count`), or `len(jobs["jobs"])` from the run-view projection — never
the absent key:

```bash
gh api "repos/<o>/<r>/actions/runs/<id>/jobs" --jq '.total_count'   # 3 (correct)
gh run view <id> --json jobs --jq '(.jobs | length)'                # 3 (correct)
```

## 10. `gh run list --workflow <name>` recency is NOT a lane-idleness signal — most fleet lane workflows are `disabled_manually`

Measured 2026-11-06: `gh api .../actions/workflows` shows `issue-refiner`, `issue-bot`, `fix-bot`, `run-failure-reactor`, `engine-bump-rebase`, `rebase-bot`, `registry-sync`, `code-review-bot`, `architecture-bot`, `bench-disk`, `queued-alarm`, `issue-dedupe`, `registry-sync-review` all `state: disabled_manually`; only `auto-merge` (and CI/gate workflows) are `active`. A "no runs for N days" reading against a lane workflow is a LIE about idleness once the lane moved to host-side/comment dispatch — the run history just stops. Before declaring a lane idle from `gh run list`, check `.workflows[].state` for that path; a `disabled_manually` lane is dispatched out-of-band (message_agent / host cron), and its liveness is measured by its comment/PR activity, NOT its Actions runs. Query: `gh api repos/<o>/<r>/actions/workflows --jq '.workflows[]|select(.path==".github/workflows/<name>.yml")|.state'`.

## 9. `gh api --paginate .../jobs` yields a response that is a CONCATENATED mix you cannot slice as one array

A naive `gh api --paginate .../jobs > f` then parsing `json.load(f)` fails because the response is
multiple JSON values glued together (object + string rows when the auth token differs or pages
interleave). The failure mode reads as "empty/garbled rows" and READ CLEAN in a job-row scan. Use a
single request with `per_page=100` when you need one page, or `gh run view <id> --json jobs`
(single object) for the whole set. Diagnose a monitor that "sees no jobs" by checking whether it
paginates jobs while the source of truth is the non-paginated run-view projection.


## 11 — Refuting an implementer's "pushed / landed" claim: a channel-exhaustive oracle, not one read
A lane claiming a force-push "landed at <sha>" that the wire does not show will insist their `git ls-remote` is truth and yours is stale. Do not argue from one probe. The closed loop that overdetermines the answer: (1) `git ls-remote origin refs/heads/<branch>` on the canonical repo; (2) `gh api pulls/<n> --jq .head.sha` (server-recorded PR head, same second); (3) `gh api pulls/<n> --jq .head.repo` (is the head tracked in the CANONICAL repo or a fork? — if canonical, ls-remote origin is authoritative and there is no second channel the repo serves); (4) if the PR head lives in a fork, `gh api repos/<fork>/branches/<branch>` + `git ls-remote` of that fork; (5) the run-record (`gh api actions/runs/<id>`: a claimed "live producer trigger" shows `completed/cancelled` = dispensed nothing). A claimed sha that matches NONE of canonical-remote, PR-head, and fork-branch exists only as a local object in a clone that never pushed GitHub's tracked ref. Record the fork sha explicitly (it is often a THIRD distinct sha, proving the lane pushed elsewhere or nowhere) and state which of the five layers each claim fails on. Name the implementer's own cited oracle and run it back at them — that is the decisive, non-arguable read.

**Cap the reconcile loop at two posts, then stand down.** A lane insisting on a sha you have disproven across several probes will keep re-sending the same stale claim each time its delivery lands; each of your replies is a real mutation but the loop produces no progress, only board noise. Post the dismissing evidence ONCE with the layer-by-layer table, DM it once, and if the lane repeats the same claim, do NOT author a fourth/fifth reconcile for it. Instead state the standing board position plainly on the thread (rebase state, what is un-pushed, the exact forward path) and end the pass. When a reconcile legitimately has to be corrected or extended (a genuinely NEW channel measured — e.g. the fork branch never queried before), that new fact earns one more post; a re-cite of the same evidence does not. The guard firing again is not a reason to manufacture another reconcile — record the completed board mutation and stop.

## 12 — Verify an acceptance write-back's NAMED artifacts at the cited head, not just that the box is ticked
A verdict-gated tick (issue-body `[x]` + `proven: comment=… head=… run=…`) is only as honest as the artifacts it names. A write-back can tick a box against a SUBSTITUTED evidence set + a self-ruled-out-scope leg: the AC4 change-note criterion named `agent-wiki/2026-11-03-engine-build-timeout.md` + `docs/changes.d/…-timeout.md` + `docs/BOTS.md` row, none of which existed at head `ea0b9033` (only a different `2026-11-02-…-budget` trio + `CHANGES.md`), and the review comment ruled BOTS.md "a mechanism this repo does not use". A tick whose cited artifacts are absent at its cited head is CONTESTED: read the acceptance box list from the live issue body, `git ls-tree -r <head>` for the exact named files, and the actual write-back comment (a later DM may contradict it — the reviewer's own DM said "AC4 not ticked" while the wire showed `[x]`). The resolution signals are (1) the reviewer un-ticking to match their own stated position, and (2) the acceptance gate's own violation count (`check_pr_acceptance.py check` → N violations stays the design hold set). The gate's violation list is the authoritative state; a lane's private DM recount never overrides it. Never accept a tick whose named-change-note files you have not verified exist at the head, and never claim "the gap is tracked" without confirming the tracking issue exists and is actually dispatched (see the #1826 case: it existed unclaimed for turns while it was called "tracked").

## 13 — `timeout_minutes: null` from the Jobs API is an ARTIFACT, not evidence of an unbounded job
The Jobs API (`.../actions/runs/<id>/jobs`, `.../actions/jobs/<id>`) exposes **no timeout field** at all, so any projection of `timeout_minutes` reads `null`/absent for EVERY job — including `guard`, which declares `timeout-minutes: 10` in yml. Concluding "this job has no timeout, that is why it hangs" from a null API field is a false diagnosis. **The workflow yml is the only authority on a job's bound.** Read it at the exact head with `gh api repos/<o>/<r>/contents/.github/workflows/<f>?ref=<sha> --jq .content | base64 -d` and grep the job block. A job absent from `main` but present at a PR head is that PR's own unmerged diff — a main-side fix cannot bound a job main does not have.

The companion trap: a step that legitimately waits (e.g. `make check-engine-pins-published WAIT=290`) may pass its bound as a **Makefile variable that is MINUTES, not seconds** (`--wait-min 290`), so a 60-minute `in_progress` reading is the design working, not a hang. Read the make target's own help line before calling a long wait a defect: `git show <sha>:Makefile | grep -n -A3 '^<target>:'`.

## 14 — A lane reporting `in_progress` for a COMPLETED job is serving a memoised read; `completed_at` outranks `status`

A lane that keeps reporting "`linux / unit` still in_progress" for a run you have measured `completed/success` is not lying and is not disputing you — its watcher is replaying a cached API response from before the job finished. Measured repeatedly: the job's `completed_at` was ~1h in the past while the lane's "live just now" read still said `in_progress`, and its `updated_at` never advanced (an unchanged `updated_at` over a long span is itself proof that nothing is left to advance).

**Durable authority rule:** a non-null `completed_at` means the job is DONE regardless of a cached `status`; when the two disagree, `completed_at` wins. A job "in progress" longer than its workflow's `timeout-minutes` is a stale read, not a hung runner.

```bash
gh api repos/<o>/<r>/actions/runs/<id> \
  --jq '"\(.status)/\(.conclusion) attempt=\(.run_attempt) updated=\(.updated_at)"'
```

**What to do (and what not to):** correct once with the state, and once more only if you hold a genuinely NEW fact (the exact `completed_at` timestamps). After that, **stop messaging the lane** — every further DM is a real mutation that produces board noise and no progress (two-post cap, trap 11). Instead post a *timestamp block* on the issue thread: the run's `status/conclusion/attempt/updated_at` and the job's `started_at`/`completed_at`, plus the note that a `completed_at`-bearing job cannot still be running. That record is durable for every future reader and cannot be re-derived wrongly.

Name it for what it is to the owner: a fleet **observability** defect (stale reader), not a coordination defect. Only restarting that lane's session/tooling clears it; the planner cannot fix another profile's tooling and must not keep re-sending to compensate. Meanwhile force the lane onto gate-free work (a fresh dispatch) so its idleness is spent on a real branch rather than a poll that will never fire.
