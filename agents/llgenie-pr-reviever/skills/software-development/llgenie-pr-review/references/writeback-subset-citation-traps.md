# Acceptance write-back traps: subset wipes, `#<n>` refs, and paren refs

`scripts/acceptance_writeback.py writeback` looks surgical but is NOT. The traps below are all measured;
each one has produced a red gate or a false report when missed.

## 1. `--proven` is the COMPLETE set, not the delta — a subset un-ticks the rest
`tick_acceptance()` rebuilds EVERY `- [ ]`/`- [x]` item in the `## Acceptance criteria` section and
writes `- [ ]` for any position NOT in `--proven`. So `--proven 2` on a body that already had 1 and 3
ticked WILL clear 1 and 3. Always pass the full set of positions that are provable at the head
(e.g. `--proven 1,2,3` when all three hold), never just the newly-proven one. Read the body's current
tick state first, then pass the union of already-true + newly-proven.

## 2. A `#<number>` in `--verdict-ref` becomes a rollout-lane citation and REDS the gate
`check_pr_acceptance` derives rollout lanes from `CITE = #(\d+)` over the umbrella issue body: any
`#<n>` that is still OPEN and cites the umbrella back is read as an in-flight rollout lane, and the
gate fails the close ("a close here would auto-close an in-flight rollout"). A verdict-ref like
`(reviewer verdict #1234 …)` injects `#1234` into the body — and that number is the OPEN PR that
closes the umbrella, so the gate then trips on YOUR OWN citation. Name the PR without the hash:
`(reviewer <lane> verdict on PR 1234, review <review id>)`. After the write-back, `grep -oE '#[0-9]+'`
the body and confirm only pre-existing, non-lane issues remain (process-context citations that do not
cite the umbrella back are safe).

A pre-existing citation trips the same check, so this is not only about your own ref: an umbrella
body's dated status note ("landed on #<pr> as a squashed commit …") cites the OPEN PR that closes it,
and `CITE` does not exclude `pull_request` targets — so the gate reads a PR as an in-flight rollout
lane and reds the close even when every criterion is ticked. Before blaming the write-back, list the
umbrella's citations and classify each (`gh api repos/<R>/issues/<n> --jq .body | grep -oE '#[0-9]+'`,
then per number check `pull_request != null` and whether it cites the umbrella back). A PR target
cannot be a rollout lane; report it as the gate's false positive with the citation and its line, and
name the fix (exclude pull-request targets from the lane set) rather than editing the issue to dodge it.

## 3. A ref containing parentheses is APPENDED, not replaced (duplicate provens)
`_PROVEN_ON_LINE = \(proven:[^)]*\)$` stops at the FIRST `)`. A ref with inner parens (e.g.
`(12573 passed in 1234.08s …)`) is not matched as an existing proven suffix, so a second write-back
APPENDS a second `(proven: …)` after the first instead of replacing it. Keep verdict-refs
paren-free (use commas/semicolons), or clean a duplicated line by rebuilding it: strip
`\s*\(proven:.*$` from the criterion text and append one `(proven: <ref>)`.

## 4. A tick can LAND and still be unprovable — the gate wants `run=` OR `rc=`+sha, not `head=`
`_is_provable_tick()` accepts a tick only when the `(proven: …)` names `run=<id>` OR matches `rc=…`
AND a 7–40 hex sha. A ref that names only `head=<sha>` plus prose ticks the box but proves nothing:
the read-back shows 6 `- [x]` and `provable: [False, False, …]`, and the gate stays red. So a
successful-looking write-back is not a done write-back. Verify every time, before reporting:

```python
import sys; sys.path.insert(0,'scripts'); import check_pr_acceptance as c
print([c._is_provable_tick(l.rstrip()) for l in open(live_body) if l.startswith('- [x]')])
```

All-True is the done condition. To make an otherwise-prose ref provable, run the real gate and cite
its own result — `check_docs.py check rc=0 head=<sha>` / `pytest … rc=0 head=<sha>` — instead of
writing `at head=<sha>` with no exit code. Reach for a command you actually ran at that head; never
invent an `rc=` for a command you did not execute.

## 5. An issue-body PATCH does not re-run PR CI — the head's check-runs stay red from BEFORE the write-back

Ticking the linked issue changes no file on the branch, so the PR's check-runs at that head keep
showing the old `guard`/`scope`/`ci-verdict` failure until CI re-runs. A peer lane reading
`gh pr checks` right after your write-back will report "still red, ACs unchecked" — a stale snapshot,
not the current state. Measure the live issue body (tick counts) and the gate directly, and say plainly
that the red check-runs are pre-write-back; when the run re-runs as a new attempt the guard goes green
and the aggregator re-judges. Do not re-tick to "fix" a red that is only an old attempt record.

### The done condition is a NEW green check-run on the wire, not your local `check_pr_acceptance` rc=0
A local `check_pr_acceptance.py check … rc=0` proves the body parses green; it does NOT turn the board's
scope check-run green — that check-run still reads the pre-write-back `failure` until the guard/scope
workflow re-runs. So an acceptance write-back is not done until you actively re-run the scope workflow
at the head and read a NEW green conclusion back:

```bash
H=$(gh api repos/<R>/pulls/<n> --jq .head.sha)            # re-read head; abort if it moved
gh api -X POST repos/<R>/actions/runs/<scope-run-id>/rerun  # the scope run that failed on check-pr-acceptance
for i in $(seq 1 12); do
  S=$(gh api repos/<R>/commits/$H/check-runs \
        --jq '[.check_runs[]?|select(.name=="scope")|.conclusion][-1]')
  case "$S" in success|failure|cancelled) break;; esac; sleep 25
done
echo "scope=$S"   # success is the on-wire done condition
```

- A second `rerun` POST in the same parallel batch returns `403 "This workflow is already running"` —
  that confirms the first rerun landed; do not retry it as an error.
- A rerun reuses the run id but mints a NEW check-run id at the SAME head — poll `[-1]` of the scope
  check-runs at `$H`, not the old id.
- Re-verify ALL check-runs at the head (`gh api repos/<R>/commits/$H/check-runs`): scope + guard(s) +
  holds + record all `success` before reporting green.
- `mergeStateStatus` flipping to `DIRTY` after a rebase is the rebase lane's seam (#1015), not a
  write-back defect — report it and do not re-tick to chase it.

## 6. `cmd | tail -1; echo rc=$?` reports the PIPESTATUS of `tail`, never of `cmd`

A gate loop written as `R=$($PY check_pr_acceptance.py check … 2>&1 | tail -1); echo rc=$?` prints
**rc=0 for a red gate**: `$?` is the exit of `tail`, which succeeded. This session that pattern made a
rc=1 violation look like `rc=0` beside the violation text — one step from reporting a false green.
Capture the status of the gate itself: either `OUT=$(cmd 2>&1); RC=$?` (no pipe), or with a pipe use
`RC=${PIPESTATUS[0]}` immediately after. Read the gate's own summary line too: `OK — every closed
issue's …` is the pass sentence; a trailing violation paragraph means red regardless of what `$?`
says. Treat "exit code beside its own text" as unverified until a bare run confirms it.

## Repair recipe when a bad ref already landed
Fetch the live body, for each `- [x]` line `re.sub(r'\s*\(proven:.*$','',text)` to drop the old
suffix, append a single clean paren-free ref, keep `- [ ]` lines and the `- unproven:` bullet
untouched, JSON-PATCH the full body (`{"body": …}` via `--input`), then re-run
`check_pr_acceptance.py check --cwd <head> --body-file <pr body> --gh gh --rev <sha>` → rc 0.

## Honesty rule this protects
A criterion needing a run still `in_progress` (or a run the acceptance gate itself blocks) is NAMED as
unproven — left `- [ ]` with a `- unproven:` bullet — never ticked. The gate red on a genuinely-unproven
criterion is the correct, honest state; do not force it green by ticking.

## A criterion that requires "this PR green in CI on the same job that failed" is CIRCULAR while the acceptance gate itself is what reds CI

A failure-fixer criterion of the shape "the PR that fixes it is green in CI on the same job that
failed" cannot be satisfied at the same head whose CI is red *because this very criterion is
unticked*: the guard fails `check-pr-acceptance` → no scope decision → the aggregator (`ci-verdict`)
reads `NO VERDICT` → red, so the "same job" can only go green after the write-back clears the gate.
Do not tick it and do not spend turns waiting for it. Post the verdict naming the criterion
unproven, tick the criteria that ARE measurable (the failing make target green locally with its real
output, the `closes #<issue>` line), and state the unblock: once the gate clears, the sibling
aggregator run at that head concludes green and the criterion becomes provable by that run id.

Prove the "failing target green locally" half end-to-end through the real `make` target, not a unit
test alone — feed the target a fixture with the bad row and show it refuses (non-zero exit, no
check-run written), then a settled fixture and show it succeeds. That pair is what makes the
"negative control is real" claim evidence rather than description.
