# A finished PR is armed when it is done, not when it is approved (fleet rule 16, #873)

> Measured against `upstream/main` **98466eb** (the sha this note and its PR were cut from).

The owner's directive is categorical: *"their skill behavior should always be to set the PRs to automerge when
they are done with the issue/pr work."* So "done" triggers the arm — the last push or the last green check —
not "approved". Operative, and pinned by [this paragraph][bots] in the merge gate's own doc:

- **The producing lane rolls its finished PR into the queue itself**: `gh pr merge <n> --squash --auto`, then
  **reads `autoMergeRequest` back** and states the arm time in the next comment. That command exits 0 while
  arming *nothing* when the base is not the default branch (`gh pr merge --auto` on a stacked base leaves
  `autoMergeRequest: null`, issue #964), so the exit code is not the fact — the read-back is.
- **A finished-but-unarmed PR is invisible to every merger sweep.** Arming is the producer's closing move, not
  a chore for whoever happens to sweep next.
- **One exception:** a PR the owner explicitly forbade is reported `auto=none (owner instruction)` with the
  line naming where the instruction lives. There is no other reason to leave a finished PR unarmed.
- **Companion (rule 13, #948):** `do-not-merge` is only for a real defect with the resolving issue named in
  the same comment, and never on a merged PR — a hold with no removal condition is abandonment, and a hold on
  a merged PR blocks nothing.

The automation side is already wired: `auto-merge` merges green, conflict-free PRs, and `#918` made the
concurrency honest (repo-wide per-outcome group, `cancel-in-progress: true`, success narrowed in the job `if:`)
so "armed" means "merged". Measured post-`#918`: 16 of the last 25 `auto-merge` runs concluded `success` with
job rows. Note: `workflow_run.types` cannot carry `success` (only `completed`/`in_progress`/`requested`), so the
conclusion filter lives in the job `if:`, not in the trigger — that is why `#918` reads as it does.

[bots]: docs/BOTS.md#a-green-conflict-free-pr-is-merged-by-ci-issue-482
