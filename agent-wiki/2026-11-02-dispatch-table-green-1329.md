# Regenerate the dispatch-forms table so make check-dispatch-forms is green

The #1329 gate's merge chain (#1334 + #1337/#1338) landed while the generated `docs/BOTS.md`
dispatch table had drifted from the dispatchable workflows — `engine-build.yml` had gained a `model`
dispatch input (from the #1322 host-verify matrix work) that the checked-in table did not carry — so
`make check-dispatch-forms` went RED on main and failed `ci-unit`'s
`tests/test_dispatch_forms.py` and `tests/test_issue_bot_manual_pick.py` at every main-tip run
(measured at `4cbb2ad4`, `793ac1dc`, and the #1334 merge commit `e9b136df`).

Fix (merged as #1347): regenerate the dispatch table (`make check-dispatch-forms report`) and splice
the exact generated rows between the `<!-- dispatch-forms:begin -->` / `<!-- dispatch-forms:end -->`
markers — the `engine-build.yml` row gains its `model` input. This change-note records that fix.

Verified on the merged head:
- `scripts/check_dispatch_forms.py check` → OK, 23 dispatchable workflows, table matches;
- `pytest tests/test_dispatch_forms.py tests/test_issue_bot_manual_pick.py` → 34 passed;
- `scripts/check_docs.py check` → rc=0; `scripts/issue_bot_gates.py check` → OK.
