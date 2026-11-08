# Tasks

- [x] Add `skill-over-char-limit` and `skill-size-unreadable` findings to `check_agent_skills.py`
- [x] Name the remedy in the finding, not only the character count
- [x] Count characters, not bytes (the tool's unit)
- [x] Slim the four over-limit skills by moving sections into `references/`
- [x] Verify zero loss on every slimmed skill
- [x] Wire the gate into `guard` as well as `ci-unit`, so a red elsewhere cannot skip it
- [x] Prove the gate by sabotage in CI: RED run `42450910032` (guard job `128639743488`), GREEN run `42450796934` (guard job `128639386829`)
- [x] Unit tests: failure shape, remedy text, exact-at-limit, chars-vs-bytes, real tree
