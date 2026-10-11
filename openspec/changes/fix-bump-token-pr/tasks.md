# fix-bump-token-pr — Tasks

- [x] 1.1 `engine-bump.yml` bump job checks out, pushes and opens the PR with `secrets.BUMP_TOKEN`; commit author is the token owner.
- [x] 1.2 `registry-sync.yml` sync job does the same.
- [x] 1.3 The collaborator guard still uses `secrets.GITHUB_TOKEN`; neither workflow merges.
- [x] 1.4 Tests lock the three scenarios; README states the owner-PAT rule.
- [x] 1.5 `make openspec-validate NAME=fix-bump-token-pr` and `make test-unit` pass.
- [x] 1.6 Commit, push, open PR against upstream main referencing #136.
