# Rebase verification & verdict reading

Fidelity, wire, and post-push checks for a llgenie rebase, especially a fork (cross-repo) PR. Run these BEFORE declaring the rebase done and AFTER the lease-push.

## Scope the fidelity check to the branch's OWN file set

To prove a rebase preserved content, compare blob identity between the pre-rebase tip and the rebased tip over **only the files the branch itself touches** (`git diff <old-base>..<old-tip> --name-only`). Do NOT diff the whole tree: files that differ but belong to a *newer main commit the rebase sits on top of* are **correctly inherited**, not a fidelity failure. Flagging them — or worse, trying to restore the old version — corrupts the rebase. The branch's own set should be byte-identical except `CHANGES.md`, which legitimately gains main's index rows (union).

Watch the absent-path trap: comparing blob hashes where a path exists on one side only yields empty==empty and reads as a false IDENT (or a spurious missing path). Explicitly classify each diff as added/changed/removed and confirm the added/removed paths are main's, not the branch's.

## Reference the merge-base as a raw sha, not a remote-tracking ref

A narrow fetch (`git fetch origin +refs/heads/main:refs/remotes/origin/main`) creates `origin/main` but **no** `origin/<sha>` ref. `git rebase --onto origin/main <merge-base-sha> <branch>` must pass the merge-base **sha directly** — it is already a local object via the fetched history. Reaching for `origin/<sha>` fails with an unknown-revision error.

## Verify the push on the wire, not locally

After `--force-with-lease=refs/heads/<branch>:<old-sha> --force-if-includes` to a **fork** remote (cross-repo head), confirm the remote head with `git ls-remote <remote> refs/heads/<branch>`. A local `git rev-parse` proves nothing about what the remote now points at; the lease held means the old tip was still the remote head, but only `ls-remote` shows the landed sha. Post-rebase guard fidelity: `git rev-parse HEAD^` (parent) and `git merge-base HEAD origin/main` must both equal live main.

## Read the CI verdict rc-driven, not via a hand-rolled rollup loop

Do not build a custom `gh pr view --json statusCheckRollup | jq` polling loop — it mis-exits on stdout buffering, jq null-key edge cases, and conclusion-vs-status confusion. Use the rc-driven form: `gh pr checks <n> >/dev/null` → **rc 0 = green, 8 = still pending, anything else = fail**; for a sharded matrix use awk-on-tabs (`awk -F"\t" '$2=="pending"'`). Read conclusions (`success`/`failure`/`cancelled`), never the human "fail" column which renders `cancelled` (a superseded run = *not yet*) as red. A genuinely **conflicting** PR reports an **empty** checks rollup because GitHub builds no merge ref — that empty rollup is the symptom of the conflict, not a workflow fault.

After a push the PR is frozen until its new runs conclude; re-read the verdict at the pushed head rather than the pre-push head.
