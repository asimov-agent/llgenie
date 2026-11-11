---
name: llm-x-benchmark-index
description: "Use when building a local-LLM trend index from X engagement."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [llm, x, twitter, lightbrd, benchmark, inference-engine, github-actions, trending]
    related_skills: [x-content-research, xurl, grounded-citations]
---

# Local-LLM benchmark index from X engagement

This governs the recurring class of task: an open-weight-LLM "trending" index
(a README + data store) ranked by real X engagement and measured tokens/sec
per inference engine, with a CI pipeline that keeps it fresh. The reference
implementation is the `trending-local-llms` repo.

## When to Use

Use when the user asks to build or keep fresh a **trending/benchmark index of
local LLMs** — a rank of open-weight models people actually run — driven by
real X posts (mirrored through lightbrd.com) and per-engine tokens/sec, usually
automated by GitHub Actions. Triggers: "trending llms", "X posts benchmark",
"per-engine t/s", "auto-maintain the README from X", "8-48 GB GPU models".

## Operating rules (user's standing preferences)

1. **X source is `lightbrd.com` ONLY.** Do not reach for other mirrors or Web
   Search for the trend signal. x.com itself is bot-walled; Nitter pulls are
   dead; plain search engines return secondary roundups, not the posts.
2. **Ship from a feature branch via a PR, and recognise WHEN the repo's own
   pipeline will merge it without you.** The user's standing rule is "never
   merge without approval — stop at the reviewable PR", but the reference repo
   (`trending-local-llms`) can override that for you: its `qa-validate.yml` has
   an `auto-merge` job that squash-merges ANY green non-draft same-repo PR
   (roughly once `validate` ~10 min + `live-smoke` are green) and deletes the
   branch, whatever reviews say. There is NO label/review/draft gate — draft is
   the one state the repo forbids — so "hold it for a human" is achievable
   only by raising it to the user EARLY, right after the PR opens, before
   `validate` turns green (ask with `clarify`, they may well choose to let the
   pipeline land it). Do not wait until it merges to mention it, and do not
   'trust' that a same-repo green PR will sit open. Separate hard rule: give
   the feature/worktree branch the issue number from the start
   (`ci/<issue>-<slug>`), else `make pr-closure` refuses to let the PR close
   the issue and you must close the PR and re-open on a renamed branch.
   Create a detailed issue first (scope, acceptance criteria, non-goals,
   how-to-verify) and reference it from the PR.
3. **Every entry carries its links.** Each model row links to its Hugging Face
   page; each engine measurement links to the engine's repo (or the specific
   draft/model repo that produced the figure). No bare engine or model names.
4. **Rank by interactions first (likes/loves + comments), then by t/s.** t/s is
   always shown **per engine** with hardware + quant, never a bare number.
5. **Backends are equal categories** — NVIDIA/CUDA, Apple/Metal, CPU each render
   as a first-class table; a model measured on multiple backends appears under
   each. Do not demote CPU/Metal to a "secondary" section.
6. **Never fabricate or wipe data.** Every figure traces to a real X post.
   When the source is unreachable, preserve last-known data and degrade
   gracefully (exit 0 with a warning) — never blank the store. Do not pad a
   sparse backend (e.g. CPU) with invented numbers.
7. **The README is generated, not hand-edited.** Change the JSON store or the
   template, then regenerate. Point contributors at the store. Validate the
   README is actually generator-produced (re-render from the store and diff,
   ignoring the `> Last generated:` stamp) — a hand-edited/stale README must
   fail CI.
8. **The Makefile is the single source of truth for every stage.** CI runs the
   same targets you run locally (`make merge`, `make validate`, `make fix`, the
   granular `validate-data/schema/search/readme/mapped`, `make test`). Do not
   inline diverging Hermes/script commands in YAML that a local run can't
   reproduce — the user tests locally first and expects CI == local. A
   `--only <group>` filter on the validator lets each Makefile stage run a
   confirmable subset.
9. **Snapshot every refresh + enforce no-removal in CI.** Each refresh writes a
   timestamped snapshot (`data/snapshots/trending-<UTC>.json`, full store) so
   history proves no model was ever removed and the README can be rebuilt from
   any point. A `scripts/validate.py` QA step (run on PRs/pushes) enforces:
   no model removed vs the previous snapshot; every model has name/full_name/HF
   link/license/params/VRAM + at least one engine measurement with engine name +
   t/s + repo link; each README backend table sorted by highest t/s descending;
   every store model present in the README. Existing models are retained and
   their t/s updated, never deleted.
10. **Validate no duplicate models AND no duplicate engine rows.** No duplicate
    model (by id or name). Dedup/merge engine rows on the **measurement
    identity `(engine, tps, normalized_gpu_size)`**, where `normalized_gpu_size`
    collapses hardware wording to a canonical token (RTX card model, `<N>GB`
    VRAM size, or platform like `apple`/`cpu`). The same measurement reported
    by two different X posts with slightly different hardware text (e.g.
    `"RTX 8GB GPU"` vs `"8 GB GPU (MoE, ~3B active/token)"`) is ONE row —
    keep the newer date. A different GPU card or a different t/s is a legit
    distinct measurement and must be KEPT. Keying on the raw `(engine, date,
    hardware, quant)` string fails this: the wording difference makes the same
    figure look like two rows. Apply the dedup in BOTH `merge_engines` (existing
    models) and `normalize_model` (a brand-new model's own engine list), or a
    new model ingests its duplicates untouched. Sort each model's engines
    newest-date-first so the README surfaces the latest trending t/s.
11. **Change a contract/format/requirement -> update the tests in the SAME
    change.** Any edit to `model_contract.json`, `search_contract.json`, the
    model/raw/snapshot format, the README template, or a validator rule must
    update the corresponding tests in the same commit so `make test` still
    passes. Keep the contract shape in one per-file fixture helper
    (`good_store()` / `store()` / `sample_store()` / a table-builder like
    `cuda_table()`) so a format change is a one-place edit that ripples to the
    assertions. CI runs `make test` on every pipeline, so a contract change
    without a test update goes red and must not be merged.
12. **Unit-test the VALIDATORS' failure and edge paths, not just happy paths,
    and make them independent of the live store.** A validator check deserves
    direct tests: feed a malformed store/snapshot and assert a real
    `FAILURES` entry, not just "no output". Monkeypatch the module globals
    (`README`, `RAW_DIR`, `ROOT`, `CONTRACT`) to temp files/dirs so tests run
    against fixtures, not the checked-in store. Doing this surfaces real bugs a
    happy-path run misses (e.g. calling `.get()` on a string format entry) and
    proves an unreachable guard branch. Run all test files from `make test` so
    every CI workflow picks them up.

13. **Keep the README tables minimal — no rank column, no redundant engine
    dump.** The user finds a `#` rank column noisy (row ORDER already implies
    rank: first row = highest engagement) and a full `Engines + t/s` column
    redundant (the CUDA/Metal columns already carry t/s + engine link +
    hardware). The "Most loved" table is exactly `Model | Full name | HF link |
    Why people love it | CUDA t/s (engine) | Metal t/s (engine) | VRAM` — no
    `#`, no `Engines + t/s`. The inference engine guide links the ENGINE NAME
    itself to its repo (`| [llama.cpp](url) | Backend | Best for |`), never a
    bare name plus a separate `Repo` column. Lock the shape with a regression
    test that renders the README and asserts the header has no `#`/no
    `Engines + t/s`/no `Repo` column and that every data row's column count
    matches the header (walk the table block and stop at the first non-`|`
    line so you don't bleed into the next table).

14. **Validate that every link RESOLVES, not just that it is present.** A
    presence-only check (non-empty, URI-shaped) lets a dead or wrong link sail
    through `make validate` green. Add a `check_links_resolve` that extracts
    every `https://` link from `data/models.json` (engine-registry URLs, model
    HF, per-format HF, `source_post`), `README.md`, and every `data/raw/*.json`
    search snapshot, then HEAD-checks each (GET fallback). Treat **404/410 and
    connection/DNS errors as FAILURES**; treat **403/429/5xx as indeterminate**
    (rate-limit / bot-block / server error — NOT a dead link) so CI doesn't
    flake when HF/GitHub rate-limits a HEAD request. Auto-fix a wrong engine
    URL when a known-good canonical repo exists (`KNOWN_ENGINE_URLS`), giving
    the fix-bot a concrete repair. This catches real bugs: a model HF id like
    `meta/Muse-Glimmer-30B` (404) vs the correct `meta-models/Muse-Glimmer-30B`.
15. **After testing, commit/push ONLY script changes — never the regenerated
    data artifacts.** `make merge`/`make requirements`/the searches dirty the
    working tree with `README.md`, `data/models.json`, `requirements.txt`, and
    new `data/raw/*.json` + `data/snapshots/*.json`. When the user says "don't
    commit/push new files, only if the scripts changed", check `git diff
    --name-only -- scripts/ tests/ Makefile .github/` — if that is empty, leave
    the data artifacts uncommitted (or revert them) and push nothing. The data
    is regenerable; the scripts are the actual deliverable.

## Procedure

1. **Create the issue first.** Detailed body: summary, goals, scope/definition
   table, checkbox acceptance criteria, non-goals, how-to-verify.
2. **Build the data store** (`data/models.json`): one row per model — id, name,
   full name, type (LLM/GGUF/ternary/etc), license, params, HF id, VRAM tier,
   backends[], engines[] (each: engine, tps, hardware, quant, date, source_post),
   engagement{likes, comments, views, last_7d_likes}, last_seen. A parallel
   `engines` map keys engine name -> backend, note, **url**.
3. **Write the regenerator script** (`scripts/update_trending.py`):
   - fetch lightbrd (per-backend search groups), merge engagement hits into the
     store, apply 7-day-trending / 30-day-retention sort (trending -> recent ->
     stale, stale models retained below with old measurements still shown),
     regenerate the README.
   - classify each engine measurement to a backend (NVIDIA/Metal/CPU) from
     engine name + hardware text; render three equal backend tables.
   - link engine names to repos and model rows to HF in every table + an
     engine-guide table with a Repo column.
   - `--no-fetch` path re-sorts/re-renders from the store (the reliable CI
     mode); `--dry-run` prints without writing.
4. **Data logic runs in the Hermes CLI; it is driven by GitHub Actions
   pipelines.** The accepted architecture is **three pipelines**:
   `refresh-bot.yml` (scheduled + owner-only manual trigger — `workflow_dispatch`
   fails unless `github.actor == github.repository_owner`; it refreshes via the
   Hermes CLI on the deepseek-v4-flash-0731 model through the Nous portal, token
   from `NOUS_PORTAL_API_TOKEN`, opens a PR **only when data is new/updated**),
   `qa-validate.yml` (**validation-only** — runs `make validate` + granular
   `validate-*` + `make test` on PRs/pushes; does NOT refresh, merge, or create
   PRs), and `fix-bot.yml` (auto on `qa-validate` failure — independently
   re-runs the Hermes fix, pushes to the same PR branch up to ~3 rounds). Do NOT
   turn one job into a silent scraper; the refresh is an explicit, owner-gated
   action whose data changes always surface as a reviewable PR.
5. **AGENTS.md + skill doc** encode the rules in this file (X-source-only,
   feature-branch gate, links-required, engagement-first, graceful degrade).
6. **Commit + push the feature branch, open the PR referencing the issue.**

## Pitfalls

- **lightbrd.com blocks plain `curl`/`urllib`** (HTTP 403 / challenge page).
   Fetch it with the **Firecrawl scrape API** using the repo secret
   `FIRECRAWL_API_KEY` (POST `api.firecrawl.dev/v1/scrape` with a `markdown`
   format) or Hermes' `web_extract`. Wire the key into every workflow env that
   runs a search/fix. Do NOT hardcode "lightbrd doesn't work" — the rendered
   path works.
- **Raw search data, the aggregated store, and snapshots are THREE formats,
   each with its own contract.** `data/raw/<backend>-<UTC>.json` (firecrawl
   per-search, contract `search_contract.json`), `data/models.json` (aggregated,
   contract `model_contract.json`), and `data/snapshots/*.json` (full-store
   copies used only as the no-removal baseline). Validate raw against its
   contract BEFORE aggregation; map each raw model to a store position by id →
   name → hf **across ALL models per key** (not per-model, or an early name
   match beats a later id match). See `references/data-contracts.md`.
- **`qa-validate` is VALIDATION ONLY; `refresh-bot` refreshes; `fix-bot`
   corrects.** The PR CI must not refresh data, run Hermes, merge, or create
   PRs — it only validates. The fix-bot self-corrects failing raw snapshots
   (`make correct-raw` fills missing fields from data it has, flags un-
   derivable ones, never fabricates t/s) then pushes until green.
- **Engine-name-only search queries return nothing.** e.g. `free%20token
   engine moE small gpu` yields "No items found" — FreeToken isn't an indexed
   X search term. Query by **model + token/VRAM qualifier** and treat engine
   names as optional signals (see `references/search-queries.md`).
- **CPU-only LLM benchmarks are genuinely sparse on X.** Most CPU signal lives
   in offload-capable engines (FreeToken, llama.cpp cpu) surfaced by the
   CUDA/engine queries. Keep the CPU table thin by nature — never pad it.
- **Peak t/s is often workload-specific.** e.g. Qwen3.8-27B ~381 tok/s is
   context-lookup/RAG reproduction, not general chat. Label engine + mode, and
   never present a peak as typical.
- **High-engagement roundup posts bundle many numbers from one post.**
   Attribute each figure to the original benchmarker, not the roundup author.
- **JSON stores get silently reformatted** (pretty-printed) after a regenerate
   writes them — re-read before later string patches and match the current
   brace/indent formatting.
- **Heredocs inside GitHub Action YAML `run:` blocks break YAML linting** when
   lines start at column 0. Build the PR body with a `mktemp` file + `printf`
   lines or keep all heredoc content indented inside the block scalar.
- **Verify obscure engine repos before wiring URLs** (e.g. TensorFold ->
   `ashhart/TensorFold`, DFlash2 -> `z-lab/dflash` were not guessable). Search
   to confirm; a wrong link is a correction the user chases.
- **Extract the max t/s with `re.findall`, not `re.search`.** `re.search` returns
   the FIRST number in a string, so "35.5-43.7" yields 35.5 and "67-71" yields
   67 — the wrong peak. Use `re.findall` + `max()`. Also, when scanning a whole
   markdown row for a sort key, the year (e.g. 2026) and date numbers get picked
   up as the max — filter to plausible t/s values (< 1000) or parse the t/s cell
   specifically.
- **Parse only the table block right after a heading when validating README
   tables.** Splitting on `\n# ` also matches `\n## `, so a backend section
   bleeds into the engine-guide table below it. Walk lines from the heading and
   stop at the first non-`|` line, skipping blank lines between the heading and
   the table — otherwise the validator counts rows from the wrong table.
- **The `patch` tool mangles f-strings with `{...}` braces in Python AND
   corrupts YAML keys.** It repeatedly corrupted `{len(rows)}` into
   `{len(len(rows)}`, added stray `|"`, over-indented blocks, and turned
   `timeout-minutes` into `timeout-min-minutes` and `gather-data.md` into
   `gather-data.md.md`. When a patch on a Python file keeps failing syntax, or
   a YAML key comes out misspelled, stop patching and fix with `execute_code`
   doing a raw string `replace` + `ast.parse`/`yaml.safe_load` verification, or
   `sed -i` for an exact single-key replacement — reliable where the fuzzy
   patch tool is not. Always re-read the line after a YAML key patch to confirm
   the key name survived.
- **The raw->store "id collision that didn't map" branch is unreachable** —
   `resolve_model_mapping` prioritises id across ALL models first, so a raw id
   matching an existing id always maps by id and never reaches the "new"/
   collision branch. Write the test to assert the id-first mapping behavior
   (no spurious collision), not the unreachable failure.
- **A duplicate-model test must vary the other key too.** To exercise the
   duplicate-*id* path alone, append a model with the same id but a different
   name; else check_no_duplicates fires BOTH duplicate-id and duplicate-name,
   failing the "exactly one FAILURES entry" assertion.
- **The refresh-bot fails in a predictable cascade; fix each stage in order.**
   When a scheduled refresh run goes red, the failure moves stage-by-stage as
   you fix it, and each has a distinct root cause: (1) the Hermes model
   truncates its reply mid-search (hits default `max_tokens`) → the incomplete
   Firecrawl action is dropped → `Error 2`; raise `max_tokens` AND
   `context_window` to the model card's ceiling (deepseek-v4-flash-0731: 1M
   input / 384K output) in the `_setup` recipe. (2) A hard `_validate` inside
   `make refresh` aborts before the "Commit + open PR" step, stranding new data
   with no PR for qa-validate/fix-bot to repair — make validation stages SOFT
   (log + report, still exit 0) so data always lands as a PR. (3) `_merge`
   crashes with `KeyError` on a raw model missing contract-required derived
   fields (`full_name`, `license`, `params`, `vram_min`, `backends`, ...) —
   normalize new models AT INGEST (mirror `self_correct_raw.py`'s fill rules)
   so merge always yields a schema-conforming store, and read display fields
   via `.get()` in the renderer as a second defense. (4) The job hits the
   runner timeout because a 30-day search window re-scans the same old posts
   every daily run — narrow the window to 7 days and raise `timeout-minutes`.
   Diagnose each by reading the step that failed in `gh run view --log`; the
   commit/PR step being SKIPPED means a HARD stage (setup/search/merge) failed,
   not validation. Conversely, if the commit/+PR step RAN and pushed a branch
   but only `gh pr create` failed with `GraphQL: GitHub Actions is not
   permitted to create or approve pull requests`, it is the repo-level
   Actions-PR toggle (or a missing PAT), NOT a code/stage failure — confirm
   by checking the branch exists on the remote (`git ls-remote origin | grep
   <branch>`) while `gh pr list --head <branch>` is empty. Pull the failing
   job's step list (`gh run view <id> --json jobs`, walk the aggregate job's
   `steps[].conclusion`) before reading logs: the step that went red names the
   root cause faster than parsing `FAIL:` lines, which the negative-path
   validator tests emit on purpose (they are assertions passing, not the bug).
- **GitHub Actions' `GITHUB_TOKEN` cannot create PRs even with
   `pull-requests: write` unless the repo setting "Allow GitHub Actions to
   create and approve pull requests" is enabled.** The commit+push step
   succeeds and only `gh pr create` fails with `GraphQL: GitHub Actions is not
   permitted to create or approve pull requests`. This is a repo-level Settings
   toggle (or a PAT), NOT a workflow YAML bug — check the setting before editing
   the workflow.
- **A markdown table whose separator row has fewer dash-groups than the
  header is BROKEN and markdown-it refuses to parse it.** The most-loved
  header (7 cols) with a 6-col separator, or a backend header (6 cols) with a
  5-col separator, makes the whole table unparseable — yet a presence-only
  validator stays green. Force-check with a real parser: separator col count
  == header col count, every data row col count == header, and no empty cell.
  A `check_readme_tables_wellformed` that walks each table block and asserts
  these catches a renderer that emits a mismatched separator. When you find
  this, fix the RENDERER's separator string (one dash-group per column), not
  the validator.
- **A legacy monotonic engagement counter must be RESET, not preserved, when**
   a model has no post-granularity signal.** If `last_7d_likes` was a cumulative
   counter that only ever grew (pre-`seen_posts`), a plain re-sort/merge that
   keeps the stored value lets a stale 681/540/520 dominate the trending rank
   forever, burying genuinely-trending models (real counts of 1-6). When a
   model has no `seen_posts`, set `last_7d_likes` to 0 so the rank reflects
   real 7-day engagement; real counts come from the post list once the refresh
   data lands. The opposite instinct — "never zero real data" — is wrong here
   because the stored counter is NOT a 7-day count.
- **Prove the raw->models.json mapping with fixture pairs, not just inline
   dicts.** The user wants "incoming data and expected data" as real JSON
   files in `tests/fixtures/` (e.g. `raw_search.json` -> `expected_models.json`,
   `raw_duplicates.json` -> `expected_duplicates.json`). Load both, run the
   real ingest, and assert (a) the output EXACTLY equals the expected fixture
   and (b) every MANDATORY + OPTIONAL field from `model_contract.json` is
   present/non-empty on every model, engine, and engagement object, and (c) the
   store validates against the contract schema. Generate the expected fixture
   by running the actual code path (not by hand), so "expected is true" is
   grounded. This catches a mapping change that breaks a field fill or leaves
   a duplicate.
- **The `patch` tool also mangles JSON contract files and Python blocks, not
   just f-strings/YAML.** It corrupted `additionalProperties` into
   `additionalPropertiesProperties`, over-indented a whole `normalize_model`
   block, and duplicated tokens in the Makefile. For a JSON contract, restore
   from git and re-apply the one semantic edit with a raw string `replace`
   (matching the file's compact brace style, not `json.dump` which reformats
   the whole file into a noisy diff). For Python, fix with `execute_code` raw
   `replace` + `ast.parse`. After any `write_file` rewrite, re-add the trailing
   newline — the newline-terminator validator fails otherwise.
- **A test that depends on a fix must ship in the SAME PR as the fix.** If you
   add a regression test that calls a function the fix introduces, a separate
   test-only PR goes red on master until the fix merges. Fold the test into the
   fix PR (per the change-contract-updates-tests rule) and prove it catches the
   bug by neutralizing the fix and confirming the test fails, then restoring it.

- **A recursive scan that returns zero may be a bug, not an absence.** When a
  walker over raw JSON returns "0 found", verify the walker is actually CALLED
  (a `def walk(...)` that is never invoked silently yields empty) and that the
  regex matches the data's shape — a blob-level scan misses structured entries
  where the engine name and the number live in different keys (e.g. `engine:
  Strata` with `tps: 140`). Trust a zero only after both checks.
- **A headline t/s that is the top of an estimated range is not a
  measurement.** "~100-140 t/s (est, <engine> docs for <card>)" — the product
  takes the max of a range on purpose, and a genuinely measured figure is often
  LOWER than the estimate's top. Before reporting under-reporting, read the
  source text for "(est)" / "~" / "docs".
- **A query set that never names the ranked models/engines caps coverage, not
  the render.** If no search query names the model or engine, every measurement
  is incidental; the pipeline cannot distinguish "no such measurement" from
  "we never looked". Audit the queries (`SEARCH_GROUPS` + the `_search-<backend>`
  prompts) before concluding the data is complete — see
  `references/audit-staleness.md`.
- **A new per-measurement data key is silently PRUNED, not stored.** The
  engine-measurement items (`model_contract.json` models[].engines[].items)
  carry `additionalProperties: false`, so any key the crawl writes on a
  measurement is dropped at ingest with a `[ingest] pruned` log line —
  model-level dimensions exist, but a single t/s figure cannot state the
  footprint of the run behind it. To add per-measurement data: widen the
  contract (OPTIONAL, additive-only), update `normalize_model` + tests so the
  key survives ingest, AND change the crawl ask (`DIM_ASK` in the Makefile and
  the gather-data skill) to request it per measurement — the field stays
  empty otherwise, because nothing asks for it.
- **The displayed "best" can be datacenter while the score is not.** The
  README best cell uses unscoped `best_measurement()` but the speed bonus uses
  `best_in_scope()` (≤48 GB consumer/workstation), so a "best" cell can show a
  multi-GB300 500+ t/s cluster figure beside a card's VRAM label. Any card-fit
  / VRAM view must gate the displayed best with the same `in_scope()`. Related
  drift: the datacenter denylist `_DATACENTER_HW` is a hand-maintained token
  tuple (`h100 ... gb300`); a part missing from it (e.g. `b300`) earns the
  speed bonus because `hardware_vram_gb()` returns None for a bare part name
  and only the tuple excludes it. Grep the tuple for new datacenter tokens
  before trusting a scope-gated number.
- **`vram_tier` is a free string, not an enum** — stored values drift (`48`,
  `8`, `CPU`, `16GB`, `512GB`), so ordering/grouping by it is unreliable.
  Never rewrite stored tiers (additive-only store); derive a canonical tier at
  render from footprint evidence.
- **A GitHub README cannot filter or sort tables.** Markdown has no script and
  README HTML is sanitized — a VRAM "filter" cannot be a dropdown. The honest
  markdown forms are an anchor-indexed set of tier tables (8/12/16/24/32/48 GB
  + unified-memory/RAM) and `<details>` collapsed by default. A real JS filter
  needs a generated GitHub Pages HTML page = a new artifact + make target +
  publish job + ARCHITECTURE row: a separate tracked phase, never bolted onto
  a README-only change.
- **An empty tier in a generated fit table is a gap, never "nothing fits".**
  A card-fit/VRAM table's whole point is "what can THIS card run", so a row
  that silently disappears reads as "no model fits" and buries model-finding.
  Render the empty tier with a named collection gap and add a **report-only
  coverage line to the validator that prints on every run** (e.g. "18/46
  models have card evidence; 0/213 carry per-run weight") so the store's own
  thinness is loud instead of hidden behind a green run — report-only, so the
  gap the pipeline is meant to close never fails the PR it is fixing. When a
  tier is thin, the search queries are usually the cause: a card query set
  that only names 3090/4090/5090 can never surface a 4060 Ti figure, so ADD
  owner-tier queries kept byte-identical across the prompt and the bounded
  smoke — see `references/card-fit-analysis.md`.
- **A card "fits" claim has exactly three honest sources:** a per-measurement
  footprint the post states (needs N GB), the card the figure was measured on
  (an UPPER bound — label "measured on N GB", never "needs N"), and a
  model-level weight that matches the measurement's quant. Anything else is a
  guess: put those rows in an "unplaced" note, never drop and never invent.
- **Analyze the live store with the project's own classifiers, then file.**
  Probe `data/models.json` by importing `scripts/update_trending.py` and
  running `hardware_vram_gb` / `in_scope` / `measurement_backend` /
  `best_measurement` / `_tps_core` over every measurement to build an evidence
  table (counts, gaps, mis-scoped rows); read the contract to see which keys
  each level allows; check what the crawl ask records before proposing a new
  field. The deliverable is a detailed issue (`gh issue create --label
  enhancement`), and — because this repo's rulebook says an issue that changes
  its behaviour must say so — ONE comment naming the exact sections that
  change and marking the AGENTS.md diff review-required. See
  `references/card-fit-analysis.md`.

## References

- `references/audit-staleness.md` — the ordered audit for "is this reported t/s
  stale or under-reported": prove README sync, find the ingested max, check the
  search queries (the decisive coverage step), classify estimate vs measurement.
- `references/card-fit-analysis.md` — deriving a VRAM card-fit view from the
  store and contract: the probe recipe (import `scripts/update_trending.py` and
  run its classifiers), the per-measurement-vs-model dimension split and
  contract pruning, footprint precedence for an honest "fits" claim, the
  ran-on/weights-only tier-placement ladder, honest gap rendering + a
  report-only coverage line, the owner-card query feedback loop (8–24 GB
  gaming-laptop low end), no-mock testing against the shipped store/README via
  a real-ingest env seam, scope-gate token drift, and the tier-table vs
  Pages-filter decision.
- `references/adding-a-backend.md` — the full checklist of places that must
  change together when adding a new backend (contract enums, search group,
  classifier, validator, engine registry, Makefile, README, tests) + the
  vendor-API-backend vs cross-vendor-engine design pattern.
- `references/search-queries.md` — verified per-backend lightbrd search-group
  queries and what each returns.
- `references/data-contracts.md` — the three-format data contract
  (raw → models → snapshots), search_contract vs model_contract JSON Schemas,
  Firecrawl fetch wiring, Makefile single-source-of-truth targets, validation-
  only vs fix-bot split, self-correction, measurement-identity dedup key,
  README-generated check, and the mapping edge-case test list.
