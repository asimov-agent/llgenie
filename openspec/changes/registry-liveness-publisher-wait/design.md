# registry-liveness-publisher-wait — design (#2592)

## Key decision: the wait gate is workflow-only, and it names the same-head CI run the publisher

The publisher of a committed engine pin on a `merge` to `main` is the `ci.yml` run at that same head
SHA (measured: run #457 redded `mlx:93e6d4a6-e5ab3798-cpu` while CI #5565 at the same head was still
building; the tag is now published). So the wait gate must identify THAT run — not a random CI run —
by filtering `head_sha` to the pushing SHA and `name`/event to the CI push workflow, then poll until
it concludes, bounded. `scripts/check_engine_launchers.py` is left behaviourally untouched: only the
workflow is reordered so the GHCR manifest read happens after the publisher concluded.

## Shape: a before-fleet wait step that records the publisher's conclusion

1. A new step (before the `full-fleet committed-tag pin-validity gate`) runs only on
   `github.event_name == 'push'`. It uses `gh api repos/$REPO/actions/runs?head_sha=$SHA&per_page=100`
   filtered to the CI run, polls `status`/`conclusion` in a bounded loop, writes three outputs
   (`publisher_run`, `publisher_status`, `publisher_conclusion`). When `publisher_conclusion ==
   'failure'`, the SAME step emits a `publisher_failed=true` marker so downstream can suppress dispatch
   and name the run in tracking issues.
2. The fleet gate step is unchanged (its `exit "$rc"` is the job's exit). A still-in-flight publisher
   is handled by the wait step's bound: if the bound expires while the run is still `in_progress`, the
   wait step writes `"publisher_still_in_flight=1"` and lets the fleet gate run — but the gate is
   wrapped so a non-zero `fleet_rc` under that marker does NOT fail the job (it records the deferral).
3. The issue-filer runs on `if: always()` (unchanged). When `publisher_failed=1` it adds the failed
   publisher run id into the tracking-issue body; the dedupe/issue-record logic is unchanged.
4. The dispatch step keeps its `[select]` parse, sweep-coalescing (`#2579`) and per-cell (`#2567`)
   shapes unchanged. Its ONLY new guard: `if [ "${{ steps.publisher.outputs.publisher_failed }}" =
   "true" ] && pins are unpublished` exit 0 with "publisher failed; sweep would reproduce it — see the
   tracking issue (#2592)" instead of calling `gh workflow run engine-build.yml`. A successful
   publisher (or a scheduled run) dispatches exactly as today.

## Bound selection

The wait bound must comfortably exceed a normal `ci.yml` push-to-main run's publish-critical path and
fit inside the job's `timeout-minutes`. A 20-minute bound with a 10-second poll, and a step
`timeout-minutes` that keeps the whole job under its 30-minute ceiling, lets a same-capacity main run
conclude while still allowing a genuinely-missing pin to settle at the next scheduled run. The bound
is a workflow variable, not a code constant, so a future CI runtime change is a one-line edit.

## Rejected

- **Making the manifest check `optional`/skippable** — the gate must still observe and report the real
  manifest state; only the *hard-fail decision* and the *dispatch decision* are conditional on the
  publisher, never the observation itself (matches "Only after the publisher finishes does the
  manifest check decide").
- **Waiting on a schedule inside `check_engine_launchers.py`** — the wait is about a workflow-run state
  only GitHub knows (the CI run's progress); putting it in Python would duplicate the poll and violate
  "the wait gate is workflow-side". The script keeps its single manifest-read responsibility.
- **Cancelling/retrying the same-head publisher** — never own the publisher's outcome; defer and let
  the next (non-racing) run settle it.
