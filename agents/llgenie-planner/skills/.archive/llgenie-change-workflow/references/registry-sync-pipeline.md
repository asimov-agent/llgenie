# The registry-sync family (vendored data → derived tables → review → implementation)

Asked "does the registry sync work / why did nothing get implemented?", the answer is almost always
that the legs are SEPARATE and only the first two are bots. Nobody implements the new contracts
inside the sync; the sync writes data, the review writes a work item, `issue-bot` writes code.

## The four legs, in order

1. **`registry-sync.yml`** (weekly Mon 05:19 UTC + `workflow_dispatch`; job `sync`) — the data leg.
   Never merges, never touches engines or code.
   - `make sync-registry` — fetch upstream `data/models.json` + `data/trending-README.md` +
     `data/model_contract.json`, validate the store against that vendored contract, write only when changed.
   - `make sync-quant-catalog` — live HF, read-only: the quant/class table. The ONE leg that needs network.
   - `make render-trend-list-matrix` — rewrites `tests/fixtures/trend-list-matrix.json`: one row per
     `(arch, vram, ram)` case, each row naming the model plus the FASTEST inference server that fits
     that card (or the reason the model cannot be offered). This is what `llgenie --matrix` prints.
   - `make render-engine-skill-gap` — rewrites `data/engine-skill-gap.json`: per-engine shipped /
     known-unsupported status and the models no engine can serve.
   - then `changed?` → test image → `check-registry`, `check-quant-catalog`, `engine-skill-gap`
     report, `skills-validate ALLOW_NEW_ENGINES=1`, `test-unit` → `sync-change-issue` (ONE issue,
     `always()`, keyed by `generated_utc`) → `spawn-engine-skill-issues` (one tracking issue per NEW
     unskilled engine) → push `chore/registry-sync` + open/update its PR.
2. **`registry-sync-review.yml`** (hourly at `:55`) — the reviewer, not an implementer. Runs only when
   the `chore/registry-sync` PR is OPEN and every check is green (`action=skip` otherwise). Its
   deterministic brief (`make registry-review-brief` → `registry-review-in.md`) checks, per card, that
   the trend list is non-empty and each row's server is the fastest of its rank class; the Hermes leg
   (`make registry-sync-review` → `registry-review.md`) judges, and
   `make registry-review-publish` files ONE issue labelled `agent:implement`, keyed by the store's
   `generated_utc` (so a re-run updates instead of duplicating).
3. **`issue-bot.yml`** — the implementation leg: picks the oldest `agent:implement` issue and opens a
   PR (new engine skill + image, ranking fix, etc.). This is where a "new contract" becomes code.
4. **`ci-unit` → `make check-engine-skill-gap`** — the ratchet: the sync PR stays red until every newly
   listed engine ships a skill or has a dated entry in `data/unsupported-engines.json`. That is why a
   sync PR can be green on data and still not land.

`make sync-change-issue` / `registry-change-report` report what changed even when a gate is red; the
issue is the durable record, so read it before re-deriving anything.

## Verify the committed state without mutating the checkout

These are read-only and answer "are the artifacts consistent?" in seconds — run them in the user's
checkout, no worktree needed:

```bash
make check-trend-list-matrix      # matrix() vs tests/fixtures/trend-list-matrix.json (prints case count)
make check-registry              # contract + README order + additive-only (check-registry-keys)
make check-engine-skill-gap      # per-engine status vs skills + dated decisions
python3 -c 'import json;[print(f, json.load(open(f)).get("generated_utc")) for f in
 ["data/models.json","data/engine-skill-gap.json","tests/fixtures/trend-list-matrix.json"]]'
```

All four carrying the SAME `generated_utc` is the proof that the last sync regenerated every derived
artifact in step; differing stamps mean a render step was skipped.

## Reading a live sync run

`--log` is only served for a COMPLETED run (an in-progress run exits non-zero with no content). Track
progress through the step list instead:

```bash
gh run view <id> --repo asimov-agent/llgenie --json status,conclusion \
  --jq '.status+" "+(.conclusion//"")'
gh run view <id> --repo asimov-agent/llgenie --json jobs \
  --jq '.jobs[]|select(.name=="sync")|.steps[]|"\(.number) \(.status) \(.conclusion//"") \(.name)"'
```

Step 8 (`Build test image`) running at all means step 7 computed `changed=1` — a real upstream delta,
not a no-op sync. Step 9 is the gates plus the full `test-unit`, and it is long: a run parked there for
20-40 minutes is normal, not stuck.

## When the run is red: split it into FAMILIES first

A red sync run carries tens of failures in 2-4 families, not tens of bugs. Split before reading any
traceback (`--log` is served only once the run completed):

```bash
gh run view <id> --repo asimov-agent/llgenie --log > /tmp/rs.log
grep -E "FAILED tests/" /tmp/rs.log | sed 's/.*Z //' | awk -F'::' '{print $1}' | sort | uniq -c
grep -E "[0-9]+ failed, [0-9]+ passed" /tmp/rs.log | tail -1
```

- **`test_engine_skill_gap.py` (3 tests), or `check-engine-skill-gap` naming engines** — the store
  lists engines with no skill and no dated decision. Those tests inject a fake engine into the REAL
  committed registry and then assert the gate PASSES, so they cannot be green while any engine is
  unresolved. That is the ratchet firing one step too early: the job reds before
  `spawn-engine-skill-issues`, so the work items it would have filed never exist.
- **`test_trending_quant_catalog.py` (2 tests) naming a model or an engine** — the regenerated catalog
  has a gap (a servable model with no entry, or an offered `(model, engine)` with no cell). It is the
  generator, not the fixture: re-run `make sync-quant-catalog` and read the table before editing tests.
- **`test_pick_full_registry.py::test_pick_matrix_real_quant_links_exist`** — a catalog plan links a
  file that answers 401 (a gated Hub repo). Fix the generator to mark the repo gated; never teach a test
  to accept an unresolvable link.
- **`test_pick_matrix_arch_perms.py` (the whole param grid)** — a stub model id now ALSO exists
  upstream, so the pick resolves it through the regenerated catalog and the cell's `use_format` stops
  being `gguf` (a whole-repo snapshot plan becomes `safetensors` / `mlx-safetensors`). The assertion
  names neither model nor engine — print the offending cell instead:

```bash
docker run --rm -v "$PWD:/repo" -w /repo llgenie/test:latest python -c "
import sys; sys.path[:0]=['scripts','tests']
import model_engine_pick as mp, test_pick_matrix_arch_perms as t
mp._tree=lambda repo,revision='main': t._trees().get(repo,[])
mp.engine_ids=lambda: t.ENGINE_IDS
for row in mp.matrix(t._mkreg(),24,64,'cuda')['permutations']:
    for c in row['engines']:
        if c['use_format']!='gguf': print(row['model']['id'], c['engine']['id'], c['use_format'], (c.get('plan') or {}).get('repo'))
"
```

Fix the FIXTURE (an id upstream cannot list, or `LLGENIE_QUANT_CATALOG='0'` to disable the table inside
that file), never the golden.

## Reproduce the chain in a worktree — the ORDER is load-bearing

```bash
git worktree add ../llgenie-wt/registry-diag origin/main
cd ../llgenie-wt/registry-diag
make sync-registry && make sync-quant-catalog \
  && make render-trend-list-matrix && make render-engine-skill-gap
make engine-skill-gap      # prints `UNRESOLVED: <engine> ...` — that count is the ratchet's work
```

Every render reads the catalog, so rendering the matrix BEFORE the catalog (or changing the catalog
afterwards) leaves `matrix()` and the committed fixture out of step and invents one
`test_trend_list_matches_the_committed_matrix[...]` failure per case — a real-looking regression that a
second render removes. Re-run `render-trend-list-matrix` and `render-engine-skill-gap` after ANY catalog
change.

`sync-quant-catalog` and `render-trend-list-matrix` are network-bound: ~5-6 minutes each, silent until
they end. Run them as `terminal(background=true, notify=true)`; a foreground call is cut off in about 7
minutes whatever `timeout=` says.

Run the suspect files against the test image — CI-identical, ~2 minutes, no suite discovery:

```bash
docker run --rm -v "$PWD:/repo" -w /repo llgenie/test:latest \
  python -m pytest tests/test_pick_matrix_arch_perms.py tests/test_engine_skill_gap.py \
                    tests/test_trend_list_matrix.py tests/test_trending_quant_catalog.py -q
```

That batch is one file short of CI's (add `test_pick_full_registry.py` when you need the CLI / link
cases). Compare FAMILIES with the CI log, not raw counts: fewer local failures is expected, not proof
that CI was wrong.

## A failed gate step SKIPS the remediation steps

`State what changed in ONE issue` carries `always() && steps.diff.outputs.changed`, so it runs on a red
run; `Spawn one tracking issue per NEW unskilled engine` and `Open / update the sync PR` carry only
`if: steps.diff.outputs.changed`, so a red step 9 skips BOTH. The deadlock follows: the store that needs
a dozen engine decisions is exactly the store whose engine issues never get filed. Before concluding the
pipeline has no remediation, check which of steps 10-12 actually RAN — and when touching that workflow,
give every remediation step `always() &&` plus its own success guard inside the recipe.
