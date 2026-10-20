# The TensorFold suites stop assuming the skill pip-installs itself

## Why

#386 (merged, PR #388) made the TensorFold seamless suite install-kind agnostic, but four
assertions still take "the pip kind" from the **repo's** skill, or hardcode the pip command. On
`chore/engine-bump-tensorfold` (#373) rebased onto that main — where the pin has moved TensorFold to
its release archive — those four red the unit lane:

```
FAILED tests/test_tensorfold_seamless.py::test_a_host_without_uv_only_blocks_the_pip_install[live]
FAILED tests/test_tensorfold_seamless.py::test_llgenie_pick_installs_tensorfold_then_execs_its_start_script
FAILED tests/test_tensorfold_seamless.py::test_interactive_llgenie_lists_pick_qwen38_27b_then_tensorfold_which_installs_and_serves
FAILED tests/test_engine_bump.py::test_tensorfold_v1_0_5_release_is_native_archives   (make test-engine-bump-live)
```

Each is the test's assumption, not the product: `[live]` needs a pip skill and gets the archive one
(so the pip assertion fails); the two subprocess pick tests assert the literal
`uv tool install --force tensorfold @ git+…@v<pinned>` line; and the live release test feeds the
already-archive repo skill into `release_archive_install`, whose contract is "a skill that
pip-installs from git" — a skill that is already archive-shaped correctly derives nothing.

## What Changes

- `tests/test_tensorfold_seamless.py`: a synthesized **pip** skill (`PIP_SKILL`) joins the
  synthesized archive one, and the `tf` fixture serves both, so a test that needs "the pip kind"
  never depends on what the repo's skill declares. The no-uv test is parameterized over the two
  synthesized kinds; the two end-to-end pick tests assert that **exactly one** install ran and
  reached the pinned release, in the step the skill declares — not a hardcoded command.
- `tests/test_engine_bump.py`: the live release test builds the pip-shaped skill the derivation's
  contract asks for, and additionally asserts that an already-archive skill derives nothing.

## Impact

- A bump that moves an engine to release archives stops reddening the lane that was supposed to
  prove the archive shape; the failing job names the test, not the engine.
- No product code changes, no `skip`, no weakened assertion: the pip kind is still proven to demand
  `uv`, and the pick tests still prove a real install landed the pin.
