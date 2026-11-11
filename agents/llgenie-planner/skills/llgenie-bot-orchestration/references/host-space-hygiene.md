# Host Space Hygiene — preflight, placement, occupant triage

**Lesson (measured 2026-11-02):** the host `/tmp` tmpfs (32G, 1,048,576 inodes) is the shared resource every lane builds in, and it has NO gate. A single probe tree `/tmp/trtllm-probe` (15G, ~197k inodes) drove it to 71% space AND 100% inodes simultaneously and wedged TWO lanes in one pass: the implementer's tool-output channel (containerized probes failing) and the reviewer's #1579 worktree-add ENOSPC.

## The rule: preflight before dispatch, not reactively
1. **Measure every dispatch:** `df -h /tmp` + `df -i /tmp` before dispatching a lane or placing a heavy worktree.
2. **Threshold gate:** below ~20% space OR ~50k free inodes → refuse to spawn a /tmp consumer; escalate to the owner with the df numbers instead of starting a doomed build.
3. **Placement:** heavy worktrees default to REAL DISK (`$HOME/repository/git/llgenie-wt/`), never /tmp. /tmp holds only small/scratch files.
4. **Occupant rule:** a large probe/scan tree grown by a lane belongs on disk or is cleaned by its owner; never let one tree hold the shared tmpfs hostage.
5. **Cleanup stays owner-gated:** `sudo rm -rf <occupant>` of /tmp is an OWNER decision, never a lane/planner default. But identifying the occupant (`du -sh /tmp/*`) and escalating with the df figures is the PLANNER's job.

## What does NOT count as a gate (verified)
- `make ci-free-disk` (Makefile:1876): CI-runner disk for large engine images only, host-agnostic. Not a /tmp check.
- No workflow, script, or gate greps host df/disk. The tree is blind to this hazard — codify it as issue+PR under `agents/` (#791), never a private habit.

## Reference numbers (owner-authorized cleanup, 2026-11-02)
- Pre: 9.2G free space (71% used) / 5,714 inodes free (100% used).
- Post `sudo rm -rf /tmp/trtllm-probe`: 25G free (24% used) / 203,361 inodes free (81% used). Reclaimed ~15.7G and ~197k inodes.
- Side effect of letting it fill: implementer 'tool channel degraded' (self-retracted, own syntax errors — but /tmp WAS genuinely full) and reviewer ENOSPC on worktree-add.
