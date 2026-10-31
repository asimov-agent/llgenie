# A lane's "already resolved" claim is verified on the API, not argued

When a lane reports that an issue's V1/primary scope is already resolved by a merged PR, do not
discard it as a stall and do not re-dispatch the closed slice. Verify on the API before steering:

- `gh pr view <n> --json state,mergedAt,mergeCommit` + `git merge-base --is-ancestor <merge> origin/main`
  → is the claimed PR actually MERGED and an ancestor of main?
- `gh pr view <n> --json body` (grep for the named test names) AND `git show origin/main:tests/<file>.py`
  (grep the hermetic twin / helper / wrapper) → does main actually carry the resolved shape for the
  exact class the issue names?
- `gh pr view <n> --json files --jq '.[].filename'` → which files the resolver touched.

## Known-good shape

A live-data-drift V1 class is resolved when the named test (e.g. `test_rank_follows_the_given_vram_ram_and_arch`,
`test_live_sync_adopts_*`) is refactored into:
- a helper (`_rank_follows_(sync)` / `_sync_adopts_(sync)`) that runs against a `sync` argument,
- a **hermetic twin** on committed vendored data (`test_the_vendored_store_rank_follows_...`), AND
- a **`@pytest.mark.network` live wrapper** (`test_rank_follows_...` against `live_sync`) that runs in the
  live seam, not the hermetic unit gate.

Both paths run the SAME oracle (re-derived from the product), so the unit gate is hermetic. #1094 (`d5fb875c`)
resolves exactly that shape. The parent issue stays open only for the second defect (e.g. #1064 V2 MLX/cuda
admission).

## Consequence

Dispatch ONLY the surviving live slice; say explicitly that the resolved slice is NOT reopened. Forcing a lane
onto an already-merged premise duplicates the #1218/#1215 (duplicate of merged #1101) and #1216/#1212
(second #1087 vehicle) error classes. Verify the surviving slice's fixture/function on main too before blessing
a fresh vehicle (`git show origin/main:...` for the fixture the API baseline builds from). And: **a fresh PR born before the latest single merge can carry a base one merge stale and read as a mass-revert.** Always compare the PR's true merge-base (`git merge-base origin/main <pr-head>`) versus current `origin/main` AND check that files merged in the newest commit still exist at the PR head (`git show <head>:<file>`). #1219 was born off `6d990570` while main was `d98c569c` (#1217), so its head was missing the engine-capability files and merging as-is would have reverted #1217. Substance green does not make a base-dirty vehicle mergeable.

## Related

- `verifying-lane-claims.md` — a claim is a report; the ref/API is the evidence.
- `stalled-lane-and-dispatch-delivery.md` — forcing versus measured quiescence; read the issue timeline,
  including dry-measurement report comments, before forcing a lane.

## A rebase that drops the mass-revert is the only cure; a "green local" claim is never the gate
When a lane's head sits on a stale merge-base it must REBASE onto current `origin/main` and re-verify — a lane that (rightly) says "check-docs green locally" while its `scope` CI job is red has not fixed the gate. Two independent blockers can both be real: (a) the lane's own shared-gate root fix, and (b) an un-rebased head whose diff still deletes merged files. Fix (b) by rebasing the branch; do not conflate it with a shared main defect.
The authoritative proof of a fixed rebase is object-level: `git merge-base origin/main <head>` equals current main tip AND `git diff --name-status origin/main <head>` shows no `D` on files merged by the newest PR(s). A lane quoting "base=current origin/main <sha>" from the PR *summary/detail* while its true merge-base is an older sha is reporting intent, not state — verify with `git fetch origin pull/<n>/head` + `git merge-base`, never the PR page.

## A shared broken gate (e.g. census pointer not an ancestor) blocks EVERY PR — file one root fix, route it to the gate's owner, and clear every lane's own diff
When `scope`/`check-docs` is red at a lane's head but its log shows the individual checks (`[check-docs] ok`, `[changes-index] ok`) passing and only a shared gate failing (e.g. `[census-gate] measured-at: the doc's pointer <sha> is not a real commit` — a pointer that IS a real commit but is NOT an ancestor of main), that is a post-merge regression on main, not the lane's diff. Confirm: `git cat-file -t <ptr>` (real) + `git merge-base --is-ancestor <ptr> origin/main` (false). File ONE issue (#1221) naming the merged PR that set the pointer (#1217/`d98c569c`/`34ad88f0`), a good ancestor fallback (`564e938`), and an acceptance criterion that re-points to an ancestor + re-measures WITHOUT weakening the gate. Route it to the gate's owning lane; tell every affected PR its code is green and its AC6 blocker is the shared root — so a lane does not chase its own (absent) diff error. Post-merge: never reopen the merged PR that caused it (fix forward, #1221).

## Lane PR-identity reports are claims, not facts
When a lane reports its own fix it often carries placeholder/unresolved identifiers ({HEAD}/{RUN}) and can cite the WRONG PR number — the engine-improver called the same vehicle #1218, then #1219 (which is another lane's tools_block branch) while the real branch fix/…->map said #1220, and claimed #1217 still "open" when it was MERGED (=current main). Doctrine: NEVER trust a lane's cited PR number/head/base summary. Resolve the vehicle yourself via the branch: `gh pr list --head <branch>` then `gh pr view <n> --json state,headRefOid,baseRefName`. A placekeeper/citation drift means the lane's own state record is unreliable on that issue — re-measure everything the report asserts.
