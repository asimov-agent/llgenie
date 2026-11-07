# Spec: exempt a check-pr-base head that is an ancestor of live main

## ADDED Requirements

### Requirement: `check-pr-base` passes a head that is an ancestor of the base

`scripts/check_pr_base.py::check` passes when `base..rev` is empty — the head is an ancestor
of the live base, so the #845 foreign-diff leak cannot apply. A branch cut from ANOTHER PR
always carries commits absent from the base (`base..rev` non-empty) and still fails; a clean
one-commit-ahead branch still has `merge-base == base` and passes unchanged. This exemption
covers the push-to-main race (a pushed main commit overtaken by a newer main before the
gate's live fetch), and because it lives in the gate's own semantics it covers every caller —
the ci.yml guard-job step and `linux/unit` via `make ci-unit` — not one invocation.

#### Scenario: a pushed main commit overtaken by a newer main passes

Given the CI run's event is a `push` to `main`
And the run's `HEAD` is the pushed commit (already part of main's history)
When the check re-fetches `origin/main` live and finds it has advanced past `HEAD`
Then `git merge-base <base> <HEAD> == HEAD != base`
And `base..HEAD` is EMPTY (foreign commits (0))
Then the gate passes
And no phantom base-staleness red is produced (issues #1867/#1906..#1909)

#### Scenario: a PR branch cut from another PR still fails

Given a `pull_request` branch cut from some base other than the live `main`
And the branch carries commits that `main` never saw
When the gate judges check-pr-base
Then `base..rev` is NON-empty (the foreign diff is present)
And the gate fails, naming the foreign commit(s) (the #845 protection is intact)

#### Scenario: a clean one-commit-ahead PR branch still passes

Given a `pull_request` branch cut from the live `main` with exactly one clean commit
When the gate judges check-pr-base
Then `git merge-base <base> <rev> == <base>`
And the gate passes (the #845 negative control is unchanged)

#### Scenario: a failed base fetch still refuses

Given the base's remote `main` cannot be freshly fetched
When the gate runs
Then it refuses (non-zero) rather than passing on a stale measure (#1734, unchanged)

### Requirement: the verdict names the ancestor exemption

The OK path distinguishes "cut from `base` (merge-base == base)" from "is an ANCESTOR of the
live base (`base..rev` empty)" so a green push-to-main run is auditable as the exemption, not
mistaken for a clean PR cut.

#### Scenario: an ancestor pass says so

Given a push-to-main head that passes via the ancestor exemption
When the gate renders its verdict
Then the message names `ANCESTOR` and `base..rev empty`

## MODIFIED Requirements

### Requirement: `check` returns (ok, foreign_or_error_lines)

The existing contract and the #845 red path are unchanged; the only new behavior is the
empty-`base..rev` ancestor pass inside the `merge-base != base` arm.

#### Scenario: foreign-commit failure output is unchanged

Given a genuine #845 foreign-commit leak
When the gate fails
Then the output names the foreign commit count and lists them, exactly as before
