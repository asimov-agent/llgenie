# Tasks — skill↔code parity gate

- [x] `scripts/skill_parity.py` (Layer A: host-only, read-only live↔tree diff) + `make skill-parity`
- [x] `scripts/check_skill_code_parity.py` (Layer B: CI gate) + `make check-skill-code-parity`
- [x] Correct `auto-merge-mechanism.md` §3 to post-#1914 behaviour + commit it (was live-only)
- [x] Wire both into the Makefile + `ci-unit` + `.PHONY` + `issue_bot_gates` registration
- [x] Mutation tests: each gate fails on a broken anchor; Layer A is read-only (byte-identical after)
- [x] Change-note (`docs/changes.d/`) + `CHANGES.md` row + `agent-wiki/` note + OpenSpec change
