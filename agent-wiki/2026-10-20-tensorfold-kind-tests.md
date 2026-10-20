# The TensorFold suites stop assuming the skill pip-installs itself (issue #389)

**Issue:** [#389](https://github.com/asimov-agent/llgenie/issues/389) · **Change:**
`openspec/changes/tensorfold-kind-tests` · **Follows:** #386 / PR #388 (merged)

## What was wrong

#388 made the TensorFold seamless suite install-kind agnostic, but four assertions still took "the
pip kind" from the **repo's** skill, or hardcoded the pip command. On
`chore/engine-bump-tensorfold` (#373) rebased onto that main — TensorFold moved to its release
archive — they reddened the unit lane:

```
FAILED tests/test_tensorfold_seamless.py::test_a_host_without_uv_only_blocks_the_pip_install[live]
FAILED tests/test_tensorfold_seamless.py::test_llgenie_pick_installs_tensorfold_then_execs_its_start_script
FAILED tests/test_tensorfold_seamless.py::test_interactive_llgenie_lists_pick_qwen38_27b_then_tensorfold_which_installs_and_serves
FAILED tests/test_engine_bump.py::test_tensorfold_v1_0_5_release_is_native_archives   (make test-engine-bump-live)
```

`release_archive_install` returning `None` for the already-archive repo skill was the *correct*
answer — a skill that pip-installs from git is its contract, and the test fed it the archive shape.

## What changed

- A synthesized **pip** skill (`PIP_SKILL` / `PIP_PINNED`) joins the synthesized archive one; the
  `tf` fixture serves `pip`, `archive` and `live`. Nothing in the suite reads the install kind off
  the repo skill any more.
- The no-uv test is parameterized over the two synthesized kinds: archive installs without uv, pip
  is still refused with `missing prerequisite: uv`.
- The two end-to-end pick tests assert **exactly one** install ran through the skill's declared step
  and the pinned release is installed (the fixture's `installs()` is already kind-aware).
- The live release test builds the pip-shaped skill the derivation asks for, and additionally
  asserts an already-archive skill derives nothing.

## Verified

- This tree (main + the fix): `test_tensorfold_seamless.py` + `test_engine_bump.py` → **107 passed**
  in `llgenie/test:latest` (with the Makefile's worktree mount).
- `chore/engine-bump-tensorfold` (#373) rebased onto this tree, same two files → **107 passed**,
  where the four tests above were red before the fix — the bump PR inherits the fix by rebase.
- `make lint`, `make check-docs`, `make check-wiring`, `make openspec-validate
  NAME=tensorfold-kind-tests` pass.
