# Handoff brief: one issue to one implementer

Fill every line; the implementer starts from this and may not ask questions. Send it as one
`message_agent` call to the implementer profile — a fire-and-forget delivery, so the brief has to be
complete on its own and must name what to report back.

```
Handoff from planner: implement <repo> issue #<n> (verdict: <implement|refine-then-implement>).
Repo: <absolute path> — origin is <UPSTREAM|fork>; push to the <remote> remote.

Why you: <who tried before and what they left behind — the phantom claim, the 404 branch, the closed PR —
and whether any competing branch or live claim exists. State that the label is absent so the in-repo bot
will not race you, or that the label was removed for this run.>

The defect: <the measured symptom, with the number, the command and the tip sha it was measured on.>
Required direction: <the shape of the fix in one or two sentences, including the failure mode it must NOT
introduce — "do not weaken the check into always-pass" — because an implementer left unconstrained will
satisfy the letter of the ask.>

Constraints:
- Fresh worktree off `origin/main`; no reuse of an existing worktree.
- One branch, one PR, ready-for-review (never `--draft`), body carries `closes #<n>`. Never merge.
- Gates through make only: <the repo's gate list>.
- Real behaviour in the test that proves the new rule — no mocks for the thing under test.
- <repo-specific setup step: openspec-new plus the chown, or the remote the push goes to.>

Report back: PR URL, branch, gate results, and anything you could not land.
```

## Rules for the sender

- **One issue per message.** Two issues in one brief produce one branch and one silent drop, and the drop
  is invisible until someone re-reads the queue.
- **Quote the measurement, not the ticket title.** The implementer cannot re-derive "it is broken"; it can
  reproduce a command and a number.
- **Name the anti-goal.** Every defect of this kind has a lazy fix that makes the symptom vanish (skip the
  gate, catch and pass, delete the test); rule it out in the same sentence as the fix.
- **Keep merge out of it.** The owner approves every merge; the implementer's deliverable is a reviewable PR.
