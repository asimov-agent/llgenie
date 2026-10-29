# Implementer remote/ref measurement lessons (2026-10-29)

Two measurement-discipline lessons versioned onto `feat/agent-profile-implementer-skill` (#919) and pinned
by tests with negative controls.

- **A PR's head is the REMOTE branch, not a local worktree or scratch ref.** During the fleet stop a lane
  claimed "#919 advanced under the freeze", citing `e9c7e7f3`, `7e4a8519`, `5e74cb68`. All three resolved to
  LOCAL scratch branches (`tmp/retake-myskill`, `tmp/lint-fix`, `pr944-replay`) — never pushed — while the
  remote #919 head was frozen throughout. The authoritative read is twice-verified:
  `git ls-remote origin refs/heads/<branch>` and `gh pr view <n> --json headRefOid` must agree; a disputed
  sha's membership on the branch is one command, `git merge-base --is-ancestor <sha> origin/<branch>`.
  `tmp/` and `pr<N>-*` worktrees are local, disposable, and NOT the PR's history.
- **A refname can be AMBIGUOUS and read a stale ref — fetch with an explicit refspec.** `git rev-parse
  origin/main` returned `6d9fef1d` (an old leftover) instead of the real current main `238dcd2c`, because
  the short name resolved to something other than the remote-tracking ref — so a base-watch claimed #919
  was "~1 behind" against a wrong sha. The fresh-main rule is
  `git fetch origin +refs/heads/main:refs/remotes/origin/main` then read `refs/remotes/origin/main`.

Referenced: `agents/llgenie-issse-implementer/skills/containerized-repo-verification/references/queue-and-pr-mechanics.md`,
`tests/test_agent_profiles.py` (`test_the_pr_head_is_the_remote_branch_lesson_is_in_the_skill`,
`test_the_ambiguous_refname_lesson_is_in_the_skill`). Board: #919 `MERGEABLE/BLOCKED` armed.
