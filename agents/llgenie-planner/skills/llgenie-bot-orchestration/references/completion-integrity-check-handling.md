# Completion-integrity / nerve check handling (mid-pass)

A completion-integrity probe ("no task-relevant mutation was attempted") that fires after you
already made a verified mutation is **not** an instruction to manufacture another one. It is a
prompt to re-measure. Handle it in this order:

1. **Re-check what is genuinely newly measured** since your last mutation (new merge on main, a
   lane's run/repro that finished, a branch head that moved). If nothing new exists, say so and
   stop — a hollow comment or edit posted only to satisfy the probe trains churn and burns the
   board. State plainly why nothing is owed.
2. **Distinguish "nothing new" from "a new fact I left implicit."** When a lane's work changes
   state (a repro concludes, a job finishes) and the board does not yet reflect the measured
   outcome, recording that verified reconciliation **is** the task-relevant change owed. Post it
   with the measured evidence and confirm the read-back (comment id / URL).
3. **Measure the lane's actual remote deliverable before recording it as done.** A repro or run
   concluding *locally* is not a push. Read the remote branch head (`git ls-remote <fork> 'refs/heads/<branch>'`)
   and the PR head sha (`gh api .../pulls/<n> --jq .head.sha`). If the head is unchanged, the
   lane's verdict + fix push is still owed — record that state, keep the tracker box unticked, and
   do not imply success.
4. **Never satisfy the probe by editing a peer lane's branch or file**, or by widening another
   lane's scope. That breaks lane boundaries; a red probe is preferred to that.

## On a planner turn the probe's premise is wrong

A planner never edits the tree — filing the tracked issue, posting the `bot-claim:`, and dispatching
the owning lane **are** the task-relevant mutations, and they are all GitHub-side. So "no changed
tree path" is the expected, correct state of a finished planner pass, never evidence of an
incomplete one. The tree evidence for that work is the owning lane's merge, which lands later.

When the probe re-fires within the same turn, do not re-litigate it and do not invent an edit to
silence it. Measure whether the lane has started and state the status once:

```bash
git ls-remote origin 'refs/heads/agent/issue-<n>-*' 'refs/heads/fix/*<n>*'   # empty ⇒ not started
gh pr list --state open --search '<n>' --json number,headRefName              # empty ⇒ no vehicle
git show origin/main:<offending file> | grep -nE '<refused shape>'            # still on main ⇒ fix not landed
```

Report "planner slice complete, fix delegated, still in flight" with those three reads as the
proof. Manufacturing a code edit to turn the probe green is both the forbidden act (a planner
branch/PR is a mistake) and the wrong fix (the defect belongs to the lane that introduced it).

Every mutation you record carries the sha and timestamp it was measured at, and you verify the
read-back before claiming it landed.

## Recon-script pitfall

When scripting `gh api ... --jq` inside a bash `for` loop, jq expressions containing parens such as
`($i|tostring)` are parsed by the *shell* first and error with `syntax error near unexpected token`.
Write separate invocations per issue/branch, or keep the jq body in single quotes with no shell
metacharacters leaking. Redirect the block to a file (`{ ...; } > file`) and read the file back so a
mid-script failure is visible rather than lost in interleaved stdout.
