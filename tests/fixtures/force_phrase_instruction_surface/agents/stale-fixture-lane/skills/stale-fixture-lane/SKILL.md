# Fixture lane SKILL — planted bad teaching (issue #2502)

This file is a planted violation: it presents the flag tuple as the general vehicle for pushing a
re-cut branch, with no qualification near the command.
`tests/test_force_phrase_instruction_surface.py` must report exactly this file:line.

```bash
git rebase origin/main
git push --force-with-lease --force-if-includes origin HEAD:<branch>
```
