# Verifying a lane's claims before you repeat them

A lane's report is a claim; the API and the object store are the evidence. Four repeat offenders
seen in practice, each with the check that settles it.

## 1. "Committed `<sha>`, merge-clean on main" → often the lane's OWN clone

Lanes build in sibling clones (e.g. `/home/asimov/repository/git/ai-repositories/llgenie`), not in
the planner's tree and not upstream. `git -C /home/asimov/repository/git/llgenie cat-file -t <sha>`
returning `fatal: Not a valid object name` does **not** mean the lane fabricated the commit.

Check, in order:

```bash
# where does it actually live?
for d in /home/asimov/repository/git/ai-repositories/llgenie; do git -C "$d" cat-file -t <sha>; done
# what's in it (file count / insertions should match the lane's description)
git -C <sibling> show --stat --oneline <sha>
# is it published, or held for the owner's gate?
git ls-remote origin refs/heads/<branch>     # empty output = not pushed (owner-gate), which is correct for lane work
```

A commit that resolves in a sibling clone with the described file count is verified work, not a
phantom. Say "held locally, owner-gated" — never "unpushed and therefore unverified".

## 2. Worktree listing is not the evidence either

`git worktree list --porcelain` shows worktrees of one clone only; a lane's work can be in a
sibling clone that no worktree listing mentions. Search clones and branches, not just worktrees.

## 3. Run-level duration includes queue dwell

Sweep tools that print `run.created_at → run.completed_at` are queue-inclusive: `217m24s` and
`246m02s` are starved runners, not test legs. The real leg wall is job-level:

```bash
gh api repos/asimov-agent/llgenie/actions/runs/<id>/jobs --jq \
  '[.jobs[]|select(.name=="linux / unit")|"competition \(.started_at)→\(.completed_at)"]'
```

Quote the job-level span when the claim is "the unit leg took N minutes".

## 4. Short shas and stale posts

- An 8-char prefix is not an identity. A re-author (off-allowlist → allowlisted) produces a *new*
  commit that can share the old prefix family; read `headRefOid` in full before comparing heads,
  and verify ancestry with `git merge-base --is-ancestor` / `compare` (expect `diverged a1/b1`,
  not an ancestor).
- A lane's message can be generated *before* your correction lands. Compare the timestamp of the
  comment it quotes against the timestamp of your correction; a "fresh pasted" post that predates
  the correction is stale board state, not a refusal to read the API. Say so plainly and re-send
  the corrected fields once, with the exact job id.
