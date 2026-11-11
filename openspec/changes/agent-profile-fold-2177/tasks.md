# Tasks

## Fold the live profile into the tree

- [x] Copy `skills/llgenie-product-manager/SKILL.md` live→tree byte-identically.
- [x] Verify byte identity (`sha256sum` tree == live `5c074c4d…`, 12,872 b).
- [x] Leave `SOUL.md` un-folded (tree is the longer side; issue step 4).
- [x] Record the change (agent-wiki note + docs/changes.d fragment + CHANGES.md row, closes #2177).
- [x] Gate through `make check-docs`, `make lane-preflight`, and the lane's `check-agent-profiles`
      live classes (0 same-lane rows).
