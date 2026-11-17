# Tasks

## Fold the bulk-mechanical-migration skill live→tree (issue #2877)

- [x] Restore the live `bulk-mechanical-migration` SKILL.md into the tree at
      `agents/llgenie-issse-implementer/skills/bulk-mechanical-migration/SKILL.md` byte-identically
      (9327 b, sha256 `2c5f8bb26a02`, version 1.0.0), equal to the live identity the issue documents.
- [x] Record the change (agent-wiki note + docs/changes.d fragment, closes #2877) and index it in
      CHANGES.md via `make changes-index`.
- [x] Gate through `make lint`, `make check-docs`, OpenSpec validate, and the lane's
      `check-agent-profiles` absences (0 same-lane rows for `llgenie-issse-implementer`).
