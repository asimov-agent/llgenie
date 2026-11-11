# Vendored registry sync + its additive-only guard

Applies to llgenie's vendored `data/models.json` (a verbatim copy of upstream `trending-local-llms`), the
weekly `make sync-registry` job, and any guard that compares a freshly synced copy against the committed
one (`scripts/registry_keys.py`).

## Rules

1. **Compare identity, not labels.** Upstream rewrites its rows in place on every refresh: it refines a
   `hardware` string (`RTX 6000` -> `RTX 6000 24GB`), re-attributes a post to a more specific model row,
   upgrades a profile link to the real status URL, and rebuilds its placeholder lists. Keying a loss check
   on `(engine, hardware)` reports every one of those as data loss and freezes the sync indefinitely. Use
   the stable external id (the `/status/<id>` of `source_post`), indexed across the WHOLE store — ranked
   `engines[]` rows and `engagement.seen_posts` alike, because a post can be demoted from one to the other.
2. **Separate fatal from reported.** Fatal: a model row, a model key, an engine that had a measurement and
   has none, a `backends` / `supported_engines` entry, a `formats` name, an engine-registry entry, a stated
   footprint, a tracked post gone from the whole store. Reported only (print both numbers, exit 0): a
   surviving post's lowered t/s, a decreased engagement counter, a shrunken derived placeholder. Live posts
   are re-scraped — likes and views genuinely fall — and a figure can be corrected.
3. **Derived lists are not data.** A list upstream regenerates (the `seen_posts` placeholder) has no
   persisted element keys; an emptied one must not read as N lost keys (the union of `[]` is empty).
4. **The unit that matters is what the product consumes.** `rank_engines` groups a model's measurements by
   engine, so "this engine had a measurement for the model and has none now" is the loss that thins the
   trend list; which hardware string carried the figure is upstream's bookkeeping.
5. **A row with no stable id still needs its static checks.** When `source_post` is a profile link or
   absent, fall back to the `(engine, hardware)` group for anything static (stated footprints) instead of
   silently no longer checking it.
6. **Before concluding "upstream lost data", test the claim**: for each reported loss, does the cited
   `source_post` still appear anywhere in the new store? If yes, the guard is over-firing, not the store.

## The upstream contract: which field is a requirement

Upstream ships `data/MODEL_CONTRACT.md` + `data/model_contract.json` (JSON Schema) beside the store. Neither
is vendored into llgenie, and `scripts/sync_registry.validate()` is a hand-rolled subset (id / name /
`vram_tier` / engines) that does not even require `vram_min` — so a contract change cannot be seen here.

- `vram_tier` is a **display category**, not a requirement: upstream says to publish `vram_min` (the least
  VRAM needed). They disagree for roughly a third of the rows, and `fits()` gates on `vram_tier`
  (`scripts/model_engine_pick.py`), so a flagship whose tier is one step above the card is dropped from that
  card's list entirely — while upstream's own per-card table puts it first.
- Ordering is **tier-local upstream** (a speed bonus earned only by a measurement that RAN on a card of
  that size or less, never a datacenter part) but **global here** (`trend_list` keeps the store order over
  `engagement.trend_score`). Compare top-N per card against upstream's `### Up to N GB` tables; they agree
  in the big buckets and disagree in the small ones.
- Ranking an engine is already card-class aware (`rank_engines`, `same_hw` / `bigger` / `unknown` /
  `datacenter`) — the list order above it is not. When fixing a "wrong pick" report, check which of the two
  layers is wrong before touching either.
- A row's headline figure can come from a bigger card (`card_class="bigger"`); that is labelled, but it is
  not proof the model ran on the reader's card.

## Recipe: prove the sync can actually land

Run the real weekly sequence in a THROWAWAY detached worktree — never in the feature worktree, because it
rewrites `data/models.json` and the generated fixtures:

```bash
git worktree add --detach ../llgenie-wt/sync-dryrun <sha>
cd ../llgenie-wt/sync-dryrun
make sync-registry            # writes the new store + README
make check-registry-keys      # the additive guard
make sync-quant-catalog       # regeneration 1: the HF class table
make render-trend-list-matrix # regeneration 2: the per arch/vram/ram fixture
make render-engine-skill-gap  # regeneration 3: per-engine list + unskilled gap
make check-registry           # shape + README order + live links
make test-unit                # the job's LAST step before it opens the PR
sudo chown -R "$(id -u):$(id -g)" . && cd - && git worktree remove --force ../llgenie-wt/sync-dryrun
```

Run them in THAT order and report each REAL exit code. Each regeneration rewrites what the next gate and
`make test-unit` see, so a probe that skips one produces a failure count that is pure fiction (skipping
the two fixture regenerations turned 101 real failures into "184").

**Read `.github/workflows/registry-sync.yml` before naming "the blocker", because the job does not run
every gate in its checking form.** It runs the REPORTING form `make engine-skill-gap` there (prints each
unskilled engine, spawns one tracking issue per new engine, still opens the PR); the CHECKING form
`make check-engine-skill-gap` is what `ci-unit` runs on that PR's own CI. Naming the checking form as the
job's failure is a wrong claim, and the job's actual stopping point is `make test-unit`.

`make test-unit` here runs ~25-35 min, and its PASSED count scales with the store (many cases are
parametrized over the registry's models, so 23 models -> ~5.2k cases, 106 models -> ~14.3k). A count change
is not a regression; assert per row against data read from the same store, never a golden row.

## Pitfalls

- **`make openspec-new` creates the change directory as root** (the container runs `-u root`), so writing
  `proposal.md` / `specs/…/spec.md` / `tasks.md` afterwards fails with permission denied. Fix it first:
  `sudo chown -R $(id -u):$(id -g) openspec/changes/<name>`.
- **Targeted pytest while iterating must mount the parent checkout too.** In a worktree `.git` is a file
  pointing at `<parent>/.git/worktrees/<name>`; mount only the worktree and git-backed tests fail with
  "fatal: not a git repository":
  ```bash
  docker run --rm -v "$PWD":/repo:rw -v /home/asimov/repository/git/llgenie:/home/asimov/repository/git/llgenie:rw \
    -w /repo -e HOME=/root llgenie/test:latest python -m pytest tests/<file> -p no:cacheprovider -q
  ```
  `make test-unit` does this for you; hand-runs do not.
- **The throwaway worktree ends up root-owned, and then cannot be deleted.** `make sync-registry`,
  `make sync-quant-catalog` and `make test-unit` run in `llgenie/test:latest` as `-u root`, so the files
  they write belong to root: `git worktree remove --force` fails `Permission denied`, and after a partial
  delete `git worktree list` no longer knows it ("is not a working tree") while the directory still exists.
  Fix in this order: `sudo chown -R $(id -u):$(id -g) <path>`, `git worktree remove --force <path>`, and if
  the directory survives `git worktree prune && sudo rm -rf <path>`.
- **Read-before-write is per path.** After switching to the worktree, read the worktree copy before
  overwriting a file — content read from the main checkout does not license the write, and the tool refuses.
- **`NOTE:` lines from the registry guard are expected** and `make check-registry-keys` is green with
  them. Never "fix" a note by editing the vendored store; a note is a report.
- **Right after a push, `gh pr checks` can say "no checks reported"** while the run is still queuing.
  `gh run list --repo <r> --branch <b> --limit 3 --json databaseId,status,conclusion,headSha` shows the
  queued run and which sha it belongs to; a superseded run shows `cancelled`, which is not a failure.

## Proving a PR claim

Run the sequence the claim asserts and quote the real exit codes in the PR body. Scope the sentence to the
change actually made ("the guard no longer freezes the sync"), never the outcome it unlocks ("the sync can
land") until the whole sequence is green — otherwise the body promises a gate you have not run. When the
run exposes the next blocker, file it as its own issue, link it both ways, and correct any body that
over-claimed (`gh pr edit --body-file`).
