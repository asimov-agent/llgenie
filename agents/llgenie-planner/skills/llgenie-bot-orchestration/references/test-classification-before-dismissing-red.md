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

## Corollary

When you get it wrong (dismissed a real ci-unit red as host-side), correct the reporting
lane in the same pass — it was right, and the next reader must not inherit your wrong
"green".
