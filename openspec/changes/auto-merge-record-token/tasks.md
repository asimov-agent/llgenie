# Tasks: auto-merge-record-token (issue #2953)

- [ ] `scripts/auto_merge.py` posts the `--record` comment through
      `_gh(..., token=RECORD_TOKEN)` when `RECORD_TOKEN` is set, ambient otherwise
- [ ] `auto-merge.yml` recheck sweep step sets `RECORD_TOKEN: ${{ github.token }}`
- [ ] fake-gh harness captures the environment token of `issue comment` calls
- [ ] new tests pin the override and the no-override default
- [ ] `make test-unit` green at the branch head
- [ ] `make lint`, `make check-wiring`, `make check-workflows`, `make lane-preflight`
      green; `make openspec-validate NAME=auto-merge-record-token` passes
- [ ] docs mirrors land in the same commit (agent-wiki entry, docs/changes.d fragment,
      docs/BOTS.md line)
- [ ] live proof: after the PR merges, the next main-head auto-merge run is green and a
      `[sweep ...]` record comment posted by github-actions[bot] lands on #2652
- [ ] the change's issue/PR/OpenSpec alignment is re-checked and the PR lands green via
      CI auto-merge
