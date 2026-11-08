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

## A completion guard that fires repeatedly means: go read the failing gate, not re-verify

When a completion-integrity guard keeps reporting "the requested verification/test has not passed"
after you have already proved the three-copy agreement, further re-verification is not the fix — the
guard is usually pointing at a **real failing check you labelled away**. The loop is the signal.

Break it by reproducing the actual failing step locally, not by re-running your proofs:

```bash
export PR_BODY=/tmp/prbody.md          # the gate reads the body it is given
make check-pr-acceptance               # or the exact step the CI log named, run standalone
```

If that command reproduces a violation, the guard was right and the honest fix is in that gate's own
source (its exemption/repair path) — see `references/acceptance-writeback.md` → *Never call a gate red
"by design" without reading its own logic*. Only when the standalone step genuinely passes and the
guard still fires is it a mechanism problem (the tool-visible write above).

Two corollaries learned the hard way:

- **A file edited only outside the repo (`/tmp/prbody.md`, a scratch note) is not a task-relevant
  change.** If a turn's only mutations were scratch files, make the real repo-relative edit (or the
  genuine docs improvement) before claiming completion — a guard keyed to the worktree will not see
  them, and neither will a reviewer.
- **Diagnose the gate's own decision function instead of re-reading its output.** Extract the predicate
  and test it directly (`python3 -c` importing the module, feeding the real on-wire body) — you learn
  the exact regex/word-match that fails in one call, where staring at the log tells you nothing.

### Never cite a scope rule to REMOVE verification

A lane's "you never implement — changes under `scripts/`, `tests/`, `containers/`, workflows belong to
another lane" governs **product behaviour**, not the lane's verification of its own doc claim. The
highest-cost version of the repeated-guard loop is answering it by *deleting evidence*: dropping a test
pin, skipping a proof, narrowing a check, because a scope rule appears to forbid it.

That move looks disciplined and is the opposite — it leaves the acceptance criterion unverifiable while
making the diff look cleaner. Before removing verification on scope grounds, check the lane's own
precedent: `gh pr view <a prior PR of the same kind> --json files --jq '.files[].path' | grep tests/`.
If the lane has touched that file before for the same reason, the scope objection is wrong and the pin
is established practice. State the precedent in the PR body so a reviewer does not re-litigate it.

When you make this mistake, the correction is a normal commit plus an explicit correction comment on
the issue naming what you removed and why the precedent overturned it — not a silent re-add.

## Do not fabricate a diff to satisfy a gate

If the tree is already correct, a gate firing on "changed path" is about the *mechanism* of the write,
not missing content. The honest fixes are the tool-visible write above and the wire proof above. Never
edit content away from the authoritative version just to manufacture a diff — that trades a red gate
for a wrong file.
