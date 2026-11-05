# Registry sync — llgenie FOLLOWS the producer's contract (never fights it)

Lesson from #1634 (2026-11-02; PR #1636).

## The mechanism

- llgenie **vendors** the producing repo's (`andyholst/trending-local-llms`) `data/models.json`, its
  README, and its `model_contract.json`/`MODEL_CONTRACT.md` byte-for-byte (#694/#699). The whole
  design is "the guard is upstream's definition of valid, not a guess" — `check_contract()` reads every
  rule from the vendored schema and must NOT restate them (`sync_registry.check_contract` docstring:
  "Every rule is READ from the schema, never restated here").
- When the producer intentionally changes its contract (e.g. #689 "normalized measurement store"
  promoted `supported_engines` to the only required per-row field and dropped per-row `engines`),
  llgenie is supposed to **re-vendor and follow** — a deliberate producer schema change is NOT a
  producer data bug, and re-adding the dropped field to the producing repo would fight the migration.

## Signs the guard (not the data) has gone stale

- A live-sync `ValueError` naming a field that is absent on **every** row of the producer's store
  (e.g. `models[0] (...) lacks 'engines'` at `validate()`:75-82) — while the producer contract had
  already dropped that field from per-row `required`. That is the guard hard-coding OLD contract keys.
- A parallel hard-coded restatement still *enforcing* a now-optional field even inside the
  schema-driven `check_contract()` — a re-vendored contract alone would not unblock it (its own
  docstring promises no restatements).
- The failing test is `test_the_vendored_contract_is_upstreams_and_the_store_satisfies_it` (byte-
  equal vendored==live + store satisfies it) → fix = re-vendor the contract files from the producer
  and drop the hard-coded restatements.

## The fix shape

1. `validate()`: require the producer's currently-required per-row field (`supported_engines`)
   instead of the dropped one (`engines`); type-check it is a list.
2. `check_contract()`: make the formerly-required field OPTIONAL — validate each entry only if
   present, against the schema's `items.required` (read from the schema, never restated).
3. Re-vendor `data/model_contract.json` (+ doc) byte-for-byte from the producer's current commit
   (`MODEL_CONTRACT.md` may already be identical).
4. Fix any test `_row`/`_store` helper fixture that modeled the OLD contract (missing the newly-
   required field) — a hermetic end-to-end `sync()` test will fail with `lacks <field>` on it.

## Verify

- Containerized (llgenie/test:latest, parent repo mounted for worktree git): the 3
  `test_check_contract_*` + `test_the_vendored_store_satisfies_the_vendored_contract` hermetic tests,
  plus the registry/trend/pick-matrix suites. Never bare-host pytest as evidence.
- Assert contract byte-equality (`data/model_contract.json` == live producer file) and that the
  committed store satisfies BOTH the committed and the LIVE contract.
- `make check-docs` change-note trio for a `scripts/` behavioural change: `agent-wiki/<stem>.md` +
  `docs/changes.d/<stem>.md` + `make changes-index`.

## Distinguish a deliberate producer change from a separate producer bug

- A producer schema change is deliberate when the contract DIFF itself renames/replaces a required
  field and the data follows it across all rows (don't fight it — follow).
- A producer **data-internal inconsistency is a separate TLL-lane producing-repo fix**, not llgenie's:
  e.g. #695 `models.json` order vs its own README "Most loved" order diverging (24 positions;
  clean at pre-#695) reds `test_live_upstream_registry_is_the_live_readme_list` + the `live_sync`
  rank tests EVEN AFTER the llgenie fix, because `sync()` enforces strict models-order == README-order.
  Route the producing-repo fix to the trending-local-llms (TLL) fleet; keep the llgenie-side fix as
  your PR and say so plainly on the issue. On #1634 the llgenie-side PR fixed only ONE of the four
  hf-live network tests (the contract test); the other three stayed red via the producer order class.
  Never call hf-live green until you have RUN the actual `-m network` tests (not just the hermetic
  half) and seen them pass. 1 passed / 1 failed / 2 errors = still red; the issue stays OPEN.

## The producer's normalized measurement store (#689) — a third field llgenie must follow

- After #689 the producing repo keeps **per-engine t/s measurements OUT of `models.json` rows**, in a
  committed `data/measurements.json` keyed by model id. `models.json` rows carry only engine NAMES
  (`supported_engines`); the README's "best engine" column renders FROM `measurements.json`.
- Therefore llgenie's `check_readme_matches` must **vendor and consult `measurements.json`**: validating
  the README engine against the model row alone falsely rejects a real engine (e.g. a model whose row
  lists one engine but whose README best is another that exists only in measurements). Thread it
  through `sync()` (fetch+vendor) and `check()` as a new parameter; keep the row-only path as proof the
  new path matters (one test asserts rejection without it, acceptance with it).
- Do NOT commit measurement engines back onto the PRODUCING repo's `models.json` rows — that fights
  #689. BUT DO **rehydrate** each row's `engines` in the **vendored** store at sync time: after
  normalising, merge the vendored `measurements.json` entries onto each row by engine name. Consumers
  (`rank_engines`, `model_engine_pick`, `check-registry-keys`) read t/s from `row["engines"]`, which is
  empty post-#689, so without rehydration they return `0.0` and the live rank/keys tests fail on
  `tps == 0`. Rehydration leaves the producer's committed shape untouched while giving llgenie's own
  consumers the denormalized rows they expect.

## Order divergence in the producing repo — the minimal fix, and the trap

- The producer's README "Most loved" table is **trend-ranked**, not models-order: it is
  `sort_models()` (band → 7-day score → posts → peak t/s), and `update_trending.py` regenerates
  `models.json` AND the README from that same sorted order. An order divergence means someone
  committed one side without the other.
- llgenie's `check_readme_matches` deliberately requires **exact array-order equality** (hermetic tests
  pin it). Do not weaken it to set-equality to let an inconsistent producer through — that teaches the
  gate to bless broken data and reds those tests.
- Fix the producing repo with a **pure JSON-array reorder**: load committed `models.json`, reorder
  `models[]` to the committed README "Most loved" order, keep every row and key byte-identical
  (verify: N line moves, identical id set, `--render-only` produces no README diff). Do NOT run
  `update_trending.py` to regenerate — it pulls a broad data refresh (measurements/posts churn, id-set
  delta) and buries the reorder in unrelated churn.

## Prove the combined fix without merging

The live network tests read upstream master, so they stay red until the producing PR merges. Proof you
CAN produce today: point the sync at the fix branch's raw files
(`https://raw.githubusercontent.com/<fork>/<repo>/<branch>/data/...`) and run `validate()` +
`check_readme_matches(data, readme, measurements)` + `check_contract()` + a full `sr.sync(...)` —
rc=0 over the fixed data is the end-to-end evidence, while stating plainly that live master is still
divergent and the issue stays OPEN until both PRs merge.

- **In-process pytest module-identity trap:** to run a real network test with `sr.UPSTREAM` patched to
the fix branch, patch the SAME module object pytest imports. `import sync_registry` (top-level) and
`import scripts.sync_registry` are two distinct module objects — patching `sr.UPSTREAM` on one leaves
the test reading live master from the other. Patch both `sys.modules['scripts.sync_registry']` and the
`scripts.sync_registry` attribute to the same object before `pytest.main([...])`.

## Reading the hf-live result honestly — setup errors vs data-direction assertions

- Re-run the `-m network` tests **per test** (`pytest.main([one_node])`) rather than one aggregate, so a
  test that previously ERRORED at fixture setup (on the contract/`engines` root) is distinguished from
  one that now RUNS PAST setup and fails a substantive assertion. ERROR→FAIL can mean your fix WORKED
  (it unblocked setup) and the remaining red is a producer-data claim — e.g. `rank_follows_the_given_vram_ram_and_arch`
  asserts live tps > a recorded pre-change snapshot; the high figures ARE present, but the card-fit top
  is producer-data direction. Name the class of each red (setup vs data-direction vs cache); never
  report "hf-live still red" without that distinction.
- `raw.githubusercontent.com/<repo>/<branch-ref>/...` is CDN-cached **per branch ref**: a fetch of a
  just-pushed fix branch can serve a STALE README/models pair and red an order check that a fresh
  fetch shows `order_equal=True`. If a branch-ref file fails an order/content check, re-verify each
  file with a fresh fetch and inspect `generated_utc` before diagnosing a code defect — do not chase a
  cache artifact, and do not "fix" code that a fresh fetch proves correct.
- A `sync()` default of a live URL for `measurements_src` makes HERMETIC `sync()` tests hit the network
  and fail on an unexpected `measurements.json` sibling. Default network sources to `None`; the CLI
  (`main`) and the `live_sync` network fixture pass the URL explicitly.
- `gh pr edit --body '-'` does NOT read stdin (it stores a one-char body); use `--body-file <file>` or
  `-F -` (with stdin) for multi-line PR bodies. `git push --force-with-lease=<ref>:<sha>` must use the
  ACTUAL current remote sha from `git ls-remote`, not the local prior head, or it rejects `stale info`.

## A gate that consults a sibling file must have that sibling COMMITTED

- `check()` reads the measurements store as `dest.with_name(VENDORED_MEASUREMENTS.name)` and `sync()`
  WRITES that sibling — but `data/measurements.json` was never added to the tree. A fresh clone has no
  `sync()` to have run, so the consult silently falls back to the row-only engine list and the exact
  false-reject the consult was written to cure comes back. Whenever you add "consult file X next to the
  store", check `git ls-tree HEAD -- data/X` — a write path in code is not an artifact in the tree.
- Fix shape: commit the producer's store as a sibling *in the same commit series* as the consult code
  (`git ls-tree` proves it), then re-prove the gate.

## Prove a consult is load-bearing with a two-variant driver, not one pass

- One green run proves nothing about a consult: a gate can accept the input for a different reason. The
  proof is the pair — run the gate on a fixture store+README **with** the sibling present and **without**
  it, and assert exit 0 then exit 1.
- `scripts/prove_measurements_consult.py` is that probe: it builds a tmp fixture from the real committed
  store, runs `check()` both ways, and prints `with-meas CHECK_RET 0 / without-meas CHECK_RET 1`. A
  `with-meas 0 / without-meas 0` pair means the sibling is decorative (see the fixture trap below);
  `assert 0 == 1` inside a regression test is the same signal.

## The fixture trap that hides a non-load-bearing consult

- A fixture model deep-copied from a real row carries the full row shape. `check_readme_matches` accepts
  a README best-engine if it appears in the row's inline `engines` **or** in `supported_engines` — so a
  copied row satisfies the check without the measurements sibling, and the "with/without" pair both
  return 0. Strip **both** `engines` (replace with one decoy entry) and `supported_engines` (narrow to
  the decoy) so the README's best engine exists ONLY in the sibling.
- A `check()` fixture also needs the **vendored contract sibling** next to `models.json` (else
  `check_contract` fails for a missing schema, not for your assertion) and a `readme-link-answers.json`
  snapshot recording the fixture's invented URLs as live (`{"links": {"<url>": "200"}}`) — otherwise
  `check()` runs the live link liveness probe against URLs that do not exist.

## Do not wholesale re-vendor llgenie's committed store — check-registry-keys is additive-only

- Re-syncing llgenie's committed `data/models.json` to the producer's #689 shape (moving per-row
  `engines` out to `measurements.json`) reds `make check-registry-keys` with hundreds of "losses":
  the additive-only gate reads the shape migration as deleted keys. Do NOT commit the re-vendored
  store as your data change. Keep the existing committed store and fix only the CODE (`check()`
  consulting `measurements.json`, sync rehydration) + tests — the store refresh should arrive through
  the normal producer-driven sync once the producer merges, not as a side effect of a contract PR.
- The gate's live re-scrape NOTES (engagement-counter drift) are non-fatal; only `LOSS` findings (and
  a non-note hard finding) return 1. Read the exact `return` condition before chasing note noise.
- `scripts/check_registry.py`'s CLI needs an explicit `--dest`; a bare positional `dest` does not work.

## Verify PR gates with the real scripts, not a log or body snapshot

- `check-pr-closing` / `check-pr-base` guard reds are disproven by RUNNING the actual scripts in the
  `llgenie/test:latest` container, wired exactly as CI does — not by reading a stale guard log or an
  earlier body snapshot. Write the LIVE body first (`gh pr view <n> --json body -q .body` to a file),
  then:
  `python3 scripts/check_pr_closing.py check --body-file /tmp/pr-body.md --head <branch> --base
  origin/main --rev HEAD` and `python3 scripts/check_pr_base.py check --base origin/main --rev HEAD`,
  each `echo <NAME>_RC=$?` so the exit code is the fact (a `gh` exit 0 can arm/print nothing).

## Known unrelated gate (don't chase it in a registry PR)

- `make check-docs` census sub-gate pins a `measured at <sha>` that may not be an ancestor of current
  `origin/main` (e.g. `bb11bb1f` after main advanced) — reddens every PR, docs-lane concern
  (#896/#1053/#1246). Confirm you did not touch `docs/ARCHITECTURE.md`, then route, don't fix.
