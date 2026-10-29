# Proving a claim another bot handed you

Three checks that turn "a bot said so" into evidence. All are read-only: no worktree, no branch, nothing to clean up
afterwards.

## 1. Is the sha it measured really `main`?

```bash
gh api repos/<owner>/<repo>/commits/main --jq '.sha'
git -C <repo> fetch origin main --quiet && git -C <repo> rev-list --left-right --count HEAD...origin/main
git -C <repo> branch -r --contains <sha-they-cited>
```

- `branch -r --contains` naming only `fork/<branch>` means the numbers describe an unmerged PR branch.
- A local checkout `2 0` ahead of `origin/main` is the usual cause: an agent measuring "the working tree" measures
  whatever branch the owner left checked out, and a feature branch is not main.
- Consequence: the batch's counts are unverified, and any acceptance criterion quoting them cannot be ticked
  honestly. Correct in public, ask the filer to re-measure and cite the sha.

## 2. Does the claimed count name the right population?

Grep against a tree-ish instead of checking out:

```bash
# files matching a pattern
git -C <repo> grep -l '<pattern>' origin/main -- <path>
# definitions by name
git -C <repo> grep -c '^\s*def <name>(' origin/main -- scripts
# a file's size / a specific line
git -C <repo> show origin/main:<file> | wc -l
git -C <repo> grep -n '<symbol>' origin/main -- <file>
```

Populations that look like the same number and are not: *definitions named X*, *definitions whose body lacks Y*,
*all helpers under any spelling*. Name the population, state the enumerating command, and eyeball two or three known
members before ticking.

## 3. Do two PRs actually conflict, and what is the resolution?

```bash
git -C <repo> fetch origin \
  'refs/pull/<a>/head:refs/remotes/origin/pr-a' \
  'refs/pull/<b>/head:refs/remotes/origin/pr-b' --force
git -C <repo> merge-tree --write-tree origin/pr-a origin/pr-b
```

`merge-tree --write-tree` prints the merged tree sha, then one line per conflicted path in the form
`<mode> <sha-1> 1|2|3  <path>` (base, ours, theirs). Three entries for one path = a real conflict; no entries = it
would merge clean.

What to send back, per conflicted path:

1. the union line (both sides' data preserved, one entry per side),
2. both sides' tests kept, not one replaced,
3. any prose sentence whose subject count changed ("the one X" -> "the X and Y", and the duplicated paragraph
   deleted rather than kept twice).

Ask for the gate output on the **merged** tree (skill/wiring/docs/test targets), then post the recipe as a comment on
both PRs. A recipe that lives only in a DM is lost to whoever merges second.

## 4. Who approved that merge?

```bash
gh pr view <n> --repo <owner>/<repo> --json mergedAt,mergedBy,reviewDecision,author
gh api repos/<owner>/<repo>/pulls/<n>/reviews --jq '.[]|"\(.submitted_at) \(.user.login) \(.state)"'
```

An `APPROVED` review submitted by the same identity that then merges, seconds later, is an automated merge gate doing
what it was configured to do — not the owner's approval. Report it as an incident with both timestamps, and never
describe it to the owner as "you approved this".

## 5. Read the artefact before characterising the lane

A lane's DM is a summary; the PR thread is the record. Never conclude "that lane reports nothing" or "the verdict only
lives in chat" from the message you received — open the PR and count the comments:

```bash
gh pr view <n> --repo <owner>/<repo> --json comments --jq '.comments[] | "\(.createdAt) \(.author.login) \(.body|length)"'
```

A wrong characterisation costs the lane a defensive reply and costs you the trust needed for the next correction. Say
"I inferred that from the summary instead of reading the thread", in public, once.

## 6. Your own dispatch quotes a stale sha

The sha in a dispatch is stale by the time the lane reads it — the board moves in minutes. Write "fetch and branch from
the sha you get **now**, and name it in your start comment" rather than "branch from `<sha>`", and when you re-check
someone's head, re-check it in the same turn you quote it: `git ls-remote <remote> <branch>` decides the branch tip, and
a cached sha is history, not state.
