# Tasks: ci-scope-mk-wildcard (issue #2942)

- [x] Add `mk/**` to `scripts/ci_scope.py::WILDCARDS` with a comment naming the #2942 proof (PR #2941 scope red on mk/*.mk)
- [x] Add `mk/bots.mk` to the wildcard-path parametrize in `tests/test_ci_scope.py`
- [x] Prove classification: `classify(["mk/bots.mk"])` → unmatched empty, every class selected; CLI rc=0
- [x] Green battery: `pytest tests/test_ci_scope.py` + `make lint` + `make check-workflows` + `make check-docs`
- [x] Docs: agent-wiki entry + `docs/changes.d/` fragment + CHANGES.md row (docs-index seam)
- [x] Final alignment: issue #2942 body, PR body, and commit text carry the same ticked AC items; `make openspec-validate NAME=ci-scope-mk-wildcard` rc=0
