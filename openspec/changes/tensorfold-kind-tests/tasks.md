# Tasks

- [x] 1. `tests/test_tensorfold_seamless.py`: synthesize the pip skill (`PIP_SKILL`, `PIP_PINNED`) next to the archive one, and let the `tf` fixture serve `pip` as well as `archive` and `live`
- [x] 2. Parameterize the no-uv test over the two synthesized kinds, so "the pip kind" never comes from the repo skill
- [x] 3. The two end-to-end pick tests assert exactly one install ran through the skill's declared step and the pinned release is installed (no hardcoded `uv tool install` line)
- [x] 4. `tests/test_engine_bump.py`: the live release test feeds the derivation a pip-shaped skill and asserts an already-archive skill derives nothing
- [x] 5. Record the change in `agent-wiki/` and reference it from the README's test notes
- [x] 6. Verify on a worktree of `chore/engine-bump-tensorfold` rebased onto this tree: the four previously failing tests pass; on this tree `test_tensorfold_seamless.py` + `test_engine_bump.py` are green
- [x] 7. Verify: `make test-unit`, `make lint`, `make check-docs`, `make check-wiring`, `make openspec-validate NAME=tensorfold-kind-tests`
- [x] 8. Commit, push the branch, open the PR against upstream `main` (`closes #389`) — leaving #373 to inherit the fix by rebase
