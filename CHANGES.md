# Changes — the index of change records

Every change in this repository has ONE dated note of its own in `agent-wiki/` — a Zettelkasten
entry that states what was verified against the spec, the decisions taken, and the issue and PR
it implements. This file is the index of those notes, newest first, and it is the file
`README.md` points at instead of carrying change history itself.

The index rows do not live here: each one is its own file, `docs/changes.d/<note-stem>.md`,
holding a single row (issue #934). A change adds its note and its fragment, and nothing else.
One row per file means two changes can never edit the same line, so no merge can re-dirty an
open PR. This page is rendered from those fragments by `make changes-index`; do not edit it by
hand.

`make check-docs` fails when a note under `agent-wiki/` has no fragment, when a fragment names
a note that does not exist, or when a row is malformed.

| Date | Change | Record | Issue / PR |
|---|---|---|---|
| 2026-10-30 | `tests/test_pr_authors.py` gains a lock asserting `AGENTS_MANDATE` keeps the shipped "authored through an allowed email — no one else" wording and that `AGENTS.md` carries "The EMAIL is the gate" + "they PASS" — the invariant that reds if the #977 author-gate revert (issues #976/#988/#1031) ever lands. Record shipped on PR #1033, pushed fork ref `fix/1031-author-alias-mandate` → verified via `ls-remote` (not local-only); executed suite 29 passed. Fresh CI at pushed head `e29035e2` = run 40975428531 in_progress (openspec/guard/holds pass; linux/unit+lint pending; no completed-run verdict claimed) | [2026-10-30-mandate-lock.md](agent-wiki/2026-10-30-mandate-lock.md) | #1033 |
| 2026-10-30 | `scope.yml` reaches the diff classifier through the new `make ci-scope` target (the repo rule that a workflow step which runs a script must route through a make target, #270/#296/#305), and gained the shared owner/collaborator guard job every dispatchable workflow carries (#295). #904 now runs ci.yml's `paths-ignore` (the #824 docs-class trigger) without tripping the #718 renovate path-filter rule, because a docs-only ignore can never skip an image build. | [2026-10-30-ci-scope-make-target.md](agent-wiki/2026-10-30-ci-scope-make-target.md) | #824 |
| 2026-10-30 | `check_architecture_census.py` now counts the tree at the `measured at <sha>` commit the doc names (and requires that commit to be an ancestor of `HEAD`) instead of at `HEAD`, so a file-adding PR no longer has to rewrite `docs/ARCHITECTURE.md` and the pointer no longer dangles after a squash; a stale number, a missing pointer, a dangling sha and a non-ancestor sha all still red, and a stale claim names both values | [2026-10-30-census-tree-at-sha.md](agent-wiki/2026-10-30-census-tree-at-sha.md) | #1053 |
| 2026-10-30 | CI's `docker/setup-buildx-action` pin was DEAD: `8d2750c68a` (tag `v3`/`v3.12.0`) is not served by upstream, so `linux / unit` failed in 7s at the action-resolve step (run 41057782597). Re-pointed all 5 uses (ci.yml ×2, engine-build.yml, publish-agent-image.yml, actions/docker/action.yml) to the resolvable `v3.11.1` commit `e468171a9de216ec08956ac3ada2f0791b6bd435`, keeping the v3 line. | [2026-10-30-buildx-pin.md](agent-wiki/2026-10-30-buildx-pin.md) | #1048 |
| 2026-10-29 | `docs/BOTS.md` states that a stacked PR has no CI verdict at all — `pull_request.branches: ["main"]` filters the BASE branch, so a PR based on a feature branch gets no run and `gh pr checks` says `no checks reported`; merge it only into its base, and retarget to `main` when the base lands | [2026-10-29-stacked-pr-no-ci-verdict.md](agent-wiki/2026-10-29-stacked-pr-no-ci-verdict.md) | #945 |
| 2026-10-29 | a finished PR is armed when it is done, not when it is approved: the producing lane rolls it in, reads the arm back, and a finished-but-unarmed PR is invisible to every sweep (#873) | [2026-10-29-rule16-arm-when-done.md](agent-wiki/2026-10-29-rule16-arm-when-done.md) | #873 |
| 2026-10-29 | every number the merger reports names the sha it was measured at: fetch → branch at that sha → bookend the act (#873) | [2026-10-29-rule15-sha-baseline.md](agent-wiki/2026-10-29-rule15-sha-baseline.md) | #873 |
| 2026-10-29 | the merger publishes what it acted on: run id, head sha and decision, after the merge returned (#873) | [2026-10-29-rule14-announce-merge.md](agent-wiki/2026-10-29-rule14-announce-merge.md) | #873 |
| 2026-10-29 | the author gate matches the commit EMAIL, not the display name: a squash writes the name from the profile, so the address is the field the committer controls (#840) | [2026-10-29-pr-email-gate.md](agent-wiki/2026-10-29-pr-email-gate.md) | #840, #873 |
| 2026-10-29 | `make ci-wait-engine-images` reads its producer cells' own job state: a cell still `queued`/`in_progress` extends the wait to a 75-minute ceiling and then fails as `BLOCKED`, a concluded one fails at once as `NOT FOUND` — so a queue delay is never reported as a missing tag | [2026-10-29-install-wait-names-the-queue.md](agent-wiki/2026-10-29-install-wait-names-the-queue.md) | #893 / #941 |
| 2026-10-29 | each host llgenie bot pins its cli toolsets and the skills it keeps; the rebase lane is the only one that may force-push | [2026-10-29-host-bot-capabilities.md](agent-wiki/2026-10-29-host-bot-capabilities.md) | #1038 |
| 2026-10-29 | `freetoken/cuda`, `mlx/cpu`, `mlx/cuda` and `tensorfold/cuda` build from their pinned sources instead of PyPI wheels and a release archive; `litert/cpu` records why its pip package cannot be built here, and the nine `prebuilt` cells are split into #936–#939 | [2026-10-29-engine-source-cells.md](agent-wiki/2026-10-29-engine-source-cells.md) | #615 |
| 2026-10-29 | the live TensorFold archive proof runs on the engine-bump pipeline after the new pin, and not on every CI unit job | [2026-10-29-engine-bump-live-on-bump.md](agent-wiki/2026-10-29-engine-bump-live-on-bump.md) | #995, #996 |
| 2026-10-29 | `make check-wiring` also asserts the reverse `.PHONY` direction: every key must name a target with a recipe, an inline `;` command or a prerequisite (a declared alias) — a key whose recipe is gone is a permanent green no-op (`make <name>` → "Nothing to be done", exit 0) | [2026-10-29-check-wiring-phony-declares-recipe.md](agent-wiki/2026-10-29-check-wiring-phony-declares-recipe.md) | #883 |
| 2026-10-29 | the change index is one row per file (`docs/changes.d/`), rendered into `CHANGES.md` by `make changes-index` — two changes can no longer edit one line, so a merge cannot re-dirty an open PR | [2026-10-29-changes-index-per-change-file.md](agent-wiki/2026-10-29-changes-index-per-change-file.md) | #934 |
| 2026-10-29 | the change-record rule states the fragment shape (`docs/changes.d/<note-stem>.md` + `make changes-index`), and `make check-docs` reds when a document tells a contributor to append a row to `CHANGES.md`; `AGENTS.md` stays a dated exception until its protected write is approved | [2026-10-29-change-record-rule-names-fragment.md](agent-wiki/2026-10-29-change-record-rule-names-fragment.md) | #942 |
| 2026-10-29 | a bot's review verdict is a comment marker naming the head it reviewed (`make bot-verdict`), never an approval: `auto_merge.decide()` accepts it only at the PR's current `headRefOid`, so a stale verdict cannot merge unreviewed code | [2026-10-29-bot-verdict-legible.md](agent-wiki/2026-10-29-bot-verdict-legible.md) | #852 |
| 2026-10-29 | the commit identity has ONE source (`scripts/git_identity.py`, derived from `check_pr_authors.ALLOWED`), every committing/PR-opening producer sources it, `guard` asserts it in seconds, and bot PR bodies report `Author:` up front | [2026-10-29-author-identity-seam.md](agent-wiki/2026-10-29-author-identity-seam.md) | #840 |
| 2026-10-29 | the commit-author gate keys on the allowlisted **address** with an explicit alias list per address, so `Andy <andy.holst@protonmail.com>` passes while the lookalike `andy.holtd@…` still fails | [2026-10-29-author-alias-emails.md](agent-wiki/2026-10-29-author-alias-emails.md) | #971 |
| 2026-10-29 | `make check-architecture-census` parses the `docs/ARCHITECTURE.md` census and counts the tree with `git ls-tree -r --name-only HEAD`, failing when they disagree (naming both values and the sha); wired into `check-docs`, and the census is corrected with a `measured at <sha>` note | [2026-10-29-architecture-census-gate.md](agent-wiki/2026-10-29-architecture-census-gate.md) | #896 |
| 2026-10-29 | agent pulls use GHCR `:latest`; publish points that tag at the content hash, including when the hash is already published | [2026-10-29-agent-image-pull-latest.md](agent-wiki/2026-10-29-agent-image-pull-latest.md) | #989, #992 |
| 2026-10-28 | a worktree the sweep unregistered but could not delete is a named leftover with its clearing command (branch still deleted, exit 0), and root-owned debris is cleared through the container engine | [2026-10-28-worktree-prune-leftover.md](agent-wiki/2026-10-28-worktree-prune-leftover.md) | #759 |
| 2026-10-28 | the rebase sweep has four outcomes, so a crash cannot read as nothing-to-do (#801) | [2026-10-28-sweep-decision-outcomes.md](agent-wiki/2026-10-28-sweep-decision-outcomes.md) | #801 |
| 2026-10-28 | llgenie follows the `2026-10-27T21:47:11Z` store: re-vendored registry, regenerated quant table / trend-list matrix / skill gap, and `Rapid-MLX` decided (43 engines, unresolved 0) | [2026-10-28-registry-sync-2026-10-27.md](agent-wiki/2026-10-28-registry-sync-2026-10-27.md) | #229, #673, #686 |
| 2026-10-28 | a plan the live search stops returning is a NOTE when its own link still answers (200, or 401/403 gated) and only a 404/410 fails the gate, while a sync carries a still-downloadable plan over instead of deleting it from the picker | [2026-10-28-quant-catalog-search-drift.md](agent-wiki/2026-10-28-quant-catalog-search-drift.md) | #769 |
| 2026-10-28 | `linux / top-tier` is off the `pull_request` matrix — main + the `ci:slow` label only — decided by `make ci-slow-rows` and carried into `pipeline.yml`'s one matrix axis (the macOS rows the issue also named were removed by #870) | [2026-10-28-pr-matrix-trim-slow-rows.md](agent-wiki/2026-10-28-pr-matrix-trim-slow-rows.md) | #859 |
| 2026-10-28 | a bot job's JEV preflight failure names its class and its fix and files ONE tracker per class, and the dedupe job finally passes `TYPESAFE_API_KEY`: `make jev-preflight-required` | [2026-10-28-issue-dedupe-jev-preflight.md](agent-wiki/2026-10-28-issue-dedupe-jev-preflight.md) | #802 |
| 2026-10-28 | the implement leg heals its own seam: a root-run agent container hands the checkout back to the invoking uid before `git add` (root-owned `.git/objects` killed the push), and the agent's `pr-body.md` is validated inside `implement-issue` instead of at the final PR step | [2026-10-28-issue-bot-implement-leg-seam.md](agent-wiki/2026-10-28-issue-bot-implement-leg-seam.md) | #770 |
| 2026-10-28 | a scaffolded engine skill derives `os:` from the backend evidence it already reads — a Metal-only engine is `darwin`, not a Linux server — and its body names where the value came from | [2026-10-28-engine-skill-scaffold-os.md](agent-wiki/2026-10-28-engine-skill-scaffold-os.md) | #772 |
| 2026-10-28 | the spawned engine-skill tracking issue is queued through the REST label API (`POST …/issues/<n>/labels`) and read back, because `--label` on create is dropped and `gh issue edit --add-label` is refused by the runner's PAT | [2026-10-28-engine-skill-gap-label-api.md](agent-wiki/2026-10-28-engine-skill-gap-label-api.md) | #724, PR #826 |
| 2026-10-28 | a launcher whose image tag lags the committed params is red in `ci-unit` (`make check-engine-launchers`), instead of silently running an older pinned engine | [2026-10-28-engine-launcher-freshness.md](agent-wiki/2026-10-28-engine-launcher-freshness.md) | #842 |
| 2026-10-28 | a shipped engine the CI matrix never builds (disabled cell, non-CI variant, no linux image) is now red in `ci-unit`: `make check-engine-coverage` + the ordered new-engine flow | [2026-10-28-engine-ci-coverage.md](agent-wiki/2026-10-28-engine-ci-coverage.md) | #771 |
| 2026-10-28 | a docs-only PR selects its stages from the diff instead of running the matrix (#824) | [2026-10-28-ci-path-scope.md](agent-wiki/2026-10-28-ci-path-scope.md) | #824 |
| 2026-10-28 | worktree-prune reports what it would delete and refuses the destructive half unless a lane asks for it | [2026-10-28-bot-worktree-report.md](agent-wiki/2026-10-28-bot-worktree-report.md) | #794 |
| 2026-10-28 | a leg proves its tree is current and cites the rulebook it obeyed (#792) | [2026-10-28-bot-preflight.md](agent-wiki/2026-10-28-bot-preflight.md) | #792 |
| 2026-10-28 | green ⇒ merged is permanent policy, and guarded: deleting `auto-merge.yml`, dropping its automatic PR-completion trigger, or loosening `REQUIRED_MERGE_STATE` each reds `ci-unit` | [2026-10-28-auto-merge-guard.md](agent-wiki/2026-10-28-auto-merge-guard.md) | #874 |
| 2026-10-28 | the architecture pass is a GATED HOST SKILL in `.hermes/skills/` (`HOST_SKILLS` by name), and a required contract section is an exact heading — not a substring | [2026-10-28-architecture-pass-host-skill.md](agent-wiki/2026-10-28-architecture-pass-host-skill.md) | #805 |
| 2026-10-27 | the security stack names no scanner this repository does not ship (Trivy + Grype/Syft + Semgrep) | [2026-10-27-security-stack-roster.md](agent-wiki/2026-10-27-security-stack-roster.md) | #714, #715, #725, #729 |
| 2026-10-27 | the scans run from pinned images; a PR run is narrower than the daily run | [2026-10-27-security-scan-workflow.md](agent-wiki/2026-10-27-security-scan-workflow.md) | #715 |
| 2026-10-27 | the compile inputs state the versions the scan demands: direct runtime deps pinned, the three scanned advisories floored, both compiled files regenerated | [2026-10-27-security-requirements-pins.md](agent-wiki/2026-10-27-security-requirements-pins.md) | #754 |
| 2026-10-27 | a finding becomes exactly one tagged issue, and never a duplicate | [2026-10-27-security-issues.md](agent-wiki/2026-10-27-security-issues.md) | #716 |
| 2026-10-27 | the scan is its own daily pipeline (never on PR/push), and the pins it names are compiled into the requirements by the run that reports them | [2026-10-27-security-daily-self-correct.md](agent-wiki/2026-10-27-security-daily-self-correct.md) | #738, #718, #739 |
| 2026-10-27 | the bot turns one auto-fixable issue into one green PR, or nothing | [2026-10-27-security-bot.md](agent-wiki/2026-10-27-security-bot.md) | #717 |
| 2026-10-27 | one immutable Wolfi image per scanner | [2026-10-27-scanner-images.md](agent-wiki/2026-10-27-scanner-images.md) | #714 |
| 2026-10-27 | Renovate owns the low-risk pins, and nothing generated | [2026-10-27-renovate-dependencies.md](agent-wiki/2026-10-27-renovate-dependencies.md) | #718 |
| 2026-10-27 | the weekly sync's own gate passes on the store it downloaded: the quant table stops inventing plans, an engine without a plan is not offered, a gated link is not a dead one, and the 18 new engines are dated and decided | [2026-10-27-registry-sync-unit-gate.md](agent-wiki/2026-10-27-registry-sync-unit-gate.md) | #750, #749, PR #753 |
| 2026-10-27 | the per-engine spawn runs on `always()` with a change guard, and its recipe re-checks the diff, so a red sync still files the work item that explains it | [2026-10-27-registry-sync-spawn-always.md](agent-wiki/2026-10-27-registry-sync-spawn-always.md) | #758 |
| 2026-10-27 | a GREEN sync PR is reviewed into ONE issue (VRAM trend list + highest-t/s server) | [2026-10-27-registry-sync-review.md](agent-wiki/2026-10-27-registry-sync-review.md) | #709, #720 |
| 2026-10-27 | a changed store opens ONE issue that states what changed | [2026-10-27-registry-sync-change-issue.md](agent-wiki/2026-10-27-registry-sync-change-issue.md) | #704 |
| 2026-10-27 | a `formats` name that is not a format is not a loss | [2026-10-27-registry-keys-format-vocab.md](agent-wiki/2026-10-27-registry-keys-format-vocab.md) | #698, #700 |
| 2026-10-27 | `check-quant-catalog` fails on a plan the committed table lost, and only notes what the live Hub re-reads (a reorder, a newly published conversion) | [2026-10-27-quant-catalog-live-drift.md](agent-wiki/2026-10-27-quant-catalog-live-drift.md) | #736, #732 |
| 2026-10-27 | a check whose exit code is discarded is not a gate | [2026-10-27-quant-catalog-check-exit.md](agent-wiki/2026-10-27-quant-catalog-check-exit.md) | #701, #702 |
| 2026-10-27 | every GitHub Action runs at a commit, not at a tag | [2026-10-27-pin-github-actions.md](agent-wiki/2026-10-27-pin-github-actions.md) | #719 |
| 2026-10-27 | the pick gates on the measured minimum, and the suite asserts rules over the store | [2026-10-27-pick-gate-engine.md](agent-wiki/2026-10-27-pick-gate-engine.md) | #669, #693, #730 |
| 2026-10-27 | Every issue states the problem, why, how, the benefit and its acceptance criteria, then one technical section — rendered by `scripts/issue_body.py` and gated by `make check-issue-bodies` | [2026-10-27-issue-body-shape.md](agent-wiki/2026-10-27-issue-body-shape.md) | #745 |
| 2026-10-27 | a new registry engine's tracking issue is queued for the bots (`agent:implement`, set explicitly and read back), and `make engine-skill-scaffold` writes its skill with every unprovable key left empty | [2026-10-27-engine-skill-automation.md](agent-wiki/2026-10-27-engine-skill-automation.md) | #757 |
| 2026-10-26 | the store is vendored with the contract it is written against | [2026-10-26-vendor-model-contract.md](agent-wiki/2026-10-26-vendor-model-contract.md) | #694, #699 |
| 2026-10-26 | the unit gate stops requiring a tag its own PR is publishing | [2026-10-26-unit-gate-bump-race.md](agent-wiki/2026-10-26-unit-gate-bump-race.md) | #672, #674, #665, #663 |
| 2026-10-26 | a dry run that outlives its deadline is retried, not raised out of the seam | [2026-10-26-top-tier-timeout-retry.md](agent-wiki/2026-10-26-top-tier-timeout-retry.md) | #676 |
| 2026-10-26 | sglang's version fallback is the pin, never a commit sha | [2026-10-26-sglang-version-not-pin.md](agent-wiki/2026-10-26-sglang-version-not-pin.md) | #636, #650 |
| 2026-10-26 | gh gets the repo slug, not the checkout path | [2026-10-26-repo-slug-default.md](agent-wiki/2026-10-26-repo-slug-default.md) | #343, #434 |
| 2026-10-26 | the rename guard reads live files, not the raw tree | [2026-10-26-rename-guard-tracked.md](agent-wiki/2026-10-26-rename-guard-tracked.md) | #350 |
| 2026-10-26 | the registry sync carries a NEW engine instead of dying on it | [2026-10-26-registry-sync-carries-new-engines.md](agent-wiki/2026-10-26-registry-sync-carries-new-engines.md) | #683, #685 |
| 2026-10-26 | the vendored registry is normalised on the way in (formats vocabulary, duplicates) | [2026-10-26-registry-normalise-on-vendor.md](agent-wiki/2026-10-26-registry-normalise-on-vendor.md) | #687 |
| 2026-10-26 | the registry link check asks the Hub's API, and a 429 is not a dead link | [2026-10-26-registry-link-check-hub.md](agent-wiki/2026-10-26-registry-link-check-hub.md) | #690, #691 |
| 2026-10-26 | the additive-only gate compares identity, so the weekly sync can land | [2026-10-26-registry-guard-measurement-identity.md](agent-wiki/2026-10-26-registry-guard-measurement-identity.md) | #668, #534, #671, #673 |
| 2026-10-26 | a dry refiner pick writes nothing | [2026-10-26-refiner-dry-no-write.md](agent-wiki/2026-10-26-refiner-dry-no-write.md) | #352 |
| 2026-10-26 | the README is the user guide; every change is a dated note indexed here | [2026-10-26-readme-user-guide-changes-index.md](agent-wiki/2026-10-26-readme-user-guide-changes-index.md) | #678, #680 |
| 2026-10-26 | the openspec gate validates every active change | [2026-10-26-openspec-validate-all.md](agent-wiki/2026-10-26-openspec-validate-all.md) | #156 |
| 2026-10-26 | the issue-bot re-checks the fast gates before it pushes | [2026-10-26-issue-bot-gates.md](agent-wiki/2026-10-26-issue-bot-gates.md) | #475, #428, #429, #407 |
| 2026-10-26 | a help line's CI claim must match what CI does | [2026-10-26-install-ci-claim.md](agent-wiki/2026-10-26-install-ci-claim.md) | #239 |
| 2026-10-26 | a fork PR's engine publish is a loud skip, not a red job | [2026-10-26-fork-pr-no-publish.md](agent-wiki/2026-10-26-fork-pr-no-publish.md) | #155, #675, #651 |
| 2026-10-26 | the wiring graph's JSON form works | [2026-10-26-check-wiring-json.md](agent-wiki/2026-10-26-check-wiring-json.md) | #395 |
| 2026-10-25 | strata: the family SHAPE is the invariant, not v0.1.43's membership | [2026-10-25-strata-family-shape-invariant.md](agent-wiki/2026-10-25-strata-family-shape-invariant.md) | #643, #605, #416, #641 |
| 2026-10-25 | rebase-bot's agent leg lost half its command to a comma | [2026-10-25-rebase-bot-skill-comma.md](agent-wiki/2026-10-25-rebase-bot-skill-comma.md) | #641, #602, #605, #460 |
| 2026-10-25 | the published-image test runs pytest in the test image | [2026-10-25-published-test-seam.md](agent-wiki/2026-10-25-published-test-seam.md) | #621, #622, #616 |
| 2026-10-25 | the review brief is a selection, not the whole tree (#597) | [2026-10-25-params-review-budget.md](agent-wiki/2026-10-25-params-review-budget.md) | #597, #583 |
| 2026-10-25 | a failed run whose PR already landed is not a fix-bot failure | [2026-10-25-fix-bot-no-pr.md](agent-wiki/2026-10-25-fix-bot-no-pr.md) | #629, #635, #627 |
| 2026-10-25 | an engine row decides through one function, with its cell's identity | [2026-10-25-engine-row-cell-identity.md](agent-wiki/2026-10-25-engine-row-cell-identity.md) | #634, #637, #625, #632 |
| 2026-10-25 | a green engine row must mean the binary answered | [2026-10-25-engine-gate-strict.md](agent-wiki/2026-10-25-engine-gate-strict.md) | #625, #626 |
| 2026-10-25 | FORCE=1 really rebuilds, and a publish carries hash + arch + latest | [2026-10-25-engine-force-rebuild.md](agent-wiki/2026-10-25-engine-force-rebuild.md) | #638, #614, #615, #103 |
| 2026-10-25 | a dispatched sweep that builds every engine at its pin | [2026-10-25-engine-build-dispatch.md](agent-wiki/2026-10-25-engine-build-dispatch.md) | #614, #615 |
| 2026-10-25 | a device verdict needs the cell it is about | [2026-10-25-decide-cell-identity.md](agent-wiki/2026-10-25-decide-cell-identity.md) | #632, #625 |
| 2026-10-25 | the bot image runs the host's nerve profile, and the build proves it | [2026-10-25-agent-nerve-operator-parity.md](agent-wiki/2026-10-25-agent-nerve-operator-parity.md) | #611, #612 |
| 2026-10-24 | a branch held by a worktree is a keep, not an Error 2 (#593) | [2026-10-24-worktree-prune-retry.md](agent-wiki/2026-10-24-worktree-prune-retry.md) | #593, #570, #592, #433 |
| 2026-10-24 | a detached worktree is matched to the branch it holds (#570) | [2026-10-24-worktree-prune-detached.md](agent-wiki/2026-10-24-worktree-prune-detached.md) | #570, #590, #591, #502 |
| 2026-10-24 | A live-Hub case asserts the invariant, not an upstream name | [2026-10-24-live-hub-test-drift.md](agent-wiki/2026-10-24-live-hub-test-drift.md) | #575 |
| 2026-10-24 | an engine bump's derived params are reviewed against the engine's own docs (#583) | [2026-10-24-engine-params-review.md](agent-wiki/2026-10-24-engine-params-review.md) | #583, #580, #427 |
| 2026-10-24 | every engine-binary flag must answer, not just one (#580) | [2026-10-24-engine-binary-flags.md](agent-wiki/2026-10-24-engine-binary-flags.md) | #580, #583 |
| 2026-10-24 | every bot leg loads its contract from a Hermes project skill | [2026-10-24-bot-agent-skills.md](agent-wiki/2026-10-24-bot-agent-skills.md) | #577 |
| 2026-10-24 | the agent image installs without an extra it never uses (#585) | [2026-10-24-agent-image-laya.md](agent-wiki/2026-10-24-agent-image-laya.md) | #585, #586, #406, #584 |
| 2026-10-23 | a top-tier dry run survives one transient Hub failure | [2026-10-23-top-tier-dry-run-transient-retry.md](agent-wiki/2026-10-23-top-tier-dry-run-transient-retry.md) | #399, #396, #549 |
| 2026-10-23 | a refine keeps the issue queueable (#522) | [2026-10-23-refine-not-parked.md](agent-wiki/2026-10-23-refine-not-parked.md) | #522, #399 |
| 2026-10-23 | the run-failure reactor files only work that is still work (#565) | [2026-10-23-reactor-superseded.md](agent-wiki/2026-10-23-reactor-superseded.md) | #565, #563, #564, #349 |
| 2026-10-23 | A failed fork-PR run is repaired, not filed | [2026-10-23-reactor-route-fork-pr.md](agent-wiki/2026-10-23-reactor-route-fork-pr.md) | #555, #556, #277, #170 |
| 2026-10-23 | the duplicate sweep, four times a day (#553) | [2026-10-23-issue-dedup-bot.md](agent-wiki/2026-10-23-issue-dedup-bot.md) | #553, #400, #254, #440 |
| 2026-10-23 | a read-phase Hub timeout is retried, not fatal | [2026-10-23-hf-get-read-timeout.md](agent-wiki/2026-10-23-hf-get-read-timeout.md) | #549, #550, #435, #339 |
| 2026-10-23 | the fix-bot is woken by the failure it repairs (#538) | [2026-10-23-fix-bot-retrigger.md](agent-wiki/2026-10-23-fix-bot-retrigger.md) | #538, #533 |
| 2026-10-23 | a PR with no checks does not kill the fix-bot sweep (#496) | [2026-10-23-fix-bot-no-checks.md](agent-wiki/2026-10-23-fix-bot-no-checks.md) | #496, #527, #497, #530 |
| 2026-10-23 | wait for `mergeable` instead of deferring on UNKNOWN (#558) | [2026-10-23-auto-merge-settle-unknown.md](agent-wiki/2026-10-23-auto-merge-settle-unknown.md) | #558, #552, #546 |
| 2026-10-23 | a deferral is retried, not parked (#545) | [2026-10-23-auto-merge-recheck-deferred.md](agent-wiki/2026-10-23-auto-merge-recheck-deferred.md) | #545, #541 |
| 2026-10-23 | the auto-merge sweep's cron was never going to fire (#560) | [2026-10-23-auto-merge-cron-odd-minutes.md](agent-wiki/2026-10-23-auto-merge-cron-odd-minutes.md) | #560, #562, #546, #275 |
| 2026-10-23 | The rename rule reaches the writer | [2026-10-23-architecture-bot-rename-guard.md](agent-wiki/2026-10-23-architecture-bot-rename-guard.md) | #573, #574, #572, #251 |
| 2026-10-23 | unattended agents never ask (#543) | [2026-10-23-agents-never-ask.md](agent-wiki/2026-10-23-agents-never-ask.md) | #543, #202 |
| 2026-10-22 | Strata's live download checks leave the hermetic unit gate (#437) | [2026-10-22-strata-download-live-target.md](agent-wiki/2026-10-22-strata-download-live-target.md) | #437, #438, #519 |
| 2026-10-22 | The rebase gate mounts the checkout | [2026-10-22-rebase-gate-mount.md](agent-wiki/2026-10-22-rebase-gate-mount.md) | #505, #506, #498 |
| 2026-10-22 | A comment is not a claim | [2026-10-22-rebase-behind-despite-comment.md](agent-wiki/2026-10-22-rebase-behind-despite-comment.md) | #501, #502, #498 |
| 2026-10-22 | a close queues the canonical issue it cites (#521) | [2026-10-22-issue-bot-queue-canonical.md](agent-wiki/2026-10-22-issue-bot-queue-canonical.md) | #521, #440, #399, #254 |
| 2026-10-22 | The guard admits the repository's own bot on a same-repo head | [2026-10-22-guard-repo-bot-same-repo-head.md](agent-wiki/2026-10-22-guard-repo-bot-same-repo-head.md) | #510, #511, #495, #480 |
| 2026-10-22 | a bot's PR is validated and can be approved (#497, #529) | [2026-10-22-bot-pr-ci-and-approval.md](agent-wiki/2026-10-22-bot-pr-ci-and-approval.md) | #497, #529, #527, #412 |
| 2026-10-22 | Auto-merge: who may open the PR | [2026-10-22-auto-merge-who-may-open.md](agent-wiki/2026-10-22-auto-merge-who-may-open.md) | #499, #500, #481, #492 |
| 2026-10-22 | wait for the approval to take effect (#531) | [2026-10-22-auto-merge-wait-for-approval.md](agent-wiki/2026-10-22-auto-merge-wait-for-approval.md) | #531, #524, #525, #530 |
| 2026-10-22 | The merge job finds a fork PR | [2026-10-22-auto-merge-resolve-pr.md](agent-wiki/2026-10-22-auto-merge-resolve-pr.md) | #503, #504, #502 |
| 2026-10-22 | A finished fork run is resolved back to its PR | [2026-10-22-auto-merge-resolve-fork-pr.md](agent-wiki/2026-10-22-auto-merge-resolve-fork-pr.md) | #508, #509, #506, #504 |
| 2026-10-22 | auto-merge asks `gh pr view` only for fields it has (#513) | [2026-10-22-auto-merge-gh-view-fields.md](agent-wiki/2026-10-22-auto-merge-gh-view-fields.md) | #513 |
| 2026-10-22 | approve as the other identity, then merge (#524) | [2026-10-22-auto-merge-approve-first.md](agent-wiki/2026-10-22-auto-merge-approve-first.md) | #524, #523, #491, #513 |
| 2026-10-21 | `make worktree-prune` — remove the worktrees and branches whose PR already merged | [2026-10-21-worktree-prune.md](agent-wiki/2026-10-21-worktree-prune.md) | #431, #436, #432, #433 |
| 2026-10-21 | The unit gate is hermetic: live-Hub work gets its own target | [2026-10-21-unit-gate-hermetic.md](agent-wiki/2026-10-21-unit-gate-hermetic.md) | #438 |
| 2026-10-21 | the weekly registry sync is blocked by a loss in the upstream store (issue #525) | [2026-10-21-registry-sync-upstream-loss.md](agent-wiki/2026-10-21-registry-sync-upstream-loss.md) | #525, #487 |
| 2026-10-21 | rebase-bot: decide from a COMPUTED merge state (issue #453) | [2026-10-21-rebase-bot-unknown-state.md](agent-wiki/2026-10-21-rebase-bot-unknown-state.md) | #453, #445, #446, #447 |
| 2026-10-21 | eligibility is the merge state, not "already rebased today" (issue #467) | [2026-10-21-rebase-bot-stale-again.md](agent-wiki/2026-10-21-rebase-bot-stale-again.md) | #467, #447, #448, #458 |
| 2026-10-21 | the rebase bot's structural gate really gates the push (issue #455) | [2026-10-21-rebase-bot-real-gates.md](agent-wiki/2026-10-21-rebase-bot-real-gates.md) | #455, #484 |
| 2026-10-21 | rebase-bot reaches its conflict agent while the Makefile is conflicted (issue #460) | [2026-10-21-rebase-bot-make-snapshot.md](agent-wiki/2026-10-21-rebase-bot-make-snapshot.md) | #460, #446, #461 |
| 2026-10-21 | rebase-bot reads its DONE marker, not any comment (issue #457) | [2026-10-21-rebase-bot-done-marker.md](agent-wiki/2026-10-21-rebase-bot-done-marker.md) | #457, #454, #446, #447 |
| 2026-10-21 | one rebase-bot run drains every eligible PR (issue #462) | [2026-10-21-rebase-bot-all-prs.md](agent-wiki/2026-10-21-rebase-bot-all-prs.md) | #462, #446, #447, #448 |
| 2026-10-21 | a failed rebase leaves a clean tree for the next decision (issue #464) | [2026-10-21-rebase-bot-actor-abort.md](agent-wiki/2026-10-21-rebase-bot-actor-abort.md) | #464, #463, #460, #465 |
| 2026-10-21 | A manual `issue-bot` run with no issue number picks one itself | [2026-10-21-issue-bot-manual-pick.md](agent-wiki/2026-10-21-issue-bot-manual-pick.md) | #472, #1234, #471 |
| 2026-10-21 | the issue-bot's implement leg has a budget and salvages its work (issue #476) | [2026-10-21-issue-bot-budget-salvage.md](agent-wiki/2026-10-21-issue-bot-budget-salvage.md) | #476, #486 |
| 2026-10-21 | `make hermes-smoke` proves the tool calling every bot leg depends on | [2026-10-21-hermes-smoke-tool-call.md](agent-wiki/2026-10-21-hermes-smoke-tool-call.md) | #407, #439, #426, #427 |
| 2026-10-21 | `hermes-smoke` runs first and judges the store it created | [2026-10-21-hermes-smoke-fresh-store.md](agent-wiki/2026-10-21-hermes-smoke-fresh-store.md) | #471, #472, #358, #359 |
| 2026-10-21 | the fix-bot can select the repository's own fork (issue #340) | [2026-10-21-fix-bot-fork-sweep.md](agent-wiki/2026-10-21-fix-bot-fork-sweep.md) | #340, #477 |
| 2026-10-21 | The bots' run inputs are ignored by construction, not by a denylist | [2026-10-21-bot-scratch-ignored.md](agent-wiki/2026-10-21-bot-scratch-ignored.md) | #427, #407, #424, #428 |
| 2026-10-21 | Each bot write runs with the token that can perform it | [2026-10-21-bot-pr-token-split.md](agent-wiki/2026-10-21-bot-pr-token-split.md) | #430, #420, #424 |
| 2026-10-21 | A bot PR's description comes from the run | [2026-10-21-bot-pr-body-from-run.md](agent-wiki/2026-10-21-bot-pr-body-from-run.md) | #429, #424, #427 |
| 2026-10-21 | The bot's implementer edits the mounted tree in place | [2026-10-21-bot-implement-in-place.md](agent-wiki/2026-10-21-bot-implement-in-place.md) | #426, #428 |
| 2026-10-21 | "Implemented" is measured from the tree, not from the exit code | [2026-10-21-bot-changed-from-tree.md](agent-wiki/2026-10-21-bot-changed-from-tree.md) | #428, #424, #407, #427 |
| 2026-10-21 | The merge runs where the secrets are: `auto-merge` is a `workflow_run` workflow | [2026-10-21-auto-merge-workflow-run.md](agent-wiki/2026-10-21-auto-merge-workflow-run.md) | #493, #491, #481 |
| 2026-10-21 | A green PR blocked only by a review is approved by the other identity — and every deferral is on the PR | [2026-10-21-auto-merge-review-approve.md](agent-wiki/2026-10-21-auto-merge-review-approve.md) | #491, #489, #481 |
| 2026-10-21 | A green, conflict-free PR is merged by CI | [2026-10-21-auto-merge-green-prs.md](agent-wiki/2026-10-21-auto-merge-green-prs.md) | #482 |
| 2026-10-21 | The auto-merge job accepts the owner's fork as a PR head | [2026-10-21-auto-merge-fork-head.md](agent-wiki/2026-10-21-auto-merge-fork-head.md) | #488, #483, #481 |
| 2026-10-21 | a lost GitHub answer no longer strands an architecture refresh (issue #479) | [2026-10-21-architecture-bot-pr-retry.md](agent-wiki/2026-10-21-architecture-bot-pr-retry.md) | #479, #478, #480, #481 |
| 2026-10-21 | architecture bot keeps docs/ARCHITECTURE.md current (issue #449) | [2026-10-21-architecture-bot.md](agent-wiki/2026-10-21-architecture-bot.md) | #449, #451, #269, #248 |
| 2026-10-21 | the agent image can publish: GITHUB_TOKEN, not the owner PAT | [2026-10-21-agent-image-ghcr-credential.md](agent-wiki/2026-10-21-agent-image-ghcr-credential.md) | #413, #441, #335, #435 |
| 2026-10-20 | The masked web reach is deployed: a bot leg uses it, and the URLs are checked | [2026-10-20-web-reach-deploy.md](agent-wiki/2026-10-20-web-reach-deploy.md) | #380, #357, #362, #402 |
| 2026-10-20 | The loop's fast suite is a named group in the roster, not a hand-list (issue #403) | [2026-10-20-unit-suite-fast-group.md](agent-wiki/2026-10-20-unit-suite-fast-group.md) | #403, #393, #397 |
| 2026-10-20 | The hermetic unit suite is discovered, never enumerated (issue #393) | [2026-10-20-unit-suite-aggregator.md](agent-wiki/2026-10-20-unit-suite-aggregator.md) | #393, #392, #395 |
| 2026-10-20 | The TensorFold suites stop assuming the skill pip-installs itself (issue #389) | [2026-10-20-tensorfold-kind-tests.md](agent-wiki/2026-10-20-tensorfold-kind-tests.md) | #389, #386, #388, #373 |
| 2026-10-20 | The Strata bump stopped dying on a family that has no Hub URL | [2026-10-20-strata-family-without-hub.md](agent-wiki/2026-10-20-strata-family-without-hub.md) | #416 |
| 2026-10-20 | `make secret-scan` reads the committable set, not the whole filesystem | [2026-10-20-secret-scan-committable.md](agent-wiki/2026-10-20-secret-scan-committable.md) | #382, #357, #360, #398 |
| 2026-10-20 | The registry states a footprint, and llgenie reads it | [2026-10-20-registry-contract-sync.md](agent-wiki/2026-10-20-registry-contract-sync.md) | #414, #463 |
| 2026-10-20 | Every target is declared `.PHONY` — and the guard that keeps it that way | [2026-10-20-phony-targets.md](agent-wiki/2026-10-20-phony-targets.md) | #392 |
| 2026-10-20 | The issue-bot's 3-per-day cap counts its own PRs | [2026-10-20-issue-bot-cap-by-branch.md](agent-wiki/2026-10-20-issue-bot-cap-by-branch.md) | #409 |
| 2026-10-20 | One Hub GET, one bounded transient budget (issue #339, part of it) | [2026-10-20-hub-transient-budget.md](agent-wiki/2026-10-20-hub-transient-budget.md) | #339, #256, #372 |
| 2026-10-20 | A gated Hub file is not a dead link | [2026-10-20-catalog-gated-link.md](agent-wiki/2026-10-20-catalog-gated-link.md) | #418, #463 |
| 2026-10-20 | A bot's write now uses the credential that can make it | [2026-10-20-bot-write-credential.md](agent-wiki/2026-10-20-bot-write-credential.md) | #412, #136, #340, #409 |
| 2026-10-20 | The bots run DeepSeek V4.1 Flash 1017, and the pin cannot drift again | [2026-10-20-bot-model-1017.md](agent-wiki/2026-10-20-bot-model-1017.md) | #405, #410, #408, #406 |
| 2026-10-19 | A release-archive install tracks {prefix}/current so the native state can be outdated (#386) | [2026-10-19-tensorfold-archive-current.md](agent-wiki/2026-10-19-tensorfold-archive-current.md) | #386, #114, #373 |
| 2026-10-19 | the secret-output guard catches the two whole-stdout shapes (#361) | [2026-10-19-secret-whole-stdout.md](agent-wiki/2026-10-19-secret-whole-stdout.md) | #361, #357, #360, #359 |
| 2026-10-19 | a committed credential VALUE is scanned, and the scanner is tested (#360) | [2026-10-19-secret-scan.md](agent-wiki/2026-10-19-secret-scan.md) | #360, #368, #357, #358 |
| 2026-10-19 | every bot leg refuses to start on a missing key (#363) | [2026-10-19-require-env-guard.md](agent-wiki/2026-10-19-require-env-guard.md) | #363, #370, #357, #349 |
| 2026-10-19 | the implementer leg's GH_TOKEN is set, and the rule that catches the next one (#364) | [2026-10-19-issue-bot-ghtoken.md](agent-wiki/2026-10-19-issue-bot-ghtoken.md) | #364, #371, #357, #358 |
| 2026-10-19 | The Firecrawl key joins the ONE credential list | [2026-10-19-firecrawl-secret-vars.md](agent-wiki/2026-10-19-firecrawl-secret-vars.md) | #379, #357, #362, #369 |
| 2026-10-19 | The masked web reach runs in CI, on the repository secret | [2026-10-19-firecrawl-ci-smoke.md](agent-wiki/2026-10-19-firecrawl-ci-smoke.md) | #381, #362, #357, #380 |
| 2026-10-19 | The engine smoke fetches its model through the one downloader (issue #385) | [2026-10-19-engine-smoke-throttle.md](agent-wiki/2026-10-19-engine-smoke-throttle.md) | #385, #374, #372, #339 |
| 2026-10-19 | the agent's masked web reach (#362) | [2026-10-19-agent-web-reach.md](agent-wiki/2026-10-19-agent-web-reach.md) | #362, #369, #357, #358 |
| 2026-10-19 | the credential reaches the AGENT's shell (issue #358) | [2026-10-19-agent-shell-keys.md](agent-wiki/2026-10-19-agent-shell-keys.md) | #358, #365, #357, #155 |
| 2026-10-19 | the agent's transcript is redacted before it prints (issue #359) | [2026-10-19-agent-log-redaction.md](agent-wiki/2026-10-19-agent-log-redaction.md) | #359, #366, #357, #361 |
| 2026-10-17 | 2026-10-17 card-aware engine ranking (issue #225) | [2026-10-17-card-aware-engine-rank.md](agent-wiki/2026-10-17-card-aware-engine-rank.md) | #225, #337, #227, #354 |
| 2026-10-16 | workflow-flow-targets — a `Flow:` header must name targets that exist (issue #323) | [2026-10-16-workflow-flow-targets.md](agent-wiki/2026-10-16-workflow-flow-targets.md) | #323, #335 |
| 2026-10-16 | A run-failure reactor: a red run becomes a fix or a deduped issue (#286) | [2026-10-16-run-failure-reactor.md](agent-wiki/2026-10-16-run-failure-reactor.md) | #286, #222, #107, #279 |
| 2026-10-16 | refiner-secrets-wiring — remove the never-used OPENROUTER/OPENCODE keys (issue #311) | [2026-10-16-refiner-secrets-wiring.md](agent-wiki/2026-10-16-refiner-secrets-wiring.md) | #311 |
| 2026-10-16 | PR bodies and commit messages state the issue, the fix and the benefit (#313) | [2026-10-16-pr-message-substance.md](agent-wiki/2026-10-16-pr-message-substance.md) | #313, #315 |
| 2026-10-16 | A PR's commits are authored by Andy Holst or Asimov Agent — and by no one else (#345) | [2026-10-16-pr-commit-authors.md](agent-wiki/2026-10-16-pr-commit-authors.md) | #345, #351, #346, #170 |
| 2026-10-16 | A PR closes the issue it implements — the closing rule loses its loophole (#324) | [2026-10-16-pr-closes-issue.md](agent-wiki/2026-10-16-pr-closes-issue.md) | #324, #328, #258, #290 |
| 2026-10-16 | loop-test-host-install (#317) | [2026-10-16-loop-test-host-install.md](agent-wiki/2026-10-16-loop-test-host-install.md) | #317, #296, #299, #305 |
| 2026-10-16 | issue-cleaner: close the issues a merged PR already implemented | [2026-10-16-issue-cleaner.md](agent-wiki/2026-10-16-issue-cleaner.md) | #325, #256, #344, #339 |
| 2026-10-16 | inline-check-all-steps (#305) | [2026-10-16-inline-check-all-steps.md](agent-wiki/2026-10-16-inline-check-all-steps.md) | #305, #296, #299, #293 |
| 2026-10-16 | One live-Hub probe, with a bounded retry and a legible cause (#256) | [2026-10-16-hub-probe-retry.md](agent-wiki/2026-10-16-hub-probe-retry.md) | #256, #339, #122, #305 |
| 2026-10-16 | The write-level guard rule reads the `case` arm (#306, from #300 / #295) | [2026-10-16-guard-write-level-arm.md](agent-wiki/2026-10-16-guard-write-level-arm.md) | #306, #300, #295, #122 |
| 2026-10-16 | A workflow GitHub refused, and the gate that stops the next one (#330, #329) | [2026-10-16-check-workflows.md](agent-wiki/2026-10-16-check-workflows.md) | #330, #329, #331 |
| 2026-10-16 | bot-decision-loud — a crashed bot decision must fail the step (issue #312) | [2026-10-16-bot-decision-loud.md](agent-wiki/2026-10-16-bot-decision-loud.md) | #312, #310, #316, #302 |
| 2026-10-16 | The agent-image push pre-flight (#335) | [2026-10-16-agent-image-push-check.md](agent-wiki/2026-10-16-agent-image-push-check.md) | #335, #323, #336, #117 |
| 2026-10-15 | One trigger guard for every dispatchable workflow (#295) | [2026-10-15-workflow-guards.md](agent-wiki/2026-10-15-workflow-guards.md) | #295, #122, #107 |
| 2026-10-15 | No secret value reaches a log — for every key, not just the JEV one (#283) | [2026-10-15-secret-output-guard.md](agent-wiki/2026-10-15-secret-output-guard.md) | #283, #238, #282 |
| 2026-10-15 | issue #319: the registry sync validates the registry it synced | [2026-10-15-registry-sync-validate-scope.md](agent-wiki/2026-10-15-registry-sync-validate-scope.md) | #319, #318 |
| 2026-10-15 | issue #314: the issue-refiner's pick runs again, and its failure is loud | [2026-10-15-refiner-valid-argv.md](agent-wiki/2026-10-15-refiner-valid-argv.md) | #314, #268, #91, #311 |
| 2026-10-15 | issue #309: the rebase bot's sweep runs again, and its failure is loud | [2026-10-15-rebase-sweep-valid.md](agent-wiki/2026-10-15-rebase-sweep-valid.md) | #309, #170, #308, #310 |
| 2026-10-15 | The queued-run alarm now reports somewhere a human reads (#294) | [2026-10-15-queued-alarm-delivery.md](agent-wiki/2026-10-15-queued-alarm-delivery.md) | #294, #254, #296 |
| 2026-10-15 | A non-blocking JEV layer must still be visible in the run (issue #238) | [2026-10-15-jev-visible.md](agent-wiki/2026-10-15-jev-visible.md) | #238, #265 |
| 2026-10-15 | The JEV signal must not overstate itself, and the docs must match the armed gate (#284) | [2026-10-15-jev-annotation-truth.md](agent-wiki/2026-10-15-jev-annotation-truth.md) | #284 |
| 2026-10-15 | The inline-script check was per step block, so a `gh` step could hide a script call (#296) | [2026-10-15-inline-check-per-line.md](agent-wiki/2026-10-15-inline-check-per-line.md) | #296, #293, #295, #305 |
| 2026-10-15 | issue #307: the code-review bot's report must equal what it files | [2026-10-15-code-review-truthful.md](agent-wiki/2026-10-15-code-review-truthful.md) | #307, #308, #305 |
| 2026-10-15 | A claim now carries its own terms, and a dead run releases it (#291, #292) | [2026-10-15-claim-lifecycle.md](agent-wiki/2026-10-15-claim-lifecycle.md) | #291, #292, #279, #285 |
| 2026-10-15 | A push to a PR terminates the run it supersedes (#288) | [2026-10-15-ci-cancel-superseded.md](agent-wiki/2026-10-15-ci-cancel-superseded.md) | #288, #254, #275, #287 |
| 2026-10-15 | Bots sync with upstream `main` before they start work | [2026-10-15-bot-sync-before-work.md](agent-wiki/2026-10-15-bot-sync-before-work.md) | #303, #246, #9 |
| 2026-10-15 | the bot-slot guard derives its scope (issue #301) | [2026-10-15-bot-slot-guard-scope.md](agent-wiki/2026-10-15-bot-slot-guard-scope.md) | #301, #275, #246, #264 |
| 2026-10-15 | Each bot on its own pipeline: a unique cron slot, its own concurrency group | [2026-10-15-bot-pipeline-isolation.md](agent-wiki/2026-10-15-bot-pipeline-isolation.md) | #275, #271, #272, #261 |
| 2026-10-14 | the wiring guard (issue #237) | [2026-10-14-wiring-guard.md](agent-wiki/2026-10-14-wiring-guard.md) | #237, #234, #239, #238 |
| 2026-10-14 | 2026-10-14 vendored registry is additive only (issue #233) | [2026-10-14-trending-registry-additive-only.md](agent-wiki/2026-10-14-trending-registry-additive-only.md) | #233, #114, #115, #113 |
| 2026-10-14 | the CLI is named after the project: the module is `scripts/llgenie_serve.py` (#251) | [2026-10-14-rename-llgenie-serve.md](agent-wiki/2026-10-14-rename-llgenie-serve.md) | #251, #82 |
| 2026-10-14 | The rebase bot: keep every open PR on `main`, one PR per run (issue #246) | [2026-10-14-rebase-bot.md](agent-wiki/2026-10-14-rebase-bot.md) | #246, #107, #257 |
| 2026-10-14 | the PR fix-bot: repair a red PR, re-check, never merge (#222) | [2026-10-14-pr-fix-bot.md](agent-wiki/2026-10-14-pr-fix-bot.md) | #222 |
| 2026-10-14 | KV cache sizing: every documented type, no silent fp16 (issue #247) | [2026-10-14-kv-quant-bytes.md](agent-wiki/2026-10-14-kv-quant-bytes.md) | #247, #245 |
| 2026-10-14 | The issue-refiner: make the backlog implementable on the spare capacity (issue #263, PR #264) | [2026-10-14-issue-refiner.md](agent-wiki/2026-10-14-issue-refiner.md) | #263, #264, #248, #261 |
| 2026-10-14 | The issue bot reads the whole thread and decides: implement / refine / close (issue #261, PR #262) | [2026-10-14-issue-bot-triage.md](agent-wiki/2026-10-14-issue-bot-triage.md) | #261, #262, #248, #257 |
| 2026-10-14 | The issue implementer never dispatched: two real-CLI bugs in the same call | [2026-10-14-issue-bot-dispatch-gh-argv.md](agent-wiki/2026-10-14-issue-bot-dispatch-gh-argv.md) | #261, #264, #260, #91 |
| 2026-10-14 | the unskilled-engine gap (issue #229) | [2026-10-14-engine-skill-gap.md](agent-wiki/2026-10-14-engine-skill-gap.md) | #229, #228, #219, #103 |
| 2026-10-14 | Documentation is part of the change: README + agent-wiki, guarded (issue #257, PR #258) | [2026-10-14-docs-mandate.md](agent-wiki/2026-10-14-docs-mandate.md) | #257, #258, #253 |
| 2026-10-14 | Every dispatchable workflow now states the work it will do (#276) | [2026-10-14-dispatch-forms.md](agent-wiki/2026-10-14-dispatch-forms.md) | #276, #270, #269, #274 |
| 2026-10-14 | A code-review bot: read the tree and the pipelines, and file what is wrong (#269) | [2026-10-14-code-review-bot.md](agent-wiki/2026-10-14-code-review-bot.md) | #269 |
| 2026-10-14 | the installed launcher's dry-run argument grid (issue #236) | [2026-10-14-cli-dry-run-grid.md](agent-wiki/2026-10-14-cli-dry-run-grid.md) | #236 |
| 2026-10-14 | How the bots stay out of each other's way: claims on the issue | [2026-10-14-bot-claims.md](agent-wiki/2026-10-14-bot-claims.md) | #261, #263 |
| 2026-10-14 | The JEV decision layer inside the agent container (issue #238, PR #265) | [2026-10-14-agent-nerve-jev.md](agent-wiki/2026-10-14-agent-nerve-jev.md) | #238, #265 |
| 2026-10-13 | 2026-10-13 weekly registry sync (issue #179) | [2026-10-13-weekly-registry-sync.md](agent-wiki/2026-10-13-weekly-registry-sync.md) | #179 |
| 2026-10-13 | 2026-10-13 registry-sync engine identity (issue #223, merged PR #224) | [2026-10-13-registry-sync-engine-identity.md](agent-wiki/2026-10-13-registry-sync-engine-identity.md) | #223, #224, #226, #225 |
| 2026-10-13 | engine-bump-rebase import | [2026-10-13-engine-bump-rebase-import.md](agent-wiki/2026-10-13-engine-bump-rebase-import.md) | #214 |
| 2026-10-13 | engine-bump-rebase guard | [2026-10-13-engine-bump-rebase-guard.md](agent-wiki/2026-10-13-engine-bump-rebase-guard.md) | #212 |
| 2026-10-13 | 2026-10-13 analysis → issues, never implementation (issue #231) | [2026-10-13-agents-debt-analysis-issue-only.md](agent-wiki/2026-10-13-agents-debt-analysis-issue-only.md) | #231, #223, #224, #225 |
| 2026-10-13 | each agent, own worktree | [2026-10-13-agent-own-worktree.md](agent-wiki/2026-10-13-agent-own-worktree.md) | #216 |
| 2026-10-12 | Top-tier dry-run budget | [2026-10-12-top-tier-dry-run-budget.md](agent-wiki/2026-10-12-top-tier-dry-run-budget.md) | #180 |
| 2026-10-12 | Forward GITHUB_TOKEN into the test containers | [2026-10-12-forward-github-token.md](agent-wiki/2026-10-12-forward-github-token.md) | #199 |
| 2026-10-12 | Engine push requires the binary | [2026-10-12-engine-push-requires-binary.md](agent-wiki/2026-10-12-engine-push-requires-binary.md) | #204, #106 |
| 2026-10-12 | Engine bump regen is real | [2026-10-12-engine-bump-regen-is-real.md](agent-wiki/2026-10-12-engine-bump-regen-is-real.md) | #192 |
| 2026-10-12 | 2026-10-12 engine bump destination release | [2026-10-12-engine-bump-destination-release.md](agent-wiki/2026-10-12-engine-bump-destination-release.md) | #171, #165, #166, #167 |
| 2026-10-12 | Engine bump dependencies | [2026-10-12-engine-bump-dependencies.md](agent-wiki/2026-10-12-engine-bump-dependencies.md) | #186, #187 |
| 2026-10-12 | bump PR publish order (issue #169, OpenSpec fix-bump-pr-install-pull-order) | [2026-10-12-bump-pr-publish-order.md](agent-wiki/2026-10-12-bump-pr-publish-order.md) | #169, #130, #168, #120 |
| 2026-10-11 | 2026-10-11 Hub tree listing over IPv4 | [2026-10-11-hub-tree-ipv4.md](agent-wiki/2026-10-11-hub-tree-ipv4.md) | #161, #154 |
| 2026-10-11 | 2026-10-11 HF token on every Hub call | [2026-10-11-hf-token-actions-secret.md](agent-wiki/2026-10-11-hf-token-actions-secret.md) | #153, #154 |
| 2026-10-11 | bump PR body newlines, pin-assert rewrite, damaged-GGUF refetch | [2026-10-11-fix-engine-bump-pr-body.md](agent-wiki/2026-10-11-fix-engine-bump-pr-body.md) | #145, #144 |
| 2026-10-11 | cuda CDI needs /dev/nvidia-modeset (issue #157) | [2026-10-11-fix-cuda-nvidia-modeset.md](agent-wiki/2026-10-11-fix-cuda-nvidia-modeset.md) | #157 |
| 2026-10-11 | 2026-10-11 engine bump install kind | [2026-10-11-engine-bump-install-kind.md](agent-wiki/2026-10-11-engine-bump-install-kind.md) | #151, #152 |
| 2026-10-10 | 2026-10-10 pick-vram-ram-matrix-tests | [2026-10-10-pick-vram-ram-matrix-tests.md](agent-wiki/2026-10-10-pick-vram-ram-matrix-tests.md) | #122, #120, #124, #123 |
| 2026-10-10 | 2026-10-10 llgenie macos / install pipeline — fixed green | [2026-10-10-macos-install-pipeline-green.md](agent-wiki/2026-10-10-macos-install-pipeline-green.md) | #121, #120 |
| 2026-10-09 | 2026-10-09 macOS pipeline parity (#120) | [2026-10-09-macos-parity-install.md](agent-wiki/2026-10-09-macos-parity-install.md) | #120, #121 |
| 2026-10-07 | 2026-10-07 fix-macos-make-install (issue #112, PR #113) | [2026-10-07-fix-macos-make-install.md](agent-wiki/2026-10-07-fix-macos-make-install.md) | #112, #113 |
| 2026-10-05 | engine skills (issue #98) | [2026-10-05-issue98-engine-skills.md](agent-wiki/2026-10-05-issue98-engine-skills.md) | #98 |
| 2026-09-27 | server-variant jobs run as a matrix | [2026-09-27-server-variant-matrix.md](agent-wiki/2026-09-27-server-variant-matrix.md) | #90 |
| 2026-09-26 | 2026-09-26 model context window | [2026-09-26-model-context-window.md](agent-wiki/2026-09-26-model-context-window.md) | #84 |
| 2026-09-25 | issue #82: rename llama-ai → llgenie | [2026-09-25-issue82-rename-llama-ai-to-llgenie.md](agent-wiki/2026-09-25-issue82-rename-llama-ai-to-llgenie.md) | #82, #83 |
| 2026-09-08 | Issue #73 — doubled tick boundary straddle (fixed) | [2026-09-08-issue73-tick-boundary-straddle.md](agent-wiki/2026-09-08-issue73-tick-boundary-straddle.md) | #73, #25, #27, #30 |
| 2026-09-08 | issue #69 follow-up: close the openspec-tasks CI gate gap | [2026-09-08-issue69-openspec-tasks-ci-gate-gap.md](agent-wiki/2026-09-08-issue69-openspec-tasks-ci-gate-gap.md) | #69, #70 |
| 2026-09-08 | issue #62: doubled-tick TOCTOU in the hold-for-interval tick lock | [2026-09-08-issue62-atomic-tick-lock-toctou.md](agent-wiki/2026-09-08-issue62-atomic-tick-lock-toctou.md) | #62, #27, #30, #71 |
| 2026-09-08 | issue #61: `--download-top-tier --family <keyword>` | [2026-09-08-issue61-top-tier-family-keyword.md](agent-wiki/2026-09-08-issue61-top-tier-family-keyword.md) | #61 |
| 2026-09-07 | project overview snapshot (full-repo survey) | [2026-09-07-project-overview-snapshot.md](agent-wiki/2026-09-07-project-overview-snapshot.md) | #53, #58, #56, #55 |
| 2026-09-05 | 2026-09-05 top-tier-trending-download | [2026-09-05-top-tier-trending-download.md](agent-wiki/2026-09-05-top-tier-trending-download.md) | #49, #50 |
| 2026-08-26 | issue #46: repair spawn reuses existing branch/worktree | [2026-08-26-issue46-repair-spawn-reuse-worktree.md](agent-wiki/2026-08-26-issue46-repair-spawn-reuse-worktree.md) | #46, #47, #9 |
