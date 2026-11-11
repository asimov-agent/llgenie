# Data contracts + CI pipeline shape (trending-local-llms class)

Depth that is needed only when building/refreshing the index repo, not on every
X search. This is the operating shape the user converged on after several
iterations — follow it rather than re-deriving.

## Three data formats, each with its own contract

Do NOT collapse these into one format. Mixing them up (treating raw search
data as the aggregated store, or the snapshots as the store) was the recurring
error this class had.

| File | Content | Contract (JSON Schema) | Role |
|---|---|---|---|
| `data/raw/<backend>-<UTC>.json` | per-search result `{backend, generated_utc, models[]}` | `data/search_contract.json` | Firecrawl search output; validated BEFORE aggregation |
| `data/models.json` | aggregated store (all backends merged) | `data/model_contract.json` | the single source of truth the README is generated from |
| `data/snapshots/trending-<UTC>.json` | full copy of the store | none (copy) | ONLY the no-removal baseline for the validator |

- **Snapshots are just the no-removal baseline.** They let `check_no_removal`
  prove a model was never dropped from the README list, the models.json list,
  or the aggregated snapshot data. Do not think of them as data to aggregate
  from.
- **Wire the raw→store mapping explicitly.** `resolve_model_mapping` maps each
  raw model to an existing store position by priority **id across ALL models →
  name → hf** (each case-insensitive). CRITICAL: the priority must be checked
  across the whole store per key, not per-model — a per-model loop lets an early
  model's name match beat a later model's id match.

## Firecrawl is the X fetch engine

the user wants Firecrawl used for the lightbrd searches because a raw
`urllib`/`curl` fetch of lightbrd gets blocked (HTTP 403 / challenge). Wire:

- Repo secret `FIRECRAWL_API_KEY`; add `FIRECRAWL_API_KEY` to the workflow env
  next to `NOUS_API_KEY`.
- `fetch_lightbrd` uses the Firecrawl scrape API when the key is set:
  `POST https://api.firecrawl.dev/v1/scrape` with `Authorization: Bearer <key>`
  and body `{"url": "https://lightbrd.com/search?f=tweets&q=<urlencoded>",
  "formats": ["markdown"]}`; fall back to urllib only when no key.
- `make correct-raw`/`make fix` may need the key in env too.

## Makefile is the single source of truth for every stage

The user insists CI and local runs use the exact same commands (so the pipeline
is testable locally first). Do not inline Hermes/script commands in YAML that
diverge from a local run. Targets that exist: `setup`, `search-nvidia`,
`search-metal`, `search-cpu`, `search-general`, `search`, `merge`, `fix`,
`correct-raw`, `validate`, `validate-data`, `validate-schema`,
`validate-search`, `validate-readme`, `validate-mapped`, `test`, `refresh`.

- **Every public `make X` is a Docker wrapper over a `_`-prefixed host recipe.**
  The repo is bind-mounted at `/workspace`; the image (`trending-local-llms:
  latest`) bakes in Python deps + the Hermes CLI. `make docker-build` once,
  then run any public target — it needs Docker up and the image built, and
  passes `NOUS_API_KEY`/`FIRECRAWL_API_KEY` through `-e` from the shell env.
  The `_`-prefixed recipes are the actual host commands; the public names just
  wrap them in `docker run`. So a local test of the pipeline == `make
  docker-build && make validate && make test` (and the search/fix/refresh
  targets additionally need the two keys exported in the shell).
- **The search/fix/refresh targets fail at the auth boundary (HTTP 401 from
  the Nous portal) when `NOUS_API_KEY` is not exported in the shell** — the
  docker plumbing runs fine, then the Hermes call 401s. Export the key in the
  shell (and optionally `~/.bashrc` + `~/.hermes/.env`) before running them;
  the keyless failure is a setup gap, not a broken target.
- `validate.py` supports `--only <comma-list>` (groups: removal, data, schema,
  search, mapping, readme) so each Makefile stage runs a confirmable subset.

## CI pipeline shape (validation vs fix)

- **refresh-bot**: scheduled + manual dispatch, OWNER-ONLY for manual
  dispatch (guard: `github.actor == github.repository_owner`). Runs the
  searches → merge → validate → opens a PR only if data changed. Never
  auto-merges.
- **qa-validate**: VALIDATION ONLY. Runs `make validate` + the granular
  `validate-*` + `make test` against the PR/branch. It must NOT refresh data,
  run Hermes, merge, or create PRs.
- **fix-bot**: triggered automatically when qa-validate fails (workflow_run) +
  manual dispatch. Runs `make fix` (self-correct raw → Hermes → merge →
  validate) then the search/mapped validation, commits + pushes to the same PR
  branch, up to 3 rounds. Never auto-merges.

## Self-correction of failing raw snapshots

`scripts/self_correct_raw.py` fills a raw snapshot's missing required fields
FROM THE DATA IT HAS (id slug from name, full_name, license `Unknown` only when
absent, params, vram_min from vram_tier, backends from the engine registry,
dates from the snapshot). Fields that genuinely cannot be derived (hf,
source_post) are FLAGGED and the job exits non-zero so a re-search happens.
NEVER fabricate t/s.

## Duplicate detection: key on the measurement identity, not the raw row

- Model-level: no duplicate model by `id` OR `name`.
- Engine-level: dedup/merge on the **measurement identity `(engine, tps,
  normalized_gpu_size)`**, where `normalized_gpu_size` collapses hardware
  wording to a canonical token (RTX card model, `<N>GB` VRAM size, or
  platform like `apple`/`cpu`). The same measurement reported by two different
  X posts with slightly different hardware text (e.g. `"RTX 8GB GPU"` vs
  `"8 GB GPU (MoE, ~3B active/token)"`) is ONE row — keep the newer date.
  A different GPU card or a different t/s is a legitimate distinct figure and
  is KEPT.
- Keying on the raw `(engine, date, hardware, quant)` string FAILS this: the
  wording difference makes the same figure look like two rows, so the same
  model+engine+GPU+VRAM gets counted twice. A raw index keyed only on
  `(engine, date)` drops valid same-date multi-hardware results (e.g. RTX 4070
  @ 60-91 vs RTX 3060 @ ~50 on the same day) — so neither the raw string key
  nor the bare `(engine, date)` key is right; the normalized-GPU-identity key
  is.
- `merge_engines` must key on the same measurement identity, AND `normalize_model`
  must dedup a brand-new model's own engine list too (dedup only in
  `merge_engines` leaves a new model's in-snapshot duplicates untouched).

## Validate the README is generated, not hand-edited

`check_readme_generated` re-renders the README from the current store via
`render_readme()` and diffs against disk, ignoring only the `> Last generated:`
timestamp line. A hand-edited or stale README fails. This is a stronger check
than just "every model appears" — it proves the README came from `make merge`.

## Unit tests for the mapping/merge edge cases

Keep `tests/test_mapping.py` covering the cases that were wrong: id/name/hf
mapping, case-insensitive, exact-id-beats-name (cross-store priority),
brand-new stay-new, same-date-different-hardware retention, truly-identical
overwrite, never-drop, idempotent merge, self-correct fills + flags. Run with
`make test`. A `(engine,date)` merge bug was caught only because the test
asserted same-date rows are both kept — keep that assertion.

## Add an end-to-end integration test (raw -> models.json -> README)

Unit tests of the helpers (mapping, merge, validators) do NOT prove the chain
works together. Add `tests/test_ingest_render.py` that runs the FULL path:
write a raw snapshot to a temp `RAW_DIR`, call `ingest_raw_snapshots`, assert
the per-engine t/s landed in the right model in `models.json` (new engine added,
same-identity overwritten, different-date kept as a new row, brand-new model
added, existing never removed), then call `render_readme` and assert the
per-engine t/s appears in the most-loved + backend tables. This catches wiring
bugs (e.g. a merge key that drops same-date-different-hardware rows, or a
render that never surfaces a newly-ingested engine) that isolated unit tests
miss. Wire it into `make test` alongside the other test files so CI runs it.

## Prove the mapping with fixture pairs (incoming JSON -> expected JSON)

The user wants the raw->models.json mapping verified against REAL JSON fixture
files, not just inline dicts. Keep `tests/fixtures/` pairs: `raw_search.json`
-> `expected_models.json`, `raw_duplicates.json` -> `expected_duplicates.json`.
A `test_fixture_mapping.py` loads both, runs the real ingest, and asserts:
(a) the output EXACTLY equals the expected fixture; (b) every MANDATORY +
OPTIONAL field from `model_contract.json` is present/non-empty on every model,
engine, and engagement object; (c) the store validates against the contract
schema. Generate the expected fixture by running the actual code path (not by
hand) so "expected is true" is grounded. A duplicate-collapse fixture
(`raw_duplicates.json` -> one engine row each) proves the dedup key works on
the exact rows that regressed. Wire the file into `_test`, `_validate-search`,
`_validate-mapped` so CI runs it.

## Test ALL validators directly (pass, edge, AND failure paths)

New test files are only valuable if CI runs them. Wire EVERY test file into
`make test` (and have `qa-validate`, `refresh-bot`, `fix-bot` all call it),
else a new file stays local-only and CI silently stops covering it.

- **Directly unit-test validators against temp fixtures, not the live store.**
  Monkeypatch the validator module globals (`README`, `RAW_DIR`, `ROOT`,
  `CONTRACT`, `SEARCH_CONTRACT`, `SNAPSHOT_DIR`) to temp files/dirs so each
  check runs its real fail/pass paths in isolation, then restore. Assert a
  concrete `FAILURES` string, not just "no failures".
- **Happy-path-only coverage misses real bugs and hides unreachable branches.**
  A direct test found `check_model_fields` crashing with `.get()` on a string
  `formats` row (fixed with `continue`). Also confirmed an unreachable guard
  (raw->store "id collision didn't map") because id-first mapping always maps by
  id — test the actual id-first behavior, not the unreachable failure.
- **Duplicate-model test must vary the other key.** To exercise duplicate-*id*
  alone, append a model with the same id but a different name, else both
  duplicate-id and duplicate-name fire and the single-FAILURES assertion fails.
- **Contract/format change requires updating the tests in the same change.**
  Keep the shape in one per-file fixture helper so a format change is a
  one-place edit that ripples to assertions; CI `make test` goes red otherwise.

## Pitfalls that cost time in this class

- **`patch` tool mangles Python f-strings with `{...}`** — when a patch keeps
  failing syntax, stop and use `execute_code` with a raw `.replace()` + `ast.parse`.
  This happened repeatedly with `{len(rows)}` corrupted to `{len(len(...)}`.
- **JSON gets pretty-printed after a regenerate writes it** — re-read before
  later string patches; match the current indent.
- **A schema enforcement loop finds real data bugs.** Running `jsonschema`
  against every model/java engine exposed duplicate engine rows and a stale
  snapshot missing `vram_min`. Add the schema check early; let it find the
  mess instead of probing manually.
- **`vram_min` (least required VRAM) is community-reported from X, not an HF
  field.** Hugging Face exposes no VRAM metadata — only file sizes via
  `?blobs=true` (the smallest usable quant approximates min VRAM). Do not
  invent a VRAM number; source it from the measurement posts.
- **A `--only` filter makes large validators runnable per stage.** Refactor the
  checks into a registry (`add(label, group, fn)`) so `make validate-X` can run
  a subset — useful when the full run is slow or you want to isolate one failure.
- **Squash to one atomic commit + force-push when the user asks to clean a
  branch.** 40 incremental commits ahead of `master` become one commit via
  `git reset --soft master && git commit -F msg`, then
  `git push --force-with-lease origin <feature>`. Amend follow-up doc fixes
  into it (`commit --amend --no-edit`) rather than stacking a second commit.
  Verify `git rev-list --count master..<feature> == 1` and remote == local
  before/after.
- **Killing a backgrounded docker-wrapped make target does NOT stop the work.**
  `process_manage kill` on the wrapper shell leaves the `docker run` container
  and the inner Hermes process alive (the searches are long — minutes each).
  To actually stop a search, `docker kill <container>` AND `pkill -f 'make
  _search-<backend>'` / the inner hermes `-z` process; verify with `docker ps`
  and `pgrep -af 'make _search'`. Run the four searches in the background with
  `notify=true` and wait on each, not a single foreground timeout that kills
  the whole loop mid-run.
- **Docker-wrapped make targets write ROOT-owned files into the bind-mounted
  repo.** The container runs as root, so `data/raw/*.json` (and any other
  output it writes) land owned by `root:root`. That breaks `git stash -u`,
  `git checkout`, and `git pull` with `Permission denied: failed to remove
  data/raw/...` — git cannot delete a root-owned file as your user. Before
  switching branches, remove the container-written dirs with `sudo rm -rf
  data/raw/` (and any other root-owned output), not by stashing them.
- **A `git stash push -u` that fails partway leaves a partial stash AND the
  tracked mods unstaged.** When the untracked root-owned files block the stash,
  the tracked changes (README.md, models.json, requirements.txt) stay modified
  and a broken stash entry is created. Don't retry the stash — reset the
  tracked artifacts with `git checkout -- README.md data/models.json
  requirements.txt`, `git stash drop`, then switch branches. The data is
  regenerable; only the scripts are the deliverable.
