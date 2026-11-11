# llgenie specifics for worktree/branch hygiene

## The audit in this repo

```bash
gh pr list --repo asimov-agent/llgenie --state all --limit 500 \
  --json number,state,headRefName,mergeCommit
make worktree-prune DRY=1        # the plan: one line per branch with its reason
make worktree-prune              # apply (SLUG= picks the owner/name, BASE= the base ref)
```

`make worktree-prune` (`scripts/worktree_prune.py`) is the supported path: it reads state from GitHub,
proves the merge with `git merge-base --is-ancestor`, removes with `git worktree remove` and deletes
with `git branch -D`, and exits 2 on a failed lookup, a locked worktree or a failed branch deletion.
`REPO` in this Makefile is `$(shell pwd)`, so a slug seam must be its own variable (`SLUG=`) — a
recipe written as `$(if $(REPO),$(REPO),asimov-agent/llgenie)` always reaches `gh` as an absolute path
and fails its `OWNER/REPO` format check.

## Gate order that keeps a PR from going red on process

1. Tick every box in `openspec/changes/<name>/tasks.md` **in the code commit**. `make
   openspec-tasks-check` runs in the `openspec` CI job (Linux **and** macOS) and fails on one
   `- [ ]`, naming the line number.
2. `make openspec-validate NAME=<name>`, `make check-wiring`, `make check-docs`, `make lint`,
   `make check-pr-hygiene`, `make check-pr-authors`.
3. `make test-unit` — the whole discovered suite in the test image, ~12–13 min, ~4,900 tests. Iterate
   on a single file first with the `--user "$(id -u):$(id -g)" -e HOME=/tmp` container form (the host
   python has no pytest).
4. Rebase onto `origin/main`, `git push --force-with-lease fork feat/<kebab>`, then confirm
   `git rev-list --count HEAD..origin/main` prints `0` — a behind PR cannot merge.

## Adding a target / gate (the four gates a new make target must satisfy)

A new verification step is not done when its recipe works — four repo gates read it, and each fails in
a different file:

1. **`.PHONY`** — a target that produces no file of its own name must be declared, or a stray file of
   that name makes `make` print "up to date" and verify nothing (`check-wiring`).
2. **`scripts/issue_bot_gates.py`** — a gate newly added to `ci-unit` must be classified there, or
   `tests/test_issue_bot_gates.py::test_the_real_tree_is_wired` reds. Put it in **`DEFERRED`** with a
   one-line reason; do **not** add it to `FAST_GATES`, whose exact membership is asserted by another
   test as a deliberate contract.
3. **`check-docs`** — a user-facing target (any `##` help line) must be named in `README.md` or a
   `docs/` page the README links, or recorded in `tests/fixtures/docs-exceptions.json`. Prefer a
   section in the relevant `docs/*.md` plus one table row in `README.md`.
4. **`check-wiring`'s CI-coverage claim** — a help line that says "CI" must be reached by a `make`
   call some workflow makes. If the real caller goes through a different target (a `ci-*` target that
   calls the script directly), reword the help line instead of inventing a second call path.

Before a change that rewrites a string across many files (pinning `uses:` refs, renaming a target),
`grep -rn '<literal>' tests/ scripts/` first: tests that assert the literal string go red on the
rewrite and need a pattern instead.

## Flakes that are not yours

Before believing a red is external, read `tests/fixtures/unit-suite.json` (`deselect`, `excluded`): the
repo moves live-network checks out of the hermetic gate over time, so a flake from last week may no
longer be in `make test-unit` at all. The current live checks run as `make test-hub-live`.

- `tests/test_trend_pick.py::test_readme_links_answer_and_a_broken_copy_is_caught`: one live request
  per README link, so a single Hub 429 reds the whole unit gate under load and passes alone in seconds.
  The rule for that check: every link goes through `hf_auth.hub_open` (the repo's ONE retry/throttle
  policy) and a Hub model page is asked at `/api/models/<org>/<repo>` WITH the token instead of the
  HTML page, whose token-bearing GET is exactly what the Hub answers with a 429. A link check that
  builds its own `urlopen` and its own 5xx-only ladder re-acquires that flake.
- `macos / top-tier`: live-Hub `TimeoutError: The read operation timed out` in
  `test_top_tier_acceptance.py` (`dry run must exit 0`). This one is NOT purely external: the top-tier
  discovery GET retried `HTTPError`/`URLError` only, and a READ-phase socket timeout is the builtin
  `TimeoutError` (not a `URLError` subclass) — so one slow read escaped the retry loop as a traceback.
  Fixed at the seam; a stall that the retry budget absorbs is now a retried call, not a red job. Only a
  stall that outlives the whole budget is left as a live-network flake.
- Triage rule: re-run the job, cite the tracking issue in the PR body, keep your change clear of it.
  Never "fix" an unrelated flake inside a feature PR.

## After the PR merges

```bash
git fetch --all --prune && git pull --ff-only          # the main checkout, not a worktree
git worktree add --detach ../llgenie-wt/retest-main-<sha> origin/main
cd ../llgenie-wt/retest-main-<sha> && make test-unit   # ~12–13 min, ~4,900 tests
make lint check-wiring check-docs check-pr-hygiene check-pr-authors openspec-tasks-check
make worktree-prune DRY=1                              # dogfood the merged target; lists merged trees
```

A merge that touched `Makefile`/`README.md` (bots do this) can break `check-docs`/`check-wiring` for
someone else's target — run them on the pulled base before reporting the merge as healthy. Keep the
worktree `--detach`ed so nothing claims a branch, and remove it afterwards.

## Proving the vendored-registry sync still lands

`data/models.json` is a verbatim copy of `andyholst/trending-local-llms`'s `data/models.json` (its
README is copied alongside as `data/trending-README.md`). The weekly `registry-sync` job is the only
writer, and it patches NOTHING upstream — upstream data is never edited to make a sync pass. The same
job regenerates the derived artifacts: `data/trending-quant-catalog.json` + its fixture,
`tests/fixtures/trend-list-matrix.json`, `data/engine-skill-gap.json`.

Run the job's own step order in a THROWAWAY DETACHED worktree (the sync rewrites tracked data — never
the feature worktree, never the user's checkout) and report each real exit code; the FIRST red is the
finding:

```bash
git worktree add --detach ../llgenie-wt/sync-probe origin/main && cd ../llgenie-wt/sync-probe
make sync-registry            # prints old -> new generated_utc and model count
make sync-quant-catalog       # live Hub, minutes
make render-trend-list-matrix
make render-engine-skill-gap
make check-registry           # shape + README order + live links
make check-quant-catalog
make skills-validate REGISTRY=data/models.json UNSUPPORTED=data/unsupported-engines.json ALLOW_NEW_ENGINES=1
make test-unit                # ~11-13 min; the step that usually stops the job
```

A later blocker is its OWN linked issue, never folded into the current change. A big upstream jump
(models 23 -> 106) reds dozens of hermetic tests that pin the old store's names, order and t/s — those
are data pins to rewrite as invariants, not regressions. `sudo chown -R $(id -u):$(id -g)` the probe
before `git worktree remove --force` when a container stage left root-owned files.

## Remotes: `origin` is the UPSTREAM here, the fork is `fork`

Check `git remote -v` before the first push of a session — in this repo's worktrees
`origin = asimov-agent/llgenie` (upstream) and `fork = andyholst/llgenie`, which is the opposite of the
usual fork layout, and `origin` is what a habitual `git push -u origin <branch>` reaches first.

```bash
git push -u fork feat/<kebab>                # the PR head
gh pr create --repo asimov-agent/llgenie --base main \
  --head andyholst:feat/<kebab> ...          # base = upstream, head = <fork owner>:<branch>
```

A branch pushed to `origin` lands on the upstream repo: not fatal (it is not `main`), but it leaves a
stray branch there and the PR still has to be opened with the `andyholst:` head. One side effect is
useful to know: a ref that exists upstream can be dispatched (`gh workflow run <wf> --ref <branch>`),
which is how a fork branch gets live CI proof of a `workflow_dispatch`-only path; delete or ignore the
upstream copy afterwards.

## Leftovers the tooling creates

- The openspec container runs as root too, so a freshly created `openspec/changes/<name>/` can be
  root-owned before you write into it: chown it through a container first, or the first write fails
  with `Permission denied`.
