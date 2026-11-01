# Version 12 live-only planner orchestration references into the tree (byte-identical) (#1299)

## What shipped

Live→tree versioning of **twelve** planner-lane orchestration references that exist in the live
profile but are absent from the tree, under
`agents/llgenie-planner/skills/llgenie-bot-orchestration/references/` (the live-only set measured
in #1299). Each tree file is now **byte-identical** to the live authoritative file at the head
(`git cat-file -p <head>:<path> | sha256sum` = `sha256sum <live-file>`; `cmp` passes for all twelve;
live hashes recorded below):

| file (live-only, absent from tree @ `bbdda411`) | head / live sha256 | head / live bytes |
|---|---|---|
| `auto-merge-arm-readback.md` | a02fd4d8… | 3681 |
| `completion-integrity-check-handling.md` | bd06f057… | 2222 |
| `dispatch-claim-marker.md` | 88e81cb6… | 2121 |
| `idle-lane-forcing.md` | f606cbae… | 3466 |
| `issue-tracking-record-placement.md` | 69906089… | 2062 |
| `main-ci-cancel-in-progress.md` | 4a846d42… | 1817 |
| `measurement-report-and-close-verification.md` | 910416e4… | 2030 |
| `mutation-readback-and-postmerge-verify.md` | b3ddd401… | 3504 |
| `one-vehicle-reconciliation.md` | 622f9c0b… | 4531 |
| `repeated-stale-head-report.md` | a1b9ea6e… | 3209 |
| `route-hold.md` | fb6f8b4c… | 1844 |
| `vehicle-detection-before-dispatch.md` | 7d9af8f2… | 2153 |

These are the twelve live-only refs #1299 counts (`tree=54, live=66, 0 tree-only`). The planner is
live-authoritative; each copies live→tree (never tree→live), direction per #791. Pure file-versioning:
no content reworded, no planner behaviour edit, no other lane's profile touched. `already-resolved-vs-live-slice.md`
(#1224/#1229) was already in the tree and is NOT re-folded. No census change (adds reference files under
`agents/`, no `scripts/` or tracked-file-count-sensitive layout change).

## Evidence (measured at PR head)

```
for each of the twelve: sha256sum <live-file> == sha256sum <head>:<path>  (byte-identical, cmp passes)
live signature stable 3× over ~16s before copy (planner lane not mid-write)
make bot-preflight / make check-docs (change-note gate) = exit 0
```

## Acceptance

- [ ] All twelve `sha256sum <live>` == `sha256sum <head>:<tree>` at head (table above).
- [ ] Note + fragment pass `make check-docs` change-note gate (#1123); `CHANGES.md` row landed via `make changes-index`.
- [ ] One PR for the twelve-file set; never merged by the implementing lane.
