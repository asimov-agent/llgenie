# Tasks: openspec-seam-uid-map

- [x] 1. Restamp issue #433 into the six-section form with tickable acceptance criteria
- [x] 2. Create the feature branch worktree off the latest `origin/main`
- [x] 3. Create the OpenSpec change via the CLI (`make openspec-new`)
- [x] 4. Write proposal.md + specs/container-run-ownership/spec.md
- [x] 5. Patch `Makefile` `OS_OPTS`: invoking-uid mapping + `HOME=/tmp`, drop `-u root` (proven: live probe `make openspec-new NAME=uidmap-probe-433` rc=0 with 0 root-owned entries at the fixed default seam)
- [x] 6. Pin the seam in `tests/test_openspec_gate.py` (OS_OPTS names id -u/id -g, no `-u root`; exactly the two carve-out stages root)
- [x] 7. `make openspec-validate NAME=openspec-seam-uid-map` exits 0
- [x] 8. Targeted tests + `make test-unit` green on the lane
- [x] 9. `make lane-preflight` prints `preflight: OK`
- [x] 10. The commit text carries `closes #433` and the mirrored ticked acceptance block
