# check-pr-base-behind-vs-foreign — Tasks

Issue: [#2138](https://github.com/asimov-agent/llgenie/issues/2138)

- [x] 1. `_own_vs_foreign` treats the head branch's own refs (`--head-ref-name`) and the PR's synthetic refs (`--pr-number`) as OWN even in the merge-ref shape; thread them through `_verdict`/`check`/`render`/`main`.
- [x] 2. `make check-pr-base` forwards `PR_BRANCH`/`PR_NUMBER`; the ci.yml guard step sets them for both call sites.
- [x] 3. `tests/test_check_pr_base.py::test_a_merge_ref_behind_branch_passes_when_the_head_branch_is_named` reds on the pre-fix gate, passes on it; and `test_a_genuine_leak_still_reds_in_the_merge_ref_shape` keeps the genuine-leak negative control red.
- [x] 4. Sabotage proof: a merely-behind own-commit branch now prints `STALE ... every commit it carries is its OWN`, exit 0, with `--head-ref-name`/`--pr-number`; without them the OLD message calls the branch's own commit foreign (exit 1). A genuine leak from `refs/remotes/origin/<other>` still FAILS naming only the foreign commit (exit 1). Transcripts in the PR body.
- [x] 5. `make openspec-validate NAME=check-pr-base-behind-vs-foreign` exits 0; check-wiring / check-workflows / check-docs / check-pr-hygiene / check-pr-closing / check-pr-authors / lint all green.
