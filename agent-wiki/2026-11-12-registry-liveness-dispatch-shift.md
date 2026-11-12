# 2026-11-12 — registry-liveness `[select]` dispatch field-shift fix (#2567)

Implements issue #2567 (OpenSpec change `registry-liveness-dispatch-shift`).

## What was verified against the spec

- **The defect is real and measured**: registry-liveness run 43187080395 / job 131076815722
  (main `e6b9b4b4f`) logged 22 dispatch lines `for [select]/llama.cpp (missing tag cpu …)` —
  the loop read THREE variables from the gate's FOUR-token `[select]` contract line, shifting
  every field right. All 22 dispatched engine-build runs (43187181181…43187252711) carried
  `engine="[select]"`, matched no committed params id, and vacuously "succeeded" publishing
  nothing — the same none/none-placeholder class #2561 documented on `aa700cf27`. This is why
  the 19-cell unpublished-pin backlog never drained and every unit gate stayed red.
- **The fix** binds the marker in its own field (`sel engine variant tag extra`), refuses any
  line that violates the contract (printed, counted, step exits 1), and dispatches only
  contract-exact lines. Spec scenarios are all proven:
  - clean sim against the gate's REAL 19 `[select]` lines at `e6b9b4b4f`: rc=0, 19 dispatches,
    engine ids dotted (`llama.cpp`, `llama.cpp-laurentzuijdwijk`, …), valid variants, push=true.
  - malformed sim (shifted line, 3-token line, 5-token line, empty engine): rc=1, 4
    `UNRECOGNIZED` reports, 0 malformed dispatches.
- **Drift guard**: `test_the_dispatch_read_loop_binds_the_select_contract_positionally` parses
  the workflow loop adjacent to `done < select.txt`; proven RED against main `e6b9b4b4f`'s
  yml (fields `engine variant tag`) and GREEN against the fix.
- Module suite: 15/16 pass; the only failure is the known live-registry backlog test
  (404s for unpublished pins — fleet-gated, red repo-wide at `e6b9b4b4f`, untouched by this change).

## Key decisions

- Loop-side validation instead of trusting the gate's own output only: a malformed producer
  can no longer dispatch a vacuous run at all.
- The complementary producer-side guard (engine-build must red on an unknown non-empty
  `inputs.engine`) was filed as its own issue #2568, per the out-of-scope rule.
- The 22 malformed runs are documented in #2567 and left to vacate the queue harmlessly;
  the post-fix registry-liveness run re-dispatches every still-missing cell correctly.

## Current status

PR opened against upstream main from `feat/registry-liveness-dispatch-shift`. The pin backlog
and the unit gates it blocks are tracked in #2518/#2529; this change is what makes the #2259
self-heal actually heal.
