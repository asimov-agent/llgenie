# check-pr-base-behind-vs-foreign

## ADDED Requirements

### Requirement: a merely-behind branch carrying only its own commits is STALE, never foreign

When a branch's merge-base with the live base ref is an OLDER real tip of that
base's `main` history (so the branch is merely behind, not cut from a divergent
lineage) and every commit in `base..rev` is reachable only from the base and the
branch's own refs, `check-pr-base` MUST report the branch as behind/stale
(green, a distinct `STALE` message) — never as carrying a foreign commit — and
MUST NOT name the branch's own commit as the foreign commit.

[comment]: # (AC: a behind branch with only its own commits exits 0 and prints the STALE verdict; the old gate on the same branch printed FAILED naming the branch's own commit.)

#### Scenario: a merely-behind branch with only its own work is green

- **Given** a branch cut from an older real `main` tip, whose `base..rev`
  commits are all its own
- **When** `check-pr-base check --base <base> --rev <rev>` runs
- **Then** it exits 0 and prints the `STALE` verdict ("is behind ... and every
  commit it carries is its OWN"), never a `FAILED`
- **Test:** `tests/test_check_pr_base.py::test_a_stale_but_clean_branch_passes_with_distinct_message`

#### Scenario: the FAIL message never calls the branch's own commit foreign

- **Given** a behind branch whose only `base..rev` commits are its own, checked
  out as the PR **merge ref**
- **When** the gate runs with `--head-ref-name <branch>` and `--pr-number <n>`
- **Then** it exits 0 and names no commit of the branch's own as foreign
- **Test:** `tests/test_check_pr_base.py::test_a_merge_ref_behind_branch_passes_when_the_head_branch_is_named`

### Requirement: the head branch's own refs are OWN in the merge-ref shape

When the PR head is checked out as its **merge ref** (the `linux / unit`
shape), `refs/heads/<branch>`, `refs/remotes/origin/<branch>`, and
`refs/pull/<n>/{head,merge}` MUST count as the branch's OWN lineage — not as a
foreign-signal — even though the branch's own remote ref does not contain the
merge `rev`. The head branch refs and PR number come from `--head-ref-name`
and `--pr-number`.

[comment]: # (AC: the discriminator treats the branch's own refs as OWN regardless of `--contains rev`.)

#### Scenario: the branch's own refs are not a foreign signal in the merge shape

- **Given** a behind branch checked out as its PR merge ref, its head commit an
  ancestor of the merge
- **When** the gate runs with `--head-ref-name <branch>` / `--pr-number <n>`
- **Then** the branch's own commits are attributed to the branch (own), not to
  a foreign ref, and the verdict is STALE (green)
- **Test:** `tests/test_check_pr_base.py::test_a_merge_ref_behind_branch_passes_when_the_head_branch_is_named`

### Requirement: a genuine foreign commit still fails, named

When a branch carries a commit that is reachable from another branch/tag/PR ref
that is NOT the base (`origin/main`) and NOT the head's own refs, `check-pr-base`
MUST exit 1 and name that foreign commit — the #845 leak must stay red even in
the merge-ref shape.

[comment]: # (AC: reintroducing a genuinely foreign commit still reds, naming only the foreign commit.)

#### Scenario: a genuine leak in the merge-ref shape still reds with the commit named

- **Given** a branch checked out as its PR merge ref that genuinely inherits a
  commit reachable from `refs/remotes/origin/<other>`
- **When** the gate runs with `--head-ref-name <branch>` / `--pr-number <n>`
- **Then** it exits 1 and names the foreign commit (its reachable ref), and does
  not weaken the #845 guard
- **Test:** `tests/test_check_pr_base.py::test_a_genuine_leak_still_reds_in_the_merge_ref_shape`

#### Scenario: a genuine leak cut from a stale other PR still reds

- **Given** a branch whose merge-base is a stale `main` tip carrying a commit
  from another open PR
- **When** the gate runs
- **Then** it exits 1 and names the leaked commit as a foreign commit
- **Test:** `tests/test_check_pr_base.py::test_a_genuine_leak_cut_from_a_stale_other_pr_still_reds`
