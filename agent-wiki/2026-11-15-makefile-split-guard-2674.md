# Makefile split guard: duplicate-target detector + line budget (issue #2674, PR #2694)

## What was verified

#800's split landed (six `mk/*.mk` files), but its two guard halves were unimplemented —
issue #2674. Both landed in `scripts/check_wiring.py` (the gate already runs in `ci-unit`,
so no new wiring):

- **Duplicate detector** (`_declarations`): declared target names collected per file over
  `Makefile` + `mk/*.mk` in include order (reuses the include-aware `_makefile_list`); a name
  declared in more than one file is a finding naming the target AND both files — because GNU
  make keeps the FIRST recipe and silently drops the other (the #460 class). `tools/Makefile`
  is out of scope: it is a separate graph reached via `make -C tools`.
- **Line budget** (`load_budgets` / `_budget_findings`): the committed source of truth is
  `tests/fixtures/makefile-line-budgets.json` — each `mk/*.mk` ceiling 600 (measured max at
  landing: `mk/engines.mk` 499), top `Makefile` ceiling 977 recorded as a RATCHET with
  baseline 977: it may decrease freely; a raise above the baseline needs a contiguous chain
  of dated entries (`from`/`to`/`reason`/`decided`) in `ratchet_raisings` — the repo's
  exemption-with-reason pattern. A missing budget file while `mk/` files exist is itself a
  finding: the enforcement cannot be silently deleted.
- **Tests** (`tests/test_wiring.py`, six new): planted duplicate across two includes → rc=1
  naming both files; planted over-budget `mk/` file → rc=1 naming file + lines + ceiling;
  budget file deleted → rc=1 (the other-direction control); ratchet raise without a dated
  chain → red, and the dated chain clears it; real-tree tests derive every number from the
  committed source (no baked constants).

## Key decisions

- `mk_default` 600 also covers a NEW `mk/` file that has no committed entry — a split can add
  a file without editing the budget, and it still lands under a ceiling.
- The budget file is validated the way `load_exceptions` validates decisions: every recorded
  ceiling carries `reason` + `decided`.
- Scratch trees without `mk/` files stay budget-vacant (the missing-budget finding only fires
  when the tree actually carries the split), keeping the pre-split fixture tests green.

## Current status

`make check-wiring` green (371 declared targets, 0 duplicates, 8 files measured — max
`mk/engines.mk` 499 vs ceiling 600). Full `make test-unit` green locally at the fix head;
PR #2694 drives the full CI green against `main`.
