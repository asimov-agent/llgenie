# Fleet failure modes: loops, collisions, lost worktrees

Depth for the orchestration loop. Load when a bot looks busy but nothing lands, when two dispatchers are live, or
when a branch exists only on one machine.

## Tell a slow bot from a looping one, then break the loop

A host bot with nothing on the repo may be working or may be spinning, and the difference decides what you send next.
Measure its own profile, not the repo:

```bash
stat -c '%y' ~/.hermes/profiles/<profile>/state.db                 # last write = last activity
tail -5 ~/.hermes/profiles/<profile>/logs/agent.log               # "API call #N" = how many turns burned
git -C <its worktree> log --oneline -1; git -C <its worktree> status --porcelain | wc -l
```

A live session with a high turn count, an unchanged branch tip and a fixed set of uncommitted paths is a loop, not
progress. Breaking it is a dispatch problem, not a persuasion problem:

- **Reduce the brief to the exact commands**, one fenced block: `git add -A && git commit -m "…" && git fetch origin &&
  git rebase origin/main && git push origin HEAD:<existing branch>`, then the `gh pr create` line. No gates, no
  analysis, no options — a looping agent asked to choose will choose to explore.
- **Remove the unreachable gate.** A local suite that cannot finish inside the agent's terminal cap will never go
  green; say "CI is the referee, commit and push" and name the CI duration so the instruction is checkable.
- **Move the specialist-shaped slice elsewhere** (see the routing table in SKILL.md §2b) instead of queueing a second
  item behind the stuck one.
- **Re-push onto the branch that already exists for the issue.** Two branches for one issue is the failure the claim
  rule exists to prevent; name the remote branch and its sha in the instruction.
- **Withdraw the rest of its queue in writing.** A stuck bot handed twelve issues will keep starting new ones
  instead of finishing the first. Say which items are *parked, not deferred*, name who took the slice you moved, and
  promise to re-issue one at a time once the artifact exists — then keep that promise. The brief becomes: one task,
  the exact commands, report one line (the PR URL).

Pushing a third or fourth polite brief at a looping bot is the mistake: the artifact count has not changed, and the
queue grows while you rephrase.

## Two dispatchers, one bot

When a recurring tick and an interactive session both orchestrate, they will hand one bot different orders — the
tick queues twelve items while you strip the queue to one, and the bot follows whichever arrived last. Reconcile by
naming the order once, in writing, to that bot (*"this supersedes the earlier brief: #X only, everything else is
parked"*), and keep the tick out of lanes that already have an order. Two orchestrators is the same failure as two
builders: duplicated, contradictory work that looks like activity.

## A worktree is not storage

Uncommitted work in a worktree is a file nobody saved, sitting in a directory that a branch switch, a sweep or a
container permission error can empty. Measured: a complete implementation — a new tree, two scripts, a 14 KB test file,
Makefile targets, an OpenSpec change and a wiki note — was lost when its worktree was repurposed to an unrelated
branch, because the branch had never been committed to. `git branch --list <branch>` showing the base sha and
`git ls-tree -r <branch> | grep -c '^agents/'` returning 0 is the proof that nothing survived.

- **Commit before the lane changes branch, in every brief.** "Commit and push before you touch anything else" is a
  preflight line, not advice.
- **Insure an unpushed branch** rather than trusting it: `git format-patch <base>..HEAD -o <scratch>/` plus
  `git bundle create <scratch>/<n>.bundle <base>..HEAD` — three files and 40 KB recover a lost afternoon.
- **Check the worktree, not the claim**: `git -C <worktree> log --oneline -1`, `git status --porcelain | wc -l`, and the
  remote branch's sha. A clean tree on an unrelated branch is a deleted implementation, not a finished one.

## Two heads in an hour

A PR whose head moves faster than its matrix runs will never produce a cited verdict: each push cancels the run and
discards the successes already paid for. The diagnostic sentence is not "CI is broken", it is "the head moved before
any run could finish". Freeze the sha, forbid cosmetic pushes, and allow the next push only after a verdict lands.
