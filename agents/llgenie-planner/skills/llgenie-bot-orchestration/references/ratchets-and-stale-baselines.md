# Ratchets and stale baselines (the #1053 class, applied to any recorded count)

A ratchet records a count and refuses growth. Its baseline is a **measurement at one tree state**, so it goes stale the moment the branch rebases onto a newer `main` — exactly like the census pointer (#1053).

## Distinguish an ADDED root from a GRANDFATHERED one

Before telling an author to fix their files, check whether the violating files are theirs:

```
gh api repos/<o>/<r>/compare/<main>...<head> --jq '[.files[]|select(.filename=="tests/<f>")]|length'   # 0 == untouched
gh api repos/<o>/<r>/contents/tests/<f>?ref=<main> --jq .size                                              # present on main?
```

Worked example (#953, `feat/import-roots-guard`): the log named `test_agent_nerve.py`, `test_ci_scope.py`, `test_trend_pick.py`, `test_network_marker.py` as carrying roots. **All four were untouched by the PR and present on main.** The PR's 89 test edits were almost all *removals* of import boilerplate; its only additions were the allowed `conftest.py` seam, the guard's own test, and the baseline.

## What "may only shrink" really forbids

- Forbidden: raising the baseline to cover roots **the PR adds** — that hides the exact growth the ratchet exists to stop.
- **Legitimate: recording roots that were already on `main`** (grandfathering). The ratchet then locks in today's debt and refuses future growth, which is its purpose.
- If the author wants the number to actually shrink, the remaining migrations are a **separate issue** — do not fold them into the guard PR.

## Rule

A ratchet PR whose baseline was measured before a rebase will fail on its own head with a delta that is **main's**, not the PR's. Re-record against the rebased head with evidence naming the untouched files, and check `git diff --numstat` on the touched files: if the PR's edits are mostly deletions, it is reducing the count, not raising it.

## One count baseline reds every branch at once — two reds are one defect class

A count-not-set baseline (`<n> recorded`) refuses growth from *any* branch, so several unrelated PRs that each add one
root red the same gate with different deltas (`bare: 53 vs 52`, `bare: 54 vs 52`) on the same day. Do not file them as
separate defects or attribute either to "a rebase": the fix is at each branch's own new site (make the added root
conform to the baseline pattern so the count returns to ≤ the recorded number), and the baseline itself is not raised.
Group them as one gate, one class, N sites.

## A red that coincides with a boardwide queue is still the gate's — read the log tail

When the whole board is queued on one long job (`linux / unit` at 40–60 min), it is tempting to write every red off as
"the contended dwell wall". The log decides it: a leg that ran its full suite to `3319 passed … in 838.21s` and *then*
red `[import-roots] bare: … — the migration may only shrink this count` plus `make[1]: *** [Makefile:<n>:
check-import-roots] Error 1` is a **content** failure, not the wall — the tests passed and a later gate in the same
`ci-unit` target failed. Always tail the failing job's log for the terminal `Error`/`FAILED` line and the gate that
emitted it before naming a cause; a boardwide queue is a hypothesis about the board, never an attribution for one PR.
