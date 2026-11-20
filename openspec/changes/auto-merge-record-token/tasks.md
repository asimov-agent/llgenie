# Tasks: auto-merge-record-token (issue #2953)

- [x] `scripts/auto_merge.py` posts the `--record` comment through `_gh(..., token=RECORD_TOKEN)` when `RECORD_TOKEN` is set, ambient otherwise (proof: `pytest tests/test_auto_merge.py -k record -q` 9 passed rc=0 at head 2fadfa8b3463)
- [x] `auto-merge.yml` recheck sweep step sets `RECORD_TOKEN: ${{ github.token }}` (proof: `make check-workflows` rc=0 at head 2fadfa8b3463)
- [x] fake-gh harness captures the environment token of `issue comment` calls into `gh.log.record.env`
- [x] new tests pin the override (`test_record_comment_uses_record_token`) and the no-override default (`test_record_comment_without_record_token_keeps_the_ambient_token`) (proof: 9 record tests pass rc=0)
- [x] `make test-unit` green at the branch head (proof: 4207 passed, rc=0, tree of head 2fadfa8b3463)
- [x] `make lint`, `make check-wiring`, `make check-workflows` green; `make openspec-validate NAME=auto-merge-record-token` passes (proof: rc=0 each at head 2fadfa8b3463); `make lane-preflight` runs on the final clean tree
- [x] docs mirrors land in the same commit (agent-wiki entry, docs/changes.d fragment, docs/BOTS.md line)
- [x] live wiring proof: `make auto-merge-recheck REPO=asimov-agent/llgenie RECORD=2652 DRY=1` rc=0 at head 2fadfa8b3463 — printed the record line the sweep would post and posted nothing
- [x] alignment: issue #2953 body mirrors this change (six sections, ACs ticked with proven clauses at 2fadfa8b3463; side issue linked by URL, no rollout-lane back-cite); #2954 carries the origin link; the post-merge live read (next main-head recheck green + a `[sweep ...]` comment by github-actions[bot] on #2652) is the lane's landing evidence, recorded in the issue body
