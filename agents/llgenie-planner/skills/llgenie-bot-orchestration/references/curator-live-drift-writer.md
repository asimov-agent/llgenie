# Curator is the live-drift writer (the real #1156 mechanism)

**Verified 2026-10-31** via `.curator_ledger.jsonl` in each profile's `skills/` dir: when llgenie lanes' LIVE profiles re-grow drift after every clearing PR, the writer is **Hermes's native skill curator**, not a cron and not lane discipline.

## Evidence signature
- Ledger lines carry `"actor": "curator"`, `"action": "patch"`, a `skill` name, the lane's own `session_id`, and a `file_path`.
- A lane's own writes show as `"actor": "agent"` — distinguish its `skill_manage` (actor=agent) from session-end curator consolidation (actor=curator).
- Timestamps land in a burst (e.g. 11:29:45→59) right after a clearing vehicle, always at session end.
- `jev-curator.yaml` (Hermes plugin catalog) only WRAPS the curator lifecycle (`on_skill_lifecycle`, 60s debounce, fail-closed) — it does not write; the native curator does.

## Consequence for dispatch
- A "clears the <lane> rows of #1060/#961" PR only clears a SNAPSHOT; the curator regenerates the diff at next session end unless told to leave `agents/<lane>/skills/**` alone.
- **Do not file a FOLLOW-UP repo vPR to chase re-grown files** — it is drift again by merge time. Chase the writer first.
- The fix is a **Hermes USER-CONFIG curator exclusion** of the tree path (`agents/<lane>/skills/**`), NOT an llgenie-repo PR: a repo PR under `agents/` cannot touch host Hermes config and would be a cosmetic no-op.
- Correct home: file/refine the ISSUE with ledger evidence + exact config dial + acceptance (zero live-only writes to a versioned tree skill on a fresh session), tag owner escalation, relay to owner. Curator under PLUGIN config is not a lane's domain — confirm routing before dispatching a lane to edit it.
- Live-drift has **TWO independent writers** on this host (both measured, both #1156 root-cause lines): (1) the dirty-watch cron 244a75ddc597 (pr-merge-conflict profile) which writes live skills across lanes, and (2) the in-session Hermes native curator (own-session `actor=curator` ledger patches). Killing the cron is necessary but NOT sufficient; the curator exclusion (agents/<lane>/skills/**) is required too. Do not consolidate to a single writer — attribute both, each with its own byte-level ledger/cron evidence.

## The same writer silently reverts YOUR edit to a live skill file

The writer does not only re-grow files after a merge — it can overwrite an edit that is already in flight. Measured: a live `SKILL.md` edited by hand came back at its pre-edit size, with the old text restored and only the concurrent lane's later addition applied on top. The mechanism is the one above — a writer that read the file *before* your write saves its own copy afterwards and wins.

- **Re-read the file after the write completes**, not just after the tool returns success. A `skill_manage` patch or `write_file` returning `verified: true` proves the bytes landed at that instant, not that they survived the next writer. Compare the size you wrote with the size on disk.
- **Sequence around the other lane.** If a cron or a lane is mid-turn on the same skill, let its task reach a terminal state, then write, then verify. Writing first and verifying later buys a silent revert.
- **The tell is a size that grew while your edit went backwards** — the file was regenerated from a stale base with the other writer's addition on top, so the literal you removed is back and new content has arrived.
- **Re-apply once the other writer is idle, then confirm stability by re-reading after a short pause.** Two re-applications confirm the pattern; do not keep re-applying into a live writer and calling it fixed.
