# Tasks — quant-catalog-refresh-3005

- [x] 1. Run the refresh chain `make -s sync-registry && make -s sync-quant-catalog && make -s render-trend-list-matrix && make -s render-engine-skill-gap && make -s skills-validate` on a worktree cut from `origin/main` (chain rc=0; 93 models, 2143 links; trend matrix 81 cases unchanged; skills 18/18, 0 errors)
- [x] 2. Run `make -s spawn-engine-skill-issues DRY=1`: no unresolved engine, nothing to file
- [x] 3. Replay the battery gate on the refreshed tree: `make check-quant-catalog` rc=0 and `make check-quant-catalog LIVE=1` rc=0
- [x] 4. `make openspec-validate NAME=quant-catalog-refresh-3005` exits 0
- [x] 5. Fast gates green on the tree: `make lint`, `make check-workflows`, `make check-wiring`, `make check-docs`, `make check-trend-list-matrix`, `make check-engine-skill-gap`, `make skills-validate`
- [x] 6. Full unit battery `make test-unit` green at the branch head
