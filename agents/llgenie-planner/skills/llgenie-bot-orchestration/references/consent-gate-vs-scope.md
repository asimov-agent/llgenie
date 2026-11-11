# Protected agent-instruction writes: scope ruling is NOT write consent

A lane editing its OWN SOUL / protected agent-instruction file under `agents/<lane>/`
(per #791) still hits the lane's live desktop one-operation human-approval prompt for
that specific file. These are TWO DIFFERENT gates and must never be conflated:

1. **Scope authorization** (planner ruling) — decides WHETHER the lane may edit the
   file. Given on-issue, on-record, permanent (does not expire).
2. **Write consent** — the lane's desktop approval prompt; only the OWNER answers it;
   a ruling/dispatch/DM does NOT substitute. Silence is NOT consent: a timed-out
   prompt means the write did NOT land and must NOT be retried via terminal,
   execute_code, another lane's dispatch, or "auto-approve".

If a lane reports N consent-prompt timeouts, the correct planner response is to escalate
to the OWNER (face the decision: owner answers the prompt = permanent grant, or owner
writes on-record that the file commits without a desktop prompt) — NEVER to offer a
route-around. A protected gate is not a procedure you can bypass; offering one teaches
the lane to distrust the planner's judgment. Withdraw the offer explicitly when the
lane declines.

Verify the stranded write: the file at the PR head genuinely lacks the required content
(e.g. `git show <head>:agents/<lane>/SOUL.md` = 0 hits) — confirms the timeout is real,
not a lane stalling. The fix lands as ONE commit carrying the file content AND the
close keyword (a squash close-set match), pushed as a real commit (a body edit will not
re-trigger a unit test), then re-run the affected job.
