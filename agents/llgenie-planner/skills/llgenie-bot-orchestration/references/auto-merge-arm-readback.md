# Auto-merge arm read-back & comment verification

## The arm fact is enablement, not request identity

A lane reporting "armed" must quote **REST** `gh api repos/<o>/<r>/pulls/<n> --jq .auto_merge.enabled_at`.

- `enabled_at` non-null = armed.
- `enabled_at` **null** while `enabled_by` / `merge_method` are populated = a *pending request that was never enabled*. GraphQL `autoMergeRequest.enabledAt` / the UI timestamp is the request's identity — quoting it as "armed" is the recurring error (four lanes in one night repeated it).
- `gh pr merge <n> --squash --auto` exits 0 and arms nothing whenever the base is not the default branch. Exit code is not a fact; read `enabled_at` back.
- Do not assert a lane's self-reported arm read-back. A peer-lane correction on-record, then a fresh raw read, is the only accepted sequence.

## Never automate "arm on green" against a head you did not just re-read

An arm-on-green watcher ("poll the checks; the moment all pass, `gh pr merge --auto`") is a #964-shaped trap when its premise is stale. A PR whose base has fallen behind main after an owner merge streak reads `mergeable=false, mergeable_state=dirty` and gets **zero CI runs** at its head — so a watcher that treats "no red checks" as green can execute the merge on an unmergeable PR (exit 0, arms nothing, or arms a stale head).

Before you bless or trust any arm-on-green automation, re-read the head the watcher will act on, live:

```bash
gh api repos/<o>/<r>/pulls/<n> --jq '{head:.head.sha,base:.base.sha,mergeable,ms:.mergeable_state,arm:.auto_merge.enabled_at}'
gh api "repos/<o>/<r>/actions/runs?head_sha=<head>" --jq '[.workflow_runs[]|{id,name,status,conclusion}]'   # empty = no CI to "pass"
```

- `mergeable=false` / `ms=dirty` ⇒ the branch is stale against the base; **kill the watcher, rebase onto current main, then arm-on-green**. A dirty PR never auto-lands.
- A `base` that is no longer an ancestor of main is the tell: `git merge-base --is-ancestor <base> origin/main` fails ⇒ DIRTY risk (squash merges that *are* ancestors absorb cleanly and need no rebase).
- The image is an **owner merge streak**: several merges land in a burst, main advances past many lanes' bases at once, and every lane built on the old base flips dirty together. Re-check the whole open-PR set for ancestor-safety on the pass after a streak, not only the one lane that reported.

## Verifying that an on-record correction actually landed

A lane saying "correction posted, comment <id>, read back" is a claim. Verify by listing the thread:

```bash
gh api "repos/<o>/<r>/issues/<n>/comments?per_page=20" --jq '.[]|{id,at:.created_at}'
```

- Fetching a single comment by id (`.../issues/<n>/comments/<comment_id>`) can 404 even when the comment exists — use the per-page listing (or `.../issues/<n>/timeline` filtered to `commented`) and match on id + `created_at`.
- Bare `curl` to api.github.com can return **401 Bad credentials** in a non-interactive shell where `GH_TOKEN` is unset; `gh api` (gh keyring/config) is the reliable path. Never read a 401/404 from your own tooling as evidence the lane failed to post — re-check the thread, then retract your own message if the comment is there.

## Order of operations when a lane's claim and the API disagree

1. Read the raw API fact first; never repeat a lane's quote to the owner.
2. Message the lane with the fact + the exact correction to post, naming the id.
3. After it reports, re-verify in the thread; if verified, send a short follow-up so it does not repost needlessly.
4. Record the settled state in the issue/PR comment itself — a correction that lives only in a DM does not exist for the next reader.
