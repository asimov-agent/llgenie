# Fold the missed 13th planner reference: mutation-readback-and-postmerge-verify.md live-ahead update (#1303)

## What shipped

Follow-up corrective fold to #1301/#1302. `mutation-readback-and-postmerge-verify.md` under
`agents/llgenie-planner/skills/llgenie-bot-orchestration/references/` was folded byte-identical by #1300
(tree `b3ddd401…`, 3504 B) but the planner lane grew it live since. This is the remaining live-ahead
drift (#1302 amendment miss), folded live→tree **byte-identical** per #791/#1062/#1273 (live is source
of truth; re-measured at branch time).

| file | head == live sha256 | live bytes |
|---|---|---|
| `mutation-readback-and-postmerge-verify.md` | 8e15ba4a… | 3972 |

`git cat-file -p <head>:<path> | sha256sum` == `sha256sum <live-file>`; `cmp` passes; live stable 3× over
~14s pre-copy. Single file — the 12 #1302 folds are each confirmed byte-identical on main and NOT
touched. No content reworded, no planner behaviour edit, no other lane's profile.

## Verification

- `make bot-preflight` — exit 0 (AGENTS line cites `origin/main@57c34127`).
- `make check-docs BASE=origin/main` — exit 0 (change-note gate + `make changes-index`).
- Census referent `bb11bb1f` ancestor of HEAD; 14↕14 CI at head normal.

## Issue / PR

Implements #1303 via one PR (single vehicle, ready-for-review, not merged by the implementer —
owner-gated).
