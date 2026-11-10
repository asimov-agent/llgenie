# Tasks

## Fold the live profile into the tree

- [x] Copy the 20 live-newer truncated reference files live→tree byte-identically (`cmp -s` / hashes on every file).
- [x] Version the 11 `absent-from-tree` live reference files (`non-negotiables`, `own-domain-audit`,
      `profile-live-tree-fold`, `wire-truth-and-make-guards`, …) into the tree byte-identically.
- [x] Leave SOUL.md / SKILL.md un-folded (the tree is the longer, authoritative side — issue rule 4;
      their live convergence is deferred to provisioning #2165).
- [x] Record the change (agent-wiki note + docs/changes.d fragment + CHANGES.md row, closes #2172).
- [x] Confirm the fold removed the truncated class: `check_agent_profiles` for this lane reports
      0 `live-longer` and 0 `absent-from-tree` rows; the only residual is the tree-longer SOUL/SKILL.
- [x] Gate through `make check-docs`, `make changes-index`, `make lint`, `make check-pr-hygiene`,
      `make skills-validate`, `make check-agent-profiles-ratchet`, and `make openspec-validate`.
