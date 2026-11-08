## ADDED Requirements

### Requirement: a merge GitHub refuses at merge-instant is a deferral or a success, never a red run

When `gh pr merge` exits non-zero on a PR this run already read as mergeable, the sweep SHALL
re-read the PR and resolve the refusal as follows:

- if the PR is already `MERGED`, a sibling run landed it: this run SHALL verify the closure and
  exit success, treating the already-done merge as a success, never a red run;
- if the PR is still `OPEN`, the refusal is genuine: this run SHALL post a deferral comment
  carrying the refusal reason ON the PR and exit 0.

A CLEAN `pr view` is never a licence to let the merge call's refusal die red: a sibling run (or
a transient async recompute) can merge the PR between the read and the call (run `42469582901`
read `#2102` CLEAN at `10:01:05Z`; a sibling had already merged it at `10:01:04Z`, so GitHub
answered `Pull Request is not mergeable`).

#### Scenario: a refusal of an already-merged PR is reported as success

- **GIVEN** a run whose `pr view` read the PR CLEAN
- **AND** `gh pr merge` is refused because a sibling already merged the PR
- **WHEN** the sweep handles the refusal
- **THEN** it re-reads the PR as `MERGED`, verifies the closure and exits 0 — never red
- **Test:** `tests/test_auto_merge.py::test_a_merge_refused_after_a_sibling_merged_is_not_a_red_run`

#### Scenario: a refusal of a still-open PR defers with the reason on the PR

- **GIVEN** a run whose `pr view` read the PR CLEAN
- **AND** `gh pr merge` is refused while the PR is still `OPEN`
- **WHEN** the sweep handles the refusal
- **THEN** it posts a deferral comment naming the refusal reason on the PR and exits 0
- **Test:** `tests/test_auto_merge.py::test_a_merge_refused_while_still_open_defers_naming_it` (the
  negative control — it reds if a real refusal is swallowed without deferring)
