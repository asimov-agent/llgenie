---
name: zettelkasten-vault
description: "Build and maintain a Zettelkasten knowledge vault."
version: 2.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [zettelkasten, obsidian, vault, knowledge-management, automation]
    related_skills: [obsidian]
---

# Zettelkasten Vault Management

Use this skill for managing a Zettelkasten-style knowledge vault with atomic notes, dense linking, progressive refinement, and automated trend gathering.

## Vault Structure

```
vault/
├── 00 - Inbox/           # Raw observations → triage
├── 01 - Fleeting/        # Quick thoughts, half-baked ideas
├── 02 - Literature/      # Source material with attribution
├── 03 - Agents/          # Agent profiles
├── 04 - Plugins/         # Plugin/extension documentation
│   └── 00 - Plugin Master Index.md
├── 05 - Architecture/    # Architecture patterns
│   └── 00 - AI Architecture Master Index.md
├── 06 - Use Cases/       # Real-world workflows
├── 07 - Structure/       # MOCs, indexes, dashboards
├── 08 - Projects/        # Time-bound work, manifests
├── 09 - Trend Radar/     # Trend analysis
│   ├── Heating Up/
│   ├── Stable/
│   └── Emerging/
└── AGENTS.md
```

## Note Naming Convention

Format: `YYYYMMDDHHMM - Descriptive title in sentence case.md`

- Timestamp prefix for sortability and uniqueness
- **Never reuse the same timestamp** — causes wikilink resolution failures
- **Sub-agents MUST check existing files first**: `search_files(pattern="*", target="files", path="03 - Agents")` to find the highest existing timestamp, then use `max + 10`

## Frontmatter Requirements

Every note MUST have:

```markdown
---
id: 2026092010
created: 2026-09-20T10:00:00+02:00
tags:
  - agent
  - cli
links:
  - "[[2026092011 - Related Note]]"
  - "[[2026092012 - Another Note]]"
---
```

**CRITICAL RULE:** Sub-agents MUST use FULL FILENAMES for wikilinks in BOTH frontmatter `links:` AND body `## Related`. Never use short names like `[[Claude Code]]` — the merge step is eliminated; agents must link correctly from the start.

## Wikilink vs Markdown Link Rules

- **Frontmatter `links:` field**: Uses Obsidian `[[wikilinks]]` format: `- "[[202609202000 - Claude Code]]"`. This is intentional — Obsidian resolves these. The CI validator skips frontmatter when checking for wikilinks.
- **Body sections** (`## Related`, `## Compatibility`, `## Sources`): Use markdown links `[text](./path)` — NOT `[[wikilinks]]`. The CI `validate-link-quality.py` fails on body wikilinks.
- **In README.md**: Use `[text](./path%20with%20spaces/file.md)` (GitHub doesn't render wikilinks)
- **Always verify target file exists** before linking. If a note doesn't exist, create it or link to an existing related note.
- **Directory links are valid**: Links ending with `/` (e.g., `./09%20-%20Trend%20Radar/`) point to folders, not files. Validators must check both `os.path.isfile()` AND `os.path.isdir()`.
- **CRITICAL**: Use `f.removesuffix('.md')` NOT `f.replace('.md', '')` to strip extensions. `replace()` removes ALL `.md` occurrences, corrupting filenames like `CLAUDE.md as Runtime Configuration` → `CLAUDE as Runtime Configuration`.

## Trend Radar Categories

- **Heating Up 🔥**: New tools with >5k stars/week, HN front page, major releases
- **Stable 📈**: Established patterns (tool-calling, RAG, MCP protocol)
- **Emerging 🌱**: Early signals (A2A, ACP, verifiable execution, memory systems)

## MOCs and Master Indexes

- Create MOCs in `07 - Structure/` when themes have 5+ notes
- Create master indexes at folder root (e.g., `04 - Plugins/00 - Plugin Master Index.md`)
- Update indexes whenever new notes are added

## Automated Trend Gathering

### Parallel Research Streams

Launch 4 streams via `delegate_task`:
- Stream A (Agents): Search trending AI coding agents
- Stream B (Plugins): Search trending plugins/extensions
- Stream C (Architecture): Search emerging architecture patterns
- Stream D (Use Cases): Search real-world workflows

**Sub-agent instructions (MANDATORY):**
1. BEFORE writing: `search_files(pattern="*", target="files", path="03 - Agents")` to see what exists
2. Use full filenames for ALL wikilinks — `[[202609202000 - Claude Code]]`, never `[[Claude Code]]`
3. Add `links:` field to frontmatter with 2+ full filename wikilinks
4. If a note already EXISTS on a topic, `patch()` it instead of writing a duplicate
5. Never delete files

### Post-Scan Scripts (MANDATORY ORDER)

Run these Python scripts in EXACT ORDER after research streams complete:

1. `python3 scripts/resolve_wikilinks.py` — Resolves short-name wikilinks to actual filenames (exact matching only)
2. `python3 scripts/fix-all-links.py` — Comprehensive link fixing: dedup + resolve + create missing targets
3. `python3 scripts/verify-vault.py` — Verifies all links resolve correctly
4. `python3 scripts/aggregate-trends.py` — Scores items based on stars/mentions/tags
5. `python3 scripts/collect_agent_plugins.py` — Builds per-agent plugin compatibility tables
6. `python3 scripts/update-mocs.py` — Updates Maps of Content with new notes (idempotent)
7. `python3 scripts/update-plugin-master-index.py` — Generates Plugin Master Index with per-agent tables
8. `python3 scripts/update-agent-master-index.py` — Generates Agent Master Index with top 5 + complete list
9. `python3 scripts/update_readme.py` — Updates README with scored trend tables
10. `python3 scripts/fix-master-index-links.py` — Syncs frontmatter links with table links
11. `python3 scripts/verify-vault.py` — Final verification
12. `git add -A && git commit -m 'Daily scan' && git push`

**NEVER skip any script. NEVER change the order. NEVER delete files.**

## CI Pipeline (MANDATORY)

The vault has a comprehensive CI pipeline that runs as GitHub Actions. When the pipeline is red, the agent's job is to fix the issues until it's green. The pipeline has **10 stages** that each FAIL (not just warn) on issues:

| Stage | Script | What it validates | Failure condition |
|-------|--------|-------------------|-------------------|
| 1 | `scripts/ci/validate-links.py` | All links point to existing files | Broken links |
| 2 | `scripts/ci/validate-frontmatter.py` | Structure correct, no duplicate links | Malformed frontmatter |
| 3 | `scripts/ci/validate-duplicates.py` | No duplicate files in same folder | Duplicate files |
| 4 | `scripts/ci/validate-tags.py` | All tags from allowed vocabulary | Invalid tags |
| 5 | `scripts/ci/validate-index-completeness.py` | All notes indexed in MOCs | Missing from MOCs |
| 6 | `scripts/ci/validate-orphans.py` | No orphan notes (not linked anywhere) | **FAILS** on orphans |
| 7 | `scripts/ci/validate-templates.py` | Templates have correct structure | Missing sections |
| 8 | `scripts/ci/validate-formatting.py` | No trailing whitespace, proper headings | Formatting issues |
| 9 | `scripts/ci/validate-link-quality.py` | No `[[wikilinks]]` in body, all targets exist | **FAILS** on wikilinks or missing targets |
| 10 | `scripts/ci/validate-readme-completeness.py` | README matches vault content | Missing entries |

### CI Testing After Adding Notes

When adding new notes via `create_note()`, ALWAYS run `python3 scripts/ci/ci-pipeline.py` after. The most common failures are:

- **Stage 4 (Tags)**: New tags must be added to `VALID_TAGS` in `validate-tags.py`. The parser skips markdown links (`[text](path)`) and quoted wikilinks in the tags section.
- **Stage 8 (Formatting)**: `create_note()` must NOT produce trailing whitespace. Use `## Sources\n-` not `## Sources\n- \n`.
- **Stage 9 (Link Quality)**: Body `## Related` and `## Compatibility` must use markdown links `[text](./path)`, not `[[wikilinks]]`. Frontmatter `links:` with `[[wikilinks]]` are OK — the validator strips frontmatter.
- **Stage 10 (README)**: New agents/plugins must appear in README tables.

**User preference: Pipeline must FAIL on issues, not just warn. A green pipeline means everything is correct.**

### When Pipeline is Red

1. Run `python3 scripts/ci/ci-pipeline.py` locally to see which stage failed
2. Run the corresponding fix script:
   - Stage 1 (broken links): Fix markdown links pointing to non-existent files. Check for `[[wikilinks]]` in frontmatter (should be `[text](./path)`) and verify all `[text](path)` targets exist.
   - Stage 5 (index completeness): `python3 scripts/update-mocs.py` — MOCs must contain ALL notes from their folder
   - Stage 6 (orphans): `python3 scripts/update-mocs.py` — Notes must be linked from MOCs or other notes
   - Stage 9 (link quality): `python3 scripts/ci/fix-fishy-links.py` — No wikilinks allowed, all markdown links must point to existing files/directories
   - Other stages: fix the underlying files directly
3. Re-run CI pipeline to verify it's green
4. Commit and push fixes

**User preference: Pipeline must FAIL on issues, not just warn. A green pipeline means everything is correct.**

### fix-fishy-links.py

This script handles two critical transformations:
1. **Convert wikilinks to markdown links**: `[[202609202000 - Claude Code]]` → `[Claude Code](./03%20-%20Agents/202609202000%20-%20Claude%20Code.md)`
2. **Create missing targets**: If a link target doesn't exist, create a placeholder file in the appropriate folder

The script must be idempotent — running it multiple times produces the same result.

### CI Link Validators (CRITICAL)

Two validators run in the pipeline. They must BOTH pass:

**validate-links.py (Stage 1)**: Scans EVERY markdown link `[text](path)` in EVERY file and verifies the target exists. Also checks wikilinks in frontmatter. Links can be:
- Relative to file: `./03%20-%20Agents/file.md`
- Relative to vault root: `03%20-%20Agents/file.md`
- Parent directory: `../09%20-%20Trend%20Radar/`
- Directory links (ending with `/`) — checked via `os.path.isdir()`

**validate-link-quality.py (Stage 9)**: Fails on ANY remaining `[[wikilinks]]` (all should be markdown by now) AND any markdown links pointing to non-existent files.

**Common failure patterns**:
- Filenames with `.md` in the name (e.g., `CLAUDE.md as Runtime Configuration`) corrupted by `replace('.md', '')` → always use `removesuffix('.md')`
- Directory links not handled — validators must check both `isfile()` and `isdir()`
- Parent directory paths (`../`) not resolved correctly
- Frontmatter links using `[[wikilinks]]` instead of `[text](./path)`

## Cron Job Setup

The AI Matrix Trends pipeline runs on the **host system crontab**, NOT Hermes cron. See the `vault-cron-workflow` skill for the exact crontab entries, stage descriptions, and troubleshooting.

**Pitfall:** Do NOT create Hermes cron jobs for this pipeline. They conflict with the host crontab and cause duplicate note creation.

### Adding New Agents/Plugins

Edit `stage-1-research.py` directly. Three sections:
- `agents_to_create` — AI coding agents (e.g., Claude Code, Hermes Agent, Jev)
- `plugins_to_create` — MCP servers, plugins (e.g., Hermes Jev, Context7 MCP)
- `arch_to_create` — Architecture patterns (e.g., ReAct)

Each entry: `title`, `tags`, `links`, `overview`. Plugins also need `agents` (array of agent keys).

**Pitfall:** Tags must be from the vault's controlled vocabulary. Invalid tags fail CI Stage 4.

### Post-Scan Scripts (MANDATORY ORDER)

Run these Python scripts in EXACT ORDER after Stage 1:

1. `python3 scripts/resolve_wikilinks.py` — Resolves short-name wikilinks
2. `python3 scripts/fix-all-links.py` — Comprehensive link fixing
3. `python3 scripts/verify-vault.py` — Verifies all links resolve
4. `python3 scripts/aggregate-trends.py` — Scores items, saves trend-data.json
5. `python3 scripts/collect_agent_plugins.py` — Builds per-agent plugin tables
6. `python3 scripts/update-mocs.py` — Updates Maps of Content
7. `python3 scripts/update-plugin-master-index.py` — Generates Plugin Master Index
8. `python3 scripts/update-agent-master-index.py` — Generates Agent Master Index
9. `python3 scripts/update_readme.py` — Updates README with scored tables
10. `python3 scripts/fix-master-index-links.py` — Syncs frontmatter links
11. `python3 scripts/verify-vault.py` — Final verification
12. `git add -A && git commit -m 'Daily scan' && git push`

**NEVER skip any script. NEVER change the order.**

## CRITICAL PITFALLS

See `references/dedup-patterns.md` for reusable Python patterns that prevent duplicate files, table rows, and links across vault indexes. These patterns emerged from fixing duplicate-creation bugs in `update-agent-master-index.py`, `update-plugin-master-index.py`, `update-mocs.py`, and `fix-master-index.py`.

See `references/ci-fix-workflow.md` for a systematic process for diagnosing and fixing CI pipeline failures. This includes stage-specific diagnosis (which stage failed and why), fix patterns per stage, and the full fix cycle to get the pipeline green again.

### 1. Timestamp Collisions
Multiple notes with same timestamp cause wikilink resolution failures — `resolve_wikilinks` maps to the FIRST match, which is wrong.
- **Rule**: Sub-agents MUST `search_files` before writing. Use `max(existing timestamp) + 10`, never fixed ranges.

### 2. Short Name Wikilinks
`[[Claude Code]]` doesn't match the actual file `2026092010 - Claude Code.md`.
- **Rule**: ALWAYS use full filenames in wikilinks. The merge step is eliminated — agents must link correctly from the start.

### 3. Duplicate Notes
Sub-agents create new files when one already exists on the topic.
- **Rule**: Before writing, search for existing files. If found, `patch()` the existing note instead.

### 4. Missing Frontmatter Links
Notes without `links:` field in frontmatter.
- **Rule**: Sub-agents MUST add `links:` with ≥2 full filename wikilinks. Never leave it empty.

### 5. Body Uses Markdown Links, Frontmatter Uses Wikilinks

The vault intentionally uses two link formats:
- **Frontmatter `links:`**: Obsidian `[[wikilinks]]` format (`- "[[202609202000 - Claude Code]]"`) — Obsidian resolves these natively. The CI `validate-link-quality.py` strips frontmatter before checking, so these are safe.
- **Body sections** (`## Related`, `## Compatibility`, `## Sources`): Must use markdown links `[text](./path)` — NOT `[[wikilinks]]`. The CI `validate-link-quality.py` fails on body wikilinks.

The `create_note()` function in `stage-1-research.py` must produce body markdown links, not wikilinks. If new notes fail Stage 9, check the body link format.

### 6. Agent Compatibility Detection
Plugin `**Agent:**` lines use wikilinks (`[[202609200759 - Hermes Agent]]`), not agent keys. The `agents:` frontmatter field can be either bracketed array (`[claude-code, opencode]`) or YAML list (`- claude-code`). MCP plugins work with ALL MCP-compatible agents.
- **Rule**: Compatibility scripts must parse BOTH frontmatter formats and match by agent key OR display name (e.g., `hermes` OR `Hermes Agent`). A plugin tagged `mcp` that says "any MCP-compatible" works with ALL MCP agents (Claude Code, OpenCode, Hermes, Cursor, Codex, Windsurf, Aider, Gemini CLI, GitHub Copilot, Kilo Code, RooCode, JetBrains Junie) — not just the ones explicitly named.

### 7. Master Index Frontmatter Links
Master Index files at folder root (`00 - Agent Master Index.md`, `00 - Plugin Master Index.md`) MUST use markdown links in frontmatter `links:` section, not wikilinks.
- **Rule**: `links:` must contain `[title](./path.md)` format. Body `## Related` can use markdown links to directories.
- **Body directory links**: Use `[Label](./09%20-%20Trend%20Radar/)` — trailing slash indicates directory link.

### 9. Host Crontab, Not Hermes Cron
The AI Matrix Trends pipeline runs on the **host system crontab** (`crontab -e`), NOT Hermes cron jobs. The user explicitly wanted host crontab execution.
- **Rule**: Use `crontab -l` to list current jobs, write to a temp file, then `crontab <file>` to install. ALWAYS backup first: `crontab -l > /path/to/bak`.
- **Rule**: Script paths in crontab MUST be absolute: `cd /home/asimov/repository/git/ai-matrix-trends/scripts && python3 stage-1-research.py >> /tmp/log 2>&1`
- **Rule**: Use `exec setsid bash` (or `exec setsid python3`) to detach cron jobs from the cron process group, preventing hangups when the cron daemon restarts.

### 10. Stage 1 Creates ALL Note Types
`stage-1-research.py` creates agents, plugins, AND architecture patterns. The skill description must reflect this three-way split.
- **Rule**: When adding new coverage to the vault, update `stage-1-research.py` in three sections: `agents_to_create`, `plugins_to_create`, `arch_to_create`. A new AI tool (e.g., Factory Code) goes in agents. A new MCP server (e.g., Slack MCP) goes in plugins. A new pattern (e.g., ReAct) goes in architecture.
- **Rule**: New notes created by `create_note()` must pass all 10 CI stages. Common failures: invalid tags (Stage 4), trailing whitespace (Stage 8), wikilinks in body (Stage 9), missing from README (Stage 10).

### 11. YAML Tag Parsing Regex
Broken regex `\s*-\s*` doesn't match YAML frontmatter format `  - tag`.
- **Rule**: Use `r'^tags:\n((?:[-\s]+.+\n?)+)'` to match indented YAML tags. Add `if t.strip()` filter to skip empty lines. Broken tag parsing causes plugins to land in 'Other' category and create duplicate table rows across index sections.

### 12. Duplicate Prevention in Index Scripts
Index scripts (`update-agent-master-index.py`, `update-plugin-master-index.py`) must deduplicate BY TITLE, not just by filename. Running scans multiple times creates duplicate table rows if the same agent/plugin appears in multiple index sections (Top 5, Complete List, By Status, By Category).
- **Rule**: Index scripts must use a `dict` keyed by `title.lower()` and keep only the highest-scored version. Output each agent/plugin ONCE per table section, not once per section it qualifies for.

### 13. Cross-Volume Duplicate Files
Stage 1 research creates notes with `2026092025xx` timestamps. Running it again creates duplicates with different timestamps but same title (e.g., `202609202000 - Claude Code.md` AND `202609202500 - Claude Code.md`). Both `update-agent-master-index.py` and `update-plugin-master-index.py` will include BOTH in their tables.
- **Rule**: Before creating any note, scan ALL vault folders for matching titles (case-insensitive). If found, skip creation. Use `get_all_existing_titles()` that walks all folders, not just the target folder.

### 14. Master Index Frontmatter Links
`fix-master-index-links.py` must be IDEMPOTENT. Running it multiple times must produce the same result — no duplicate links added on re-run.
- **Rule**: Use set operations (`existing_links | needed_links`) to deduplicate. Only add links that are truly missing. The script should report 'links complete' when nothing changed.

### 15. resolve_wikilinks.py Must Skip Already-Resolved Links
Re-running `resolve_wikilinks.py` must not modify links that already have timestamps.
- **Rule**: Skip wikilinks matching `\d{12,14} - ` pattern (already resolved). Use exact matching only — partial/fuzzy matching causes false positives (e.g., 'cursor' matching 'Cursor' AND 'Cursor IDE').

### 16. MOC Update Deduplication
`update-mocs.py` appends new notes to existing MOC files. Running it multiple times adds duplicate entries.
- **Rule**: Before adding a note to a MOC, extract ALL existing entries (both wikilinks AND markdown links) and skip any that already exist (case-insensitive). Use `extract_existing_entries()` to build a set of current links, then only add notes not in that set. Apply `deduplicate_moc_content()` after any insertion to clean up historical duplicates.
- **MOC links must be markdown format**: `[title](./path.md)` not `[[wikilinks]]` — validators reject wikilinks.
- **Use full relative paths**: `get_notes_in_folder()` must return paths relative to vault root (e.g., `03 - Agents/202609200758 - OpenCode`), not just filenames. This ensures subfolder notes (like `09 - Trend Radar/Heating Up/202609200100 - MCP Server.md`) are linked correctly.
- **CRITICAL**: Use `f.removesuffix('.md')` NOT `f.replace('.md', '')` — filenames containing `.md` (like `CLAUDE.md`) get corrupted otherwise.

### 17. Hermes Cron Script Path
Hermes cron jobs with `--script` look for scripts in `~/.hermes/profiles/<profile>/scripts/`, NOT in the repo's `scripts/` directory.
- **Rule**: After any script change, copy the updated script to `~/.hermes/profiles/ai-matrix-trends/scripts/`. Symlinks work but copies are safer (no stale references). Stage 1 (agent-based) doesn't need this — it uses `--prompt`.

### 18. create_note() Trailing Whitespace

The `create_note()` function in `stage-1-research.py` generates note files. A common bug: adding a trailing space after `-` in the Sources section (`## Sources\n- \n`), which causes Stage 8 (Markdown Formatting) to fail.

- **Rule**: End files with `## Sources\n-` (no trailing space, no extra newline). The `validate-formatting.py` script flags any line where `line.rstrip() != line`.
Using `str.replace('.md', '')` removes ALL occurrences of the substring `.md`, not just the file extension. Filenames like `CLAUDE.md as Runtime Configuration` become `CLAUDE as Runtime Configuration`.
- **Rule**: ALWAYS use `str.removesuffix('.md')` to strip a known suffix. This method was added in Python 3.9. Fall back to `[:-3] if s.endswith('.md') else s` for older versions. This applies to ALL vault Python scripts: validators, index generators, MOC updaters, and fix scripts.

### 19. README Table Column Limits

Wide tables don't render on GitHub and are unreadable on mobile. A 22-column compatibility matrix forces horizontal scrolling and looks broken.
- **Rule**: Limit README tables to ≤ 7 data columns. For compatibility/agent matrices, show only the top 6 agents by plugin count + a "Total" column. Use `…` for truncated plugin names (max 28 chars). Link to the Plugin Master Index or Agent Master Index for full breakdowns — the README is a dashboard, not the complete dataset.
- **Rule**: The "Top Plugins & Extensions" section in README must show top 5 plugins FOR EACH of the top 5 agents (Claude Code, OpenCode, Hermes, Cursor, Codex), not a single global top 5. Each agent gets its own sub-table with its specific plugins first, then the best universal MCP plugins.
- **Rule**: Scoring in per-agent tables must prioritize agent-specific plugins (e.g., Cursor Tab for Cursor) over universal MCP plugins (e.g., Sentry MCP). Agent-specific plugins get a +100 point bonus in the scoring algorithm to ensure they appear first.

Wide tables don't render on GitHub and are unreadable on mobile. A 22-column compatibility matrix forces horizontal scrolling and looks broken.
- **Rule**: Limit README tables to ≤ 7 data columns. For compatibility/agent matrices, show only the top 6 agents by plugin count + a "Total" column. Use `…` for truncated plugin names (max 28 chars). Link to the Plugin Master Index or Agent Master Index for full breakdowns — the README is a dashboard, not the complete dataset.

### 21. Top Plugins Must Be Per-Agent, Not Global

The README "Top Plugins & Extensions" section must show **top 5 plugins for each of the top 5 agents**, NOT a single global top 5. User explicitly rejected identical plugin lists across all agents.

- **Rule**: `update_readme.py` must generate a sub-table per agent (Claude Code, OpenCode, Hermes Agent, Cursor, Codex). Each sub-table shows that agent's specific plugins first, then the best universal MCP plugins as filler.
- **Rule**: Agent-specific plugins (e.g., Cursor Tab for Cursor, OpenCodeRAG for OpenCode) must score higher than universal MCP plugins (e.g., Sentry MCP) in per-agent tables. Use a +100 point bonus for agent-specific plugins.
- **Rule**: The top 5 agents are: Claude Code, OpenCode, Hermes Agent, Cursor, Codex. These are the agents with the most ecosystem activity in 2026.
- **Universal MCP table**: After the per-agent tables, include a separate "Common MCP Plugins" table listing all universal MCP servers (those supporting 10+ agents) with their agent counts. This avoids repeating the same MCP plugins in every agent's table.

After batch-rewriting files (e.g., adding `agents:` field to all plugins via a script), the output often contains consecutive blank lines (`\n\n\n`) or trailing whitespace that fails Stage 8 (Markdown Formatting).
- **Rule**: After any batch file modification, run a cleanup pass: `re.sub(r'\n\n\n+', '\n\n', content)` on every modified file, then re-run `python3 scripts/ci/ci-pipeline.py` to verify all 10 stages pass before committing.

## Tools

- `search_files`, `read_file`, `write_file`, `patch`
- `terminal` for git operations
- `delegate_task` for parallel streams
- `web_search` / `web_extract` for trend discovery
- `cronjob_manage` for scheduling
- `execute_code` for vault validation
- `hermes cron create/edit` for managing scheduled jobs
