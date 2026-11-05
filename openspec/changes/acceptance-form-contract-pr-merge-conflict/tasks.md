# Tasks — per-lane acceptance-criteria form contract

- [x] State the form contract verbatim in `agents/llgenie-pr-merge-conflict/skills/llgenie-pr-rebase/SKILL.md`
      (Hard rules): every issue this lane files AND every PR body it opens carries a
      `## Acceptance criteria` section, each criterion a `- [ ]` checkbox, one per provable
      outcome; a criterion a reviewer cannot tick is not one (#745).
- [x] Add change-note triad (agent-wiki + docs/changes.d fragment + CHANGES.md row) per #1123.
- [x] Validate: `make openspec-validate NAME=acceptance-form-contract-pr-merge-conflict`,
      `make check-docs`, `make lint`.
- [x] PR body carries `## Acceptance criteria` `- [ ]` checklist + closes #1812.
