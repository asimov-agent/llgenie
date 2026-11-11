# Registry sync and the additive-only guard (llgenie)

Use when touching `data/models.json`, `scripts/registry_keys.py`, `scripts/sync_registry.py`, the trend
list, the `(arch, vram, ram)` matrix, or a claim that "the trending list is stale / broken".

## Prove the defect against the live upstream file

- Compare the vendored copy with the upstream clone on `generated_utc` plus model/engine counts, then run
  the guard itself against the live upstream store:
  `python3 scripts/registry_keys.py --cur <upstream>/data/models.json`.
- A tracking issue's stated cause is a hypothesis. Measure the guard's own output on the live file before
  repeating it; the finding classes (how many are relabels, re-scrapes, placeholder churn, genuine
  removals) are what the fix has to answer.
- Never widen, hand-edit or patch `data/models.json` to make a gate pass. The file is a verbatim upstream
  copy; a loss is reported upstream, not smoothed over here.

## Guard identity: compare what the product consumes

- A measurement is identified by the `/status/<id>` of its `source_post`, searched across the WHOLE store
  (`engines[]` measurements **and** `engagement.seen_posts`). Upstream refines hardware strings
  (`RTX 6000` → `RTX 6000 24GB`), re-attributes a post to a split model row, and upgrades a profile link
  to the real status URL — all of that is the same measurement, and keying on `(engine, hardware)` reads
  every one of them as a loss.
- The unit whose loss really thins the trend list is `(model, engine)`, because `rank_engines` groups a
  model's measurements by engine and takes the best figure.
- Fatal: a model row gone, a key gone from a model row, an engine with no measurement left, a lost
  `backends` / `supported_engines` / `formats` entry, a removed engine-registry entry, a lowered stated
  footprint (`weight_gb`, `context_tokens`, `system_ram_min` — model or measurement), a tracked post that
  is nowhere in the new store.
- Note, not fatal: a surviving post's lowered t/s, a decreased engagement counter, a shrunken
  `seen_posts` placeholder. X re-scrapes move likes/views both ways and upstream corrects figures; none of
  it removes a model, an engine or a post. Print them with both numbers so a reviewer still sees the
  movement.
- A derived/placeholder list (`engagement.seen_posts`) stores nothing: never compare its element keys. The
  union of an empty list is an empty set, so an emptied placeholder reads as one lost key per field.
- A measurement with no status post (profile link, absent `source_post`) has no identity — fall back to its
  own `(engine, hardware)` group for the stated-footprint comparison only.

## After unblocking one gate, probe the next one before claiming the pipeline works

A sync job has several gates in series; fixing the first one does not make the sync land.

```bash
cd /path/to/checkout
git worktree add --detach ../llgenie-wt/<name>-dryrun <branch-sha>
cd ../llgenie-wt/<name>-dryrun
make sync-registry              # writes the new store (dirty worktree is fine here)
make check-registry-keys
make render-trend-list-matrix
make render-engine-skill-gap
make check-engine-skill-gap     # a new upstream engine with no skill and no dated decision reds here
cd - && git worktree remove --force ../llgenie-wt/<name>-dryrun
```

- Run it detached at the branch head, never in the PR worktree: the sync rewrites `data/models.json` and
the generated fixtures, which must not end up in the change.
- File each downstream blocker as its OWN linked issue (the sync landing is not this change's objective)
and scope the PR body's benefit claim to the gate actually fixed — then edit the body if a later
measurement narrows it. An overclaim in the body is a defect a reviewer has to catch.

## Pitfalls that cost time

- **Hand-running pytest in the test image for a worktree**: mount the PARENT repo as well, or
  `test_default_prev_is_a_git_revision_of_the_vendored_file` fails. A worktree's `.git` is a file pointing
  at `<parent>/.git/worktrees/<name>`, outside the mount. `make test-unit` already adds it; if you invoke
  the container yourself, add `-v <parent>:<parent>:rw`.
- **`make openspec-new` leaves a root-owned change dir.** The CLI runs as root in the container, so
  `openspec/changes/<name>/` cannot be written by your user: `sudo chown -R $(id -u):$(id -g)
  openspec/changes/<name>` before writing `proposal.md` / `specs/<cap>/spec.md` / `tasks.md`.
- **`make check-docs` needs the PR number in the `agent-wiki/` entry.** Write the entry after
  `gh pr create`, or add a `PR: #<n>` line in a follow-up commit; the entry must reference the issue AND
  the PR.
- **`gh api .../contents/<path>?ref=<branch>` 404s on a fork-head PR.** Read the blob from the fork repo
  (`repos/<owner>/<repo>/contents/...`), not from the upstream repo.
- **Narrowing a guard's semantics reddens existing tests you did not grep for.** Search the test tree for
  the helper names and old message strings first: a footprint test can pin the very
  `(engine, hardware)` grouping you are removing, and its fixture may carry no `source_post` at all.
- **`make test-unit` is 25-40 minutes here.** Run it in the background with a notification, keep working on
  the docs/PR body meanwhile, and re-run only the targeted test files in the container while iterating.
