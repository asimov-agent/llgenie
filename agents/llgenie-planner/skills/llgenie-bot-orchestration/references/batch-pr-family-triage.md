# Triage a family of generator-produced PRs as one batch

## When

Two or more open PRs share a generator: same author bot, same head-name prefix (`chore/<x>-bump`), or — the decisive signal — **identical failing check names across heads**. Version bumps are the common case: a scheduled workflow opens N PRs and every one is born red on the same two gates.

## Why one batch, not N dispatches

N PRs with one root cause are one unit of work. A lane run per PR spends N runs learning the same thing N times, floods the board with N claims, and leaves N half-fixed branches when the lane stalls. The owner reads a board of N red PRs either way; the difference is whether the fix is one queue entry or N.

## Procedure

1. **Enumerate the family together with the whole board.** `gh pr list --state open --json number,title,headRefName,author,mergeStateStatus,reviewDecision` and `gh issue list --state open --limit 200 --json number,title,labels`. Never stop at what arrived in notifications — a partial inventory is exactly what "there is more work" means.
2. **Compare failures across two heads, not one.**
   ```bash
   for n in <first> <last>; do
     h=$(gh pr view $n --json headRefOid --jq .headRefOid)
     gh api "repos/<owner>/<repo>/commits/$h/check-runs?per_page=100" \
       --jq '.check_runs[]|select(.status=="completed")|select(.conclusion=="failure" or .conclusion=="timed_out")|"\(.name) [\(.conclusion)] id=\(.id)"'
   done
   ```
   Identical failing names across heads proves one root cause. Different names means two causes, therefore two batches.
3. **Read the failing job's log for the gate's own sentence.** `gh run view --log --job <job-id> | grep -iE 'error|ERROR|Error 1' | tail`. The gate prints its rule verbatim (which close keyword it wanted, which note or file was missing) — quote that line, not a paraphrase, so the implementer fixes the gate's actual requirement rather than its summary.
4. **Classify by where the fix lives.** Body/commit-message only (a claimed issue with no adjacent `closes #N` in *both* squash text and body) is an edit, not a branch rewrite. File-level (a behavioural-change note + `docs/changes.d` row + regenerated index — the "change owes a note" trio) needs a push on every branch. Both in one batch is fine; say which PR needs which.
5. **File ONE tracker issue** in the repo's six-section shape, labelled for implementation, listing every PR number and the engine/file each touches, with acceptance criteria of the form: all N PRs show the named gates success at head, plus the trio/close each, single trail each, no gate weakened.
6. **Comment once on each PR** pointing at the tracker: the verified root cause, that the fix lands with the batch, and that no lane may fork-push or open a competing PR before then. That last sentence is what stops a second vehicle appearing while the batch waits in the queue.
7. **Dispatch as one queue entry** to the owning implementer lane, named by the tracker id, positioned in its existing queue order; tell every other lane explicitly not to touch those branches.

## Pitfalls

- **A generated body's "(issue #N)" is a claim, and the gate then demands an adjacent `closes #N`.** Verify #N is the right issue and still open before adding the keyword. Adding `closes` to a guessed or already-closed number turns a red PR into a wrongly-closed tracker — worse than the red it replaced. If the target is wrong, drop the claim instead of inventing one.
- **Never widen or disable a gate for a generator family.** If the generator itself should be emitting the note trio, that is a separate finding for the pipeline lane: the batch fixes the PRs, the finding fixes the workflow that will otherwise re-create the same red on the next run.
- **Do not let the batch become a fleet sprint.** One implementer, its queue, one trail per branch; parallel lanes force-pushing the same branches is the two-vehicle failure the batch exists to prevent.
- **Re-measure heads immediately before dispatch.** A generator workflow re-pushes its branches; a head quoted from an earlier read is stale, and the acceptance criteria must name the head you measured.
