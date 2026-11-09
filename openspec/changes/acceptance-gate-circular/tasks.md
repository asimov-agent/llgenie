# acceptance-gate-circular — Tasks

Issue: [#2094](https://github.com/asimov-agent/llgenie/issues/2094)

- [x] 1. `scripts/check_pr_acceptance.py`: `_requires_own_gate_verdict()` detects a criterion that names
      the acceptance gate's own footprint (`check-pr-acceptance`, `check-pr-acceptance-form`,
      `ci-verdict`, `ci-scope-decision`, or the `guard job` / `judge job`), and `acceptance_verdict`
      classifies it `gate-circular` — a distinct, NON-blocking finding with a message naming the loop —
      instead of `acceptance-unchecked`. `render()` labels it `[gate-circular]`. Proved at the fixing
      head: `tests/test_check_pr_acceptance.py` 51/51 pass.
- [x] 2. `scripts/issue_body.py`: the `_criteria` docstring documents the authoring rule — a criterion
      must be provable by a run or command it does not itself gate.
- [x] 3. `docs/BOTS.md`: the `check-pr-acceptance` states paragraph gains the `gate-circular`      non-red state.
- [x] 4. `tests/test_check_pr_acceptance.py`: classification, close-not-red-once-peers-proven, render
      label, negative controls (ordinary unchecked stays red; a product "guard" is never trapped), the
      `## Not covered` escape still wins, and the live CLI exits zero on a gate-circular close.
      Verified: 51/51 module tests pass, `make lint`, `make check-wiring`, `make check-docs` green at
      the fixing head.
