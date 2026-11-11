# "My tool channel is degraded" — verify before diagnosing a host incident

A lane reporting *"every terminal/file/execute_code result returns empty"* is a claim, not evidence of a broken host.

## Order of checks

1. **Ask for a minimal probe.** One `echo hi` or `date` from that lane. If the lane can read that output, its multi-line probes were the problem.
2. **Reproduce outside the lane.** Run the same class of command on your own shell. If your shell is fine, the failure is lane-local.
3. **Look for lane-authored artifacts.** A branch, a pushed commit, a bookend comment, a worktree on disk with the expected diff. A lane that can produce these was never actually wedged.
4. **Only then** consider a host cause (tmpfs inode exhaustion, full disk, tool-layer marshalling failure). Measure it (`df -i /tmp`) rather than asserting it.

## Lessons

- Two lanes "wedged" simultaneously is a coincidence until the second cause is measured separately. Do not let a pattern of two reports harden into an incident.
- The common real cause is the lane's own shell/Python quoting: unterminated f-strings, braces inside heredocs, `$(...)` expanded by the wrong shell. That produces empty-looking output on several probes while the channel is healthy.
- Keep the diagnosis provisional and say so on the board. A retraction is the *expected* outcome, not a surprise.
- **Never escalate host cleanup (deleting scratch trees, pruning worktrees, freeing tmpfs) on a lane's unverified report.** Cleanup destroys work if the report was wrong, and worktree/scratch deletion is the owner's call regardless.
- When the lane retracts, record the retraction on the issue so the next reader does not re-derive the false incident. The technical finding that came with it still stands and should be re-endorsed separately from the retracted claim.

## Incidental environment fact

Where the host cause *is* real: `/tmp` in a tmpfs has a fixed inode budget (this host: 1,048,576). Large engine-verification staging trees (venvs with tens of thousands of `site-packages` files) can exhaust it and then every tool write through `/tmp` fails. `df -i /tmp` plus `du -x --inodes -d1 /tmp` identifies the consumer in one shot. Report the number and the removal command; do not run the removal yourself.
