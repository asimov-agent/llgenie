# llgenie-issse-implementer — `$HOME` paths in the issue-to-pr skill (#2145)

- **Date:** 2026-11-08 · **Issue:** #2145 (fleet portability rule: write `$HOME`, never `/home/<user>`)
- **Branch:** `fix/2145-home-dollar-myprofile` (from `origin/main`)
- **PR:** #2152

## The rule

Owner standing rule 2026-11-08: every lane's SOUL, skills, references and documentation/config
examples must use `$HOME` instead of `/home/asimov`. Every lane shells through bash, so `$HOME`
resolves; the absolute form encodes one machine's account name in a public repository. Carve-outs
(parsed-by-a-program contexts — systemd units, crontab lines, YAML/JSON values) and `scripts/*.py`
(which may need a resolved absolute path or build it from `pathlib.Path.home()`) keep the literal.

## What changed (this lane's files only)

Three shell/doc-context lines in the `llgenie-issue-to-pr` skill were rewritten from the literal
`/home/asimov` to `$HOME`:

- `SKILL.md` — the edit-worktree warning: a path that resolves to
  `$HOME/repository/git/llgenie/...` (was `/home/asimov/...`) edits the canonical checkout instead of
  the scratch worktree.
- `references/local-worktree-hygiene.md` — the worktree-on-real-disk template
  `$HOME/repository/git/llgenie-wt/<w>-<slug>` (was `/home/asimov/...`).
- `references/terminal-and-guard-pitfalls.md` — the explicit `workdir=$HOME` example (was
  `workdir=/home/asimov`).

All three are executed-shell / documented-shell contexts where `$HOME` resolves, so the substitution
is behaviour-preserving and removes the machine-specific account name from the tree.

## Carve-outs left literal (on purpose)

- `scripts/verify_fold_identity.py:13,16` — a `scripts/*.py`; `$HOME` does not expand in a Python
  string, so it stays absolute. This PR does not touch that file.
- No systemd unit, crontab line, or program-parsed YAML/JSON value changed.

## Why this note exists

`check-docs` (issue #1123) treats an `agents/<lane>/skills/**` diff as a behavioural surface: a change
to a skill owes an `agent-wiki/` note plus its `docs/changes.d/` row. This is that note. It records
**what changed and why** (portability rule #2145 for this lane's tree copy), not the diff itself.

## Files

- `agents/llgenie-issse-implementer/skills/software-development/llgenie-issue-to-pr/SKILL.md`
- `agents/llgenie-issse-implementer/skills/software-development/llgenie-issue-to-pr/references/local-worktree-hygiene.md`
- `agents/llgenie-issse-implementer/skills/software-development/llgenie-issue-to-pr/references/terminal-and-guard-pitfalls.md`
- `docs/changes.d/2026-11-08-issse-implementer-home-portability.md`
- `agent-wiki/2026-11-08-issse-implementer-home-portability.md` (this note)
- `CHANGES.md` (regenerated index)
