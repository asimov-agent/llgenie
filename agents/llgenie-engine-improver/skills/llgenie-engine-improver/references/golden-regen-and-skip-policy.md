# skip/xfail policy and golden regeneration

The tree FORBIDS skip/xfail: `AGENTS.md` — "A skipped test means a broken prerequisite is being
masked … never leave a skip"; `pytest.ini`/conftest turn any `xfail`/`skip` into a FAILURE. A plan
saying "xfail until the fix lands" is not executable here.

## When a code change moves product output

Its committed golden can only go green by REGENERATING. Regenerating before a dependent fix lands
BAKES the known defect into the expectation — a golden recording wrong behaviour that the next lane
then "fixes" by regenerating again.

Rules:
- Do NOT regenerate to green when the regen would encode a known hole.
- Do NOT xfail. The code change is a RED pending PR until the dependent fix lands; then regenerate
  ONCE with both fixes.
- Split the independently-green parts (a gate, a real-data regression test) into their own clean PR
  and carry the golden-coupled part with the dependent fix.

## The green-able honest interim is a CANARY test, not a skip

When the regen is permitted but the dependent fix has not landed, add a test that asserts the defect
is PRESENT (e.g. `n > 0` ternary rows on plain `llama.cpp`) whose failure message says "delete this
canary + the PR-body paragraph when the fix lands". It passes now, REDS the moment the routing lands,
and is not a skip/xfail.

## When a regen IS permitted

When the PR body documents the known-defect rows by name (the tracking issue + the correct-routing
dependency), the regen is permitted — a golden describing current behaviour that says which rows are
known-broken is honest; silence is not.

Before splitting, confirm WHICH rows the change moves: main's fixture + your fix reds exactly the
affected cases. A broad diff is the signal to force the regen, and the amount (e.g. 77 of 83) tells
you the change is golden-coupled, not a local test edit.
