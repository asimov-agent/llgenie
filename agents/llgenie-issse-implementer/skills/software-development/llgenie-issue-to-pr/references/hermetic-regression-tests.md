# Where a regression test belongs: ci-unit (hermetic) vs ci-hf-live (network)

## Rule: a business-logic regression test goes in the HERMETIC unit set, even when a network-marked duplicate already exists

When you fix pick/matrix/scope/recommend logic and add a regression test, the test must run in
`make test-unit` (the hermetic, HF-stubbed set) so the business rule is gated on every PR. Do NOT
add it only as a `@pytest.mark.network` test next to the duplicated live suite: the network set runs
only in ci-hf-live, which is slow, flaky and already the most RED-prone gate, so a fix "covered"
only there is not covered at all for everyday CI. A duplicated HF-live test is NOT a substitute for
a hermetic unit test — it is a second, slower witness.

This is an owner preference stated as a correction, not a style choice: the regression test must be
part of the CI-unit pipeline, not just the HF-live suite.

## The FILE decides membership, not the individual test case

"Is my test part of ci-unit?" is answered by which file the test lives in, not by per-function
markers:

- `tests/test_pick_matrix.py`-style files (stubbed/offline registry, fixture renderers) are
  collected by `make test-unit` → every `test_…` you add there runs hermetically.
- `tests/test_pick_*.py` network files carry `@pytest.mark.network` → they run only under
  ci-hf-live and are excluded from the unit leg.

So put the new test in the hermetic sibling file, not in the network file. Do not rely on a marker
to selectively include one function of a network file — the unit runner selects by file set.

## How to write the hermetic repro

Reproduce the defect against the stub registry the hermetic file already builds (its synthetic
`fits()`/tier fixtures), asserting the OBSERVABLE contract rather than internal helpers — e.g. an
off-band-but-fitting model lands in `skipped` with a reason and is never silently dropped from both
`offered` and `skipped`. Assert behaviour (membership + reason), never a fixed list the tree is meant
to extend (`expected <= set(actual)`, not equality).

## Verify in the unit path, not the network path

Run the hermetic file the way CI does (containerised `make test-unit`, or
`python scripts/unit_tests.py run` in the test image — a background process, see the 300s cell cap),
and read the count arithmetic: prior + N new = total at the current head. A green network run proves
nothing about the unit leg; a green unit run on the hermetic file is the acceptance for this class
of fix.
