# `check-pr-base` docs state its three-verdict contract, not the pre-#2023 all-or-nothing rule (issue #2299)

The `make check-pr-base` block in `docs/BOTS.md` taught the pre-#2023 contract: a PR's
merge-base with the base ref "must equal `PR_BASE` itself", and a foreign commit makes the gate
fail. That was the all-or-nothing reading issue #2016's review pass flagged: a merely-stale-but-clean
branch (merge-base IS a `main` ancestor, every carry the branch's own) is NOT a #845 foreign leak —
the gate already exits 0 and names it STALE, so a reader who follows the old text "fixes" it with a
rebase-race that #2023 already resolved.

## What changed

`docs/BOTS.md`'s `make check-pr-base` block now names the three verdicts `scripts/check_pr_base.py`
actually renders since #2023: **OK** (exit 0 — cut from the base, or the #1867/#1906..#1909
ancestor/push-to-main exemption), **STALE** (exit 0 — behind main but clean, issue #2016 resolved by
#2023, a rebase clears it not a #845 leak), and **FAILED** (exit 1 — a genuine #845 foreign-branch
leak, or a refused measure, issue #1734/1527). `docs/ARCHITECTURE.md`'s Structural-gates row names
the STALE-but-clean exit-0 verdict on its `check_pr_base.py` entry. The pre-#2023 "must equal PR_BASE
itself" sentence is gone (`grep "must equal .*PR_BASE itself" docs/BOTS.md` → no hit).

Measured at the source: `scripts/check_pr_base.py::_verdict` returns `clean`/`stale`/`foreign`/`refused`;
`render()` maps those to OK (exit 0, cut or ancestor), STALE (exit 0, behind-but-clean, #2016) and
FAILED (exit 1, foreign #845 leak or refusal). The code half of #2299 (the OWN-ref counting) landed as
#2183; this PR records the contract in the docs only.

Gates green on this branch: `make check-docs`, `make check-architecture-census`,
`python3 -m scripts.lint_linefeeds`, `python3 -m pytest tests/test_check_pr_base.py`.
