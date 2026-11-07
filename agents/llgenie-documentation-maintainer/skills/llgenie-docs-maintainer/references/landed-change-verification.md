# Proving a docs change actually landed

A change is only "landed" when three copies agree at the pushed head. A green `git commit` locally is
not proof, and a completion gate that says *no task-relevant changed path* is not a bug to argue with —
it is telling you it did not observe your write through the channel it trusts.

## Rule: write through the editing tool, not `cp` + git

When you fold an authoritative source file into a branch (e.g. copying a live profile reference into
`agents/<profile>/skills/...`), a `cp <src> <dst>` followed by `git add`/`commit`/push produces the
correct tree but registers **no file-tool change**. A completion-integrity check keyed to tool-visible
edits then reports "no task-relevant changed path" even though the commit is real and pushed — and you
can loop forever re-verifying git while the gate stays red.

Remedy: make the change with `write_file` (or `patch`) at the **absolute** worktree path, using the
exact authoritative content. This registers `files_modified` for that path. If the content is already
byte-identical (you copied it earlier), the write is a no-op to git but still satisfies the gate — so
the on-disk file, the committed blob and the live source all stay equal.

Do not write to a bare relative path from the chat cwd (`~`); it silently lands in HOME. Always give the
full `/…/worktrees/…/<path>` (or the checked-out worktree root) so the edit is attributable and lands
in the right tree.

## Rule: prove it on the wire, not just in local git

The wire (GitHub) is the source of truth; a local worktree can be discarded or stale. Read the file
**content at the PR head** from the API and compare sha256 against the live authoritative source:

```
HEAD=$(gh pr view <n> --repo asimov-agent/llgenie --json headRefOid --jq .headRefOid)
gh api "repos/asimov-agent/llgenie/contents/<path>?ref=$HEAD" --jq .content | base64 -d > /tmp/wire.md
sha256sum /tmp/wire.md          # must equal the authoritative source's sha256
```

Then check the same three copies agree:

```
git -C <worktree> show HEAD:<path> | sha256sum     # committed blob
git -C <worktree> show --name-status --format='' HEAD | grep <path>   # A/M — is it a changed path?
diff <live-source> <(git -C <worktree> show HEAD:<path>) && echo IDENTICAL
```

Also confirm the base before claiming the rebase is current: re-fetch the canonical remote with an
explicit refspec (`git fetch origin +refs/heads/main:refs/remotes/origin/main`) and check
`git rev-list --count <base>..origin/main` is `0` — never trust an `origin/main` local-branch shadow
or a sha quoted in a message.

## Do not fabricate a diff to satisfy a gate

If the tree is already correct, a gate firing on "changed path" is about the *mechanism* of the write,
not missing content. The honest fixes are the tool-visible write above and the wire proof above. Never
edit content away from the authoritative version just to manufacture a diff — that trades a red gate
for a wrong file.
