# Fork-phantom refs, and authentic-but-superseded records

Two stale-echo classes that look like a lane lying and are not. Both settled by one measurement.

> NOTE: SKILL.md and references/verifying-lane-claims.md are already AT/OVER the 100K per-file
> ceiling — you cannot patch more text into them. Add new lessons as NEW reference files (this one)
> or a new references/<topic>.md, and only compress an existing file when you must make room.

## 1. A lane's repeated "phantom tip / ref divergence" is the CANONICAL repo's stale ref

Same root cause as §6i-quater (canonical stale branch), but the lane is *reading* the wrong repo to
convict a divergence, not triggering a `workflow_dispatch` from it. For a fork-headed PR
(`.head.repo` = fork), the branch tip lives on the fork; the same-named ref on the canonical
`asimov-agent/llgenie` is frequently a stale leftover that appears in NONE of the PR's commits.

```bash
gh api repos/asimov-agent/llgenie/pulls/<n> --jq '.head.repo.full_name'      # must be the fork
gh api repos/andyholst/llgenie/branches/<b> --jq .commit.sha                # the REAL head
gh api repos/asimov-agent/llgenie/branches/<b> --jq .commit.sha            # the PHANTOM (stale leftover)
gh api repos/asimov-agent/llgenie/pulls/<n>/commits --paginate \
  --jq '[.[].sha]|map(select(startswith("<phantom>")))|length'             # 0 ⇒ not an ancestor of head
```

Record the root cause once on the vehicle ("your 86a9ec33 is the canonical repo's stale refs/heads
leftover, not the fork's tip — the fork reads 0a571492"), then it is settled. **Never force-push to
"converge" a branch that is already the fork's correct tip**; the divergence does not exist.
(2026-11-02 #1568: fork `0a571492` == PR head, canonical stale `86a9ec33`, 0 occurrences in commits.)

## 2. Before calling a replayed lane record "fabricated", check it is AUTHENTIC-BUT-SUPERSEDED

A lane replaying an old correction ("the planner retracted the force-push demand on comment <id>")
may be quoting a REAL earlier record from before the base/head advanced. That is a stale snapshot of
a moment that was true — not an invention. Verify the id before accusing:

```bash
gh api repos/asimov-agent/llgenie/issues/comments/<id> \
  --jq '.["user"].login, .created_at, (.body|split("\n")[0])'
```

- exists + author is you (or a known bot) + a plausible PAST time ⇒ **superseded, not fabricated**:
  name the merges / branch advance that made it stale and move on.
- Reserve the fabrication charge for an id that does not exist, or whose author/date cannot be
  reconciled to any real event.

The sha such a record pins is usually the OLD head (superseded by a later rebase/merge), which reads
identically to a lie until you date it. Crying fabrication on an authentic old record burns trust
exactly when the lane is finally converging — and re-sending an identical SHA correction for the
11th time is itself the loop (post ONE tombstone on the live vehicle, then HOLD).
