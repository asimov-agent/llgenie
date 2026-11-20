# Tasks: sweep-record-2652

- [x] 1. `scripts/auto_merge.py`: `recheck --record <issue>` — instrument the sweep
  decisions (merged / approved / deferred + reason) and post the ONE fixed-format
  record comment after a non-dry sweep; `--dry` posts nothing; no `--record` means
  byte-identical old behavior.
- [x] 2. Tests in `tests/test_auto_merge.py`: fixed-format comment exactly once;
  per-deferral reason line; dry posts nothing; unrecorded sweep stays quiet.
- [x] 3. `mk/bots.mk`: `auto-merge-recheck` forwards `RECORD=<issue>`;
  `.github/workflows/auto-merge.yml` recheck step passes `RECORD=2652`.
- [x] 4. Gate proofs run locally: `make test-unit` green, `make check-wiring`,
  `make check-workflows`, `make check-ci-discipline`, `make openspec-validate
  NAME=sweep-record-2652` rc=0.
- [x] 5. Three-mirror alignment: issue #2652 body keeps its AC; the PR body carries
  the AC mirrors with replayable proven clauses and `Issue: #2652` WITHOUT any
  closing keyword (tracker never closes); agent-wiki note + docs/changes.d fragment
  name the issue and the PR.
- [x] 6. Live proof: `make auto-merge-recheck REPO=asimov-agent/llgenie MAX=50
  RECORD=2652` runs ONCE from this branch as a real sweep and posts its
  `[sweep <stamp>] …` comment on #2652; the comment id is quoted in the PR body.
  (After landing, the scheduled lane keeps recording on its own cadence; #2652's AC
  is stamped with that comment id — the tracker stays OPEN.)
