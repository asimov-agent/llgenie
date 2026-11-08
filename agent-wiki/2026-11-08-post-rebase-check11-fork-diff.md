# check 11 stops firing on every correct code edit — it now uses the branch's own diff (issue #2099) — 2026-11-08

**Implements:** issue #2099 — `post-rebase-verify.sh` check 11 ("no silent revert of base
content") exists to catch a `-X theirs` / `-X ours` rebase silently re-dropping a base line the
branch never meant to lose. Its predicate was `gone > 0 && added > 0` per changed tracked text file
— the signature of a substitution, which is what a correct code edit *is*. So every ordinary rebase
that carried the branch's own rewrite (the only conflict being `CHANGES.md`) read `FAIL / DO NOT
PUSH`:

```
#2069 cc72588c -> fbbc29a6, base ea8c239e:
  base lines replaced: scripts/engine_build_trigger.py(5-51) tests/test_engine_build_trigger.py(2-66) FAIL
#2085 ef950796 -> 4797d215, base ea8c239e:
  base lines replaced: scripts/engine_image.py(5-49) tests/test_engine_force_rebuild.py(2-64) FAIL
```

Hand-diffing against `ea8c239e` showed only the branch's own intended substitutions — the gate
could not tell intent from a revert, and after two false reds in a row a real revert would be waved
through. A gate that rejects correct work teaches the reader to ignore it.

## What changed

- **`post-rebase-verify.sh` check 11** now compares the base lines HEAD lost against **the branch's
  own diff**: the lines deleted from the fork point where the branch diverged from the base, read
  from `ORIG_HEAD` (the pre-rebase tip `git rebase` records) diffed to
  `merge-base(base, ORIG_HEAD)`. A base line the branch deleted on its own base is a deliberate
  edit → `NOTE`; a base line HEAD lacks that the branch's own diff never deleted is a revert →
  `FAIL`; no `ORIG_HEAD` makes intent unprovable → `NOTE`, never `FAIL`.
- **`test-revert-detector.sh`** now builds **real** rebases instead of direct commits: a clean
  rebase carrying a branch edit asserts `rc=0`, a `-X theirs` rebase asserting `rc=1`, a pure
  deletion `rc=0`, plus the authorship-wiring and #1015 behind/divergent guarantees unchanged.
- **`tests/test_rebase_lane_scripts.py`** and the lane's `SKILL.md` / `sweep-mechanics.md` resources
  assert the new verdict lines and describe the new discriminator.

## Proof (quoted from the control run at this head)

- **Correct edit passes:** `case1 correct edit (clean): verify rc=0` with output
  `c1: base lines replaced by branch's own diff (review): engine.py(2) NOTE` — not a failure.
- **Real `-X theirs` revert still reds:** `case2 -X theirs revert: verify rc=1` with output
  `c2: base lines reverted: recipe.mk(1-2) FAIL` — the provable revert shape survives.

`scripts/test-revert-detector.sh` prints `PASS: a deliberate edit passes, a real -X theirs revert
reds, a pure deletion passes` (the pytest suite runs the control, so a regression reds CI).

**Issue:** #2099 · **Branch cut from:** `origin/main@7ef346c8`.
