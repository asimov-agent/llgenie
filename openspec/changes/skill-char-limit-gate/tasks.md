# Tasks

- [x] Add `skill-over-char-limit` and `skill-size-unreadable` findings to `check_agent_skills.py`
- [x] Name the remedy in the finding, not only the character count
- [x] Count characters, not bytes (the tool's unit)
- [x] Slim the four over-limit skills by moving sections into `references/`
- [x] Verify zero loss on every slimmed skill
- [x] Prove the gate by sabotage (RED over-limit, GREEN after)
- [x] Unit tests: failure shape, remedy text, exact-at-limit, chars-vs-bytes, real tree
