---
name: grok-cli
description: Use when delegating to Grok CLI or resuming a Grok session.
---

# Grok CLI (grok-build-plan agent)

`grok` is a coding-agent CLI (build TUI) installed via mise at `~/.local/share/mise/installs/node/*/bin/grok`. The user's agent is `grok-build-plan`.

## Resume a session non-interactively (no TUI)

```
grok --resume <SESSION_ID> --single "<prompt>" --output-format plain --no-plan
```

- `--single` runs one turn, prints to stdout, exits. Without it, `--resume` opens the interactive TUI.
- `--no-plan` avoids plan mode; `--output-format plain` gives clean text.
- `--fork-session` creates a new session ID instead of mutating the original.
- `--restore-code` restores the original repo snapshot (remote sessions need `--worktree`).

## Session storage

Sessions live under `~/.grok/sessions/<urlencoded-cwd>/<session-id>/` (e.g. `%2Fhome%2Fasimov%2Frepository%2Fgit%2Fllgenie/`).
- `summary.json` — title, cwd, git root/branch/head, model, last recap.
- `chat_history.jsonl` — the conversation (user queries, system reminders).
- `events.jsonl` / `updates.jsonl` — full event stream.
- `terminal/call-*.log` — per tool-call logs.

## Pitfalls

- A session's stored `cwd`/`head_branch` is the checkout it ran in (often `main`), NOT the feature worktree. Feature work lives in a separate worktree (e.g. `llgenie-wt/<branch>`); resuming the session does not move the user's checkout.
- `grok --resume` restores conversation only unless `--restore-code` is passed.
- Verify a session's actual content by grepping `chat_history.jsonl` for the user's phrases — the title alone is not proof the questions are stored.
- `grok sessions list|search|delete` manages sessions; `grok export` dumps a transcript as Markdown.
