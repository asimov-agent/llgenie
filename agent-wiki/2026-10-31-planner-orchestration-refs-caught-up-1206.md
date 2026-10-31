# Planner orchestration refs caught up to live, live→tree (issues #1206)

The planner lane's versioned tree under `agents/llgenie-planner/skills/llgenie-bot-orchestration/references/`
lagged the live profile on two references grown this session. `make sync-agent-profile
PROFILE=llgenie-planner CHECK=1` would not report byte-identity until the tree carried the current
live bytes. Both files are now committed byte-identical to the live profile, verifying the lane's
versioned surface matches what the running planner actually uses:

- **`verifying-lane-claims.md`** — live 37,795 b (tree was 15,802 b). The grown §5b lesson: *a real
  drift is still not the reporting lane's work — ownership follows the tree.*
- **`stalled-lane-and-dispatch-delivery.md`** — live 15,699 b (tree was 12,381 b). The grown rule:
  *a lane's stated "queue now" line is a claim — verify it against the dispatch list.* The #1140
  silent-drop-then-redispatch lesson: a lane's reported queue can omit a queued issue; cross-check
  `gh pr view <n>` + `git show origin/main:<defect-site>` before crediting the line, and re-dispatch
  on-record when genuinely unfixed.

This is profile versioning (#791, #1062) — the implementer lane commits the live text byte-identical;
it is not planner implementation and is not merged by the implementer (owner approval). Both files
verified byte-identical to `/home/asimov/.hermes/profiles/llgenie-planner/` at branch time; the
paired `docs/changes.d/` row + `CHANGES.md` index satisfy the change-note gate (#1123).
