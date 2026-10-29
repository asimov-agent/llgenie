# Versioning this lane's behaviour (SOUL.md) into the repo

An agent's behaviour is a repository artifact: it changes by issue **and** PR under
`agents/<profile>/`, never by editing `~/.hermes/profiles/<profile>/SOUL.md` directly — an
instruction that changes what a credential-holding agent does must be diffable and reviewable.

## Layout

```
agents/manifest.json                 # the index: which profiles this tree is the source of truth for
agents/<profile>/SOUL.md             # the role + standing rules
agents/<profile>/skills/<name>/SKILL.md
```

`make sync-agent-profile PROFILE=<name>` copies `agents/<name>/` into that profile's Hermes home;
`make check-agent-profiles` gates the tree.

## Procedure

1. **Read the canonical rule block from its issue, and copy it byte-identically.** Fetch the issue body
   and extract the fenced block programmatically rather than retyping it — a paraphrased block fails the
   acceptance criterion and makes a cross-lane diff lie:
   ```bash
   gh issue view <n> --repo <owner/repo> --json body --jq .body > /tmp/issue.md
   python3 - <<'PY'
   import re, pathlib
   t = pathlib.Path("/tmp/issue.md").read_text()
   block = re.search(r"### Canonical block\n\n```\n(.*?)\n```\n", t, re.S).group(1)
   pathlib.Path("/tmp/canonical.txt").write_text(block)
   PY
   ```
   Then prove it after writing: `print(block in soul_text)` → must be `True`.
2. **Add only lane rules the canonical block cannot express** — the security lane's shape is: never
   weaken a gate to go green; report scope instead of implementing; verify before asserting a secret is
   missing; read a write back before believing it; treat a scanner as untrusted code; the scan is its own
   pipeline; a finding carries its run id and digests.
3. **Add the manifest entry in the same PR.** The gate treats *a profile directory the manifest does not
   list* as a failure ("a tree nobody syncs and nobody gates"), so a SOUL.md without the entry reds `main`
   the moment the tree lands.
4. **Stack on the branch that creates the tree, when it is not on `main` yet.** `agents/` and
   `manifest.json` existing only in an open PR means your own branch cannot contain the manifest edit
   without duplicating that file. Branch from that PR's head instead — that is the fleet convention, and
   the diff collapses to your own files once the base PR merges:
   ```bash
   git fetch <fork-or-origin-url> feat/agents-profile-tree
   git checkout -B agents/<lane>-soul FETCH_HEAD
   ```
   Say so in the PR body (base PR + its sha), so a reviewer knows which commits are yours.
5. **Declare only manifest rules that are true.** `rules` accepts the keys the gate knows
   (`never-implement`, `never-merge`); an unknown key is a manifest defect, and a declared rule the
   `SOUL.md` stops stating is a finding. A lane that lands work through the repo's green-PR auto-merge
   declares `never-implement` only — declaring `never-merge` there would be false.
6. **Gate before the PR:** `python3 scripts/check_agent_profiles.py check` → OK, and it reports how many
   profiles it read (an unchecked tree passes vacuously).

## Pitfalls

- **The canonical block GROWS — re-extract, never hand-append the new bullet.** A rule added later
  arrives as one more bullet inside the same fenced block, and the version announced in chat is usually
  a paraphrase that differs by a sentence of evidence. On every update re-run the extraction over the
  issue body, replace the WHOLE block, and re-assert `block in soul_text`; appending the announced
  wording is how a cross-lane diff starts to lie.
- **Land it ready-for-review, never as a draft.** A draft is invisible to the merge queue, to
  auto-merge and to reviewers — and when the lane's output is a finding, a draft reads as "blocked on
  approvals" while the exposure stays open. A change that must prove itself first is named by run id
  and sha, not parked.
- Never `sync-agent-profile` over a live profile before the PR is merged: the repo copy then differs from
  the running behaviour with no diff to review.
- Another lane's SOUL branch is read-only; propose a patch as a review comment, do not push to it.
- The canonical block's *heading* is part of the contract (the gate and cross-lane diffs match on it) —
  copy the heading with the bullets.
- **Find the live tree PR by file, not from memory.** Consolidation PRs get closed and replaced by a new PR
  whose head branch keeps the same name, so a remembered number points at a closed PR with no `agents/` tree
  on its branch. Ask GitHub which OPEN PR touches the manifest:
  `gh pr list --state open --json number,headRefName,files` (or `gh pr view <n> --json files`) and base the
  lane branch on the one that is actually open; state its number and sha in the PR body.
- **A skill file in the tree needs frontmatter** — `---`, a `name:` identical to its directory, a non-empty
  `description:`, then the body. The profile gate fails on a missing block or a name/directory mismatch, and
  Hermes resolves a skill by the frontmatter name, so a mismatch means the profile loads nothing. Write the
  whole file instead of patching its frontmatter: an approximate patch at that boundary duplicates the block.
- **Do not edit another lane's SOUL or skill to make a gate green.** When the gate names a different profile,
  report the numbers and hand it to that lane; only a lane edits its own behaviour files. A pre-existing
  failure is proved pre-existing by stashing your change and re-running the gate, not by assuming it.
