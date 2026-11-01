# Classify a test red before you dismiss it as host-side

A red reported by a lane is a claim; "it won't hit CI" is also a claim. Verify the
test's CI membership before you tell anyone a red is harmless.

## The two categories

- **Host-only**: needs a live host checkout/profiles that CI runners do not have, so the
  suite is deselected on runners. Example: `tests/test_agent_profiles.py` ("host-only
  proof ... against the owner's live profiles"). A red here is real on the host but does
  **not** red a PR.
- **ci-unit**: discovered and run in the `ci-unit` job. A red here blocks **every** PR's
  unit leg on `main`. Example: `tests/test_dispatch_forms.py`,
  `tests/test_issue_bot_manual_pick.py` — NOT in the exclusion/deselect set; a stale
  `docs/BOTS.md` dispatch table reds them via `make check-dispatch-forms`.

## Rule

Before saying "that red is host-side / not a CI blocker", open
`tests/fixtures/unit-suite.json` (the exclusion/deselect set) and confirm the test is
actually excluded. If it is not, it runs in `ci-unit` and reds every PR — treat it as a
main red and file a tracked issue to the owning lane.

Fastest oracle: the test file's own docstring ("runs in the ci-unit job" vs "host-only"),
then confirm against the exclusion set.

## The merge event is not the verdict

The owner merges through a still-`pending` CI leg; the merge event does not prove the
unit leg passed. When a PR merges while its `ci-unit`/`linux/unit` run is pending, the
real head verdict is still owed — watch the run at the PR head and report its conclusion,
and re-run the gate yourself (`make check-<gate>`) at the merge tip.

## Prove a red is the ambient class, not something the PR introduced

A red leg on a PR's own head is not automatically the PR's fault. Before you record it as a defect
of that branch — or before you tell the owner a PR "introduces no new red" — drill into the failing
**STEP**, not just the job conclusion, and match it to the tracked main-red class:

```bash
gh api repos/<o>/<r>/actions/jobs/<job_id> --jq \
  '{name:.name, steps:[.steps[]|select(.conclusion=="failure")|{n:.name}]}'
```

If the failing step name is the same gate the tracked main-red issue already owns (e.g.
`make ci-unit (test-unit, skills-validate, check-registry, …)` when the main unit-red is tracked),
then the PR's red **is** that ambient class — the branch shipped the ambient defect, it did not add
one. That distinction is what lets you say "await the tracked fix, or merge over the known ambient
red per precedent" instead of chasing a phantom regression in the diff.

Conversely: if the step name is a gate the tracked red does **not** own, treat it as the branch's own
defect and send it back to the lane. Matching the step, not the job title, is the whole test — two
different gates can live in one job, and only the step says which one fired.

Ambient red also persists through re-runs: a post-merge re-run of a red-merged PR staying red on the
same step is confirmation, not a new finding.

## Corollary

When you get it wrong (dismissed a real ci-unit red as host-side), correct the reporting
lane in the same pass — it was right, and the next reader must not inherit your wrong
"green".
