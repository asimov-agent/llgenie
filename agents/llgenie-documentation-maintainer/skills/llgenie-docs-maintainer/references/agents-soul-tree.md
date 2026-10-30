# The `agents/` behaviour tree (SOUL.md, skills, manifest)

A bot's behaviour is a repository artifact on `asimov-agent/llgenie`, under `agents/<profile>/`, so
it can be diffed and reviewed. Editing it is a docs-lane change with its own gate.

## Layout and gate

```
agents/manifest.json                 the index: one entry per profile, each with `rules`
agents/<profile>/SOUL.md             the role + standing rules that profile runs under
agents/<profile>/skills/<name>/SKILL.md
```

- `make check-agent-profiles` is the gate. It fails on: a manifest profile with no directory, a
directory the manifest does not list, a profile with no `SOUL.md`, a skill whose frontmatter `name`
disagrees with its directory, an empty `description:`, a `references/<x>.md` named in a skill body
but absent, a secret-shaped value anywhere in the tree, and a `SOUL.md` that stops stating a rule its
manifest entry declares. Run `make -s lint check-agent-profiles check-pr-authors check-docs` before
pushing.
- `rules` is matched by REGEX over the SOUL text — `never-implement` needs a literal
  "never implement" (or "does not implement"), `never-merge` needs "never merge". Declaring a rule
  your lane genuinely does not hold makes the file lie; a lane that lands documentation-only PRs
  therefore declares `never-implement` only, and another profile carries `never-merge` (the gate
  requires at least one to).
- `make sync-agent-profile PROFILE=<name>` copies `agents/<name>/` into that profile's Hermes home.
  The local profile copy is a COPY: change behaviour here, by PR, and never only in the private file.

## Adding or updating a lane's SOUL

1. Read the instruction issue and take the canonical rules block from it **verbatim** — other lanes
   commit the same text, and the point is that a cross-profile diff shows identical lines. Extract it
   in code rather than retyping:

   ```python
   # tolerant of a heading suffix: it gets edited ("### Canonical block (16 rules — …)"),
   # and a bare '### Canonical block\n' regex then returns None instead of the block.
   block = re.search(r'### Canonical block[^\n]*\n\n```\n(.*?)\n```\n', issue_body, re.S).group(1)
   assert block in soul_text            # the assertion IS the deliverable, not a comment
   assert '## Standing rules (fleet' in soul_text
   ```
2. **Re-extract on every update.** The canonical block grows as rules are learned, so text that was
   verbatim yesterday is stale today; re-running the `block in soul` assertion is cheaper than a
   reviewer finding the missing bullet.
3. **The fenced block can lag the numbered rationale — compare the two before trusting it.** New rules
   are often appended to the issue's numbered list (`**13. …**`, `**14. …**`) while the fenced
   `### Canonical block` still carries the old count, so a lane that follows "copy the block verbatim"
   silently loses every newer rule. Count the fence's bullets and compare against the highest numbered
   item; when they disagree, quote the missing rules verbatim in their own sections (leaving the fence
   byte-intact so the assertion still passes) **and ask the issue's owner to patch the fence at the
   source** — a local patch per lane is how the next lane re-invents the same omission.
4. **When the source is fixed, re-extract and delete your local copies.** Once the fence carries the
   rules, keeping both leaves the rulebook longer than its source with two places to edit; dropping the
   duplicates is a net deletion (the file gets shorter and more authoritative). Keep only what a fence
   cannot express: the lane-specific reading of each rule.
5. **`make sync-agent-profile` refuses (`live-longer`) when the live file was edited after the tree
   copy was committed** — the guard working, because a sync would replace a newer live rulebook with an
   older tree copy. Decide deliberately: merge the delta by hand, or take the tree copy with
   `python3 scripts/agent_profile_sync.py --profile <name> --force` when the live file is only your own
   earlier sync, then prove it with `--check`, which must report byte-identical and print the size.
   Never `cp` the live profile into `agents/`: live is a moving snapshot, the tree copy is the artifact
   another lane reviews.
6. **Another lane may re-take your live file into its vehicle — verify it, then close your own PR.**
   The tree branch is one lane's vehicle, so its owner can copy the live profile into
   `agents/<profile>/SOUL.md` at a sha of their choosing. Both copies then exist; the right move is to
   **close your PR as superseded** once the copies are provably identical, not to keep a second branch
   carrying the same file.

   ```bash
   git fetch origin +pull/<n>/head:refs/remotes/origin/pr<n>   # leading + matters: the ref already exists,
                                                                # so a plain fetch no-ops and you diff a stale base
   git show origin/pr<n>:agents/<profile>/SOUL.md > /tmp/tree.md
   diff -q /tmp/tree.md ~/.hermes/profiles/<profile>/SOUL.md    # must print nothing
   wc -c /tmp/tree.md ~/.hermes/profiles/<profile>/SOUL.md      # equal, and both quoted in the reply
   ```

   The drift is structural, not a mistake: the tree is a copy, the lane edits the live file, nothing
   watches the copy — two edits in an hour produce two drifts. Acceptance is
   `sync-agent-profile --check` reporting **byte-identical**, never a size comparison: a tree copy can be
   *larger* than live while dropping lines, and a copy can be a strict prefix of the rulebook missing a
   third of it. Size tells you nothing; the set of lines does.
7. **The gate is repo-wide, so a red can be another lane's file.** Once the tree carries several
   profiles, `check-agent-profiles` may fail `live-longer` on a profile you do not own. Report it with
   the two byte counts and who owns it; editing or syncing someone else's profile to make your PR green
   is the same boundary violation as pushing to their branch.
7. Add at least one lane-specific rule the canonical block cannot express — what this lane does not
   do, and the check that stops its characteristic mistake. Numbered and imperative.
8. Add the profile to `agents/manifest.json` with formatting that matches the existing entries. Do not
   round-trip the file through `json.dumps(indent=2)`: it reflows every sibling entry and turns a
   two-line change into a whole-file diff that conflicts with every other lane's PR.
9. Branch, commit as the repo's allowed author identity, run the gate above, open the PR
   ready-for-review naming the instruction issue.

## Versioning a lane's live-only skill (and SOUL) when the task is to version it

A lane's skill can live ONLY on the host (`~/.hermes/profiles/<p>/skills/<name>/`) and be absent from
`agents/<p>/skills/` entirely. When an issue asks to **version the behaviour** (not to reconcile an
incidental edit), the live copy IS the sanctioned source — but decide direction per hunk, never by `cp`:

```bash
gh api "repos/asimov-agent/llgenie/contents/agents/<p>/SOUL.md?ref=<vehicle-sha>" --jq .content \
  | base64 -d > /tmp/repo.md
diff /tmp/repo.md ~/.hermes/profiles/<p>/SOUL.md     # read EVERY hunk
```

Read the diff: **additions-only** (the tree lacks a whole block that live carries) means live is newer →
take live→tree. **Any deletion** (live lost lines the tree has) means the tree is ahead → do not take live
wholesale; merge by hand. This is the one case where live→tree is correct; an incidental live edit that is
not part of a versioning task still goes through review, not a copy.

Build it on a **local** branch off the base vehicle's head — `agents/` does not exist on `main` until that
PR merges, so a branch off `main` cannot carry these files:

```bash
git worktree add -b <branch> <path> refs/remotes/origin/pr<N>
cp ~/.hermes/profiles/<p>/SOUL.md agents/<p>/SOUL.md
cp -r ~/.hermes/profiles/<p>/skills/<name>/. agents/<p>/skills/<name>/
```

Commit, then verify with the gate's OWN two commands (a green fast-gate set does not prove this):

```bash
make -s sync-agent-profile PROFILE=<p> CHECK=1     # must print "N file(s) ... match byte for byte", exit 0
make -s check-agent-profiles 2>&1 | grep -oE 'FAIL [a-z-]+: <p>'   # must print NOTHING for your profile
```

`check-agent-profiles` is repo-wide and will usually be red on OTHER lanes' files — that is not your slice;
prove yours clean by the grep returning empty, then report the remaining FAILs grouped per lane. Do NOT push
or open the PR until the vehicle PR merges (Stacking rule below): the finish comment names the local head sha
and the `CHECK=1` result, and the push + ordinary PR (re-fetch `main`, rebase, re-diff the SOUL hunk against
the merged tree) happens only after. The skill `version` field is part of the bytes you compare, so bump it
when the SKILL.md content changes, before the copy.

**Never run `sync-agent-profile` in write mode for a lane you are versioning.** Write mode treats the
tree as authoritative and would silently truncate a live rulebook that nothing lints — the `live-longer`
finding is the guard against exactly that; use `CHECK=1` (compare only). And **fix any lint defect in the
LIVE copy, not only the tree**: a live skill sits where `ci-lint` never runs, so a markdown defect (a
`## Tools` heading with no blank line above it, say) survives there indefinitely; patching only the tree
copy reds `CHECK=1` and the next sync reverts it. The live file belongs to that lane — ask its owner to
apply the one-liner (or be explicitly directed to), then re-copy and re-verify `CHECK=1` byte-identical.

## Reloading when `agents/` is not on `main` yet

`make sync-agent-profile PROFILE=<name>` copies the tree at the CURRENT repo into the profile home, so **while the `agents/` branch is unmerged the check must run in the branch's worktree, never in a `main` checkout.** `git ls-tree -r --name-only refs/remotes/origin/main -- agents | wc -l` is `0` until the tree lands — a sync against `main` has nothing to copy and would clobber the live rulebook. When the owner asks to "reload from the tree", verify the real source first, then run `python3 scripts/agent_profile_sync.py --profile <name> --check` in the worktree that holds the tree (it must report byte-identical and exit 0), and say in the report that the authoritative copy is the vehicle branch's tree, not empty `main`. The gate's own functions cannot be trusted against a base that has none of the files (`fleet_block()` returns `None` when `agents/standing-rules.md` is absent).

## Stacking rule

When the `agents/` tree itself is not yet on `main`, every lane stacks its SOUL PR on the branch that
creates it. Such a PR shows the base commits plus its own files, so **merging it into `main` alone
squashes the base PR's entire diff into `main`** under the smaller PR's name. Verify with
`git merge-base --is-ancestor <base-sha> origin/main`; if it is not an ancestor, the PR waits for its
base and says so in its body.
