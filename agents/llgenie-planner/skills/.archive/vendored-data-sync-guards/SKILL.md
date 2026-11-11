---
name: vendored-data-sync-guards
description: Use when guarding a vendored copy of external data.
version: 1.0.0
author: Hermes Agent
license: CC-BY-4.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [data-sync, vendored-data, guards, ci, upstream]
---

# Vendored data + its additive-only sync guard

## When to Use

A repository keeps a byte-for-byte copy of an external data store (a registry, a catalog, a generated index)
that a scheduled job replaces wholesale, plus a guard that refuses a sync which lost data. Use this when
diagnosing why such a sync has stopped landing, when writing or changing that guard, or when a sync PR must
be proven to go green. Not for a one-off copy — only when the copy is refreshed on a schedule and something
has to notice a loss.

Worked example with all the concrete commands lives in a different skill: load `llgenie-engine-image-ci` and
open its supporting file `registry-sync-and-vendored-data-guards.md` (listed in that skill's
`linked_files`), which carries the exact make targets, container command lines and guard module for the
llgenie vendored-registry case.

## The core rule: compare identity, not labels

An upstream that rewrites its rows in place — refining a `hardware` string, splitting one entity into a
more specific row, promoting a profile link to a canonical URL, rebuilding a placeholder list — will read as
massive data loss to any guard keyed on a display label such as `(engine, hardware)`. That is the failure
mode that keeps a weekly sync frozen for weeks while the guard looks like it is doing its job.

- Key every loss check on a **stable external id** (a post id, a URI, an upstream row id), indexed across
  the **whole store**, not per parent row: an entry can move between the ranked list and a placeholder list
  and still be the same datum.
- **Derived lists are not data.** A list upstream regenerates on each build (placeholder / seen-posts
  style) has no persisted element keys; an emptied one must not read as N lost keys — the union of `[]` is
  empty, so guard the code against that explicitly.
- **Fall back deliberately, never silently.** A row with no stable id still needs its static checks tied
  to its old label; state that in the code path rather than dropping the check.
- **Ask what the product consumes.** A loss only matters if it thins what downstream ranks: if the reader
  groups measurements by `engine`, then "no measurement left for this engine" is the fatal unit — which
  source row carried the figure is bookkeeping.

## Split fatal from reported

- **Fatal (non-zero):** a whole entity/row gone, a key gone from a row, a grouping the product consumes
  gone, an enum-list entry gone, a stated static footprint lowered, a tracked stable id gone from the whole
  store.
- **Reported only (print both values, exit 0):** a re-read live metric that can move either way, a
  corrected figure on a surviving row, a derived list shrinking. Live sources re-scrape: counts genuinely
  fall, and failing on that freezes the sync for a reason nobody can fix.

Print the reported movements anyway, with old → new and the reason, so a reviewer sees the store's new
reading without diffing the file. A guard that hides them is as bad as one that fails on them.

## Before blaming upstream, test the claim

For every reported loss, ask: **does the cited identity still exist anywhere in the new store?** If it
does, the guard is over-firing. A tracked issue claiming "upstream lost N items" is worth re-measuring
before it is trusted — correct the issue in a comment when the measurement disagrees.

## Read the upstream contract, not only the data

A store that ships a contract — a prose schema doc, a JSON Schema, a generated README whose columns are a
promise — is telling you which fields are *requirements* and which are display categories. Read it before
gating on any field, and vendor it with the store so a contract change is visible in a diff instead of
arriving silently inside the data.

- **A category is not a requirement.** Stores commonly keep a coarse label (a tier, a bucket, a class) next
to the measured minimum. Gating on the label over-restricts churn-free: the label disagrees with the real
minimum on a third of the rows, so genuinely runnable entries disappear from the product's list while the
rule reads as if it were deliberate.
- **Ranking may be scoped per parent, not global.** If upstream publishes a list per bucket (per card, per
tier, per region) and the reader keeps one global order, the reader answers a different question than the
source for the small buckets — usually the ones the product exists for. Compare the reader's order to the
published per-bucket order, bucket by bucket, and report which buckets agree.
- **A consumer's own schema check is not the upstream schema.** A hand-rolled validator (a handful of
required keys) passes a store the upstream contract rejects; validating against the vendored schema is what
makes a contract change fail loudly.

## Prove the sync can land (never assert it)

Run the real scheduled sequence yourself, in a **throwaway detached worktree** (the sync rewrites tracked
data and generated fixtures — never do it in the feature worktree), in the order the job runs it, and report
each step's real exit code:

1. the sync command (writes the new store),
2. the additive guard,
3. **every** regeneration step (derived table / matrix / index / skill-gap), each one before the next gate,
4. the shape/order check the job runs on the new files,
5. the job's test step — usually the one that actually stops it,
6. each downstream gate, in the form the job invokes it.

Order is load-bearing, and so is the form: each regeneration changes what the following gate and the test
suite see, so a probe that skips one yields a failure count that is fiction and a "blocker" that is not the
blocker. **Open the scheduled workflow file and read which command each step runs** — a job often uses a
REPORTING form of a gate (`make <x>-gap`, prints and continues) while CI's checking form (`make
check-<x>-gap`) is what reds the resulting PR; naming the checking form as the job's failure is a wrong
claim, and the job may in fact be stopping on its test step.

When the sequence stops at the test step, separate the failures: a **data-pinned** class (goldens holding
an entity name, a list order, an exact figure, a per-entity coverage count) is a different blocker from the
rule the gate enforces, and it is usually the larger one. A suite parametrized over the store multiplies
with it, so its passed count grows too — that is not a regression. File each class as its own issue.

Publishing one layer of this and then finding more is normal; when a number you already quoted turns out to
come from an incomplete probe, state the corrected measurement next to the wrong one in the record rather
than silently replacing it.

A fix to one gate does not mean the sync lands — it usually exposes the next gate, and that next one is a
**separate work item** linked both ways, not part of the current change. Then remove the throwaway
worktree (`git worktree remove --force <path>`), after `chown`-ing it to yourself if the job's containers
ran as root.

## Writing the PR for such a change

- Scope the benefit sentence to the gate actually fixed ("the guard no longer freezes the sync"), never
the outcome it unlocks ("the sync can land") until the whole sequence is green. Over-claiming is corrected
in the body itself (`gh pr edit --body-file`), not just in chat.
- Keep the vendored file **untouched** in the guard change: the data arrives through the scheduled job's own
  PR. Weakening or hand-editing the store to make the gate pass is the failure this guard exists to catch.
- Red-first proof: run the new test/check against the pre-change code and show the finding it produces
  (e.g. a label refinement reported as "measurement gone"), then show the new code reporting none.

## Pitfalls

- **Container-written files are root-owned, and that bites twice.** A CLI that scaffolds inside a
  container running as root (`-u root`) blocks your next write with permission denied, and a throwaway
  worktree full of such files cannot be deleted (`git worktree remove --force` -> Permission denied, then
  "is not a working tree" while the directory survives). `sudo chown -R $(id -u):$(id -g) <path>` first, then
  remove; if the directory is still there, `git worktree prune && sudo rm -rf <path>`.
- **Targeted tests in a worktree need the parent checkout mounted too.** `.git` is a file pointing at
  `<parent>/.git/worktrees/<name>`, so a container with only the worktree mounted fails git-backed tests
  with "not a git repository". The repo's own aggregate target handles this; a hand-run container does not.
- **Read-before-write is per path.** After switching to a worktree, read the worktree copy before
  overwriting a file; content read from the main checkout does not license the write.
- **Right after a push, `gh pr checks` can report "no checks reported"** while the run is queuing; list runs
  by branch (`gh run list --branch <b> --json databaseId,status,conclusion,headSha`) to see the queued run
  and its sha. A superseded run shows `cancelled` — that is not a failure.
