# Classifying a suite red: inherited-main vs your regression

A whole-suite run that reds (e.g. `make ci-unit`) is not yet a verdict on your change. Before
reporting a single failure as yours, split every red into two buckets:

1. **Fold/PR regression** — the changed files are in the failing gate's dependency path.
2. **Inherited main red** — the gate already reds on the base sha you branched from, with no
   contribution from your diff.

## How to prove it (never assert, always reproduce)

- Run `git diff --stat <base> <head>` and check whether *any* changed path is a file the failing
  gate reads (`docs/BOTS.md`, `scripts/check_*.py`, etc.). If nothing you touched is in the
  gate's input set, that alone is strong evidence it is inherited.
- Add a **clean-detached worktree at the exact base sha** and run the two or three failing gates
  there:

  ```
  git -C <repo> worktree add --detach /tmp/ck-<base8> <base-full-sha>
  cd /tmp/ck-<base8> && python3 scripts/<gate>.py check   # or the pytest node ids
  git -C <repo> worktree remove --force /tmp/ck-<base8>
  ```

  If the same failures reproduce identically on the clean base, they are **inherited** — report
  them as such with the base sha, and attribute zero of them to your change.

## Known llgenie host/pre-existing red sets (2026-11)

These red on the host tree but are NOT wired into `ci.yml`/`scope.yml` as blocking checks, so they
are not automatically your regression:

- `scripts/check_agent_profiles.py check` — reds on multi-lane live-only artifact directories and
  on a tracked SKILL.md that names a reference file only present in the live profile
  (`skill-reference-missing`). Pre-existing unless your diff edits `agents/**`.
- `scripts/check_dispatch_forms.py check` — reds when `docs/BOTS.md`'s dispatch table is stale after
  a docs-surface edit elsewhere (e.g. new user-facing run rows added without regenerating the
  table). Regenerate with `make check-dispatch-forms report`. This one IS in the ci-unit discovered
  suite (`test_dispatch_forms.py`, `test_issue_bot_manual_pick.py`), so a stale table reds every
  PR's unit leg — file an issue for the docs lane rather than "fixing" it inside an unrelated PR.

## Rule

A red you did not cause is still evidence to report (name, sha, gate) — but never count it as your
failure, and never edit the failing gate to make an inherited red pass.
