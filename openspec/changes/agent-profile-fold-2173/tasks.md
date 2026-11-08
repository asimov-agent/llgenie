# Tasks

## Fold the live profile into the tree

- [x] Copy the 30 live-newer tracked files live→tree byte-identically.
- [x] Version the 16 absent-from-tree files into the tree.
- [x] Verify byte identity (`verify_fold_identity.py` aggregate `identical: True`).
- [x] Leave SOUL.md / containerized-repo-verification/SKILL.md un-folded (tree is the longer side).
- [x] Record the change (agent-wiki note + docs/changes.d fragment + CHANGES.md row, closes #2173).
- [x] Gate through `make check-docs`, `make lint`, `make changes-index`, and the lane's
      `check-agent-profiles` live classes (0 same-lane rows).
