## Working a test/CI refactor in this tree (issue-class "real-call tests out of the gate")

When the change is about which tests run in `ci-unit` vs a dedicated network/probe pipeline:

- **Reuse the existing seam, never reinvent the selection.** Before writing any `pytest -m
  "<marker>"` step, grep the tree for that marker and a make target that already runs the marked set:
  the marker is likely ALREADY registered in `pytest.ini` (ci-unit deselects it with `-m "not
  <marker>"`) and a `test-unit-<marker>`-style seam already runs it through the repo's own discovery
  (`scripts/unit_tests.py run --marker <name>`, containerized). The lane that owns the unit gate owns
  the marker + deselect; you only consume the set. A bare `python3 -m pytest` in a workflow fails —
  the venv/image are provided by the `make ci-<job>`/`make test-*` target, not by the runner.
- **A routing decision is a claim until a test pins it.** When you decide which tests are owned by
  the network pipeline (real opens) versus hermetic, add a hermetic test that asserts the exact
  `@pytest.mark.<marker>` membership across the routed files (marked set == a named allowlist) and
  that no file outside it carries the mark. Then it cannot silently drift either direction (a
  hermetic test losing coverage, or a real one escaping the gate).
- **A host-scanner census is defeated by the model-dict pattern — the exact-equality pin is the
  net, not the scan.** A real Hub call like `mp.download(model, …)` or `mp.gguf_files(model["hf"])`
  carries NO literal `huggingface.co` on the line: the host is implied by the model dict's `hf` key.
  A literal-host grep undercounts (caught live twice on #1000), so rely on the membership pin that
  reds when the marked set != every mark actually in the file — it flags the test a host scan
  could not see. When a teammate's review adds a real mark your census didn't predict, verify the
  test is genuinely a real open, then enshrine it in the pin (do not argue your undercount).
- **A workflow's red must route somewhere; BOTH a roster row and a #349 exemption satisfy the gate.**
  `check_workflows.py` treats `covered (roster row) or exempt` identically — the dated, reasoned
  exemption file IS the routing (security-scan is the live exempted precedent; a red routing nowhere,
  no roster AND no exemption, is the defect). The CI lane owns the choice and can flip it once they
  read the gate's code — do not encode "roster over exempt" as law. Match their CURRENT ruling and
  pin it with a test: if exemption, the entry is dated, names the workflow by exact top-level `name:`,
  and its `reason` says WHY the red is acceptably-routed (the real-call-fake/scan class), like
  security-scan's. A first-time live pipeline can validly be exempted with a stated reason.
- **An owner's "another pipeline" split is two PRs, not one reshaped PR.** When the gate-mechanics
  refactor (#1000: marker + deselect + liveness make targets) and the standalone pipeline (#1002:
  the workflow file) are separated, keep #1001 to mechanics and deliver the workflow as its own
  stacked PR. A workflow that depends on the seam's make targets must STACK on the seam branch
  (cut the worktree from it, base the PR on `main` — the diff collapses once the seam merges), or
  the admission Flow-target check reds on targets the base main doesn't have yet. Give it the owner's
  trigger (`push: branches: [main]` = merge-to-main) plus nightly + dispatch, no `pull_request`.
- **Never run the full hermetic suite on a tree you are still editing.** A mid-run edit to a test
  file the suite will read produces an artifact `usage`/collection failure that looks like a real
  red. Settle the tree, start the suite, and do NOT edit it until it returns; run parallel work on
  a different worktree. If you edited mid-run, kill it and start clean rather than trust the result.
- **Removing a workflow job (or a whole workflow) is a tree-wide cascade, not a one-file edit.**
  Before deleting a job, grep the repo for the job's label AND the workflow's filename. Then reconcile
  every hit in the same change:  shape tests assert `jobs["<label>"]` directly (KeyError the moment it
  vanishes), publish-order/install tests pin the stage's matrix/`none`-row/steps, `run-failure-reactor.yml`
  may list the workflow's `name:` under `workflow_run.workflows` (`make check-workflows` reds with
  "watches a workflow that does not exist"), any test that reads the removed file FileNotFoundErrors, and the
  wiring layer has its own greppable surface: `tests/fixtures/host-only-wiring.json` must record a test the
gate no longer reaches as a host-only document, and any `WORKFLOWS = ("ci.yml", "pipeline.yml", …)`
  enumeration tuple (e.g. `test_pipeline_timeouts`) must drop the removed workflow. When the change kept
  a gate's derived data attached to the registry (a cell enabled / a tag-computation change), regenerate the
  committed tables with their make target (`make render-engine-skill-gap`, `make sync-quant-catalog`, which
  also syncs `tests/fixtures/`) rather than hand-editing — the gate asserts the committed file matches the
  generator. When the stage's behavior has a new owner (e.g. an engine install-test moved into the producer workflow's
  single build job), RE-POINT the tests at that owner's structure — never resurrect the removed labels.
  Distinguish change-caused reds (KeyError/FileNotFoundError on the removed label/file) from genuinely
  external ones. Do NOT label a red "pre-existing" on a hunch — prove it: run that exact test on a clean
  `git worktree add --detach <path> origin/main`; green-on-main + red-on-your-branch means it is YOUR
  regression, not a cancelled sweep or a data drift (both "obviously external" reds have turned out to be
  branch-caused this way — the fix is the cause, not a mangled shape test).
  - `tests/fixtures/host-only-wiring.json` has TWO sections: `documents` records a TEST FILE reached only
    by a CI-never-ran target; `targets` records a MAKE TARGET whose `##` help still claims CI coverage that
    a removed CI job no longer delivers. For the targets side, EITHER reword the help to drop the CI claim
    (the wiring test then accepts the host-only target) OR record it — do not leave a `##` line saying "CI
    engine stage" on a target ci-unit no longer runs.
  - A TARGET + SCRIPT left fully orphaned by the removal (nothing CI-runs calls it and no test references
    it) should be DELETED, not recorded as host-only — the wiring checker asks for deletion and a host-only
    entry for a dead path just papers the rot. Remove the target rule, its entry in the enumerated
    target-list line, any dangling comment mentioning it, and the script; `rg -l <name>` to confirm no
    workflow/test/fixture still references it before you push.
  - An ENABLED backend cell (flipping a variant off its `cpu` fallback) ripples the variant-want maps and
    row censuses AND the derived arch catalog across several test files in ONE change, not just the first
    that reds: the `<engine>-<arch>` variant wants in `test_engine_skills` AND `test_trend_pick`, the
    proven+exempt row census in `test_engine_gate_strict`, and the `arch: [...]` lists in
    `data/trending-quant-catalog.json` + its synced fixture (run `make sync-quant-catalog` after the data
    edit so the fixture matches). Grep the whole tree for the variant before you ship the enable. A DISABLED cell is
    the MIRROR: dropping a variant (e.g. `llama.cpp-prism` cuda off for #103) makes the committed quant
    catalog list an `arch` that `engine_ids()` no longer reports, so `test_every_model_and_engine_is_real`
    reds — refresh the catalog to the DISABLED-aware generator (`make sync-quant-catalog` regenerates
    `engine_ids()[eng]["variants"]`, so `check-quant-catalog` OK is the proof it is DATA-TRUTH not a
    weakened assertion), and edit BOTH `data/trending-quant-catalog.json` AND
    `tests/fixtures/trending-quant-catalog.json` (the exact-match fixture reds otherwise).
    The SAME disable ALSO re-picks the ENGINE in the trend-list matrix — a model whose best cuda engine
    was the disabled PrismML-fork falls back to `llama.cpp` at a much lower tps (the regen records it);
    that tps swing (e.g. 128→6, where a cpu variant would be 128 and faster) is an ORDERING decision
    (arch-match vs best-throughput), NOT an admission bug — file it as its own issue rather than
    revisiting the correct #103 disable inside the feature PR (keep the PR scoped to one concern).
- **Before blaming a code change for a `linux / unit` red, confirm the test is actually IN the gate — a
  direct `python3 -m pytest` run on a live/metal-only file is NOT the gate.** The hermetic unit suite's exact
  selection is `python3 scripts/unit_tests.py argv` (every `tests/test_*.py` minus the `tests/fixtures/unit-suite.json`
  `excluded` and `deselect` entries, minus network-marked). Live-GHCR published-image tests and native-Metal-only
  tests fail on a bare x86 host whether or not the gate runs them; when they are excluded/deselected from the suite
  they  never red `linux / unit`. Run/read the gate `argv` (and the job's actual status — an `in_progress` job is not a
  failure) before writing a regression; a branch that never dispatched the producer to publish its pins leaves the
  live published-image tests red for a reason no code change fixes.
- **A pty/subprocess test must set the SAME env var its code READS — a helper that forces one value while the
  process reads a different env (or the real host) is the flake, not the test's assert.** `mp.system_ram_gb()` reads
  `LLGENIE_SYSTEM_RAM_BYTES` (else the real `/proc/meminfo`), so a pty `_env` that only sets `LLAMA_RAM_BYTES` (a
  name the picker never reads) leaves the process machine-dependent: its row set then differs from the test's
  fixed-64 expectation by exactly the rows whose `system_ram_min` sits between the two, and the test reds (list count
  62-vs-63, reprompt range `enter 1-41` vs `enter 1-42`) without any product change. Pin the var the process actually
  reads in BOTH the harness env and the expectation recompute; when a pty test's count differs from its own `_offer`
  recompute by one row, the RAM/arch seam is the first suspect, not the list code.
- **A test that passes on clean main but reds on a rebased branch usually PINS A STATE MAIN MOVED PAST, not a
  regression in your change.** When you take over a branch rebased onto newer main, run the red test at the branch's
  PARENT before your own commits (a detached `git worktree add --detach <path> <parent-oid>`) to attribute: if it
  fails there too, the branch lineage pins an old expectation (e.g. a cell main enabled — `llama.cpp-prism` "cpu,
  disabled" when the cuda cell is now enabled). Update the expectation to the current enabled reality (the code is
  correct; the test carries stale pre-enable state), and the parametrized sibling rows must change in the same patch.
- **A tag/params change is whole-fleet, so defer the whole fleet — a registry gate that defers only
  params-changed engines reds on every tag.** Enabling a cell or touching a tag-computation source
  (e.g. `scripts/engine_image.py`) re-tags EVERY engine to a new, unpublished hash while leaving the
  params files untouched; a live `wait_published` / publish-order gate then fails across all of them at
  once. Fix the defer logic to treat a change to the tag-computation source like a params repin: defer
  defer every engine to its producer publish (and make the hermetic counterpart assert BOTH the stable-tag case
  and the re-tag case), rather than re-writing the live test to "expect" the missing tags.
- **A `linux / unit` job is COMPOSED: pytest THEN gate steps — a red is the FAILING STEP, not necessarily a
  test.** Read the job log: the pytest summary can be green (`15025 passed`) while a later `make` step in the
  same job reds it — `openspec-tasks-check` (an unchecked openspec task checkbox), `check-docs`, the census, or
  `check-secret-output`. Grep the log for the `N passed` line AND the failing step (`openspec-tasks] FAIL …`,
  `[issue-bot-gates] FAIL …`, `ci-unit Error 2`); never read "unit=failure" as "a test failed" without both.
  The `scope` check red is often the SAME `openspec-tasks-check` failure (the scope job runs it), so ONE
  checkbox fix greens `linux/openspec` + `scope` + the unit job together. Tick a task checkbox only for a task
  whose stated evidence you have — run the promised command first; `openspec-validate` checks the spec TEXT,
  `openspec-tasks-check` checks the BOXES (it fails on ANY unchecked box in a changed change), and
  `make openspec-tasks-check` locally (RC=0) is the pre-push proof. A ticked-but-false task is the exact class
  the gate exists to catch — leave a not-done task unchecked and name it.
  When the suite IS green at a head, re-tick that box in a **SEPARATE commit** whose message cites that
  green run id + `completed_at` — never in the same commit as the code/marker change. The tick's sha must
  be a fact about a green run at that head, not a hope attached to an untested push; a false tick has
  cost this fleet more than once. If the tick's commit message later cites a head where the test was RED
  (the fix landed AFTER the tick), do NOT `git commit --amend` that ANCESTOR to rewrite the citation —
  amending rewrites EVERY descendant sha, so the run id you cite becomes a dangling sha for a superseded
  head. Record the provenance in a PR COMMENT (the green run id + which subsets the old citation
  covered) instead; the state is already correct, only the citation needs correcting, and a comment
  carries it without a history rewrite. But note the chicken-and-egg: `ci-unit` runs `issue-bot-gates`→
  `openspec-tasks-check`, so an UNTICKED box keeps `linux/unit` RED — there is no green unit run at an
  un-ticked head to cite. So validate the box's claim with TARGETED pytest runs at the fixed head (the
  exact tests it promises, e.g. `-m network` → 2 passed), tick there, and the CI unit greens BECAUSE the
  suite is genuinely green — not because the box was unclicked; "unit green THEN tick" is unreachable. And note the PR head can be stale: a commit you made but never pushed
  leaves CI running the pre-fix code at the OLD sha (a check-runs query answering there is the tell) —
  after every commit, push, then `gh api repos/<upstream>/pulls/<n> --jq '.head.sha'` must equal the new
  commit before you read any verdict.
- **A local `make test-unit` red is NOT the CI gate — the same suite in CI can be fully green.** This tree has
  real-HF-call tests (`test_pick_full_registry::test_pick_matrix_real_quant_links_exist`) that are NOT
  network-marked (on main too — the #1000 class), so they fail on a host without Hub access while the CI pytest
  passes (`15025 passed`). Read the CI job's OWN `N passed`/`N failed` summary before treating a local unit red
  as a branch defect; only a CI-pytest failure that is NOT the unmarked real-call test is a real regression.
- **A new test file must reach `scripts/*` through the conftest seam, never its own `sys.path.insert` +
  bare import.** The import-roots ratchet (`scripts/check_import_roots.py ratchet`) reds a file that adds
  its own root with `bare: N+1 vs N` / `sys-path: M+1 vs M`; `tests/conftest.py` already puts `REPO_ROOT`
  on `sys.path`, so write `from scripts import model_engine_pick as mp` and drop `import sys` if it
  becomes unused. A branch cut before that convention writes the old style even when you only added a
  test to an existing file — the ratchet counts the whole merged tree, and the `+N` is usually the one
  NEW file on the branch (files already on main keep main's seam through the 3-way merge). Fix is
  editing the import lines, never a rebase: the PR is mergeable, this is a stale-base style artifact,
  not a conflict. Pre-check on the tree CI actually runs — `git merge-tree --write-tree origin/main
  <fork-ref>` → extract → `ratchet` (**not** `check`, which is the unfiltered report that reds on clean
  main) — and read the pytest summary separately from the gate step, because a `linux / unit` FAILURE can
  be `15046 passed` plus this ratchet `Error 1`.
- **A test whose verdict depends on LIVE upstream data is `@pytest.mark.network` — CLASSIFY it, do not
  pin a duplicate fixture.** `pytest.ini` defines the marker as "a test that calls the real Hub for real …
  EXCLUDED from ci-unit by `-m "not network"`"; a test that downloads the live registry (a `live_sync`
  fixture) or asserts on live upstream runs belongs in the network pipeline, not the hermetic gate. The
  fix is to ADD the marker (assertion unchanged); pinning a snapshot for the hermetic gate just duplicates
  what the live pipeline already runs for real. A test whose verdict moves when someone publishes a
  benchmark upstream is not a regression test. Prove the split: `pytest -m "not network"` deselects them
  and the rest pass; `pytest -m "network"` collects exactly them. And note **`scripts/unit_tests.py` defaults to `-m "not
  network"`**, so a bare `pytest <file>` WITHOUT `-m` EXECUTES the network-marked tests directly and can
  red on live upstream data — a reviewer's "control" that runs `pytest tests/<file>` with no `-m` is not
  running the gate, and its red may be live-data, not a branch defect; always state the `-m` mode you ran.
- **Thread a parameter across call-sites OUTPUT-NEUTRALLY — and quote the criterion before you move any
  expectation.** Making `fits`/`trend_list`/`rank_models` take `arch` must not reorder surviving rows:
  prove it with an A-vs-B run (`trend_list(reg,gb)` vs `trend_list(reg,gb,arch="cuda")`) — surviving rows
  keep identical order, only MEMBERSHIP changes (an Apple-only row drops = the authorised admission
  change). When a test's expectation then differs, decide by the criterion's own words, not preference:
  quote the sentence that authorises the change (e.g. "the card's list is the published tier-local
  ranking") before editing, and NEVER rewrite an assertion to match new output without it. An incomplete
  threading shows up as a product inconsistency (`rank_models` takes `arch` but drops it calling
  `trend_list` while `recommend` threads it) — fix the product call-site, then a broad regression run
  confirms no collateral. The matching TEST call-sites must thread the SAME value the product uses (`fits(…,
  arch=backend)` where `offer` passes `backend`), not a bare `fits` that counts every run.
- **A test's oracle must parse the SOURCE independently, never call the product's own function — and prove
  it discriminates.** An order/selection oracle that calls `mp.tier_tables()`/`mp.card_order` agrees with
  the code by construction (rubber stamp). Parse the README/generator output yourself, and prove it is not
  vacuous: force the OLD expectation (e.g. the global `readme_order`) and show the test goes RED — if it
  still passes, the oracle tests nothing.
- **Before calling a fit assertion a defect, quote WHICH run admits the model (`ran_on` ≤ card).** A "27B
  cannot fit 8 GB" assumption is false when the registry carries a genuine run on an 8 GB card (an RTX 4060
  8 GB, or a MoE/partial-offload build in `4GB VRAM + 32GB system RAM`); `card_evidence="run"` names the
  mechanism but not the row — list the admitting runs (`ran_on_gb` ≤ gb) and quote the hardware string
  before ruling a live-data assertion stale vs a product bug. The stale part is often the test's hardcoded
  absence, not the gate.
- **A branch-vs-main red is a DIFFERENCE, not a verdict — a sibling INVARIANT test decides which side is
  stale, never "main passes".** A behavior-changing PR (e.g. #669's measured-evidence admission) is
  SUPPOSED to differ from main; a same-fixture control showing main-pass/branch-fail proves the change
  happened, not that it is a bug. Before "fixing the product to match main," run the proposed change and
  watch the sibling invariant: the README's own tier table is the #669 admission contract, and
  `test_every_model_the_published_tier_table_places_is_admitted` ("every model its `Up to N GB` table
  places is admitted by `fits(model,N)`") REQUIRES a model the table PLACES to be admitted — so a test
  asserting that model's ABSENCE is the stale side. If making the red test pass (restoring main's
  `vram_min` admission) BREAKS the passing invariant test, the code is RIGHT and the TEST is stale: fix the
  assertion (quote the README placement / criterion that authorises the new expectation), not the product.
  Two tests that contradict (one asserts absence, one asserts admission) are resolved by the authority only
  one of them cites — the README/criterion. Never "fix the code to match main" when a passing invariant
  test proves the code correct; and revert any speculative product fix the moment an invariant test reds
  under it (the `weight > run_card` offload reject was tried, broke `test_every_model…`, and was reverted —
  the test, not the gate, was wrong). **When you correct a stale assertion, move the invariant it
  ACCIDENTALLY carried into its own hermetic (cached-fixture) test.** An `is None` for a model was also
  implicitly asserting "this model is too big for the card"; once the model is (correctly) admitted, keep
  the "a genuinely-too-big model is refused at 8 GB" check as a separate hermetic case rather than
  losing it with the rewrite — correcting the assertion must not delete the real check it was carrying.
- **One PR, one concern — an orthogonal refactor gets its own issue, never folded into the feature PR.**
  A #669 admission/order change must not also thread a multi-function README seam or fix an unrelated
  `rank_engines` variant-normalisation bug; those are real but folding them makes the feature PR
  unreviewable at the moment review matters and mixes unrelated failure modes. File them as separate
  issues with their own acceptance (the forced-old-order red proof, a regression test with the exact
  offending row) and keep the feature PR tight.
- **A stale committed derived fixture reds a mass of parametrized tests at once — regenerate, do not debug the
  product.** `tests/fixtures/trend-list-matrix.json` is DERIVED: after a branch's `trend_list`/registry change it
  is stale, and `test_trend_list_matrix::test_trend_list_matches_the_committed_matrix[...]` fails for many
  (arch, vram, ram) cases at once (e.g. 93, or 17 cuda cases when the arch-aware gate later altered `trend_list`).
  Fix with `make render-trend-list-matrix` then `make check-trend-list-matrix` green, and COMMIT the regenerated
  fixture — never hand-edit it, and never read the mass of matrix failures as a product bug. **Verify the regen's SCOPE before committing a large diff**: diff the old vs new fixture per-case — every changed case must be the TARGET arch (0 non-target rows moved), the admitted model SET unchanged (0 models added/removed), and each changed row the expected mechanism (quote 2–3 before/after). A big diff (e.g. 231+/231−) is legitimate when it is only the target rows re-picked; a diff that also moves a non-target arch row is unrelated drift — call it out, never sweep it in. Two operational
  traps: (1) the render (~37 s) plus the matrix test (~40–110 s) are SLOW — a single foreground command that runs
  stale-check + render + re-check exceeds a 180 s tool timeout MID-render, so the fixture is never written
  (`git status` empty) and it looks like the render produced no diff; run `make render-trend-list-matrix` ALONE
  with a generous timeout, then run the matrix test on its own; and (3) the render walks the live Hub PER MODEL
  (`trend_rows`→`_hub_json`) and 429s HARD on a cold cache — a default `HUB_CACHE_TTL=3600` re-throttles it into a
  timeout that never writes the fixture. Set `LLGENIE_HUB_CACHE_TTL=86400` (a day-long disk cache) so the prior runs'
  fetches persist and the render COMPLETES (`wrote 81 cases`), and run it in the background with notify when the Hub
  is cold. Only then fold the regenerated fixture in and re-run the matrix test. The regen's live-Hub dependency is
  itself the #1020/#1067 non-hermeticity — it hits the regen, not just the tests. (2) A CANCELLED/queued/superseded unit run never
  surfaces this — the stale-fixture reds appear only in a COMPLETED `linux/unit`, so a stream of cancelled unit
  runs at successive heads is NOT evidence the fixture matches; confirm with a local matrix run or a completed
  unit before declaring the derived tables green.
- **The project FORBIDS skip/xfail — an honest interim is a RED, not a marker — and a code change that moves
  product output makes its derived golden red.** `AGENTS.md` states "A skipped test means a broken prerequisite
  is being masked … never leave a skip", and `pytest.ini`/conftest turns any `xfail`/`skip` into a FAILURE, so a
  plan that says "xfail the test until the fix lands" is not executable in this tree (it does not exist as
  policy). When a fix intentionally changes a product output (e.g. the classifier default relabels 77 matrix
  cases), the committed golden can only go green by REGENERATING — and regenerating before a dependent fix
  lands BAKES the known defect into the expectation (a golden that records the wrong behaviour, which the next
  lane then "fixes" by regenerating again). The rule: do NOT regenerate to green when the regen would encode a
  known hole, and do NOT xfail; the code change is a RED pending PR until the dependent fix lands, then
  regenerate ONCE with both fixes. Split the independently-green parts (a gate, a real-data regression test)
  into their own clean PR and carry the golden-coupled part with the dependent fix. **The GREEN-able honest interim is a CANARY test, not a skip:** when the regen is permitted but the dependent fix has not landed, add a test that asserts the defect is PRESENT (e.g. `n > 0` ternary rows on plain `llama.cpp`) whose failure message says 'delete this canary + the PR-body paragraph when the fix lands' — it passes now, REDS the moment the routing lands, and is NOT a skip/xfail; and when the PR body documents the known-defect rows by name (the tracking issue + the correct-routing dependency), the REGEN IS PERMITTED — a golden describing current behaviour that says which rows are known-broken is honest, silence is not. Before splitting, confirm
  WHICH rows the change moves: main's fixture + your fix reds exactly the affected cases — a broad diff is the
  signal to force the regen, and the amount (e.g. 77 of 83) tells you the change is golden-coupled, not a local
  test edit.
- **A family of PRs from one lane can live on DIFFERENT remotes — verify each head via the PR's own
  `pulls/<n>.head.sha`, never `git ls-remote` of a branch name.** An engine-family PR opened from a fork
  (`andyholst/llgenie`) is pushed to that fork's branch; pushing the same branch name to the upstream
  (asimov-agent) either rejects or creates a second, unrelated STALE branch there, and the PR still reads the
  old head. After each push, `gh api repos/<upstream>/pulls/<n> --jq '.head.sha'` must equal the new commit —
  if it does not, the push went to the wrong remote (see the Step 3b fork-publish note). A commit you made
  but did NOT push leaves the PR at the old head while CI runs the stale code — after every commit push,
  then re-read the head; a stale head dimension is a process error, not a CI verdict.
- **A ci/pipeline/engine-job removal is not proven by the touched-files run — run the FULL `make test-unit` gate locally before it is called green.** The tree-wide blast (host-only-wiring documents/targets, a `.PHONY:`-parser corruption, the `trend-list-matrix`/`quant-catalog`/`engine-skill-gap` derived fixtures, row censuses) surfaces ONLY under the complete gate, not the subset of test files you edited; the first full run after a wide change turns up the wiring/matrix/census reds the touched-file run hid. The user wants the local gate actually EXECUTED (not reasoned about) before "green" is claimed — ~20 min / 14.8k tests, worth it.
- **A stale local `origin/main` misleads every base/env-dependent test, so `git fetch origin main` fresh before judging one.** The whole-fleet tag-source deferral fires against an old local main that lacks the tag-change, while CI's current main (which has it merged) sees no defer — a concrete published-image test can then pass locally and red in CI for a base-state difference, not a code bug. On a base-relative test (the deferral, `origin/main`-keyed fixtures, publish-order), re-fetch first; and when the live registry genuinely lacks the pinned tag, the gate stays red until the producer publishes it — no code change moves that, so say so instead of chasing it.
- **A break in a `.PHONY:` multi-line continuation is a TREE-WIDE "not declared .PHONY" red, not 150 missing entries.** Appending a new target as `… test-engine-install \\ ci-install-product` (a space after the continuation backslash) breaks the `\`-newline continuation, so make treats the next TAB-prefixed line as a recipe and only the FIRST `.PHONY:` line's targets parse — every other target suddenly reports "is not declared .PHONY" (28 parsed vs 150) and wiring/phony/issue-bot-gates tests red in a mass. Add the new name BEFORE the trailing `\` and keep the backslash the last char of the line; a huge "not declared .PHONY" list is a parser-corruption symptom, not each target needing an entry. A `make -n <target>` dry-run shows the resolved recipe and catches this before you push.
- **A new ci-install* / product-install stage that builds the repo's pinned python venv runs in the `$(ENGINE_TEST_RUN)` test container, NOT on the bare runner.** The hosted ubuntu runner carries only the distro python (3.12); `make venv-install`/create-venv needs the repo's 3.11, which lives in the `llgenie/test` CI image (pulled by `make test-env`). A product-only install that runs `venv-install`/`link`/`smoke` directly on the runner fails "Python 3.11 was not found" (exit 2) — wrap it in `$(ENGINE_TEST_RUN) sh -c '…'` (Darwin keeps the direct venv branch) like every other ci-install stage. This is why CI broke on a change that passed locally: the test container provides the python the bare host lacks.
- **`git add -A <paths…>` that includes an index-deleted path runs rc=128 and stages NOTHING, silently.**
  The follow-up `git commit` succeeds anyway with whatever was ALREADY staged, so the push can look right
  while your intended edits stay uncommitted. Stage files explicitly one at a time (`git add -- <file>`)
  and read `git status --porcelain` immediately before committing; after the push, `git show --stat HEAD`
  to confirm the intended files are really in the commit.
- **Run a new test to GREEN before you push it.** A pinning test whose assertion form is wrong reds
  at the moment you least want it (caught mid-write this way); run the file, fix the comparison,
  re-run to green, then commit.
- **A new `## ` make target must be documented or be deliberately internal.** Giving a target a
  `##` help line makes `check-docs` require it in docs/ (or a docs-exceptions entry). An internal
  seam carries no `##` line (the `engine-matrix-pushed` precedent); regenerate the dispatch table
  from the generator, never by hand.
- **A new `agent-wiki/<date>-<name>.md` must be INDEXED in `docs/changes.d/<date>-<name>.md` or `check-docs`
  reds** (`[changes-index] ERROR: … is not indexed — add docs/changes.d/…`). The changes.d file is ONE row:
  `| <date> | <summary> | [<name>.md](agent-wiki/<name>.md) | <refs> |`. Add the index row in the SAME commit as
  the agent-wiki file — a good doc with no index row is a RED gate, not a finished change.
- **Editing an EXISTING tracked behaviour file (an agent skill/SOUL, a script that moves product output)
  owes an agent-wiki note even when you add no new wiki file — the #1123 rule fires on the CHANGE, not
  just on a new note.** `check-docs` reds `[check-docs] ERROR: change->note: this branch changes
  <path> (+N more) but adds no agent-wiki/<stem>.md note — a behavioural change owes a note`. So after any
  such edit, write `agent-wiki/<stem>.md` + its one-row `docs/changes.d/<stem>.md`, then run
  `make changes-index` (it regenerates `CHANGES.md` from the fragments) and **COMMIT that regenerated
  `CHANGES.md`** in the same PR — an unindexed note reds, and a regenerated-but-uncommitted CHANGES.md
  leaves the tree dirty. Only then does `make check-docs` go green.
- **Shared branch that two lanes co-push: fetch, then `git rebase origin/<branch>`, then push
  additive.** Never guess divergence with `merge-base --is-ancestor` (it misreads an amend-vs-
  remote-head shape) and never force-push over a teammate; when the remote head moved while you were
  mid-commit, `git fetch origin/<branch>` and `git rebase origin/<branch>` then a plain push leaves
  your commit on the new tip.
- **A taken-over PR branch is `refs/heads/<branch>`, NOT `refs/pull/<n>/head` — the PR API caches
  `headRefOid` and can lag the real branch, so branching from the PR-ref and force-pushing CLOBBERS
  the branch's newer head.** A rebase lane or a co-push moves the branch ref to a new commit while
  `gh pr view … --json headRefOid` still reports the old one; work based on the stale PR-ref, then
  `--force-with-lease` over the real head, deletes work that is not yours. Before taking an existing
  branch, `git fetch origin +refs/heads/<branch>:refs/remotes/origin/<branch>` and base on THAT ref
  (re-measure with `gh api …/git/ref/heads/<branch>` if in doubt), never on `refs/pull/<n>/head` or
  a quoted sha. If you already clobbered it, restore the prior head (`git branch -f <br> <prior-oid>`),
  `git reset --hard` the worktree to it, and CHERRY-PICK your commits additively on top before the
  lease-push — never re-push a lineage that dropped it.
- **Rebasing onto a main that MOVED A PRODUCT'S OUTPUT ORDER: take main's DERIVED expectation, never the branch's hardcoded one.** A branch cut before a gate change (e.g. the measured-VRAM card gate reordering `trend_list`) hardcodes the pre-change order in its test, while main's copy of the same test DERIVES the order from the source and passes. A `--onto` conflict resolution that takes `theirs` (the branch's side) bakes that stale hardcoded order and reds on the rebased tree — and it will read as a merge artifact when it is really an outdated expectation. Before resolving: run the red test at main and at the branch's parent (`git worktree add --detach`); if main DERIVES and the branch hardcodes, KEEP main's derived form and re-apply only the branch's real additions (the new hermetic twins/tests). Never hand-adjust the expectation to satisfy both sides — re-derive it from the product and quote the product's order (`trend_list(reg, gb, arch=…)` gives the README's tier order) as the authority.
- **A `git worktree add` PATH is relative to the REPO'S OWN directory, not the parent — a "worktree is
  missing" report is usually a wrong-path probe.** `git worktree add -b <br> llgenie-wt/<x> <ref>` run
  with cwd inside the repo creates the worktree at `<repo>/llgenie-wt/<x>`, not the sibling workspace
  path you probed. Resolve the real locations with `git worktree list --porcelain` and probe those
  before concluding a worktree add failed or the edit vanished.
- **A "superseded / close it" verdict is a count against main, not a peer's assertion.** A teammate's
  "everything already landed on main, close the co-owned PR" can be wrong while sounding measured: the
  seam (marker, `-m "not network"`, the pipeline) merges but the ROUTING MARKS do not, so real-call
  tests stay unmarked and run inside the hermetic gate. Before consenting to a close/merge, count what
  main actually carries (e.g. `git show refs/remotes/origin/main:<file> | grep -c
  '@pytest.mark.<marker>'` versus the expected set) and confirm the missing piece is genuinely absent —
  a wrong-but-confident verdict is corrected the same way, by measurement, on the record, not by
  deferring to the claimant.
- **An owner split across a workflow-ownership boundary: agree the shared branch + ONE-PR vehicle BEFORE
  either lane cuts, and opening the ADDITIVE half first is safe only because the removal side is still
  on main.** When one lane owns the engine build/publish path and another owns the workflow files,
  coordinate the branch name and base first. Cutting your additive half (e.g. a per-row producer install
  test) ahead of the counterpart's removal (the consumer tag-poll) is a no-gap shape only while that
  removal hasn't landed on main; never let the removal outrun the addition or install-testing goes
  untested in between. Open the vehicle, flag the counterpart to join, and hold the co-push until both
  halves are queued on the same branch.

- **A file-adding PR's `docs/ARCHITECTURE.md` census pointer CANNOT be made main-ancestor AND
  count-correct at the same time — do not chase it; HOLD THE MERGE for #1053.** The gate uses
  `git ls-tree HEAD` as ground truth, so a file-adding PR must point `measured at` at a sha whose tree
  count == its own head (2009 files) — but no sha carrying those added files is an ancestor of main
  (they don't exist on main until the merge). Pick the PR's own tip → tree-count correct but dangles
  on squash (main re-reds, the #1048/#1052 class); pick a main ancestor → survives squash but its
  count (2002) != the PR's head (2009) → the gate reds now. It is structurally unachievable per-PR;
  that is exactly the gate defect **#1053** fixes (referent = tree-at-named-sha + tolerate the
  file-adding case). So: hold the PR's MERGE until #1053 lands (its unit may show green mid-flight —
  do NOT let it merge and re-break main's `check-docs`), then re-derive once against the fixed gate.
- **Do NOT chase a per-PR `docs/ARCHITECTURE.md` census pointer — it is a GATE DEFECT (#1053), not a
  lane fix.** The census gate (`check_architecture_census.py`) uses `git ls-tree HEAD` as ground truth,
  so EVERY file-adding PR must rewrite the census to its own head + point `measured at` at a sha
  matching it — and that per-PR sha dangles the moment the PR is squash-merged (the same
  dangling-pointer class, now on `main`). The correct fix is the gate's referent = the tree at the
  NAMED sha, not HEAD (issue #1053). So: a file-adding PR that only reds the census gate is HELD for
  #1053, not given a per-PR pointer rewrite; re-verify its unit green once #1053 merges + main moves
  (re-base then). Rewriting the pointer per-PR is a second vehicle that the squash re-breaks.
- **Read `autoMergeRequest` and `pulls/<n>.head.sha` from the API at the moment you write the sentence
  that names them.** Both are writable fields with no history: an arm can be set by an automation acting
  against the lane's charter, cleared by a peer, or re-armed a minute later, and a remembered value is a
  guess. Stale arm reads err consistently toward "calmer than reality" (a PR believed parked is MERGEABLE
  and armed), so quote `mergeMethod` + `enabledAt` from `gh pr view <n> --json autoMergeRequest` before
  any claim about arming.
- **Author every commit as an ALLOWLISTED identity — a `-c user.email=<not-allowlisted>` at commit
time is a CI red, not a local preference.** `make check-pr-authors` (issues #345/#971) accept only
  `Andy Holst <andy.holst@protonmail.com>` or `Asimov Agent <support@docondee.com>`; the address IS the
  identity, and an alias names a display name, never an address. Committing through
  `git -c user.name=… -c user.email=asimov@localhost commit` (a natural-looking override) authors the
  commit outside the allowlist and reds the `guard` job while every local gate is green. Fix in place:
  set the repo identity to the allowlisted one, then `git rebase --exec 'git commit --amend --no-edit
  --reset-author' origin/main` re-authors every commit and `git push --force-with-lease`. Verify with
  `make check-pr-authors` (OK) and the PR's `commits` endpoint showing the allowed name/email on every sha.
- **A rebase/`--reset-author` rewrites the shas, so the `docs/ARCHITECTURE.md` census pointer must be
  re-pointed at the new head — a rewritten `measured at` sha is no longer an ancestor and the gate reds
  `the census has no usable referent`.** After any history rewrite, re-derive the census's `measured at`
  to the new HEAD (`check_architecture_census.measure(<head>)` gives the counts) and commit it before you
  push; `make check-architecture-census` OK is the proof. Do NOT blanket `git checkout origin/main -- .`
  to tidy stray files — it reverts every intended change and reintroduces main's tree; remove the one
  stray path by plumbing (`git rm --cached '<literal-name>'`), then re-verify the file set is exactly the
  intended ones vs `origin/main`.
- **Report the PR head from the API (`gh api repos/asimov-agent/llgenie/pulls/<n> --jq .head.sha`),
  never the sha you believe you are on.** A commit that exists in your tree but was never pushed
  leaves the PR head stale while your local HEAD is ahead — the single largest source of false
  "done" reports. After every push, assert `pulls/<n>.head.sha == $(git rev-parse HEAD)` (it is the
  only check that catches an unpushed commit); if they differ, the push did not land. Also read
  `pulls/<n>.state` + `mergedAt` BEFORE any rebase/catch-up push: a PR you were asked to move can already be
  MERGED (`headRefOid` null, `state=MERGED`) by another lane or the owner — force-pushing its branch then rewrites
  a STALE branch of a merged PR while the work is already on main (verify with `git log origin/main --grep`). Check
  the state first; if merged, there is nothing to catch up — say so, do not rebase a dead branch.
- **A test that makes a real Hub call belongs in `@pytest.mark.network`** (pytest.ini: "a test that
  calls the real Hub for real … EXCLUDED from ci-unit by -m 'not network'", issue #1000) — so the
  hermetic gate never depends on live upstream data. Marking is the fix, not pinning/weakening; the
  assertion stays and runs in the live pipeline. A test whose verdict moves when someone publishes a
  benchmark is not a regression test. When an engine cell is built from a pinned source
  sha rather than a PyPI/installed wheel (vllm, sglang + a prebuilt cell's `runtime_copy`), the
  census/gap row and the `linux/unit` detect must point at a sha reachable from `refs/remotes/origin/main`,
  or the gate reds with the dangling-pointer class (the `bc3859b`/`#1052` shape: a census pointer
  to a sha not on main is un-verifiable). Prove it before merging: `git merge-base
  --is-ancestor refs/remotes/origin/main <sha>` must be YES for every committed sha the build's
  census/detect names. A PR whose head predates the main census-pointer fix keeps its
  `linux/unit` red until main is pulled in (`is-ancestor main <head>` = NO means the fix hasn't
  landed under it) — re-base/merge main, then the unit re-runs green.
- **A generated spec/params/openspec file must end with a newline — `linux/lint` checks it and
  reds otherwise.** A `.md`/engines file committed without a trailing `\n` (e.g. a vllm/sglang
  spec.md) fails the lint-newline check; append the trailing newline in the same change that
  introduces the file, before pushing. The `linux/unit` and `linux/lint` are separate checks —
  confirm each check's completed conclusion separately, never fold one green into a claim for
  the other.
- **The card gate is ARCH-AWARE: a measured run admits a model only on hardware this host can
  reproduce.** An Apple/Metal "unified memory" run (an MLX "M1 Pro 16GB" row beside a "M4 Max
  128GB") is never a cuda/vulkan/rocm/cpu card, so it must not admit the model on such a host; but a
  real run on this host's own arch on a smaller card DOES admit it even above its declared `vram_min`
  (issue #669 — the run wins, `vram_tier` never decides). Thread `arch` through `fits` →
  `card_evidence` → `admitting_measurement` → `trend_list` → `recommend` (default `None` = a bare gate
  call counts every card-sized run, preserving the #669 gate tests; a container arch excludes Apple
  runs, a Metal host counts them). Do NOT "fix" an over-listing by making `vram_min` a hard floor
  before the run evidence — that breaks the #669 run-wins semantics.
- **A retry budget SMALLER than the real backoff window is a fail-fast, not a budget — size it between the real window and the refused cap, and do NOT "allow one wait" instead.** A 429 wait bounded by a total below the Hub's own window raises on the FIRST 429 at "1 attempt, 0 waits, 0 s spent", turning a transient error into a suite failure (a live matrix/pick test reds on the branch while main's un-budgeted retry passes). The fix that works sizes the total to the real window (300 s = the Hub's 5-minute default) while still refusing the pathological cap (600 s), so a transient window is waited out and the 20-minute hop stays impossible. The tempting "always allow the first wait" is WRONG: it sleeps the 600 s cap and breaks the sibling test that pins the cap refused — run that test before choosing the shape. A changed DEFAULT is a doc-truth cascade: `grep` the literal old value and update EVERY place that quotes it (agent-wiki, proposal, spec, docstring, openspec task text), leaving only the test-scenario lines that `monkeypatch` it deliberately.
- **A worktree branch can track a stale/gone remote and carry an UNRELATED commit — verify the branch and your commit's parent before committing or pushing.** A minimal PR fix is the PR's OWN head plus your one commit: confirm `git rev-parse <your-commit>^` equals the PR's `headRefOid`, and check `git log --oneline -3` + `git status -sb` (an `…origin/prNNN [gone]` upstream is the tell). If the worktree was switched onto a local branch that carries another lane's work on a newer base, locate your isolated commit with `git log --all --oneline`, then `git reset --hard <your-commit>` — never stack onto the stale branch or push a rebase nobody asked for over an unrelated history. Cherry-picking your one-file commit onto a newer stale branch drags that branch's unrelated commits into the PR.
- **`pkill -f <pattern>` can kill your OWN shell when the pattern appears in the running command line.** A repo/test command whose script text contains the pattern (e.g. `pkill -f "pytest tests/foo"` inside a compound command that also names that path) matches its own bash process and dies with exit −15 and no output. Use the process tool's kill by session id, or a pattern that cannot match the current command, instead of a broad `pkill -f`.
