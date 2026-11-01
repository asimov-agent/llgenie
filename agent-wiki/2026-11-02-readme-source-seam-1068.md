# README-source seam for the trend order tests (issue #1068)

The order tests in `tests/test_registry_sync_trend.py` assert the order of the fitting
models. The product orders a store by the README **beside it**, but `registry_readme()`
resolved only `trending-README.md` beside the store, and the historical fixture's README
is named `README.md` — so the env route could not resolve it, and the tests ordered a
**dated** snapshot by **today's** vendored `data/trending-README.md`. A test's outcome
therefore changed whenever unrelated upstream data updated (the same non-hermetic class
as #1059/#1016).

This change adds an injectable README-source seam (behaviour-neutral): `readme_path` /
`readme_text` threaded through `tier_tables → card_tier → tier_rank → card_order →
trend_list → recommend → offer`, default `None` = the current vendored path (production
byte-identical). The historical fixture now injects its OWN `README.md`, so the order
tests are hermetic again.

Acceptance (the honest-oracle check): the test's oracle parses README **text** (the
tier-local `### Up to N GB` ranking) and, when forced to the global `readme_order`, goes
RED — proving it discriminates and is not self-referential / not `mp.card_order`. A
live-path control shows the same live store with identical row order before vs after
(the `None` default is behaviour-neutral).

Split out of #935 per one-PR-one-concern — #935 is the #669 admission/order/quant
change; this seam is orthogonal.