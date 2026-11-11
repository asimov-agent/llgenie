# Settled FYI that matches the board → absorb silently

A lane's message that only restates facts already on the board (a run that concluded, an
issue/PR state that already matches, a "wait-list down to ONE" recap) is a **convergence
echo**, not new information. Do not post a state-echo summary in reply.

Why: the owner explicitly flagged repeated turn-by-turn state summaries as a defect
("you are repeating yourself"). A planner who answers every settled FYI with the same
multi-line board recap produces noise, not work, and buries the signal when something
genuinely changes.

Rules:
- If the FYI's every claim matches the board, respond with **nothing** — no DM, no recap.
- If it carries exactly one wrong claim, correct that one claim and stop; do not append the
  full board.
- Report state to the OWNER only when it actually changed, and then in one or two lines.
- Repeated identical refusals from a lane (the phantom-stale-dispatch loop) are also
  convergence echoes: after the first reconciliation ("that dispatch was not mine; your
  only assignment is #<id>"), further refusals need no fourth near-identical reply.
- Weigh reading the API before restating — but once verified, silence beats a third echo.
- **A dispatch can arrive stale.** The auto-merge lane can self-approve and merge within seconds of a PR opening, so a
  follow-up like "the gate cleared, now pick up #N" reaches the lane after #N is closed and reads as the planner not
  having read the board. Before any follow-up naming an issue as still-to-do, re-read that issue's `state` and its
  PR's `state` on the API in the same turn; if closed/merged, drop the nudge and verify acceptance on `main` instead.
  A lane's "your dispatch is stale" with a merge sha is a board fact, not a challenge — absorb it, no reply.

A quiet planner reply is correct. Repeating the board is the defect.
