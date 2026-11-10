# ci-verdict self-count defect — verified resolution (issue #1882, 2026-11-06)

## The defect (measured on the wire)

`ci-verdict.yml`'s judge POSTs its verdict as a `ci-verdict` check-run on the judged run's head. GitHub
lists that posted row BACK as a job of the very run being judged. Measured 2026-11-06, run **42275871131** @
head `cf88d285` (PR #1837, attempt 7): the CI run concluded **SUCCESS** (all 10 real jobs green) yet the
`ci-verdict` check `128132878370` was red, because the jobs API returned an 11th row `ci-verdict =>
failure` and `scripts/ci_scope.py::verify()` counts any observed row not in the scope table that reports
`failure` as an unaccounted failure → verdict red. Every re-judge re-counted the judge's own one-off
`failure` → a self-referential permanent red.

## The fix (retained vehicle #1883)

`scripts/ci_verdict.py` drops the verdict's own `CHECK_NAME` (`ci-verdict`) row from the job set it judges
before calling `verify()`. Two lanes (implementer, this lane) independently arrived at the identical
`own_check_run()` / `CHECK_NAME`-drop. `ci_scope.verify()`'s rule that an unknown REAL failing job is an
unaccounted failure stays intact — only the judge's own output is removed.

Re-judge of the exact onboard shape (10 real green jobs + 1 self `ci-verdict => failure` row):
- **pre-fix**: verdict=red (failure=1)
- **post-fix**: verdict=green (success=10, failure=0)

THE LIVE RE-JUDGE OF RUN 42275871131 DOES **NOT** POST SUCCESS — it posts **RED FOR A REAL CAUSE**. Because ci-verdict.yml has NO `workflow_dispatch`, the only way to re-judge is to re-run the judged run so its `workflow_run` judge re-fires. When I re-dispatched it (re-run 4047), the fresh check-run `128153241467` read `guard FAILED` (the guard's `make check-pr-base` red; #1837 was cut from another PR's base `742676cb`) → verdict=red **attributed to the real guard job, NOT to a `ci-verdict` self-row**. That is the #1883 fix working on the wire, and it reveals #1837 is blocked by its own base defect, not the verdict gate. Also: a finished run's job records eventually expire (`GET /actions/runs/{id}/jobs` → `total_count` shrinks/0), after which the post-fix judge correctly posts `none` (all rows ABSENT), not success. Re-judge success therefore requires a live/fresh run whose real jobs are actually green. Because ci-verdict.yml has NO `workflow_dispatch`, re-judging requires re-running the whole judged CI — the gap is filed as **issue #1886** (proposes a dispatchable run_id-input re-judge path).

## One-vehicle-per-issue outcome (#824)

- **#1883** (implementer, head `ff0aadb5`, `closes #1882`, reviewer-verdict-gated) is the **retained vehicle**.
- **#1883 MERGED** as merge commit **`3ab5eca`** (2026-11-06 20:51:16Z); the merge commit carries `scripts/ci_verdict.py` +
  `tests/test_ci_verdict.py` + openspec change `ci-verdict-does-not-judge-itself` + docs trio. **#1882 is resolved on
  the wire; #1837 unblocks.**
- **#1884** (this lane's independent fix) was correctly **closed by the owner as #1883's duplicate** — the
  diagnosis was NOT rejected, it was identical.
- Owner (andyholst) dispatched #1882 to this lane at 20:29Z then reconciled 3 min later (#1883 is the vehicle;
  the 20:29 dispatch predated discovering it). This lane stood down and did NOT open a second fixing PR. Later the
  planner asked this lane to review #1883 against #1882's ACs (not to re-implement): **review PASS, no defect**
  (posted `6695330125`); AC2 re-judge evidence + honesty correction posted `6695322948`.
- Lesson: the closing keyword must name the DEFECT issue (matched by root cause), never the product PR a red
  appeared against; and a sibling lane with the identical fix means the owner keeps one vehicle — close yours,
  deliver the shared evidence on the retained PR, never reopen or push a competing code path.

## Evidence / gates

- `tests/test_ci_verdict.py` regression on the measured shape; `test_ci_scope.py` untouched path.
- Guard-prove (pinned `llgenie/test:latest`): `test_ci_verdict.py` green; stash of the fix → red.
- `make openspec-validate-all` 333 passed / 0 failed (retained vehicle's openspec change valid).

No merge/arm (#1088). #1837 unblocks when #1883 lands + its re-judge of 42275871131 posts `ci-verdict:
success` on `cf88d285`.
