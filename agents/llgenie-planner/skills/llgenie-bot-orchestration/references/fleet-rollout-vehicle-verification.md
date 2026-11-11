# Verifying and dispatching a per-lane fleet-rollout vehicle

When a tracker issue says "each affected lane carries X in its own skill/surface, versioned per-lane",
your job is not to dispatch all six. It is to **measure each lane's current state and dispatch only the
lanes whose vehicle is genuinely unlanded** — and to say, in the dispatch, exactly what already exists so
the lane adds a pointer instead of rewriting.

## Measure on the live tree, never the working clone

The primary clone is owner-mediated and runs dozens of commits behind. Any "is it already there?" answer
taken from the local working tree is false drift.

```bash
cd $HOME/repository/git/llgenie
git grep -l '<distinguishing phrase from the procedure>' origin/main -- agents/<lane>/
git log --oneline origin/main -- agents/<lane>/skills/ agents/<lane>/SOUL.md | head -5
```

`git show origin/main:<path>` for the actual text. Decide from these, never from `cat` of the checkout.

## Match the criterion's exact surface

"In its own **skill**" is not satisfied by a discipline sentence in the lane's **SOUL.md**. SOUL is the
always-loaded rule surface; `skills/<name>/SKILL.md` + `references/` is the loadable surface. When the
criterion names the skill, grep the skill directory specifically — a hit in SOUL.md alone means the
vehicle is **still unlanded** and the dispatch is real, but the dispatch must say so ("keep the SOUL line,
add the skill-surface pointer, pointer addition not rewrite") or the lane will duplicate the text.

Related-but-distinct is not landed: a lane that restates the same discipline in its own words has not
added the pointer to the canonical procedure. Check for the canonical reference path (or an explicit
link to it), not a topic keyword.

## Dispatch shape that keeps the lane from inventing scope

- Name the lane, the tracker id, the criterion quoted exactly, and the measured pre-existing state
  (which file/line already carries what).
- Give the gap, the target surface, and "pointer addition, not rewrite".
- One vehicle = one PR under `agents/<lane>/`; no cross-lane file edits; versioned per the per-lane rule
  (issue → PR), never a private edit.
- Done = ready-for-review PR with the preflight/AGENTS/BASE lines and the change-note trio the gate
  demands, plus head sha + run id reported. Acceptance write-back is reviewer-gated; stop at the
  reviewable PR. No merge, no arm, no push to main.
- Post the dispatch on the **tracker issue** (durable, one comment per lane) and DM the lane with the
  same scope plus the comment id. Then read the comment back by id and assert issue number + length.

## Ordering when several lanes are named

Dispatch the lanes that are idle-capable and unlanded; note the ones that are occupied (their own reactive
queue, an in-flight audit, a live claim) and say when their vehicle comes due. Never batch-dispatch the
whole fleet at once — you cannot verify six pickups, and a lane dispatched while busy invents scope.
