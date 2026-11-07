# Spec: check-pr-base attributes a stale-but-clean PR to its stale base, not to #845

## ADDED Requirements

### Requirement: `check_pr_base.py::check` returns a stale-but-clean verdict distinct from #845

When the merge-base IS an ancestor of the live `origin/main` (the branch was cut from a real
`main` tip) and every commit in `base..rev` is reachable only from the base or the head's own
branch (nothing belongs to another ref/PR), `check` returns a `stale` verdict: ok (exit 0, so
the `guard` job passes and the walking legs run) with a distinct non-#845 message naming
"rebase onto a fresh origin/main". The head carries only its own work; it is stale, not a
foreign-branch leak.

#### Scenario: a stale-but-clean branch cut from an older main passes with a distinct message

Given a branch cut from an OLDER real `origin/main` tip (merge-base IS a `main` ancestor)
And every commit in `base..rev` is reachable only from the base or the head's own branch
When the gate judges check-pr-base against the live `origin/main`
Then the gate exits 0
And the rendered message is the distinct "rebase onto a fresh origin/main" wording
And the message does NOT contain the #845 "foreign commits from another PR" accusation

- **Test:** `tests/test_check_pr_base.py::test_a_stale_but_clean_branch_passes_with_distinct_message`

#### Scenario: a stale-but-clean guard verdict does not cancel the walking legs

Given the ci.yml `guard` job runs `make check-pr-base` on a stale-but-clean PR head
When the gate returns the stale verdict (exit 0)
Then `guard` does not fail on this step
And the `linux`/`ci-images`/`scanner-images` legs (all `needs: [guard]`) still run
And a unit verdict exists at the head even though the base is stale

- **Test:** `tests/test_check_pr_base.py` (the gate exits 0 on a stale-but-clean head; the
  `guard` job only cancels legs when a step fails)

### Requirement: `check_pr_base.py` still reds a genuine #845 foreign-branch leak

A branch cut from another PR — one whose `base..rev` carries a commit reachable from a
DIFFERENT ref (it belongs to another PR), or whose merge-base is not on `main` at all — still
FAILS with the original #845 message naming the foreign commit. The discriminator must not
weaken the real detection.

#### Scenario: a genuine foreign-branch leak still fails with the original message

Given the #845 shape: a branch cut from another open PR's tip carrying that PR's commit
When the gate judges check-pr-base
Then the gate exits non-zero
And the rendered message contains the original "carries commits from another PR" / issue #845
accusation naming the foreign commit

- **Test:** `tests/test_check_pr_base.py::test_a_foreign_commit_fails_and_is_named` (unchanged)

### Requirement: a branch cut from the current main tip still passes

The negative control is unchanged: a branch whose merge-base == the live `origin/main` passes,
whether it is the one-commit-ahead clean cut or the ancestor/push-to-main exemption.

#### Scenario: a clean one-ahead branch cut from the current main passes

Given a branch cut from the live `origin/main` with exactly one clean commit
When the gate judges check-pr-base
Then the gate exits 0 with the clean-cut message (unchanged)

- **Test:** `tests/test_check_pr_base.py::test_a_clean_one_ahead_branch_passes` (unchanged)

### Requirement: the review pass classifies a stale-but-clean red as "rebase owed"

The dispatch protocol / review skill's "own-gate red = not a review target" rule gains the
stale-vs-foreign distinction: a `check-pr-base`-only red whose gate output shows
merge-base-on-main and own-commits-only is "code green at the measured legs, base stale, rebase
owed" and the reviewer posts that verdict instead of standing down silent.

#### Scenario: a reviewable stale-but-clean red gets a verdict

Given a PR whose only own-gate red is `check-pr-base` at a stale-but-clean head (merge-base on
main, own commits only)
When the review pass classifies it
Then it records "code green, base stale, rebase owed"
And it does not stand down as "own-gate red = not a review target"

## MODIFIED Requirements

### Requirement: an ancestor/push-to-main exemption still passes (#1867)

The existing exemption (merge-base != base but `base..rev` empty — a push to main overtaken by a
newer main) passes unchanged. A stale-but-clean branch (non-empty `base..rev`, merge-base on
main, own commits only) is the NEW distinct case between it and the genuine #845 leak.

#### Scenario: an overtaken push-to-main head still passes

Given a head that is an ancestor of the live base (`base..rev` empty)
When the gate judges check-pr-base
Then the gate exits 0 with the ANCESTOR message (unchanged)

- **Test:** `tests/test_check_pr_base.py::test_a_pushed_main_commit_overtaken_by_a_newer_main_passes`
