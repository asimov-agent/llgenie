---
name: vault-cron-workflow
description: "The exact daily scan cron workflow for the AI Matrix Trends vault."
---

# Vault Cron Workflow

## Host Crontab Entries

The daily scan runs via the host system crontab (not Hermes cron). To add:

```bash
crontab -l 2>/dev/null > ~/crontab-backup-$(date +%Y%m%d).bak
```

Then add these entries:

```cron
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# AI Matrix Trends — Daily Scan Stages
0 20 * * * cd ~/repository/git/ai-matrix-trends/scripts && exec setsid python3 stage-1-research.py >> /tmp/ai-matrix-trends-stage1.log 2>&1
30 20 * * * cd ~/repository/git/ai-matrix-trends/scripts && exec setsid python3 stage-2-links.py >> /tmp/ai-matrix-trends-stage2.log 2>&1
45 20 * * * cd ~/repository/git/ai-matrix-trends/scripts && exec setsid python3 stage-3-scoring.py >> /tmp/ai-matrix-trends-stage3.log 2>&1
0 21 * * * cd ~/repository/git/ai-matrix-trends/scripts && exec setsid python3 stage-4-indexes.py >> /tmp/ai-matrix-trends-stage4.log 2>&1
```

**Pitfall:** The `setsid` detaches the process so the SSH agent is inherited for git push. Without it, stage 4 can't authenticate to GitHub.

**Pitfall:** Each log is separate. Check `/tmp/ai-matrix-trends-stage*.log` if a stage fails.

**Pitfall:** Trust the crontab + `stage-*.py` files over the prose in the vault's AGENTS.md and `scripts/daily-scan-prompt.md`. The docs drift: AGENTS.md has claimed the scan runs in a different number of stages than the 4 stage scripts that the host crontab actually runs, and `daily-scan-prompt.md` references `stage-2-links.sh`/`stage-3-scoring.sh`/`fix_all_links.py` which do not exist (the real stage-2/stage-3 are `.py` and the link fixer is `fix-all-links.py`). When the doc and the scripts disagree, the scripts + crontab win.

## Stage 1: Research (20:00)

`stage-1-research.py` creates new agent and plugin notes from HARDCODED lists. No web search, no delegate_task — all notes are generated locally from predefined arrays.

**What it does:** Iterates through hardcoded `agents_to_create`, `plugins_to_create`, and `arch_to_create` lists. Creates notes with proper frontmatter, tags, links, and body content. Skips any note whose title already exists (checks ALL vault folders case-insensitively).

**Limitation:** Does NOT update existing notes with new information. Does NOT discover new agents/plugins on its own. The vault only reflects whoever set up the initial lists.

**After Stage 1 completes:** If you manually added new notes (outside Stage 1), you MUST re-run stages 3-4 to regenerate indexes.

**Pitfall:** To add new agents/plugins/architectures, edit the `*_to_create` lists inside `stage-1-research.py` — do NOT try to add them via Hermes cron or delegate_task prompts.

## Stage 2: Link Resolution (20:30)

`stage-2-links.py` calls:
1. `resolve_wikilinks.py` — resolves `[[Claude Code]]` to `[[202609202000 - Claude Code]]` using a file map
2. `fix-all-links.py` — fixes frontmatter links and body wikilinks
3. `verify-vault.py` — verifies zero broken links

**Pitfall:** Run Stage 2 AFTER Stage 1. Stage 1 may create notes with short-name wikilinks that need resolution.

## Stage 3: Scoring (20:45)

`stage-3-scoring.py` calls:
1. `aggregate-trends.py` — scores all items (stars + mentions + tag bonuses), saves to `08 - Projects/trend-data.json`, updates Trend Radar
2. `collect_agent_plugins.py` — builds per-agent plugin compatibility tables, updates README section

**Pitfall:** Scores depend on tags. Notes without standard tags get score 0.

## Stage 4: Indexes & Commit (21:00)

`stage-4-indexes.py` calls:
1. `update-mocs.py` — updates all 5 MOCs with notes from their folders
2. `update-plugin-master-index.py` — updates Plugin Master Index
3. `update-agent-master-index.py` — updates Agent Master Index
4. `update_readme.py` — updates README Trend Radar tables and agent tables
5. `fix-master-index-links.py` — fixes frontmatter links in Master Index files
6. `ci/fix-links-relative.py` — rewrites vault-root-style links to file-relative
7. `verify-vault.py` — final verification
8. `git add -A && git commit && git push`

**Pitfall:** Stage 4 commits and pushes. If the user wants to review changes first, run stages 1-3 only, or modify stage 4 to not commit.

**Pitfall:** The README has manual count strings ("All 41 tracked agent tools/CLIs") that `update_readme.py` does NOT update. You must fix these with `patch()` after running stage 4.

## Manual Execution (for testing or ad-hoc runs)

```bash
cd ~/repository/git/ai-matrix-trends/scripts
python3 stage-1-research.py 2>&1 | tail -20
python3 stage-2-links.py 2>&1 | tail -30
python3 stage-3-scoring.py 2>&1 | tail -30
python3 stage-4-indexes.py 2>&1 | tail -40
```

## Adding New Agents/Plugins/Architectures

Edit `stage-1-research.py` directly. There are three sections:

1. **`agents_to_create`** — AI coding agents (e.g., Claude Code, Hermes Agent, Jev)
2. **`plugins_to_create`** — MCP servers, plugins, extensions (e.g., Hermes Jev, Context7 MCP)
3. **`arch_to_create`** — Architecture patterns (e.g., ReAct, Tree of Thought)

Each entry requires: `title`, `tags`, `links`, `overview`. Plugins also need `agents` (array of agent keys).

**Pitfall:** When adding a plugin for Hermes Agent, use `agents: ["hermes"]` — the plugin's frontmatter `agents:` field must match the agent key used in the Plugin Master Index.

**Pitfall:** Tags must be from the vault's controlled vocabulary (see AGENTS.md tag taxonomy). Invalid tags cause CI Stage 4 (validate-tags.py) to fail.

## Troubleshooting

- **Stage 1 skipped all notes:** All hardcoded notes already exist. Add new entries to `stage-1-research.py` if you want more.
- **Stage 2 reports broken links:** Notes have `[[short-name]]` wikilinks that don't resolve. `resolve_wikilinks.py` should have fixed them; check that the note actually exists in the vault.
- **Stage 4 fails on git push:** SSH agent not available. Run `ssh-add` or use a deploy key.
- **README count mismatch:** The header strings like "All 41 tracked" are hardcoded in update_readme.py. After stage 4, check counts with `grep 'Total plugins tracked' README.md` and patch if stale.
- **Plugin not appearing in Hermes Agent table:** The plugin's frontmatter must have `agents: [hermes]` AND the Plugin Master Index scan must match the agent key. Check `update-plugin-master-index.py`'s `AGENTS` dict includes `hermes`.
