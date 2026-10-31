# Version the planner's security/architect advisory-solicitation duty

Implements #1195. The rule text lives under `agents/llgenie-planner/skills/llgenie-bot-orchestration/SKILL.md`
§2c (this PR); the planner's `SOUL.md` is a protected agent-instruction file and is left on the old text when the
carrier's write is consent-blocked — the duty is carried in the writable skill carrier and the SOUL half is stated
here as owed.

## What was versioned

The planner's orchestration skill now states the solicitation+classification duty that #1195 demands: before a
change is treated as mergeable, the planner classifies it (`security` / `arch` / `both` / `none`), writes the
classification into the PR's routing comment (so the boundary was assessed, not assumed), and dispatches the
matching advisory lane(s) on-record:

- `security` boundary (`auth`, network egress, file/pipe writes, credential handling, downloads / `hub_open`) →
  `llgenie-security`;
- `arch` surface (pipeline shape, admittance/gates, engine-variant coherence) → `llgenie-architect`;
- `both` → both lanes; `none` → no advisory, and the comment says `none` so the absence is a decision.

The advisory is **solicited and answered, never silently skipped** (a busy advisory lane is forced onto the advisory
like any forced-delegation, #1030; a lane that cannot answer reports `cannot answer: <reason>`). The verdict is
**advisory, not a merge gate** — approval stays the owner's (#1088).

## Verified

`make check-agent-profiles` green at head (no live-profile comparison on this checkout); the note+fragment make the
`changes/` index stay consistent for `make check-docs`.
