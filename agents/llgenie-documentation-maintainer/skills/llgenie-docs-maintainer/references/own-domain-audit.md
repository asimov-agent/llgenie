# Own-domain audit — the empty-queue bounded sweep

Versioned behaviour (owner #1245 contract). When the reactive queue is empty for **N=2 consecutive
passes** and no in-flight gate is owned, run ONE bounded own-domain audit. Never overrides reactive
work. One pass, no loop. Clean → record `re-audited at <sha>, no findings`; finding → a refined
six-section issue tagged `agent:implement`, routed through the queue, **never implemented by the same
pass**.

My three checks: main-vs-docs alignment, skill freshness, change-note coverage (#1123).

## Measure in a pure-tip worktree, never your own branch checkout

**Every measurement runs in a scratch worktree cut at the freshly fetched tip sha, not in the branch
worktree you are already sitting in.** A branch worktree's `HEAD` is your PR's base commit; its
`docs/changes.d/`, `CHANGES.md` and file counts belong to that branch, not to `main`. Measuring them
there gives a confident, wrong census. Fix:

    git worktree add --detach /tmp/adm-audit <tip-sha>
    cd /tmp/adm-audit && <run the checks below>
    cd - && git worktree remove /tmp/adm-audit

Remove the scratch worktree when done (it is yours, not a fleet vehicle); never remove another lane's.

## Check 1 — main vs docs alignment

Pick the sentence the dispatch names and **read the code path it describes, not just a grep of the
doc.** A doc sentence "X is a later change" is true iff the code does **not** do X: a picker that
*consumes* pre-measured `engines[].tps` from the registry is not a picker that *measures* t/s, so
"measuring in the picker is a later change" still holds. Check each concrete claim against the tree:
where a decision lives (`detect_server.py` tree/backend vs `model_engine_pick.py` gates), the
ordering rule ("measured on this card, else not a claim"), and any threshold constant. Aligned = cite
the file:line that keeps the sentence true; drifted = issue naming the drift sha and what the doc
should say.

## Check 2 — skill freshness

Enumerate every skill, then read `version:` frontmatter against the release ledger. **The glob
trap:** `git ls-tree -r --name-only <tip> | grep 'skills/SKILL.md'` returns nothing — real paths are
`agents/<profile>/skills/<name>/SKILL.md`, `.hermes/skills/<name>/SKILL.md`, and
`skills/engines/<ns>/SKILL.md`. Match `SKILL\.md$` (and `SOUL\.md$`) instead. A flat `v1.0.0` is
normal for most lanes; "2+ releases stale" is a behavioural reading — read the one skill in the
domain of the newest behavioural merge (e.g. the Prism skill after a Prism-only gate lands) to judge
drift, not the version number alone.

## Check 3 — change-note coverage (#1123)

For each recent merge that touched a notified surface (`docs/**`, `scripts/`, workflows, Makefile
targets, `agents/**`), confirm its full trio exists **at the tip**. **Enumerate the real fragment
names — do not guess the slug from the PR title.** Fragment filenames are `<date>-<their-slug>-<issue>.md`
and the slug is authored, not derived from the title, so `grep '<title-derived-stem>'` returns nothing
for a fragment that exists and you read a false MISSING:

    git ls-tree -r --name-only <tip> docs/changes.d/ | grep -- '-<issue>\.md$'   # locate by IS issue number
    git ls-tree -r --name-only <tip> agent-wiki/          | grep -- '-<issue>\b'   # note
    git show <tip>:CHANGES.md                              | grep -- '-<issue>'      # indexed row

Matching on the trailing issue number is stable across slug renames; matching on a remembered stem is
not. **The gate is the source of truth, a guessed stem is not:** run `python3 scripts/check_docs.py
check` at the tip and expect rc=0 with a `fragments == notes` count in its summary (`[changes-index]
ok: <N> fragment(s) index every agent-wiki/ note`). If your per-merge grep says MISSING but the gate
is green, the **grep was wrong** — you guessed a slug, you did not find a gap. Never file a
change-note finding off a stem you invented; a real gap makes the gate itself red.

## Deliverable and the missing tracker

The clean-audit record needs a durable home. If no **open** docs-lane tracking issue exists (the
past audit issues are often already CLOSED), say so in the report and send the `re-audited at <sha>
no findings` to `@llgenie-planner` rather than fabricating a tracker.
