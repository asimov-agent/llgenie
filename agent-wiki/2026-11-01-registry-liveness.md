# Registry-liveness monitor: an unpublished engine pin is named to the board (#1396, #1397)

The one gate that catches a committed engine pin whose image was never published —
`make check-engine-launchers CHECK_REGISTRY=1` — was opt-in and NO workflow set it, so the
#1365 class (a committed pin whose ghcr image resolves no manifest) passed every committed CI
forever, visible only to a manual run. A control no CI reads is a control that does not exist.

Merged `d28abd26` (#1397, closing #1396) added `.github/workflows/registry-liveness.yml`: a
schedule (three times daily) + push-to-main control that runs the `CHECK_REGISTRY` gate and
opens ONE duplicated tracking issue per engine whose committed pinned tag resolves no manifest,
registering itself in the run-failure-reactor roster so even a crash is not invisible. It never
runs in a PR (a PR's pin tags are legitimately unpublished — engine-build publishes on merge),
so it can never false-red the fleet. This change is its behavioural change-note; the workflow
itself landed in #1397.