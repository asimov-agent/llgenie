# LLGenie Pipeline Maintainer: version the live skill + references back into the tree

Second half of the #1257 live→tree versioning (the SOUL half is PR #1263 on `fix/1257-soul-live-tree-version`).
Versions the `llgenie-pipeline-maintenance` skill live→tree so the tree catches up to the
owner-confirmed authoritative live profile (issue #1257; does not close #961 — the doc-lane drift tracker).

## What drifted (measured at `1db367a2`)

- **SKILL.md**: tree 101,346 b / 766 lines vs live 100,791 b / 764 lines. The live carries the newer
  "Role artifact (2026-11-01)" block (tree grep 0) and re-points several lessons into `references/`
  that the tree keeps inline (e.g. `check_pr_authors` → `references/auto-merge-identity.md`). After this
  PR the tree `SKILL.md` is byte-identical to the live profile.
- **references/**: tree had 12 files; live has 19. The tree lacked
  `verifying-agent-tree-parity.md`, `verifying-planner-claims.md`,
  `measuring-job-duration-bands.md`, `pr-issue-linking-and-force-push.md`,
  `engine-build-cuda-cdi.md`, `hermetic-run-and-census-quirks.md` and the newer content of 8 updated
  files. After this PR the tree carries the full live set (union, live wins, tree-only kept).

## Verification

- Tree `SKILL.md` md5 == live profile md5 (diff clean; `Role artifact (2026-11-01)` grep 0→1).
- Tree `references/` count 12→19, matching the live profile.
- `check_docs.py check` rc=0 on this head (change-record note ships in the same PR).
