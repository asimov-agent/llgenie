# Waiting on a CI verdict without false-early fires

A watcher that reports "concluded" too early costs a whole re-arm cycle and can produce a
verdict about a job that never ran. Three ways this happened:

1. **`gh pr checks` is tab-separated; `awk '{print $2}'` grabs the wrong token.** A row whose
status cell contains a `/` (e.g. `linux / unit`) yields `/` instead of `pending`/`pass`. Split on
tabs explicitly and match the full name field:
   `gh pr checks <pr> --json name,state` (or `awk -F'\t' '$1=="linux / unit"{print $2}'`).
2. **`status != in_progress` is not "concluded".** A run queued by the scheduler reads `queued`;
that is not a verdict. Require `conclusion` to be a real value (`success`/`failure`/`cancelled`)
for the specific JOB at the exact head sha.
3. **Judge the job, not the run.** A run-level `cancelled` can hide a genuinely failed job, and a
run-level `success` says nothing about whether the leg you need actually started.

Robust check before arming any watcher:

    gh pr view <pr> --repo asimov-agent/llgenie --json headRefOid,state,mergedAt
    gh run list --repo asimov-agent/llgenie --branch <ref> --limit 10 \
      --json status,conclusion,headSha,databaseId,workflowName

Loop until `headSha[0:8] == <head>` AND `conclusion in {success,failure,cancelled}` for the
workflow you need; exit early on `mergedAt != null` or branch-gone (the merge is the answer then,
not a verdict).

## A watcher loop that survived re-arming twice

Both failures above recurred in one session with the same two bugs, so copy this shape rather than
hand-rolling: it tab-splits the exact leg, treats only a real `conclusion` as done, and re-checks the
tip each cycle.

```
HEAD8=<head-8>; BR=agent/issue-<n>-<slug>
for i in $(seq 1 600); do
  ref=$(git ls-remote origin refs/heads/$BR | awk '{print $1}')
  if [ -z "$ref" ]; then echo "BRANCH_GONE"; gh pr view <pr> --json state,mergedAt,mergeCommit; exit 0; fi
  if [ "${ref:0:8}" != "$HEAD8" ]; then echo "HEAD_MOVED to ${ref:0:8}"; exit 0; fi
  unit=$(gh pr checks <pr> --json name,state --jq '.[]|select(.name=="linux / unit")|.state')
  case "$unit" in success|failure|cancelled|skipped) echo "UNIT_CONCLUDED=$unit@$HEAD8"; exit 0;; esac
  sleep 45
done; echo TIMEOUT_UNIT
```

Do not accept `pending`/`queued`/`waiting`/`in_progress` as a wake-up, and do not fold an empty
`ls-remote` result into the "head moved" branch — it means merged, so read `.state/.mergedAt`.

## A pending CI leg is not a reason to withhold your own acceptance evidence

On a docs/reference-only fold the deciding leg can sit `pending` for a long time (scheduler queue)
while every other run is green. That is not a verdict either way — it is a wait. The lane's own
decisive evidence is the acceptance run executed at the head, so produce it while CI waits:

```
docker run --rm -v "$PWD":/repo -w /repo -e PYTHONPATH=/repo/scripts \
  ghcr.io/asimov-agent/llgenie/test:<sha> python3 -m pytest tests/<acceptance_test>.py -q -p no:cacheprovider
```

Report it as `head <sha> · <n> passed` and state the CI leg as still `pending` — never invent a
conclusion from the suite, and never present the pending leg as a failure. A verdict needs a
completed run; an unfinished wait needs an honest "still pending" plus whatever you could prove.

## Post-merge: stop waiting

Once the PR is MERGED, the deciding fact is the tree blob on main, not a standalone suite run.
Release the wait: do not cancel, do not re-run, do not re-verify. Report the landing (merge sha,
issue closed, blob == folded content) and move to the next vehicle.

An orphaned suite from an ALREADY-MERGED vehicle still gets its result recorded when its notification
arrives (`N passed`, `CIUNIT_RC=<n>`, head sha) — labelled moot-post-merge, report-only. Never cancel
it to free a slot, and never re-run it against the new main and call that the verdict.

## Hermetic suite housekeeping

`make ci-unit` can end with `CIUNIT_RC=2` while the pytest summary reads `N passed` (a sibling
gate in the same target reds). Read `CIUNIT_RC` for the target's exit and the pytest line for the
test tally separately; never quote `N passed` as proof that `make ci-unit` returned 0.

Run `make` through bash, not through a Python subprocess string that uses bash-only syntax
(`PIPESTATUS`) — that returns a bash syntax error, not yours.
