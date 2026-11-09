# Verdict + write-back: post once, verify by read-back, never re-run

Applies to the finalization step of a review: posting the verdict and running the #1644
acceptance write-back (`scripts/acceptance_writeback.py writeback --issue <n> --proven …
--verdict-ref 'reviewer=<lane> comment=<id> head=<sha> run=<runid>'`).

## 1. One write per head, then confirm on the wire

- Post the verdict **exactly once per head**. Self-authored PRs reject `-a`/`-r`
  ("Can not approve your own pull request"), so use `gh pr review --comment` or
  `gh pr comment`; the merge-state signal is not available to the fleet token.
- A write-back ticked on a RE-STAGED head still cites THAT head. When the rebase lane re-pushes
  a branch onto live main (`#1848`: `dd57b47e92` → re-staged `9fd08a43` on base `b4e366c2`), the
  evidence battery (tests, merge-tree, gate) is re-run at the NEW head and the `--verdict-ref`
  names the new sha. Old-head citations on the issue thread are historical, not the tick's anchor.
- The write-back itself creates **no CI run id** — it is an issue-body PATCH (`PATCHED #<n>`);
  reporting "the write-back run id" when a lane asks for one means reporting the gate evidence run
  at the head (e.g. run `<id>` @ head) and saying no run is created by the PATCH.
- Run the write-back once. Read the verdict comment id from the *write's own URL output*
  (`…#issuecomment-<id>`) — not from a re-query that may match an older copy.
- Confirm with a direct read-back, not an assumption:
  `gh api repos/<owner>/<repo>/issues/<n>/comments --paginate --jq '.[] | select(.body|test("proven")) | .id'`
  and re-read the body's `- [x]` count against the criteria count
  (`gh api repos/<owner>/<repo>/issues/<n> --jq .body` then count `^- \[x\]`).

## 2. Empty-looking output means READ BACK, not re-run

A tool result that appears empty, truncated, or missing is **not** evidence the write failed.
Re-invoking the write is the wrong move: it duplicates comments and review submissions on the
wire, and a duplicated trail then has to be cleaned. The evidence that a write landed is its
exit status plus returned URL/id; a re-run only manufactures duplicates.

Corollary: never send the planner a "finalization unconfirmed — please re-run the write-back"
escalation before doing the read-back. If such a DM already went out and the work turns out to
have landed, send one correction carrying the confirmed state; do not redo the writes.

**Inverse failure mode: a read that DID return data is proof — stop verifying.** The opposite
trap is a verification cascade: re-deriving a read-back that already surfaced its answer, then
writing `deferred-proof` / `readback-status` / `confirm` scratch files that restate what the tool
already returned. One successful read-back is the whole proof. Before concluding a read was
"suppressed", check whether the tool result actually came back empty — a result carrying
`ticked:5`/`blank:0` (or `PATCHED #<n>` with exit 0) answered the question, and the correct next
action is to report, not to build a file-based readback handshake around it. Do not re-run the
same `gh api` query "to be sure", and do not manufacture a decision record for a check that
passed. Keep exactly one final verified record per head, not a series of them: a trail of
near-identical status files makes a completed verification look unfinished to the next reader.

## 3. Dedupe: keep the comment the provenance pins

The write-back stamps `(proven: … comment=<id> …)` into each ticked box. That `<id>` is
load-bearing — the surviving verdict comment must be the one referenced there, or the markers
dangle. Delete only redundant copies:
`gh api repos/<owner>/<repo>/issues/comments/<id> -X DELETE`, then read back the survivor list.
PR **review** submissions (state `COMMENTED`) cannot be deleted via the API — leave them and
state that plainly rather than claiming the thread is clean.

## 4. Report the run id you actually verified against

Record the completed SUCCESS run id at the head in the provenance ref (the holds/CI run that
finished green at that sha). A run that is still in-flight, or `cancelled`, proves nothing; cite
only a concluded run and tie every finding to the head sha.

## 4b. The `--verdict-ref` anchor must be THIS PR's own verdict at THIS head

The `comment=<id>` inside a written-back `(proven: …)` citation is the identity anchor for the
tick. Two ways to get it wrong, both silent — no gate, diff or test flags a bad anchor:

- **A review id copied from a different PR.** The id was grabbed from an older note or a queue
  reply rather than this PR's own artifact, so the marker cites another PR's verdict. Before
  citing any review id, confirm it belongs to this PR at this head:
  `gh api repos/<o>/<r>/pulls/<n>/reviews --jq '[.[]|select(.commit_id=="<full-head-sha>")|{id,state}]'`
  — an empty list means no verdict exists at the head and nothing may be cited.
- **A review whose `commit_id` is a superseded head.** After a re-stage onto a moved base, the
  old review is history. It cannot anchor a tick at the new head; re-run the evidence battery at
  the new head and post a fresh verdict there.

**Preference order for the anchor: post the verdict at the current head first, then cite it.**
`gh api -X POST repos/<o>/<r>/pulls/<n>/reviews -f commit_id=<full-head-sha> -f event=COMMENT -F
body=@<file>` (self-authored PRs reject `-a`/`-r`), read the returned id back with a direct
`…/reviews/<id>` fetch, and use that id. Only when no review can be posted at the head does the
fallback apply — the writer's own source-record comment id on the issue + full head sha + the
gate evidence run id, stated as such in the marker, so the next reader knows why a review id is
absent.

A wrong anchor in an already-PATCHed body is fixed by **posting a correction comment** that names
the right anchor and whose id you record — never by re-running the write-back, which fabricates a
second PATCH and a duplicate citation trail. Correcting the citation does not re-open the tick:
say plainly that the boxes stand and only the provenance text was wrong.

## 4c. `apply` and `writeback` take DIFFERENT arguments — and a discarded stderr hides the refusal

The two subcommands of `scripts/acceptance_writeback.py` are not the same call shape:

- `writeback` takes `--issue <n>` (plus `--repo`, `--dry`) and PATCHes the live issue body.
- `apply` takes **only** `--body-file`, `--proven`, `--verdict-ref` and prints the rendered body to
  **stdout**. It has no `--issue`/`--repo`: passing them exits
  `error: unrecognized arguments: --issue <n>` with a non-zero status and **no** rendered output.

So the local preview is always the redirect form:

```bash
python3 scripts/acceptance_writeback.py apply --body-file /tmp/<pr>_body.md \
  --proven 2,3 --verdict-ref '<literal ref>' > /tmp/<pr>_rendered.md
sed -n '/## Acceptance criteria/,/^## /p' /tmp/<pr>_rendered.md   # inspect the ticks
```

Never `2>/dev/null` this call. With stderr dropped, a bad invocation produces a **zero-byte render
file** and the useful line (`unrecognized arguments: …`) is gone — the empty file then reads as a
rendering bug or as "the tool suppressed output", inviting a retry of the live PATCH instead of a
fix of the command line. When a render comes back empty, re-run it with stderr visible **before**
concluding anything about the body.

## 5. A partial tick cannot go through the full-count wrapper — drop to the seam
When only a *subset* of an umbrella's criteria is provable at this head (the rest need a later
vehicle, or one criterion is self-referential and un-tickable pre-merge), do NOT use
`scripts/review_finalize.py finalize` — its read-back asserts `len(ticked) == --criteria`, so a
4-of-5 tick reads `unconfirmed` even though it landed correctly. Use the seam directly:
`python3 scripts/acceptance_writeback.py writeback --issue <n> --repo asimov-agent/llgenie
--proven 1,2,3,4 --verdict-ref 'reviewer=<lane> comment=<id> head=<full-sha> run=<runid>'`,
`--dry` first. Before the live PATCH, run `apply --body-file <fetched body>` locally and inspect
the five acceptance lines: every proven box `- [x]` with the `(proven: … comment=<id>)` citation,
every unproven box still `- [ ]` with **no** citation, and the criteria count unchanged. After the
live PATCH the same read-back is the proof: ticked count == the proven subset (not the full
count), all citations == the single verdict comment id, the deliberately-held box still `- [ ]`.
Tick exactly the delivered subset — an over-tick fabricates proof no diff supports, and the gate
then reads a false green on criteria nothing shipped. A head move does **not** automatically invalidate the write-back — classify it before deciding. Diff the graded files the verdict rests on (`git diff --quiet <old-sha> <new-sha> -- <code/test paths>`): **byte-identical graded files = a content move** (a docs/changelog/agent-wiki push). The verdict holds, so re-anchor — fetch the new head, re-run the proving command at it, and cite the new full 40-hex sha in `--verdict-ref` and every `(proven: …)` marker; the old head's citations are then stale, not wrong. **Changed graded files = a re-judge**: read the new diff and re-run the gates before any tick. A docs-only push can also *clear* a gate the earlier verdict named red (a `check-docs`/agent-wiki-note requirement) — re-run that gate at the new head and record the finding as resolved on the PR instead of leaving the old red standing unretracted. Run the script from a worktree that has
`scripts/acceptance_writeback.py` checked out — the repo root dir may not carry it.

The script renders each held criterion as a `- unproven: <n>.` line naming why it is not
provable — that marker IS the intended representation of a deliberately-held box. Do not
hand-edit it out or replace it with a bare `- [ ]`: the marker is what makes a held criterion
distinguishable from an unfinished one to the next reader.

**The three signals below are the whole proof of a partial tick — stop there.** `PATCHED
#<n>` (exit 0), the census (`- [x]` count == proven subset, held box still `- [ ]`), and the
gate violation count dropping by exactly the boxes ticked (§6) together close the loop. Do NOT
then run the write-back a second time in `--dry` as an "idempotency check" — a re-dry against
an already-PATCHed body re-renders the same body and prints `would PATCH`, which proves only
that the tool is deterministic, not that the first write landed; the census already did. Nor
write a scratch status file restating reads that already returned (see §2's cascade rule). One
verified record per head.

## 6. The CI acceptance guard stays red after the tick — rerun it at the same head

Measured #1868 (13:32Z): after the AC1-AC3 write-back on #1865, the LIVE-BODY local re-read
(`scripts/check_pr_acceptance.py check --body-file <fresh PR body>`) returned
`OK — every closed issue's … is checked or named out of scope` rc=0 with zero `tick-unprovable`
and zero `acceptance-unchecked` on the rendered body. When both that local live-body re-read and
the rendered-body class check pass, the CI-side rerun (`gh run rerun --failed`) is optional
evidence, not a requirement — the local re-read against the LIVE fetched PR body is the
authoritative drop proof (§6 numeric-drop rule). If you choose the CI rerun, enumerate every stale
run at the head first (`gh pr checks` rollup + each row's `detailsUrl` → run id) and group by run
id: #1868's hold redded the design guard run AND a separate ci-scope run, each carrying its own
`check-pr-acceptance` job, so one rerun would have left the other red.

After the write-back ticks the criteria, the design acceptance-gate guard run
(`check-pr-acceptance`) at that head is still **RED**: that run executed *before* the tick, so its
live-body read saw the unticked criteria. "Local gate green" and "CI check-run red" are both
true and describe two different body states — the red is a **stale read, not a build break**, and
must never be reported as a defect of the PR.

To prove the gate actually cleared on the CI wire, rerun the failed guard at the **same head**:
`gh run rerun <run-id> --failed`. This re-reads the live issue body (§944 live-body re-read) with
the now-ticked criteria in place. A rerun exits 0 but dispatches asynchronously — poll the exact
fresh job, not the run, until it concludes: `gh api repos/<o>/<r>/actions/jobs/<id> --jq
'{status,conclusion}'` in a bounded loop. Confirm the log line carries
`[check-pr-acceptance] OK — every closed issue's `## Acceptance criteria` is checked or named out
of scope` (job conclusion `success`).

Post that confirmation on the PR as the durable CI-side evidence — run id + head + the OK line —
as a **separate** artifact from the local gate read, so the evidence chain reads
`verdict → local gate OK → CI rerun OK` with three distinct comment ids.

**On the local side the numeric drop is the proof, and it needs no CI rerun.** Re-run
`python3 scripts/check_pr_acceptance.py check --body-file <freshly fetched PR body>`: the
violation count must fall by exactly the number of boxes ticked, and a full tick takes it to
`[check-pr-acceptance] OK — every closed issue's ## Acceptance criteria is checked or named out of
scope` with rc 0. A drop smaller than the boxes ticked means a tick failed to bind its criterion;
a larger drop means something else got unticked. Fetch the body fresh for this run — a cached body
file re-tests the pre-PATCH state and shows the old violations.

Feed the check the **PR** body (`gh api repos/<o>/<r>/pulls/<n> --jq .body`), never the linked
issue's body. A synthesized PR body you assemble locally to exercise the render (a hand-written
`## Not covered` bullet, a pasted title) only proves the tool's parsing, never that the live body
exempts what you claim — a green on the fake body is a false green. The authoritative run is the
one the CI job makes, with the live fetched PR body. The wrong body file fails in **either** direction, and both failures look like a verdict about the
code rather than about your input:

- Usually the issue body carries no `closes #<n>` trailer, so the checker has no closed issue to
  judge and returns a vacuous `OK` — a false green that looks exactly like the fix worked.
- But when the issue body *quotes* a closing trailer as example prose ("measured on PR #<x>
  (closes #<y>)", a pasted log, a prior PR's summary), the checker takes that example as a live
  reference and reds on an issue this PR does not close — a **phantom** violation naming an
  unrelated `#N`. That is a wrong-body-file artifact, not a regression the PR introduced: confirm by
  re-running against the PR body, which goes `OK` rc 0. Never retract the verdict, re-judge, or add a
  `## Not covered` bullet for a phantom issue — re-run on the right input and say what the input was.

The gate's input is the PR body (`gh api repos/<o>/<r>/pulls/<n> --jq .body`); the issue body is
only the place the boxes live. State which body file each gate run used whenever you report a
pre- and post-write-back pair, or the two numbers are not comparable.

The `check` subcommand takes `--body-file` / `--body` / `--repo` / `--gh` and nothing else —
read the `check-pr-acceptance` Makefile target (or `-h`) before invoking it; `--pr-num`/`--title`
are not flags and error out as unrecognized arguments. The script fetches the linked issue itself
from `--repo`, so you never hand it AC state.

**An out-of-scope criterion keeps the gate red BY DESIGN — read which item it names.** When a PR
delivers only one half of an umbrella's criteria (the rest are held for a later vehicle per
dispatch), a correct partial write-back still leaves the gate at rc 1, reporting e.g. `acceptance
item 2 (“…” ) is still \`- [ ]\` in the linked issue`. That red is the held criterion, not a failed
tick. The proof of a correct partial write-back is NOT `OK`/rc 0 — it is: (a) zero `tick-unprovable`
findings on the written-back body, and (b) the gate naming ONLY the criteria you deliberately held
(out of scope), never the criterion you ticked. A gate red that names your JUDGED criterion means
the tick failed to bind; a gate red naming only the out-of-scope ones is the expected end state
until their own vehicle lands and ticks them.

**Rerun EVERY stale run at the head, not just the one you first noticed.** More than one
workflow run can be pinned stale-red at the same sha, each dispatched before the tick: the
design acceptance `guard`/`check-pr-acceptance` run *and* a separate `ci-scope` workflow run
(the one carrying the `scope` check). Rerunning the guard clears the guard; it does nothing for
the `scope` check that belongs to a different run id. Enumerate the whole board before you call
the reruns done: `gh pr checks <n> -R <R>` (or `gh pr view <n> --json statusCheckRollup`) lists
every row with its `detailsUrl`, which names the run id each red row belongs to. Group red rows
by run id and issue `gh run rerun <run-id> --failed` once per distinct run. Confirm with the
rollup fully `COMPLETED`/`SUCCESS`, not with the one check you set out to fix — a single green
check beside a still-red `scope` row is a half-cleared gate.

Never rerun a *different* head, and never cancel/re-queue to "clear the queue" — a rerun at the
same sha is the only legitimate action here. Also: `mergeStateStatus` can stay `BLOCKED` after the
acceptance gate goes green, because unrelated runs (ci-verdict, ci-images, scanner-images) are
still in flight or failing — report the acceptance-gate state separately and name which runs
remain red; do not conflate the gate being green with the PR being mergeable. When every
check-run at the head is `success` and no hold label is present, `blocked` is ref/queue bookkeeping,
not a control: prove the claim instead of asserting it by enumerating
`gh api repos/<o>/<r>/commits/<sha>/check-runs --jq '.check_runs[]|{name,conclusion}'` plus
`pulls/<n> --jq '.labels[].name'`, then report "N/N check-runs success, no labels, head==base==main
tip, ms=blocked" — the numbers carry it, the adjective does not. **And re-read
`state`/`mergedAt` before posting any further confirmation:** another lane can merge the PR while
your rerun polls — a green rollup at a now-`MERGED` head takes no more comments, only a status
report to the dispatcher (see `references/ci-check-state-polling.md`, "A `MERGED` PR gets no
verdict"). No merge/arm (#1088) regardless.

## 7. Dispatch read-back and gate checks from a script file, not a shell heredoc

Multi-line Python piped through `python3 - <<'PY' … PY` breaks on any nested quoting: the shell
layer mangles it into `SyntaxError: unexpected character after line continuation character`, and
the failure reads like a broken tool rather than a typo — so it burns a retry and can be
misdiagnosed as the read-back being suppressed. Write the probe with `write_file` to a `.py`
file, then run that file. One script per check also leaves a re-runnable artifact instead of a
one-shot command you retype (and mistype) each time.

### 7b. Run the write-back unmask probe with the PR's OWN checker, not your local main copy

After a write-back tick, the local `check_pr_acceptance.py` at `main` may report a finding your
write-back did not cause — a rollout-lane hold it derives from the umbrella's live body. Before routing
it, run the PR's own checker from a worktree at the head (`git worktree add /tmp/wt<n> <head>`, then
`python3 scripts/check_pr_acceptance.py check` there). A checker that has outgrown `main` (e.g. a
#2088-era `if is_pr: continue` guard that `main` lacks) can flag the closing PR itself as a rollout
lane — a stale-checker FALSE POSITIVE, not an unmasked second red. The branch/CI checker is the
authoritative read; the pre-tick CI log showing the SAME live body with no rollout finding is
corroboration. Reproduce, don't assume.

### 7c. A unit leg SKIPPED behind an early guard red is a real coverage gap, not a free pass

When `guard`/`check-pr-acceptance` jobs fail early, the `linux / unit` legs report `skipping` and the
full suite never runs at that head. Approving on the AC ticks alone is fine; approving the PR as
mergeable is NOT — the unit suite is unrun. On `gh run rerun --failed` the previously-skipped unit legs
finally execute and can surface a REAL regression the approve never saw. Measured #2111: commit
17c8115f moved auto-merge.yml's workflow-level `concurrency:` into `jobs.merge` (job-level), breaking
`test_every_bot_has_its_own_concurrency_group` (reads `wf.get("concurrency")`, i.e. workflow-level)
with `auto-merge.yml: no concurrency group`. After ANY rerun, poll every previously-skipped leg to a
conclusion before the verdict stands; a masked unit red flips approve→changes.

## 8. The `--verdict-ref` is a payload — compose it literally, then read the rendered body

`--verdict-ref` is written verbatim into every ticked box. Build it from a plain literal or a
shell variable that was asserted non-empty (`CID=$(...); [ -n "$CID" ] || exit 1`), never from a
command substitution whose failing branch can land its own error text in the string: a malformed
`jq`/`gh` substitution injects junk lines into the issue body that no diff, gate or test will ever
flag, and the gate stays green because the boxes themselves are correct.

Before the live PATCH, `--dry`; after it, fetch the body and confirm it contains **only** the four
known line shapes for the changed region (the criterion line plus its `(proven: …)` suffix) and no
stray fragment. Counting `- [x]`/`comment=<id>` occurrences does not catch this — polluted and clean
bodies have identical counts.

An injected line survives re-runs: `acceptance_writeback.py` re-renders the body it read, so a
second write-back reproduces the garbage instead of dropping it. Sanitize the fetched body (strip
everything between the criterion text and the next criterion), verify the sanitized text is within a
few bytes of the original size, PATCH that, then re-anchor the citations to the head you are
actually at.

## 9b. Validate every composed `(proven: …)` ref against the gate's own predicate BEFORE the PATCH

A ref can read perfectly and still be unprovable: the gate accepts `run=<id>` of a concluded success, or a
command form carrying **both** `rc=<n>` and a `head=<sha>`. A ref with only `run=`, only `rc=`, or a bare
`head=` reads honest and reds `tick-unprovable` at merge time. Check with the checker itself, not by eye:

```bash
cd <worktree>; python3 - <<'PY'
import sys; sys.path.insert(0,'scripts'); import check_pr_acceptance as c
for line in [<tick lines you rendered>]: print(c._is_provable_tick(line))
PY
```

Require `True` for every one before `writeback`/PATCH. A `False` there is a one-line ref edit, not a verdict
change — fix the ref, re-render, and only then PATCH. The same predicate is the cheapest post-PATCH audit:
feed it the live issue body's ticked lines and confirm all `True`.

## 9. The ticked marker must SURVIVE the gate whose class you are proving

Since `tick-unprovable` (issue #1858), the `(proven: …)` marker the write-back renders is itself
judged by the acceptance gate at merge time. When your verdict proves a gate that you just
introduced, the write-back citation must pass THAT class: name `run=<id>` of a **concluded success**
run, or the reproducible command form `pytest tests/….py -q rc=0 <full-sha>`. Never cite a run id
that concluded `failure` at the head (a red run proves nothing, and the gate's `RUN_ID` regex will
happily swallow it) — the command+rc+sha drift-lamp form is the honest citation when no green run
exists. After the PATCH, re-run `acceptance_verdict` (or the CLI) against the **written-back live
issue body**: the proof that the tick clears its own class is a GREEN read with zero
`tick-unprovable` findings, not just a `- [x]` count.

## 10. Never truncate the body you PATCH — and prove the transition by diffing the pre-PATCH copy

**Never pipe a rendered or fetched body through `head -N` (or `sed -n '1,Np'`) before PATCHing it.** The
render's tail carries `## Not covered` and `## Technical`; slicing to the first lines drops them on the wire
and the gate then reds on a body you believe you already fixed. The truncation is silent — `gh api -X PATCH`
returns success and the tick count reads right, so only a section census catches it. Before any PATCH,
`wc -l` the render and `grep -c '^## '` it; after the PATCH, re-fetch the live body and assert every section
heading (`## Acceptance criteria`, `## Not covered`, `## Technical`, …) is still present, not just the boxes.

**Prove the write-back as a state transition, not a re-read.** Before rendering, save the fetched body to
`/tmp/<pr>_body.md`; after the PATCH, fetch the live body to `/tmp/<pr>_live.md` and `diff -u` the two. The
diff is the deliverable evidence: every criterion line must show `- [ ]` → `- [x] …(proven: …)`, the held
lines unchanged, and the out-of-scope/technical sections byte-identical (a moved-but-unchanged section is
fine; a *missing* one is the truncation of the previous paragraph). A digest of the two files
(`pre [x]=0 [ ]=3 → live [x]=3 [ ]=0`) is the one-line summary to post. Re-reading the live body alone says
what the state IS; the diff says what the write-back DID, and only the second is evidence the tick was yours.

## 11. Re-running writeback REWRITES existing provenance — confirm a tick by reading, never by re-applying

`tick_acceptance` is idempotent only about the box mark: for an already-`- [x]` line it strips the existing
`(proven: …)` suffix (`_PROVEN_ON_LINE`) and appends the *new* `--verdict-ref`. So a second `writeback` with a
shorter ref (say `review=<id> head=<sha> run=<id>`) silently deletes the richer anchors a first run wrote —
the check-run id, the `pytest … N passed` line — while still reporting `PATCHED`. Measured on #2046: its three
ticks carried `review 5816519827 … check-run 128621429676 … pytest 83 passed`; `apply --body-file` with a
shorter ref rewrote all three to `review 5816519827 … run=42442802168` and dropped the trailing newline.

Rules:
- **Verify a write-back by reading** the live issue: `grep -c '^- \[x\]'`, `grep -c '^- \[ \]'`, and
  `grep -n 'proven:'` to confirm the anchors you expect are still there. Never "confirm" by re-running.
- `writeback --dry` only prints `would PATCH #N body (… chars)` — rc 0 on dry proves nothing about change or
  no-change. Use `apply --body-file <fetched body>` and `diff` if you need the no-op proof, but read the diff:
  a diff means the ref you passed differs from the one on the wire.
- If a re-run is genuinely needed (head moved, a new criterion delivered), pass the **full** ref including
  check-run/run/test anchors you want to keep; a short ref is a downgrade of the record.

### 11a. Never start the ref with `proven:` — the renderer adds it

`--verdict-ref 'proven: reviewer …'` (a form copied from the body you are trying to imitate) stamps
`(proven: proven: reviewer …)` into every box. It passes the gate, so nothing reds it; the doubled word is
pure noise in the permanent record and only a body read catches it. Pass the ref **bare** (`reviewer <lane>
review <id> head=<sha>; <command+result>`).

Repair is cheap and lossless: a second `writeback` with a clean, *fuller* ref strips the old suffix via
`_PROVEN_ON_LINE` and appends the new one, so the doubled prefix disappears and the citation upgrades to the
review that carries the stronger evidence. Simulate first with the seam, not the CLI:
`acceptance_writeback.tick_acceptance(<live body>, proven, ref)` then count `out.count('proven: proven:')`
— 0 means the repair renders clean — then run the live `writeback` once and read the body back.

### 11c. A subset `--proven` DESTROYS ticks not in the subset — pass the full union, then dedupe

A call like `writeback --proven 1` on an issue whose items 2-8 are already `- [x]` rebuilds the
whole section and writes `- [ ]` for every item not in this run's proven set (`tick_acceptance`
line ~190 appends `- [ ] {text}` for non-proven items, ignoring existing ticks). Measured on
#2101: a `--proven 1` un-ticked 7 prior-proven items in one PATCH. The safe call is
`--proven` = the union of (already ticked) + (newly proven) — pass all of them — never a bare
subset on a partially-ticked issue. The re-tick also replaces each item's `(proven: …)` with the
single new `--verdict-ref`, flattening prior `command + rc + head` evidence into a
non-replayable marker — the acceptance gate then reds those items as "names no CI run and no
reproducible command". Verify BEFORE and AFTER with the gate's own predicate (`check_pr_acceptance`
`_is_provable_tick` per `--proven` item), and repair a flatten by re-rendering the section with
EACH item's original replayable marker restored (a manual PATCH is cleanest), then dedupe
identical duplicated `(proven: …)` suffixes.

### 11d. `gh api ... -f body=@file` writes the LITERAL `@file` — verify the patch size

The raw `-f` flag does not expand `@`. `gh api --method PATCH repos/<o>/<r>/issues/<n> -f
body=@/tmp/body.md` stores the 20-byte literal `@/tmp/body.md` as the issue body, silently
wiping the whole body (gate then reds everything). Use multipart `-F body=@path` or
`-f "body=$(cat file)"` (or a python subprocess `-f f'body={body}'`). After ANY body PATCH,
re-fetch and assert `wc -c` is the intended size and `grep -c '^## '` still shows
`## Acceptance criteria`, `## Not covered`, `## Technical` — a 20-byte body is the tell.

### 11b. Two instances of this lane can post at one head — reconcile, do not re-post

A parallel dispatch (same profile, different process) can post its verdict and run the write-back while you
are still measuring; you then find two `COMMENTED` reviews at the same head and boxes already ticked. The
right move: read both review bodies and the issue body, keep the ticks (never re-tick a completed
verdict-gated write-back), and post **one** status comment stating that both verdicts agree, which review id
the ticks cite and why, plus any new fact you measured that the first one did not. Re-running a verdict or a
tick because the board looked unclaimed duplicates board state the next lane must reconcile again.
