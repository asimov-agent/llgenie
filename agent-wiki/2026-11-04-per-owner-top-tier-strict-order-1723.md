# Per-owner high+lower top-tier pick is strictly size-descending (#1723)

A behavioural fix to `scripts/llgenie_serve.py::discover_top_tier`: the per-provider high+lower
selection emitted a provider's picks in discovery order, so near-identical sizes (a 32-byte tier
boundary — e.g. `ccore [4482402848, 4482402816]`) could surface as a "lower" quant or smaller-before-
larger, failing `assert sizes == sorted(sizes, reverse=True)` in
`tests/test_top_tier_acceptance.py` (the `linux / top-tier (run)` main gate, issue #1713).

The fix keeps the gate's semantics (the assertion is NOT weakened): each owner (the org before the
first `/`, which is what the acceptance test groups by) is one bucket across all its repos; its
picks are emitted strictly descending by `size_bytes`, the next (lower) pick is taken only when it is
`>= ~25%` smaller, near-identical best-fits within an owner collapse to the single largest,
`candidate_files` sorts by exact bytes (not the float `size_gb`), and probes are cached per
`(owner, filename)` so refill passes never re-probe.

Verified: new hermetic `tests/test_1723_top_tier_owner_pick.py` reproduces the 32-byte-tier case and
asserts no ascending picks / no near-identical double-pick, plus the preserved high→lower pair; the
full discover suite is green (project venv). The main post-push `top-tier (run)` matrix green at the
merge tip is the real acceptance (the PR-head `(none)` gate cannot prove it), per issue #1713.
