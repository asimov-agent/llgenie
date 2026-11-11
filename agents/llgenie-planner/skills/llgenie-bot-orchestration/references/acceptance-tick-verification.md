# Verifying an acceptance-criteria tick

A `[x]` in an issue body's acceptance criteria is an assertion, not evidence. Before you relay
"AC<n> done", open the criterion's OWN text and confirm the artifacts **it names** exist at the
**head the tick cites** — not merely that the box reads `[x]`.

## The check

```bash
# every artefact the criterion calls out, at the cited head
git cat-file -e <head>:<path-the-AC-names>
# and search the tree for the of-record file by topic
git ls-tree -r --name-only <head> | grep -i <topic>
```

A tick carries a provenance suffix: `proven: reviewer=<lane> comment=<id> head=<sha> run=<id>`.
Read it and verify at THAT head — a tick at a superseded head proves nothing about the live head.

## Pitfalls

- **A tick can cite SUBSTITUTED evidence.** The common failure: a change-note criterion names
  `agent-wiki/<date>-<topic-A>.md`, and the write-back ticks it using a DIFFERENT, earlier note
  (`<date>-<topic-B>`) whose stem covers another change. The AC names specific files; a look-alike
  note is not satisfaction. Treat the box as unticked until the named file exists (or the criterion
  is rewritten). The `git ls-tree` / `git diff --name-only origin/main <head> -- agent-wiki/` check in
  `change-note-gate.md` settles which note is really on the head.
- **A reviewer "ruling a leg out of scope" inside a write-back is not a tick.** When the write-back
  argues a named artifact "names a mechanism this repo does not use" and ticks anyway, that is a
  scope change: it needs a `## Not covered` entry with a linked issue (the add-only escape), never a
  silent `[x]`. Route it back to the write-back owner — the reviewer owns acceptance ticks per the
  write-back contract; the planner does NOT tick or untick peer-lane criteria. Post the measured
  discrepancy and let the owner reconcile.
- **A lane's DM can contradict its own on-wire write-back.** Reconcile against the wire, not the DM:
  read the issue body's current boxes and the cited comment. If the DM says "not ticked / genuine
  gap" while the body reads `[x]`, the body is what ships — flag the contradiction to the lane,
  quoting the exact comment id and head you measured.
- **An AC that names a job/run pair must be checked for MEMBERSHIP, not existence.** A criterion
  like "failure in job <jid> run <rid>, log line quoted in a comment on this issue" fails when
  `gh api repos/<o>/<r>/actions/jobs/<jid> --jq .run_id` returns a DIFFERENT run, or the job's
  conclusion is `skipped`, or the named run's conclusion is `cancelled` — a real job id paired with
  the wrong run is a false citation even though both ids exist. Check `run_id`, `conclusion` and
  `head_sha` on the job, and the run's own `conclusion`, before calling the evidence present.
- **A bare path-marker comment is not "a quoted log line".** `#1880`-style comments reading only
  `@/tmp/1880_ac1.md` (body_html empty, ~20B) do NOT satisfy "log line quoted in a comment" — the
  quoted line must be IN the comment body. Fetch the comments and confirm the body actually carries
  the log text; a reference to a scratch file the reader cannot see proves nothing. When the
  reviewer refuses to tick on this basis, the refusal is CORRECT — do not push a tick; route the
  evidence gap back to the lane that authored the AC.
- **A "cannot locate the proof text / grep returned ZERO under agents/" refusal is a claim about the
  lane's SEARCH, not the tree — measure it yourself before accepting or routing around it.**
  `git fetch origin main && git grep -ilE '<wording>' origin/main -- 'agents/*'` then
  `git show origin/main:<path> | grep -nE '<wording>'`. A "nowhere carries the contract" refusal
  resolves routinely to several lanes that DO carry it (wrong grep pattern or stale scope). Hand
  back path + blob sha + the quoted line and ask the lane to re-measure. Never manufacture a tick and
  never accept a false-absent refusal as a real gate.
- **A criterion that is PER-LANE propagation cannot be satisfied by a GATE PR's diff.** A criterion
  like "each affected lane carries, via #791, a stated contract" is a fleet state reached by many
  lanes' own `agents/<lane>/` PRs — a gate PR that changes only `scripts/`/`.github/`/`Makefile` (zero
  `agents/` files) can never make it provable, and a reviewer refusing on that basis is measuring the
  wrong object. Measure the fleet state yourself first (`git grep` across `origin/main -- 'agents/*'`),
  then offer exactly two honest routes: **(A)** the reviewer ticks citing the lanes that already carry
  it (quote their blobs); or **(B)** the gate PR names the criterion under `## Not covered` with a
  linked work item tracking the remaining lanes. Never push an `agents/` change into a gate PR to
  force the tick, and never manufacture the tick — the planner routes, the reviewer owns acceptance.
- **A criterion that names a gate/run as its OWN evidence cannot be ticked while that run is pending — the tick IS the verdict.** A criterion like "`make check-workflows`, `make check-wiring`, `make check-docs`, and the hermetic unit tests pass at the PR head (run ids quoted)" is self-referential: its proof is the very run still `pending`/`in_progress`. Ticking it to clear `check-pr-acceptance` before that run concludes is fabricating the verdict the gate exists to demand, and the gate reads exactly as red on a merge. Hold the box as unticked and state its status honestly ("RUNNING: <workflow> run <id> at head <sha> — ticked with the run id once it concludes") — the read-back box carries the run id, not a bare `[x]`. Equally, do NOT tick against a run at a SUPERSEDED head: re-read `headRefOid` first, because a lane re-pushing moves the head under you and a green at the old sha proves nothing about the tip (`acceptance-at-moving-head.md`). The only two honest exits are the run concluding green at the CURRENT head (then tick with its run id) or `## Not covered` with a linked work item when the criterion is genuinely out of the PR's scope.
- **Your own prior "AC<n> verified" comment is a claim too.** If you verified that the box existed but
  not the artifacts the AC names, correct it on-thread rather than letting a stale "verified" stand —
  a correction is not churn when it removes a false green.
