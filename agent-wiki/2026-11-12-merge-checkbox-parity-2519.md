# Merge-lane checkbox parity — commit text must carry the ticked acceptance mirror (#2519)

Issue: #2519 · branch: feat/merge-checkbox-parity (PR number recorded when the PR opens)

## What was verified

- **The measured defect.** PR #2509 merged as squash `49f0cc3be` whose commit text carries
  `checked=0 unchecked=3`: the bot pasted the issue's unticked `## Acceptance criteria` into the
  squash commit message and no gate read it. A squash merge concatenates branch commit messages into
  the commit that lands on `main` forever — the commit text is the PERMANENT record of the checklist,
  and only the issue body was ticked.
- **One rule, one implementation, three mirrors.** `scripts/check_pr_hygiene.py` gained
  `commit_text_findings(messages, body)` with two findings: `commit-unchecked-acceptance` (an unticked
  `- [ ]` under an acceptance heading in any commit of the range) and `commit-acceptance-unmirrored`
  (the PR body declares N items via `acceptance_writeback.acceptance_items`, reused not restated, while
  the commit text carries fewer than N ticked boxes). `scripts/auto_merge.py` gained
  `commit_checkbox_hold(state, gh)`: the merge lane re-runs the SAME findings against the live commits
  (`gh api …/pulls/<n>/commits`, record-separator split — `execv` refuses a real NUL in argv, so the
  jq escape is `\u001e`) immediately before `gh pr merge`, deferring with a `commit-checkboxes:`
  reason comment and never touching `--squash`/`--admin` on a held PR.
- **Wiring.** `make check-pr-commit-checkboxes` (mk/gates.mk) + the `ci.yml` guard-job step with the
  LIVE `gh api` body fetch (issue #1589 pattern) + the hermetic `ci-unit` mount (commit-side rule
  only, `--body-file` empty) + `DEFERRED` classification in `scripts/issue_bot_gates.py` with its
  reason + the declared `auto_merge -> check_pr_hygiene` edge in `scripts/package-layers.json` (one
  parity rule, one implementation, so the lane and the lane gate cannot disagree).
- **Tests.** `tests/test_pr_hygiene_commit_checkboxes.py` (unit + CLI + fixture range, the #2509
  message shape refused; merge-lane deferral asserted) and a shim-based end-to-end test in
  `tests/test_auto_merge.py` (`test_unticked_acceptance_boxes_in_the_commits_hold_the_merge`): green +
  CLEAN head with unticked boxes → deferral comment, no merge call; ticked mirror → merge proceeds.
  Targeted suite 162/162 green across package-layers / check-docs / issue-bot-gates / auto-merge /
  commit-checkboxes after the docs + mount fixes; `make lint` and `make check-wiring` rc=0.

## Decision

Tick at CLOSE time, not post-hoc: the squash commit IS the act that carries the ticks, so a post-merge
edit pass would be double work (owner-confirmed). The gate never ticks and never closes — closing stays
the ONE automatic act (`closes #N` on merge); it only refuses to merge text that breaks the parity.

## Current status

Branch pushed, PR up against upstream main; `tasks.md` fully ticked at merge time per this very rule.

2026-11-12 rebase + replay (head `a59b9563c` on `origin/main` `c4734a020`): the unpushed reword
commit was cherry-picked onto the rebased remote chain and tasks 7-8 carry measured evidence —
`openspec-validate` rc=0; `commit-checkboxes` replay of `49f0cc3be` RED rc=1 (3 unticked boxes,
0 ticked mirror); `d8700c60e` and `aa700cf27` rc=0. CI `linux / unit` on this head (run
43175752662) is 1 failed / 3646 passed: the sole failure is the fleet-publish gate
`test_every_image_install_pulls_is_published` (unpublished engine images under the #2529 dispatch
wave), not this change's files — unit goes green when the fleet wave lands and the jobs rerun.
