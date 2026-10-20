# Every target is declared `.PHONY` — and the guard that keeps it that way

Issue #392. OpenSpec change: `phony-targets`.

## What was wrong

`make` decides to run a recipe by looking for a file with the target's name. A target that produces no
such file must be `.PHONY`, and the check for that was the hand-written `.PHONY:` block plus hope:
176 targets, 154 declared, **22 undeclared**, and nothing compared the two. A file named after a target
(a left-over scratch file, a checkout on a case-insensitive filesystem) makes the target print
`make: '<target>' is up to date.` and run nothing — a green run that verified nothing.

```
$ touch test-env && make test-env
make: 'test-env' is up to date.        # no recipe ran
```

## What changed

- The 22 targets from the issue joined the `.PHONY:` block, plus `generate-requirements-dev-venv`
  (`tools/Makefile`) — found by the new rule on its first real run, which is the rule proving itself.
- `scripts/check_wiring.py` parses the `.PHONY:` blocks (continuations included) and fails on any
  target that is neither declared nor recorded. A target that really writes a file of its own name is
  exempt only via a dated `not_phony` entry in `tests/fixtures/host-only-wiring.json` — refused without
  a reason, and reported stale once the target is declared phony or disappears.
- `tests/test_wiring.py` pins the fault with real `make` (a file shadows the target, nothing runs) and
  the fix (the recipe runs), plus the decision path and the real tree.
- `make wiring-report` prints declared / recorded / undeclared counts; README documents the rule.

## Verification

- `make check-wiring` — 184 targets, 184 declared, 0 undeclared.
- `make wiring-report` — same counts, no `NOT .PHONY` line.
- `make test-unit`, `make check-docs`, `make lint`, `make check-workflows`,
  `make openspec-validate NAME=phony-targets`.
