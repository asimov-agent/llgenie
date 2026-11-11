# llgenie trend-list / model-selection vs upstream trending-local-llms

When asked "does llgenie pick the right model for MY card / VRAM", the answer is a
comparison, never a guess. llgenie's selection logic and upstream's index logic are
TWO different fit rules over the SAME vendored `data/models.json`, and they disagree.

## The two rules (why they diverge)

- **llgenie** (`scripts/model_engine_pick.py`): `fits()` compares only the coarse
  `vram_tier` string to the card; `rank_engines()` groups measurements by BACKEND
  CLASS (CUDA/ROCm/Metal/CPU) and sorts by raw t/s. The size of the card a figure was
  measured on never enters the decision. `same_hw` means "same backend class", NOT
  "same card size".
- **upstream** (trending-local-llms): a per-card evidence ladder `fits_tier` — a model
  appears in a tier only with evidence, strongest first: `ran-on` (a measurement ran
  on a card of <= N GB), `weights-only` (weights fit but the run card is bigger),
  `declared` (`vram_min`), `tier` (coarse string). A measurement on a BIGGER card does
  not qualify a smaller tier. Datacenter parts are excluded entirely (`in_scope`).
- **ordering** — upstream ranks each card tier with a TIER-LOCAL trend: the model's own
  7-day buzz plus a speed bonus earned only by a measurement that actually RAN on a card
  of <= that tier (a 32 GB figure can never top the 8 GB table, and a datacenter figure
  never counts). llgenie keeps the GLOBAL `engagement.trend_score` order and filters it,
  so for an 8/12/16 GB owner the list differs in ORDER as well as in set; the top-6
  agrees only from 24 GB up.

Consequences that reproduce on real data:
- A 300 t/s figure measured on 2x RTX 4090 (48 GB) is shown to a 16 GB owner as
  `same_hw=True` and unqualified in the pick UI.
- A datacenter figure (e.g. 21 000 t/s on a B300) ranks near the top of a 16 GB list
  because llgenie has no datacenter exclusion.
- `vram_min` is vendored (every model has it) but read by NOTHING in llgenie — grep
  finds it only in fixtures.
- The list filter uses `vram_tier` (GPU-only), then `plan_download` spends a RAM-aware
  `weight_budget_gb` — two different fit rules for the same question, so a model the
  budget would allow (MoE offload into system RAM) is killed by the list filter first.

## Comparison recipe (prove the divergence, don't assert it)

1. Fetch the CURRENT upstream registry and diff against the vendored copy:
   `curl -sL -o /tmp/up_models.json https://raw.githubusercontent.com/<owner>/trending-local-llms/master/data/models.json`
   then compare `generated_utc`, model count, and the per-model / per-measurement key
   sets. New upstream fields (`weight_gb`, `context_tokens`, `system_ram_min`,
   `storage_offload`, `engine_min_version`) arrive only on the next weekly sync —
   staleness is expected between Mondays, not a bug.
2. Port upstream's helpers (`hardware_vram_gb` + `_CARD_VRAM`, `in_scope` +
   `_DATACENTER_HW`, `fits_tier`, `tier_rows`) into a scratch script. They are ~60
   lines and self-contained; reuse llgenie's `measurement_backend`/`_num` for the
   Metal/CPU skip and t/s core.
3. Run BOTH logics on the SAME data (upstream data, so the comparison isolates the
   LOGIC difference from registry staleness):
   - upstream `tier_rows(models, tier)` vs llgenie `rank_models(registry, arch, gb)`
   - report: models upstream proves fit but llgenie hides; models llgenie offers with
     no card evidence; how many rows have their top engine measured on a card LARGER
     than the host.
4. Also run llgenie on its OWN vendored data to show what a user actually sees today
   (the staleness layer on top of the logic gap).

## Pitfalls

- **Datacenter hardware must be excluded from consumer card ranking.** A B300/H100/
  Instinct figure is not "what fits your card". llgenie has no `_DATACENTER_HW` list;
  upstream does. Match the family, never one spelling (`b300` was missing once and a
  bare "single NVIDIA B300 GPU" passed as in-scope).
- **`same_hw` is backend-class, not card-size.** Do not read it as "measured on
  hardware like yours".
- **A coarse `vram_tier` disagrees with `vram_min`** for a meaningful share of models;
  never render the coarse string as a requirement.
- **The vendored registry is a verbatim copy** — a sync brings new fields automatically,
  but llgenie's code must be updated to READ them before they have any effect.
- **`git show` of a large file truncates** through the terminal tool; write the ref to
  scratch and grep the full text in Python before concluding a symbol is absent.
- **Hand-running pytest in the test image for a worktree needs the PARENT repo mounted**
  too: a worktree's `.git` is a file pointing at `<parent>/.git/worktrees/<name>`, outside
  the mount, so `test_default_prev_is_a_git_revision_of_the_vendored_file` fails on `not a
  git repository`. `make test-unit` adds that mount; add `-v <parent>:<parent>:rw` when you
  invoke the container yourself.
- **`make openspec-new` leaves a root-owned change dir** (the CLI runs as root in the
  container), so writing `proposal.md` / `specs/<cap>/spec.md` / `tasks.md` fails with
  Permission denied — `sudo chown -R $(id -u):$(id -g) openspec/changes/<name>` first.
- **`make check-docs` wants the PR number in the `agent-wiki/` entry.** Write the entry
  after `gh pr create`, or add a `PR: #<n>` line in a follow-up commit.
- **`gh api .../contents/<path>?ref=<branch>` 404s for a fork-head PR** — read the blob
  from the fork repo (`repos/<owner>/<repo>/contents/...`), not the upstream.
- **Narrowing a guard's semantics reddens tests you did not grep for.** Search the test
  tree for the helper names and old message strings first: a footprint test can pin the
  very `(engine, hardware)` grouping you are removing, and its fixture may carry no
  `source_post` at all.

## Is the vendored registry stale? Prove it, don't assume

A tracking issue that says "the sync is frozen because upstream lost data" is a
HYPOTHESIS. Measure before repeating it:

```bash
# how far behind is the vendored copy: compare generated_utc + model/engine counts in
# data/models.json against the upstream clone's data/models.json, then ask the GUARD what
# it says about the live upstream store:
python3 scripts/registry_keys.py --cur /path/to/trending-local-llms/data/models.json
```

That second command is the evidence: classify every finding (measurement relabels, live
re-scrapes, placeholder churn, genuine removals) before deciding whether the DATA or the
GATE is wrong. Never widen `data/models.json` to make a gate pass — it is a verbatim
upstream copy, and a real loss is reported upstream.

## The additive-only guard: identity, not labels

`scripts/registry_keys.py` compares the committed store with the sync candidate. Upstream
rewrites rows on every refresh, so identity must be what the product consumes:

- **A measurement is its post**: the `/status/<id>` of `source_post`, searched across the
  WHOLE store (`engines[]` measurements AND `engagement.seen_posts`). Upstream refines
  hardware strings (`RTX 6000` → `RTX 6000 24GB`), re-attributes a post to a split model
  row, and upgrades a profile link to the real status URL — the same measurement every
  time. Keying on `(engine, hardware)` reads all of them as losses and freezes the sync.
- **The fatal unit is `(model, engine)`** — `rank_engines` groups by engine, so an engine
  that keeps no measurement is what actually thins the trend list.
- **Fatal**: model row gone; key gone from a model row; engine with no measurement left;
  lost `backends` / `supported_engines` / `formats` entry; removed engine-registry entry;
  a lowered stated footprint (`weight_gb`, `context_tokens`, `system_ram_min` — model or
  measurement); a tracked post that is nowhere in the new store.
- **Note, never fatal**: a surviving post's lowered t/s, a decreased engagement counter, a
  shrunken `seen_posts` placeholder. X re-scrapes move likes/views both ways and upstream
  corrects figures; none of it removes a model, an engine or a post. Print them with both
  numbers so a reviewer still sees the movement.
- **A derived placeholder stores nothing**: `engagement.seen_posts` is rebuilt on every
  sort, so never compare its element keys — the union of an empty list is an empty set and
  an emptied placeholder reads as one lost key per field.
- A measurement with no status post (profile link, absent `source_post`) has no identity:
  fall back to its own `(engine, hardware)` group for the stated-footprint comparison only.

## After the gate passes, the sync still has more gates

A sync job runs several gates in series; fixing the first does not make the data land.
Probe the real sequence in a throwaway DETACHED worktree at the branch head (never in the
PR worktree — it rewrites `data/models.json` and the generated fixtures):

```bash
git worktree add --detach ../llgenie-wt/<name>-dryrun <sha>
cd ../llgenie-wt/<name>-dryrun
make sync-registry && make check-registry-keys && make render-trend-list-matrix
make render-engine-skill-gap && make check-engine-skill-gap
cd - && git worktree remove --force ../llgenie-wt/<name>-dryrun
```

`check-engine-skill-gap` reds for every engine the new store adds that has no skill and no
dated `data/unsupported-engines.json` decision. File each such blocker as its OWN linked
issue and scope the PR body's benefit claim to the gate you actually fixed — then edit the
body if a later measurement narrows it. An overclaim is a defect a reviewer has to catch.

## What "acting accordingly" means

A 16 GB owner should see the best figure PROVEN on <= 16 GB (e.g. a 5060 Ti 16 GB run),
not a 2x 4090 or datacenter figure. All the data to do this is in `models.json` (the
per-measurement `hardware` string is enough); no new data source is needed. The fix is
adopting upstream's evidence ladder in `fits`/`rank_engines`, making `same_hw`
card-size-aware, and excluding datacenter parts — then regenerating the trend-list
fixtures.
