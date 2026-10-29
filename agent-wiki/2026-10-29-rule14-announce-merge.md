# The merger publishes what it acted on (#873, rule 14)

Rule 14 in `agents/standing-rules.md` is about lanes, and `auto-merge` is a lane: it reads every PR,
approves, and merges. A merger that merges silently cannot be told apart from a coincidence — the next
reader cannot tell work from luck. The rule's own numbers make the cost concrete: four PRs merged by
`asimov-agent`, twenty-three sweeps cancelled, and long stretches with no `success` at all took three
triage ticks to explain precisely because **the decisions were invisible**.

## What was measured first

`scripts/auto_merge.py` already deferred a PR with its reason on the PR
(`test_a_refused_merge_defers_with_the_reason_on_the_pr`), so the *decline* half of the rule existed.
The *merge* half did not: a successful merge printed to the job log and nowhere else. The run id and the
head sha judged — the two facts that make a merge auditable — existed only in the log of a job nobody
opens after the PR is closed.

## The mechanism

`announce_merge()` posts one comment naming the run id (`GITHUB_RUN_ID`), the head sha judged, and the
decision, and it is called **after** the merge call returned:

- `_merge()` — the normal green + `CLEAN` path.
- `_clear_review()` — the `--admin` fallback, which merges without a review verdict. It announces the
  bypass, because a merge without an approval is exactly the kind of act that needs a written reason.

The order is the guarantee. `merge()` raises `SystemExit` when GitHub refuses; a refused merge never
reaches the announcement and reaches the existing deferral instead. Announcing before the merge returned
would tell the next reader a PR had merged when it had not — the same defect as the silent merger, with a
worse failure mode.

The announcement is idempotent per head: the marker carries the head sha, so a recheck of an
already-merged PR posts nothing, and a moved head announces again because the old marker described a
different tree. That mirrors how `defer()` already avoids re-commenting.

## Verified

- `tests/test_auto_merge.py`: 53 passed. Four new tests — the merge announces run/sha/decision and does so
  *after* the merge; a refused merge announces nothing; the admin path announces its bypass; the
  announcement is posted once per head.
- Negative control: with `announce_merge` replaced by a no-op, the three announcement tests fail as
  assertions. The "refused merge announces nothing" test keeps passing, which is the point — it is the
  control for the control.

Refs #873. The SOUL text for this lane lives in the `agents/` tree, which is not on `main` yet, so the
verbatim rule text lands with that tree rather than here.
