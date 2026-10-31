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

1. **Copy the canonical block from `agents/standing-rules.md`, byte-identically.** The rule's *issue* is
   the source of truth for the wording, but the file every gate compares a `SOUL.md` against is
   `agents/standing-rules.md` — so adding a rule means adding the bullet THERE first, then re-splicing the
   whole block into the SOUL and asserting `block in soul_text`. A SOUL-only edit fails `fleet-block-drift`
   ("the section is present but differs from the canonical text"). A new rule often arrives as a numbered
   item in the issue body, OUTSIDE the fenced block: extract it rather than retyping
   (`re.search(r"^\*\*(\d+)\. (.*)$", body, re.M)`, prefix `- **`) — a paraphrase fails the gate exactly
   as a typo does. The issue-extraction recipe, when the bullet is not in the fence yet:
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
5b. **`rules: []` is not "nothing to declare" — it is `UNPROTECTED`.** The gate prints "the manifest
   declares no standing rule for this profile, so nothing in its SOUL.md is gated — that is not the same as
   passing". Declare the rule the SOUL actually states (`never-implement` where the SOUL says "does not
   implement"), and never a rule the SOUL does not carry — that is the manifest defect the same gate exists
   to catch. One declared rule is enough to make the profile gated.
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
- **`agents/<profile>/SOUL.md` is a protected agent-instruction file: a direct write is refused with an
  approval prompt that can time out, and a timeout is NOT consent.** Do not route the edit around the guard
  (not through `terminal`, not by writing the profile copy and syncing backwards). Put the exact
  replacement text in the PR body/comment, land everything else, and report the one blocked sentence as an
  open item needing the owner's approval — a skill or reference file in the same tree is editable, so the
  operational half can still ship.
- **A host-only skill cannot be the survivor, but do not delete it first.** When the live profile skill is
  richer than its tree copy: copy the whole thing (SKILL.md + `references/` + `scripts/`) into
  `agents/<profile>/skills/<name>/`, rename the frontmatter `name:` to the directory name,
  `make sync-agent-profile PROFILE=<p>` then `CHECK=1` → `byte for byte`, and only THEN remove the
  host-only directory. Deleting first loses content nobody can diff; syncing is additive, so nothing is
  lost while both exist.
- **The canonical block grows while your branch is open, and a rebase can duplicate it.** Re-splice the
  whole block from the new base after every rebase, and check that each rule appears exactly once
  (`grep -c "^- \*\*<rule opening>"`) — merges that carry the same stream of rule additions leave the
  closing bullet followed by a second copy of the last three rules.
- **Sync is one-way: tree → live, and a live edit after the tree commit is never re-taken backwards.**
  `check-agent-profiles` distinguishes `fleet-block-drift` (a bullet missing from the SOUL), `live-longer` /
  `live-lines-missing` (a live file larger, or carrying lines the tree lacks), `live-edited-not-tree` (live
  mtime after the tree commit) and `UNPROTECTED`. For the live-ahead cases the gate's own instruction is the
  rule: *commit the live content via an issue+PR under `agents/<lane>/`, then `make sync-agent-profile`* —
  never copy the live file back into the tree, and never `--force` the sync. Forcing discards lines nobody
  diffed; the reload is only "byte-identical" once the tree catches up.
- **A live profile that regrows after you sync has a WRITER — name it from the live ledger, not from memory.**
  The re-growth shows up as `live-edited-not-tree` again with a newer mtime, so `sync-agent-profile` can never
  close it. Read the live profile's own ledger before blaming a human or a cron:
  `~/.hermes/profiles/<p>/skills/.curator_ledger.jsonl` carries per-patch `{actor, action, skill, before, after}`,
  and `actor:curator` means Hermes's native lesson-capture patched the live skill mid-session (it appends the
  procedure just demonstrated). Quote the timestamps and the `before`/`after` hashes in the issue as writer
  evidence; the root fix (curator exclusion / live-write gate) belongs to the issue that owns it, not to your
  sync PR.
- **Fold live-ahead content into the tree; never byte-copy it over a rulebook.** When the live file is a strict
  superset, a byte copy is safe; when the tree carries a section the live file lacks (this lane's `## Rules` /
  `## Procedure` / `## Never` block), copying live→tree **deletes it**, and the next one-way tree→live sync then
  deletes it from the running profile too. Union the sections explicitly and say in the PR which section is
  tree-only and why it survives. Each fold round gets its own issue+PR — content that regenerates mid-review is
  the next vehicle, not a reason to reopen the PR you already armed.
- **A section spliced above a markdown heading keeps a blank line in front of it.** `lint_linefeeds` reds a
  `##` heading that directly follows text, and it is a different gate from `check-agent-profiles` — so
  splicing a block in front of `## Standing rules` can pass the canonical-block assertion and still red
  `make lint`. After any splice check both: `block in soul_text` AND `make lint` on the changed file.
- **Do not edit another lane's SOUL or skill to make a gate green.** When the gate names a different profile,
  report the numbers and hand it to that lane; only a lane edits its own behaviour files. A pre-existing
  failure is proved pre-existing by stashing your change and re-running the gate, not by assuming it.
