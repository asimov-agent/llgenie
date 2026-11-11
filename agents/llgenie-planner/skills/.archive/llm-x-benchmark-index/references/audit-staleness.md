# Auditing whether a reported t/s figure is stale or under-reported

When the user suspects a model's headline t/s "should be higher", the question
is not "is the README stale" — it is "does the pipeline even look for a higher
figure". Audit in this order; each step is cheap and rules out a whole class.

1. **Prove the README is in sync with the store first.** Run the repo's own
   validator (`scripts/validate.py --only readme` / `make validate`). If it
   passes ("README.md matches the generator output", N/N models), the render
   path is NOT the problem — a stale or hand-edited README cannot get through.
   Do not re-derive the README by hand; trust the generator check.
2. **Find the max figure actually ingested for that engine x model.** Scan the
   raw snapshots (`data/raw/*.json`) for the engine's entries for the model and
   take the max. This is the ceiling of what the pipeline knows. (See the
   walker pitfall in SKILL.md — a scan that returns 0 may be a bug, not an
   absence.)
3. **Check the SEARCH QUERIES — the decisive step.** Read `SEARCH_GROUPS` in
   `scripts/update_trending.py` AND the search prompts in the Makefile
   (`_search-<backend>` targets). If no query names the model or the engine,
   every measurement arrived incidentally (a generic card query happened to
   surface a post). The pipeline cannot look for the model/engine, so it
   cannot notice a higher upstream figure, and cannot tell "no such
   measurement" from "we never looked". That is the real gap — file it as a
   coverage issue, not a render issue.
4. **Classify the top figure: estimate or measurement.** A headline that is the
   top of an estimated range ("~100-140 t/s (est, <engine> docs for <card>)")
   is NOT a measurement. The product takes the max of a range on purpose, and
   a genuinely measured figure is often LOWER than the estimate's top. Before
   telling the user "it's under-reported", read the source text for
   "(est)" / "~" / "docs".

## The coverage-vs-staleness rule

A fixed, hand-maintained keyword query list that never names the models/engines
the store ranks silently caps what the pipeline can know. The fix is to derive
the query set from the store (every trending model gets a query naming it) and
add a guard that makes a queryless top model loud — falsified (queryless ->
red), so the gap cannot hide. The repo's own search skill often documents that
engine-name-only queries do not index and to prefer model + token/VRAM queries
— yet the top models/engines may still have no query of their own; check, do
not assume.
