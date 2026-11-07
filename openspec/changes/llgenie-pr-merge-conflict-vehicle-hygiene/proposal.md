# llgenie-pr-merge-conflict-vehicle-hygiene

## Why

The lane's own #1849 vehicle (PR #1850) was red on the wire while cited green by an audit dispatch: it
edited `agents/llgenie-pr-merge-conflict/skills/llgenie-pr-rebase/SKILL.md` but its body had no `SYNC:` line
(`check-pr-sync-line` red, #1724), and it carried `Closes #1849` against unticked acceptance boxes
(`check-pr-acceptance` red, #1792). A `MERGEABLE` PR that "is ready for review" is not CI-green — the fleet
read a "passed" claim its own checks contradicted, exactly the stale-witness defect #1852's audit exists to
count.

## How

Codify two durable regression guards into the lane's `measurement-and-readback.md`: (1) the fleet-witness
rule — cite a PR as green only from its live `check-runs` conclusions at the measured head, never a
`mergeable` status or a relayed claim; and (2) the per-lane SYNC rule — any profile-editing vehicle that
touches `agents/<lane>/` carries its `SYNC: <profile> make sync-agent-profile …` line in the same
commit/push as the skill edit (#1724). AC-1/AC-2 of finding #1854 (fix #1850) reference a now-CLOSED PR and
are satisfied as recorded on-issue; this vehicle's provable deliverable is AC-3 (the durable regression
guard), exercised by this very PR carrying its own `SYNC:` line.

## Benefits

- A lane vehicle is never cited green while red on a mechanical gate the fleet scans for.
- The per-lane SYNC rule stops the deferred-line gap where a profile-edit PR is red on the wire in the window
  between edit and re-push.
- Proves a green via `check-runs` `.conclusion` rows, so the next audit reads wire truth, not a relayed claim.

## Tasks

- [ ] Add the fleet-witness rule (read a cited PR's `check-runs` conclusions at the measured head) to
      `references/measurement-and-readback.md`.
- [ ] Add the per-lane SYNC-line-in-same-push rule (#1724) to `references/measurement-and-readback.md`.
- [ ] Change-note trio (agent-wiki + changes.d + CHANGES.md); check-docs / lint / sync gate green.
- [ ] Opened as READY-for-review PR (not draft) carrying its own `SYNC:` line; no merge/arm (#1088).
