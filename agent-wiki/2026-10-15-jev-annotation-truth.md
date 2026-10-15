# The JEV signal must not overstate itself, and the docs must match the armed gate (#284)

## Why

Two inaccuracies, both in the thing a maintainer reads to answer "is JEV on?":

1. **The offline path claimed a live call.** With `NERVE_GATE_SKIP_PROVIDER=1` the preflight does not
   contact the provider, yet the final annotation still said *"JEV is ON for this run … provider
   typesafe answered a real decision call"*. A signal that overstates itself is worse than no signal.
2. **The prose still described the old, advisory contract.** After the bot workflows were changed to
   **arm** the gate (`make agent-jev-preflight NERVE_REQUIRE=1` — "Prove the JEV engine is active — the
   run does not start without it"), the preflight header still said *"No bot workflow sets it"*, and so
   did the README. The file contradicted the pipeline.

## What changed

- **The skip path says what it did**: `JEV is configured for this run: … — the provider was NOT
  contacted (NERVE_GATE_SKIP_PROVIDER=1)`. With the provider actually contacted, the notice still says
  it answered.
- **The two modes are stated where they are used** (preflight header): the default reports and
  continues (manual/local), `NERVE_REQUIRE=1` makes the layer a precondition — and **the bot workflows
  arm it**, which is the maintainer's rule for autonomous runs.
- **The refusal message covers both uses**: `(NERVE_REQUIRE=1 — the JEV layer is required here: a bot
  run does not start without it, and an image check fails without it)`.
- README corrected to the same wording.

## Tests

`tests/test_agent_nerve.py` → **27 passed** (was 25):

- `test_the_annotation_does_not_claim_a_call_that_was_skipped` — offline: "configured", "the provider
  was NOT contacted", and **not** "answered a real decision call"; online: the notice says it answered.
- `test_the_docs_match_the_armed_contract` — neither the preflight nor the README may still claim "no
  bot workflow sets it", and both must state that the bot workflows arm the gate.
- the pre-existing `test_every_bot_workflow_arms_the_jev_gate` (the maintainer's rule) keeps passing.
