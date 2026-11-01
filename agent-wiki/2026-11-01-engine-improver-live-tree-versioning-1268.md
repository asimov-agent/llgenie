# Version engine-improver live→tree drift (#1268)

The engine-improver lane's **live profile is ahead of the tree copy** under `agents/llgenie-engine-improver/` — the recurring drift #1156 tracks (`make sync-agent-profile PROFILE=llgenie-engine-improver CHECK=1`). This change versions the live-only edits into the tree so the one-way sync can run without truncating live behaviour.

## What drifted (`CHECK=1`, on main 543466ca)

| file | tree (b) | live (b) |
|---|---|---|
| `SOUL.md` | 10,473 | 10,849 |
| `skills/…/SKILL.md` | 91,355 | 100,590 |
| `skills/…/references/engine-image-cells.md` | 3,576 | 4,891 |
| `skills/…/references/proving-and-pitfalls.md` | 19,340 | 21,675 |
| `skills/…/references/engine-install-leg.md` | 13,010 (tree AHEAD) | 12,555 |

Four files are live-ahead and are copied **byte-identically** live→tree. `engine-install-leg.md` is deliberately **left** — the tree is now AHEAD of live (it carries the product-LESS #1027 language merged via #1220), so copying live→tree would regress it; the live copy should pick that up on a later tree→live sync.

## Content

- **SOUL**: owner's "Arm auto-merge when the work is done" directive replaces the never-arm line — reads `.autoMergeRequest` back, never approves own PR, never hand-merges.
- **SKILL**: the "Role artifact (2026-11-01)" block: an engine change is this lane's PR; the arm does not survive a base move (`autoMergeRequest: null`, `mergeable_state: dirty`) → rebase → re-push → re-arm → re-read, and re-run checks rather than quoting an old-base run.
- **engine-image-cells.md / proving-and-pitfalls.md**: expanded reference lessons (dispatch-run-pinned-to-older-sha stays valid when inputs are byte-identical; a peer's ruling must name the tip, checked via `/pulls/<n>` head).

Verify at head: `check_agent_profiles.py` (HERMES_PROFILES_HOME=/nonexistent) shows 0 engine findings; `make lint`; `make check-docs` census green. Arm on green per #964 (read `autoMergeRequest.enabled_at` back, not the exit code). Merge owner-gated.
