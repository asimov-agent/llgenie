# llgenie-tester — `$HOME` portability in the lane SOUL/skills (#2145)

- **Date:** 2026-11-08 · **Issue:** #2145 (owner standing rule: write `$HOME`, never `/home/<user>`)
- **Branch:** `fix/2145-tester-home-portability` (from `origin/main` `4664bda7`)
- **PR:** ready-for-review PR closes #2145

## The rule

Owner instruction 2026-11-08 (#2145): every lane's SOUL, skills, references and documentation/config
examples must use `$HOME` instead of `/home/asimov`. Every lane shells through bash, so `$HOME`
resolves; the absolute form encodes one machine's account name in a public repository. Carve-outs:
systemd units / crontab / YAML/JSON values consumed by a program (parsed, not executed) and
`scripts/*.py` (may need a resolved absolute path or build it from `pathlib.Path.home()`) keep the
literal.

## What changed (my lane's files only)

`agents/llgenie-tester/` — 4 occurrences in executed-shell contexts converted to `$HOME`:

- `skills/llgenie-pr-testing/SKILL.md` — worktree path, the `docker run -v` host mount, the host-side
  redirect target.
- `skills/llgenie-pr-testing/references/agent-profile-versioning.md` —
  `fold-live-profile.py --live-home "$HOME/.hermes/profiles"`.

Carve-outs confirmed untouched: no `scripts/*.py` edited, no systemd/YAML/JSON/crontab value changed,
no other lane's file edited. The live profile mirrors the same 4 edits (life→tree direction, #791);
no `make sync-agent-profile` (tree still holds the literal until this lands, per #2145).

Counts at branch: `agents/llgenie-tester/{SOUL.md,skills/}` had 4 non-py `/home/asimov`
occurrences (SKILL.md ×3, agent-profile-versioning.md ×1) → **0 after**. Remaining `/home/asimov`
in my profile's LIVE general-content skills are report-only (9 occurrences across non-lane content
skills; two are parsed-context carve-outs).
