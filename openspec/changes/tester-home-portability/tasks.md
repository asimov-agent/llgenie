# Tasks — `$HOME` portability in the tester lane (2026-11-08)

- [x] Rewrite the 3 executed-shell paths in `agents/llgenie-tester/skills/llgenie-pr-testing/SKILL.md` to `$HOME`.
- [x] Rewrite `--live-home` to `"$HOME/.hermes/profiles"` in `references/agent-profile-versioning.md`.
- [x] Leave carve-outs literal: no `scripts/*.py`, no systemd/YAML/JSON/crontab, no other lane.
- [x] Verify: `grep -rn '/home/asimov' agents/llgenie-tester/ | grep -vE '\.py'` is empty at the head.
- [x] `make check-docs check-wiring lint` green at the fixing head.
