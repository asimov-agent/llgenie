# Fork-sourced PRs (push target, head repo, comment identity)

Every implementer PR in `asimov-agent/llgenie` is a FORK PR whose head repo is
`andyholst/llgenie`. `origin` is the owner/merge side (`asimov-agent/llgenie`) and is
read-only for you.

## Push to the fork, not origin

- Push the branch: `git push fork <branch>` (the `fork` remote points at
  `https://github.com/andyholst/llgenie`).
- Open the PR fork-sourced: `gh pr create --base main --head andyholst:<branch> --body-file <f>`.
- Verify the head repo after opening:
  `gh api repos/asimov-agent/llgenie/pulls/<n> --jq .head.repo.full_name` must read
  `andyholst/llgenie`.

**Why origin-push is a defect even when it "works":** pushing to `origin` succeeds and a PR
opens, but it is origin-headed. The dispatcher/board measures the FORK ref
(`github.com/andyholst/llgenie/branches/<branch>`), which 404s for an origin-only push, so the
board reads your branch as "created but pushed nothing" and can report a stall on gate-free work.
All sibling PRs (#1681, #1680, #1655 in one window) were fork-headed; match them.

## Recovering an origin-head PR (keep ONE vehicle)

If you already opened an origin-head PR: do NOT close it and open a second (violates the
one-issue-one-branch-one-PR rule). Instead push the SAME commit to the fork so the fork ref
exists — same sha, no CI re-run, single vehicle intact:

    git push fork <branch>     # fork ref now == origin head sha
    git ls-remote fork refs/heads/<branch>   # verify same sha

Re-source the PR to `andyholst:` head only if the board explicitly requires it.

## Bot comments are authored under the human account

Issue/PR comments you post land under the human `andyholst` login, not a bot username. When
checking whether your bookend exists, `gh api repos/asimov-agent/llgenie/issues/<n>/comments --jq '.[] | .user.login'`
shows `andyholst` for your own posts — a filter on a bot-specific login returns empty and tempts a
false "zero implementer comments."
