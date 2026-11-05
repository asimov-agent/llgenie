# PR vehicle & gate lessons (learned 2026-11-03, #1639; engine-branch rule 2026-11-03 #1696)

## OLD → NEW rule: fix(engines) PRs branch on the CANONICAL repo, not the fork
- OWNER DIRECTIVE (2026-11-03, #1696): a `fix(engines)` change MUST open its PR branch on
  `asimov-agent/llgenie` IN-REPO (canonical), NOT the `andyholst/llgenie` fork. The
  `engine-build-pr-trigger` workflow refuses a foreign (fork) head — "a foreign-head bump
  cannot trigger a push=true dispatch" — so a fork head cannot run the producer that builds
  and publishes the engine cells. #1568 was exactly this: same branch on `andyholst/llgenie`,
  fork-headed, and `engine-build-pr-trigger` refused it. #1696 is the same fix re-opened
  with head `asimov-agent/llgenie:fix/1558-vllm-rocm-build`.
- The OLD convention (section below) — "PR head must live on the FORK" — applied to
  implementer-lane PRs and code-review surfaces; it is SUPERSEDED for this lane's `fix(engines)`
  PRs. Verify the head repo before relying on a trigger: `gh api repos/asimov-agent/llgenie/
  pulls/<n> --jq .head.repo.full_name` must read `asimov-agent/llgenie`.
- Trigger dispatch needs the branch on the canonical repo: `engine-build-pr-trigger` passes
  `BRANCH=${{ github.head_ref }}` (a detached `pull_request` checkout otherwise resolves `HEAD`
  and the dispatch 422s). Push `fix/1558-vllm-rocm-build` to **`origin`** (canonical), not `fork`.

## (superseded for engine PRs) The PR head must live on the FORK remote, not the canonical repo
- Fleet convention: every llgenie PR head repo = `andyholst/llgenie` (the fork). #1636,
  #1568, #1640 all use it. In a worktree the `origin` remote points at `asimov-agent/llgenie`
  (canonical) and `fork` at `andyholst/llgenie`. Push the branch to **`fork`**, not `origin`.
- If you push the branch to the canonical repo instead, the fork 404s, the PR's `head.repo`
  becomes the canonical repo, and a reviewer reading the fork sees "branch absent". The
  expected sha read-back from the canonical repo is just the default-branch fallback (absent
  named branch -> main tip), which looks identical to a real branch — a trap.
- Verify: `gh api repos/andyholst/llgenie/branches/<branch> --jq '.commit.sha'` must equal the
  real commit, NOT the base/main sha. Then open the PR with `--head 'andyholst:<branch>'` and
  read `head.repo.full_name` back = `andyholst/llgenie`.
- If you already created a wrong-repo PR: push branch to `fork`, delete the canonical branch
  (`git push origin --delete`), close the wrong PR, recreate with the fork head. Read the new
  PR number back the same turn.

## check-pr-closing needs the adjacent close in the squash text TOO, not just the body
- The gate (`scripts/check_pr_closing.py`) requires the claimed issue to be closed by the
  squash (joined commit-1-stackhead message) AND the PR body, and those two sets must match.
  A PR body that says `closes #N` but whose commit message does not FAILS:
  "The joined commit messages close (none). The pull request body closes #N."
- Fix: end the HEAD commit message with an adjacent `closes #N` line. Then force-push with
  `--force-with-lease` and re-run the gate locally before pushing:
  `python3 scripts/check_pr_closing.py check --body-file <body> --head <branch> --base origin/main --rev HEAD`.
- A `(#N)` in a commit SUBJECT is itself a CLAIM: the gate treats a title ending `(#N)` the same
  as an `Issue: #N` line, so that commit's body MUST also carry an adjacent `closes #N`. Amend the
  commit body (not just the PR body) — `git commit --amend` with a `closes #N` line — then the
  joined close-set across all commits must equal the PR body's close-set exactly. `closes **#N**`
  (bolded) does NOT count: the keyword must be bare `closes #N`.

## After an amend/force-push, re-edit the body: `AGENTS:` must equal the NEW head
- The `AGENTS: <sha>` line is checked against the PR's CURRENT head. A commit `--amend` (adding
  `closes #N`, folding docs) moves the head, leaving the body's `AGENTS:` sha stale — update it in the
  same turn (`gh pr edit <n> --body-file <body>`) and read `headRefOid` + the AGENTS/BASE/closes lines
  back to confirm they now agree. `BASE:` should stay the sha you branched from; only `AGENTS:` follows
  the head.
- Order the fixes so they land in ONE push: amend the commit message (squash-text closes) FIRST, then
  rewrite the body with the new `AGENTS:` sha, then push once and run the local gate
  `python3 scripts/check_pr_closing.py check --body-file <body> --base origin/main --rev HEAD` — a
  body edit after the push runs is the stale-capture race above and costs a rerun.

## A post-push PR-body edit needs a RERUN: CI captures the body live at run start
- `ci.yml` builds `/tmp/pr-body.md` from a live read (`gh api repos/<o>/<r>/pulls/<n> --jq .body`)
  at the run's start, NOT from an event snapshot. So editing the PR body AFTER the push that fired
  the run leaves the in-flight run holding the STALE body — `check-pr-closing` reds even though the
  live body is now correct (verified via `gh pr view --json body`). The workflow comment states the
  intent: "a body-only fix clears on rerun."
- The remedy is `rerun-failed-jobs`, which re-reads the live body: `gh api -X POST
  repos/<o>/<r>/actions/runs/<run>/rerun-failed-jobs`. It returns 403 `"This workflow is already
  running"` while ANY job in that run is still `in_progress` — typical when `engine-pins`/`ci-images`
  jobs are still waiting on the engine-build producer to publish. Wait for the run to CONCLUDE
  (`gh run view <run> --json status` == `completed`), then rerun; do not cancel other jobs to free it.
- A run can conclude `cancelled` (superseded head / concurrency), not just `completed`. `rerun-failed-jobs` on a cancelled run is accepted and RE-QUEUES the whole run (its status flips back to `queued`) rather than 403ing. Until that requeued attempt finishes, a ci-verdict / lint gate that quotes the run id keeps echoing the CANCELLED attempt's `check-pr-closing` red — so a red that persists in the gate output is NOT proof the body is still wrong. Confirm the live body (`gh pr view --json body` + local `check_pr_closing.py` RC) and read the requeued attempt's own linux/unit job result before patching anything again.
- Diagnose the red as stale-body-vs-real before patching anything: pull the step log
  (`gh api --allow-escape-sequences repos/<o>/<r>/actions/jobs/<job>/logs`), confirm the failing
  gate is `check-pr-closing` and that the other gates (`check-engine-params` 0 stale, unit, etc.)
  are green — a lone `check-pr-closing` red against a correct live body is the stale-capture race,
  not a code defect.

## A behavioural change owes the change-note trio (check-docs, #1123)
- `make check-docs` fails a PR that edits a behavioural surface without adding an
  `agent-wiki/<stem>.md` note AND its `docs/changes.d/<stem>.md` index row.
- Behavioural surfaces are NOT just `scripts/`: they include **`agents/<profile>/SOUL.md` and that
  profile's `skills/**` files** (`scripts/check_docs.py` `NOTE_SURFACE_RES`). A PR that changes an
  agent's SOUL or a skill reference DOES owe the trio — a body claiming "SOUL-only, so no note owed"
  is wrong and the gate reds. If any changed path matches the surface list, add the note.
- Trio: (1) `agent-wiki/<date>-<stem>.md` referencing the issue/PR with `#<n>`; (2)
  `docs/changes.d/<date>-<stem>.md` one-line fragment `| date | text | [(date-stem).md](agent-wiki/<date>-<stem>.md) | #N |`;
  (3) `python3 scripts/changes_index.py write` (or `make changes-index`) re-renders `CHANGES.md`
  from all fragments. Note and fragment MUST share the same stem. Verify with `make check-docs` RC=0.
- **`check-docs` diffs COMMITTED paths only — an untracked/staged-but-uncommitted note still reds.**
  After writing the note + fragment, `git add` them AND `git commit` locally (a prep branch is fine,
  no push needed), then re-run the gate; an uncommitted note is invisible to the gate's
  `git diff <base>...HEAD` path set, so "lint green but check-docs still red" means "commit it", not
  "the fix failed".
- Fragment rows must end with a trailing newline — `python3 scripts/lint_linefeeds.py` (part of
  `ci-lint`) reds a fragment whose last line has no `\n`. Append one before committing.
- Verify gates against the PR's WORKTREE, not the shared/primary checkout: the primary dir is often
  dirty on `main` and `make check-docs` there can exit non-zero for reasons unrelated to the branch.
  Run `python3 scripts/check_docs.py check --root <worktree> --base origin/main 2>&1 | tail -3` in the
  worktree at the PR head before citing a green.

## A quant-catalog DATA edit owes the fixture re-render, or `linux/unit` reds alone
- Editing `data/trending-quant-catalog.json` (dropping a dead model's rows, retiring a plan) leaves
  `tests/fixtures/trend-list-matrix.json` and `tests/fixtures/hub-snapshot.json` STALE. The hermetic
  byte-identity tests (`tests/test_hub_snapshot.py::test_the_check_reproduces_the_fixture_with_no_route`,
  and `trend_list_matrix.py --check`) rebuild the matrix from the vendored registry + `hub-snapshot.json`
  and compare BYTES — so a small data edit produces a wide fit-text re-tabulation diff and reds
  `linux/unit` while `scope`, `guard` and `holds` stay green. That asymmetry is the tell: a lone unit red
  after a data change is a stale fixture, not a logic defect.
- Fix before pushing, not after: `make render-trend-list-matrix` (offline, deterministic — re-renders
  both fixtures from the snapshot; expect ~hundreds of changed lines of fit-text, that churn is
  mechanical). Diff a couple of hunks to confirm it is re-tabulation (GB/Verdict/Verdict text), not
  unrelated registry noise, then commit the fixtures WITH the data edit.
- Verify with the tools venv, not the harness python: `<venv>/bin/python -m pytest tests/test_hub_snapshot.py -q`
  (exit 2 + "file or directory not found" means you guessed a test filename — list `ls tests/ | grep -iE
  'trend|hub|quant|matrix|snapshot'` first) plus the fixture siblings `test_trend_list_matrix.py`,
  `test_trending_quant_catalog.py`, `test_quant_catalog_compare.py`, `test_quant_generator_edges.py`,
  `test_cli_dry_run_matrix.py`.
- Re-prove BOTH seams after the re-render: `gen_trending_quant_catalog.py --check` (LIVE) and
  `--check --snapshot` (hermetic). Both must print OK; their note counts legitimately DIFFER (LIVE probes
  the real Hub and carries more plan notes than the replayed fixture) — a differing count is not a red.
- Push a fixture fix as a PLAIN fast-forward on top of the PR head (read the remote branch sha first,
  assert it equals your local base). No rewrite, so no lease and no re-arm of auto-merge.

## A green SUBSET of checks is not a green PR
- `scope`/`guard`/`holds` green while `linux/unit` or `ci-verdict` is red is the single most common
  shape here, because a data or fixture defect is caught ONLY by `linux/unit` (see the section above).
  Never report "green at head" from the checks you happened to look at.
- Enumerate EVERY check-run name and its LATEST conclusion, and require the non-green set to be empty:
  `gh api repos/O/R/commits/<full-sha>/check-runs --jq '.check_runs|map({n:.name,c:.conclusion})|group_by(.n)|map({n:.[0].n,c:map(.c)[-1]})'`.
  Group by name and take the LAST entry per name — a re-push re-triggers a fresh `linux/unit` run, and
  the older run's `success` must not mask the newer one's `in_progress`/`failure`.
- `ci-verdict` is a derived rollup: a red there is usually the same root as a red `linux/unit`, so fix the
  substrate job and re-read, rather than treating it as a second defect.

## Rebase onto canonical main, not the fork's main
- The PR base is `asimov-agent/llgenie` main. `fork/main` (andyholst) can lag. Rebase onto the
  canonical `origin/main` (fetch `origin main` first). Only rebase on a REAL conflict (#1015):
  a concurrent change-note merge landing a new CHANGES.md row collides -> resolve by keeping
  both rows, `git add`, `GIT_EDITOR=true git rebase --continue`.
- After rebase force-push with lease: `git fetch fork <branch>`; `git rev-parse fork/<branch>`
  for the expected tip; `git push --force-with-lease fork <branch>`.

## Verify WHICH workflow concluded before citing a CI verdict (ci.yml vs ci-hf-live)
- `ci.yml` (the `CI` workflow) runs `make ci-unit` = hermetic unit + registry/skill/Strata/
  engine-param/quant-catalog checks only. Its `linux/unit` step5 make line lists NO
  `test-unit-network`; ci.yml has zero `network` references. So a green PR CI does NOT prove
  the `@pytest.mark.network` acceptance case (e.g. `test_rank_follows...`) ran.
- `ci-hf-live.yml` is the ONLY workflow that runs `make test-unit-network`. Its header states
  it is merge-to-main real-Hub testing and "never runs in a pull request" — branches:[main],
  no `pull_request` trigger. So there is NO ci-hf-live verdict at any PR head by design;
  demanding one at a PR sha is invalid (planner retracted this exact demand, #1642).
- Always read the workflow's step names/job from the API before claiming a verdict covers a
  specific test: `gh api repos/<o>/<r>/actions/runs/<id>/jobs --jq '<steps>'` to see the actual
  `make` target, and the Makefile line for that target's deps. Do not let a `linux/unit`
  green be reported as the acceptance case passing.
- When the real acceptance lives in a merge-to-main workflow, the fresh verdict on a fix can
  only be produced AFTER the PR lands on main (owner-gated merge, e.g. #1088).

## Reading a live-acceptance failure: fetch the log correctly, then read the failing LINE
- `gh api repos/<o>/<r>/actions/jobs/<job>/logs > out` returns a ~99-byte error unless you
  pass `--allow-escape-sequences`: "the response contains terminal escape sequences; pass
  --allow-escape-sequences to output it anyway". That stub then dies in `json.loads` at char 0
  and greps find nothing — a false "empty log". Always fetch with
  `gh api --allow-escape-sequences repos/<o>/<r>/actions/jobs/<job>/logs`.
- A multi-assertion acceptance test SHORT-CIRCUITS on its first failing `assert`. Fixing that
  assertion does not green the test: the run proceeds and a LATER latent assertion (same test,
  different line) can fail. A re-run that reds the "same" test may be a DIFFERENT defect — so
  read the traceback's `tests/...py:<line>` and the `E` line before concluding, and separately
  confirm the FIXED assertion actually passed (locate it above the `=== FAILURES ===` marker).
  "The test still fails" and "the fix failed" are not the same claim; report both halves.

FEEDBACK CORRECTION (2026-11-03): a live 'not admitted at cuda/8' red for a model the README still places may be an IN-REPO merge collapse, NOT upstream drift. The #1636 measurement rehydration (sync_registry.sync: existing.setdefault(e['engine'])) keyed runs by engine NAME only, so re-building a row from measurements.json squashed every run of one engine on different cards into a single arbitrary entry — erasing the small-card runs card_evidence/fits need (qwen3.8-27b: 130 runs->26, lost llama.cpp 14.06@4GB and 5@RTX4060 8GB). Diagnose by comparing the committed store (never redding, all runs) against a fresh live re-sync; the asymmetry proves the defect is here, not upstream. Fix: key distinct runs by (engine, hardware).


NEVER read-back-guarded gate: any llgenie PR body MUST carry BOTH an `AGENTS: <sha> <bytes>b <lines>l` line AND a `BASE: <sha> (== origin/main at open)` line (check-pr-agents-line, issue #792), or the guard job reds and the whole matrix skips. `make bot-preflight` prints both lines verbatim — run it, paste into the PR body. A body-only edit does NOT re-trigger CI: `gh run rerun <run> --job <guard-job-id>` the failed guard job (own PR, corrected body). The SAES agents/BASE sha is origin/main at branch time.


Classify an 'not admitted' acceptance red as (a) vs (b) before touching pick logic
- #669 oracle: a README tier never places a model `card_evidence` refuses
  (`test_every_model_the_published_tier_table_places_is_admitted`). When the live acceptance
  reds on a model `rank_models(...gb)` excludes that the README places, MEASURE before patching
  `fits`/`card_evidence` — the code may be right and the upstream data wrong.
- To measure, re-sync the EXACT path the test consumes: `sr.sync(sr.UPSTREAM, dest, sr.UPSTREAM_README,
  measurements_src=sr.UPSTREAM_MEASUREMENTS)` (upstream = andyholst/trending-local-llms `master`,
  NOT `main` — `_UPSTREAM_DATA` uses `master`). Then read back, persisted: live README tier
  placement, `card_evidence(model, gb, arch)`/`fits`, `rank_models`/`trend_list` membership, and
  the model row's `vram_min`/`weight_gb` + min non-Apple engine card.
- Split: (a) = `fits(model,gb)` TRUE but `rank_models` excludes → engine-lane self-admission
  regression (pinpoint the line). (b) = upstream data drift. **Both can be non-obvious:** a live
  README that STILL places the model AND a live `measurements.json` that still carries the ≤8GB
  run, while the live `models.json` row lost/omitted that run → the store the pick code reads no
  longer admits it, so `card_evidence`="" and `fits`=false is CORRECT. That is (b) upstream
  internal inconsistency (README+measurements vs models.json), never a pick-logic patch (never
  patch upstream, #687); route to the data-contract owner (producer lane).
- Compare against the committed vendored store (`data/models.json`): if it still admits the model
  at the tier, that's why the hermetic twin passes and the live twin reds — confirming drift is
  upstream, not in the committed code or fixtures.
- Reusable probe: `scripts/measure_live_admission.py <worktree> <model-id> <gb> [--arch cuda]
  [--out DIR]` runs this exact live sync and prints tier-placement / `card_evidence` / `fits` /
  `rank_models` / `trend_list` / min non-Apple card. Use it instead of hand-rolling the sync.
- Parse README tier placement by the model id's LITERAL case-insensitive substring; never
  normalize by stripping hyphens. The README renders display ids hyphenated (`Qwen3.8-27B`), so a
  hyphen-stripped pattern (`qwen3.8 27b`) never matches and the probe reports "not placed" for a
  row visibly present in the table — a false (b)/admitted mismatch.
- A measurement script that has only been `py_compile`d is UNVERIFIED: run it end-to-end and diff
  its output against your hand measurement before trusting its verdict. `sync_registry.sync` is
  idempotent (writes only when the store changed, ~1s), so re-running the persisted script is
  cheap and is what catches parser bugs.
- Before re-measuring a verdict when `main` has moved, diff the pick logic between the measured
  head and current main (`git diff --stat <head> origin/main -- scripts/model_engine_pick.py`);
  byte-identical files mean the earlier verdict still stands and no re-run is owed.

## Misc
- `git add -A` in a worktree can sweep scratch/redirect files into a commit — review
  `git show --stat` before committing; use explicit paths.
- Backgrounded pytest under the wrong interpreter (`python3` w/o pytest) exits 2 with zero
  output; the harness `python3` may lack pytest — invoke the venv python explicitly.
