# Tasks

## Fold the live profile into the tree

- [x] Copy the 20 live-newer reference files live→tree byte-identically (`cmp -s` on every file).
- [x] Leave SOUL.md / SKILL.md un-folded (the tree is the longer side; folding would lose tree lines).
- [x] Record the change (agent-wiki note + docs/changes.d fragment + CHANGES.md row, closes #2172).
- [x] Reach `0 of 42 file(s) differ` for `sync-agent-profile PROFILE=llgenie-engine-improver CHECK=1`
      via the sanctioned post-fold tree→live sync on the host.
- [x] Gate through `make check-docs`, `make changes-index`, `make lint`, `make check-pr-hygiene`,
      `make skills-validate`, `make check-agent-profiles-ratchet`, and the lane's
      `check_agent_profiles` live classes (0 same-lane rows).
