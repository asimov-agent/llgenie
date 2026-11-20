# Proposal: ci-scope-base-ref-behavior

## Why

Issue #857: the base-ref fallback of the `scope` job's "classify the diff" step used to be pinned by
a syntax grep (`assert "${EVENT_BASE_REF:-main}" in body`). That pin reds on any *correct* rewrite of
the step while never proving the behaviour the step exists to have. The tree has since been rewritten
(`BASE="${{ github.base_ref }}"` + an explicit `if [ -z "$BASE" ]` fallback that logs why), which
removed the grep pin — but no behavioural test replaced it. Today nothing executes the fallback: an
edit that silently drops the `if` block or the log line would keep every test green while the
classifier quietly diffs against the empty string and classifies nothing (the failure mode #824 was
filed for).

## What Changes

- Add execution-based tests to `tests/test_ci_scope.py` that **run** the step's `run:` body under
  bash with `make` and `git` stubbed to record their argv:
  - **resolution**: with `github.base_ref` empty (a `workflow_dispatch`-shaped event), the ref handed
    to `make ci-scope` is `BASE=origin/main`;
  - **visibility**: the run prints why it fell back (`No github.base_ref for event …`);
  - **normal path**: with a real `base_ref`, the step uses `origin/<ref>` and prints no fallback line.
- Negative controls (planted variants of the same body): fallback removed ⇒ the recorded ref is
  `origin/` not `origin/main`; fallback log removed ⇒ the visibility assertion goes red. The pinned
  properties must fail for the right reason.
- No edit to `scope.yml`: the behaviour already exists; this lane only pins it behaviourally.

## Impact

- Affected specs: `ci-scope-workflow-reporting` (ADDED: behavioural base-ref pinning)
- Affected code: `tests/test_ci_scope.py` only.
