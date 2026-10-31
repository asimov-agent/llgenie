# Version the planner's grown "verifying lane claims" reference into the tree (live→tree) (#1206)

## What shipped

A live→tree alignment of ONE planner-lane versioned reference:

- tree `agents/llgenie-planner/skills/llgenie-bot-orchestration/references/verifying-lane-claims.md`
  was **37,795 bytes** at the merge base (the #1228 copy, which did not close #1206); the live
  authoritative file is now **51,923 bytes** (`~/.hermes/profiles/llgenie-planner/skills/.../verifying-lane-claims.md`).
- Committed the tree file += the current live bytes, byte-identical, at the head this PR is measured at
  (delta +14,128 bytes; `git diff origin/main:<path> <live>` empty at head).

The live-only delta is the planner's post-#1228 growth of the reference: the §6i-bis/"re-confirm at an
older sha is not head-evidence", §6j (post-merge pass over a rapid approval batch), §6k (duplicate
"picked & implemented → PR #N"), §6l (placeholders / guessed PR number), the "lawful in-lane mutation
does NOT clear the guard" and "do not revert your own verified mutation" hold lessons, and the
recipient-side check-run/job-failure recipes. SKILL.md is untouched (correctly tree-ahead after
#1194/#1195); no other `agents/llgenie-planner/` file changed (the six further live-longer references
found while measuring are filed separately as #1234).

## Evidence (measured at PR head, `git show <head>:<path> | wc -c`)

```
49644 → 51923 bytes live while measuring (settled at 51,923 after two reads 22:10Z)
tree @ head = 51923  (== live authoritative bytes)
diff origin/main:<path> <live> = empty
make check-docs (change-note gate) = exit 0
check_import_roots ratchet: baseline not raised
```

## Acceptance

- [ ] `git diff origin/main:<tree path> <live>` empty at head.
- [ ] `git show <head>:<tree path> | wc -c` = 51,923 (current live authority; the issue body's 22,181
      is a pre-#1228 re-measure).
- [ ] Note + fragment pass `make check-docs` change-note gate (#1123); `check_import_roots` unraised.
