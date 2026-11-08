# post-rebase-check11-fork-diff

## Why

`agents/llgenie-pr-merge-conflict/skills/llgenie-pr-rebase/scripts/post-rebase-verify.sh` check 11
("base lines replaced", detection of a `-X theirs` / `-X ours` silent revert of base content)
fired on every **correct** code edit. Its predicate was `gone > 0 && added > 0` for each changed
tracked text file — the exact signature of a substitution, which is what an edit *is*. A rebase
that carried a branch's own intended code change (the only conflict being `CHANGES.md`) reported
`FAIL / DO NOT PUSH` because the branch's own rewrite removed base lines and added its own:

```
#2069 cc72588c -> fbbc29a6, base ea8c239e:
  base lines replaced: scripts/engine_build_trigger.py(5-51) tests/test_engine_build_trigger.py(2-66) FAIL
#2085 ef950796 -> 4797d215, base ea8c239e:
  base lines replaced: scripts/engine_image.py(5-49) tests/test_engine_force_rebuild.py(2-64) FAIL
```

Hand-diffing against `ea8c239e` showed only the branch's own intended substitutions. So the gate
could not tell "the author replaced these lines deliberately" from "a merge strategy reverted the
base". A gate that reds on every correct edit is worse than none: the operator learns to override
`DO NOT PUSH`, and the real `-X theirs` revert hides in the noise.

## How

Replace the `gone > 0 && added > 0` census with a comparison against **the branch's own diff** —
the lines the branch deleted from the fork point where it diverged from the base:

- The branch's own diff is `git diff <merge-base(base, ORIG_HEAD)> <ORIG_HEAD>` per file, where
  `ORIG_HEAD` is the pre-rebase tip `git rebase` records.
- A base line HEAD lacks is a **deliberate edit** when it is also a `-` line in the branch's own
  diff (the author deleted it on their own base) → `NOTE`, never `FAIL`.
- A base line HEAD lacks that the branch's own diff never deleted is a **revert** → `FAIL`.
- No `ORIG_HEAD` (no rebase happened) makes intent unprovable → `NOTE`, never `FAIL` (reserve FAIL
  for the provable shape, per the issue).

The shipped control `test-revert-detector.sh` now builds **real** rebases — a clean one for the
deliberate-edit control (`rc=0`) and a `-X theirs` one for the revert control (`rc=1`) — instead of
a direct commit, which cannot distinguish the two.

## Benefits

- The pre-push gate becomes trustworthy: green means "no silent revert", red means one.
- Correct rebases stop being blocked on a hand-audit of every touched file.
- The real `-X theirs` revert shape still reds (proven by the new negative control).
- No weakening: a base line the branch never asked to delete still `FAIL`s.

## Out of scope

- Weakening or removing check 11.
- Rebase mechanic changes (owned by the rebase lane).
- `docs/` prose beyond the required change-note.
