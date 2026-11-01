# tester lane live→tree fold, round 4 (2026-11-01)

Versioning the tester lane's live `SKILL.md` into the tree at `7e8062cb` (the #1270 merge commit).
Live had grown two post-#1270 lessons while the tree was frozen at the fold — pure accretion, nothing
shrank. This round folds them byte-identically.

## The two folded lessons

1. **A just-opened PR reports `no checks reported` from `gh pr checks` for a minute or two.**
   That empty board is a timing artifact, not "CI never triggered": check-runs register only after
   dispatch, so a poller's first pass sees nothing and a naive `ALL_CONCLUDED` fires on an empty set.
   Enumerate the workflows by name (`CI`, `ci-scope …`, `holds — …`) with
   `gh run list --branch <ref> --json databaseId,status,headSha,workflowName`, then judge each with
   `gh run view <id> --json status,conclusion,jobs`. An empty `gh pr checks` is not evidence.

2. **Never batch a MUTATING command across parallel tool calls.** Independent calls in one response
   run concurrently, so one `gh pr comment` fanned into several calls posts several comments. In this
   round the same `--body-file` was issued twice from independent tool calls and produced two identical
   bookend comments on one PR thread before I deduped them. Batching is for reads only; write each
   mutation exactly once (one tool call, then read the id back), and keep dedupe costs off the record.

## Proof at the committed head

Tree `SKILL.md` == live by `sha256` (`e5efc019c227`); 990 / 990 lines; 5 reference files + SOUL
byte-identical (only SKILL drifted in this cycle); `make changes-index` regenerates `CHANGES.md`.
