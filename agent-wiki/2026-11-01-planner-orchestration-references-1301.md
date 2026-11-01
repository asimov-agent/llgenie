# Fold remaining planner reference drift into the tree: 1 new + 11 tree-truncated refs, byte-identical (#1301)

## What shipped

Follow-up to #1299/#1300. The planner lane keeps editing its live orchestration references. Measured
at `origin/main@8591e318`: `tree=66, live=67, 0 tree-only`. Two classes of live-ahead drift folded
live→tree **byte-identical** under
`agents/llgenie-planner/skills/llgenie-bot-orchestration/references/` (live is source of truth, #1273;
direction per #791):

1. **One new live-only file** absent from the tree: `issue-already-done-detection.md` (2079 B,
   sha `35f86337…`). After this file: `tree=67, live=67` → 0 live-only, 0 tree-only.
2. **Eleven present-but-content-diff files** where the tree held a truncated copy and live has grown:
   each updated byte-identical live == tree.

| file (live == head sha256) | live bytes |
|---|---|
| `issue-already-done-detection.md` | 35f86337… | 2079 |
| `agent-behaviour-versioning.md` | 999a1417… | 12311 |
| `agent-profile-sync.md` | 907a44c9… | 9846 |
| `assertions-and-gates.md` | ca4797db… | 30070 |
| `ceiling-config-verdict-vs-defect.md` | e05731a6… | 3939 |
| `census-pointer-structural.md` | c357ec7c… | 5145 |
| `change-note-gate.md` | b099fcc1… | 3126 |
| `ci-gate-vs-live-pipeline.md` | 95c305e1… | 10235 |
| `pr-state-vs-mergeable-state.md` | f9958aef… | 5541 |
| `report-integrity.md` | 984848b1… | 6182 |
| `stalled-lane-and-dispatch-delivery.md` | 5afc8393… | 23012 |
| `verifying-lane-claims.md` | 4e2f0256… | 70404 |

Given the orchestration rules these files carry grew on this very host over prior lanes' work, they were
already partially captured (#1299 folded 12 live-only refs). This PR folds the residual drift: the 
one new file plus the eleven whose tree copies had fallen behind the live-authoritative content (the
same #791/"live is source of truth, never tree→live" bound).

Each `git cat-file -p <head>:<path> | sha256sum` == `sha256sum <live-file>` at head; `cmp` passes all
twelve; live stable 3× over ~16s pre-copy. Pure file-versioning: no content reworded, no planner
behaviour edit, no other lane's profile touched. `already-resolved-vs-live-slice.md` (#1224/#1229) and
the 12 refs folded in #1300 are NOT in this diff. Exception noted to the planner:
`mutation-readback-and-postmerge-verify.md` was #1300-folded at `b3ddd401…` (3504 B) and the planner
lane has since grown it live to `8e15ba4a…` (3972 B) — it is in #1300's "don't touch" set, so it is
**not** folded here; it remains a live-ahead drift for a follow-up fold.

## Verification

- `make bot-preflight` — exit 0 (AGENTS line cites `origin/main@8591e318`).
- `make check-docs BASE=origin/main` — exit 0 (change-note gate + `make changes-index`).
- Census referent `bb11bb1f` is an ancestor of HEAD.
- CI: the skills-class/unit set normal for a docs-and-references-only diff (live comparison skipped on
  the runner; host-only `test_agent_profiles.py` reds are ambient and reproduce identically on `main`).

## Issue / PR

Implements #1301 via PR (one vehicle, ready-for-review, not merged by the implementer — owner-gated).
