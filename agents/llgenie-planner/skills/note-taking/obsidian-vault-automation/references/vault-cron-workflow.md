---
name: vault-cron-workflow
description: "The exact daily scan cron workflow for the AI Matrix Trends vault."
---

# Vault Cron Workflow

## Pre-Scan Setup

1. `skill_view(name="obsidian")`
2. `skill_view(name="obsidian-vault-automation")`
3. Read AGENTS.md for vault structure
4. Read all 4 note templates:
   - `.obsidian/templates/agent-profile.md`
   - `.obsidian/templates/plugin-profile.md`
   - `.obsidian/templates/architecture-pattern.md`
   - `.obsidian/templates/atomic-note.md`
5. Check vault state: `search_files` on all folders
6. Read existing MOCs and README
7. Initial commit checkpoint

**Pitfall:** Do NOT improvise link resolution. Use the deterministic Python scripts below — they build file maps from actual vault contents and resolve short names correctly.

## Parallel Research Streams (4 via delegate_task)

### Timestamp Allocation (CRITICAL)
- Stream A (Agents): minutes 10-14
- Stream B (Plugins): minutes 20-24
- Stream C (Architecture): minutes 30-32
- Stream D (Use Cases): minutes 40-42

### Sub-Agent Rules
- DO NOT add `links:` to frontmatter
- ONLY use `## Related` section at bottom with short names
- Create manifest file after writing notes

### Stream A: Agents (03 - Agents/)
Goal: 3-5 agents
Frontmatter (NO links):
```yaml
---
id: 2026092010
created: 2026-09-20T10:00:00+02:00
tags:
  - agent
  - cli
---
```
Body: `## Related` with `[[Name 1]], [[Name 2]]`
Manifest: `08 - Projects/scan-manifests/stream-a-UNIQUE.json`
Git: commit + push

### Stream B: Plugins (04 - Plugins/)
Goal: 3-5 plugins
Frontmatter (NO links):
```yaml
---
id: 2026092020
created: 2026-09-20T20:00:00+02:00
tags:
  - plugin
  - mcp
---
```
Body: `## Related` with `[[MOC-Plugin-Ecosystem]], [[MOC-Trending-Agents]]`
Manifest: `08 - Projects/scan-manifests/stream-b-UNIQUE.json`
Git: commit + push

### Stream C: Architecture (05 - Architecture/)
Goal: 2-3 patterns
Frontmatter (NO links):
```yaml
---
id: 2026092030
created: 2026-09-20T30:00:00+02:00
tags:
  - architecture
  - mcp
---
```
Body: `## Related` with `[[Pattern 1]], [[Pattern 2]]`
Manifest: `08 - Projects/scan-manifests/stream-c-UNIQUE.json`
Git: commit + push

### Stream D: Use Cases (06 - Use Cases/)
Goal: 2-3 use cases
Frontmatter (NO links):
```yaml
---
id: 2026092040
created: 2026-09-20T40:00:00+02:00
tags:
  - workflow
  - config
---
```
Body: `## Related` with `[[MOC-Plugin-Ecosystem]], [[MOC-Architecture-Patterns]]`
Manifest: `08 - Projects/scan-manifests/stream-d-UNIQUE.json`
Git: commit + push

## Post-Scan Merge (MANDATORY — Run Scripts in Order)

**Pitfall:** Do NOT skip scripts. Do NOT change order. Each script depends on the previous one.

### Step 1: Fix All Links
```bash
cd ~/repository/git/ai-matrix-trends && python3 scripts/fix_all_links.py
```
- Resolves short-name wikilinks (`[[Claude Code]]` → `[[202609202000 - Claude Code]]`)
- Fixes frontmatter links to point to actual filenames
- Adds missing `links:` fields

### Step 2: Aggregate Trends
```bash
cd ~/repository/git/ai-matrix-trends && python3 scripts/aggregate-trends.py
```
- Scores all items (stars + mentions + tag bonuses)
- Saves to `08 - Projects/trend-data.json`

### Step 3: Collect Agent Plugins
```bash
cd ~/repository/git/ai-matrix-trends && python3 scripts/collect_agent_plugins.py
```
- Builds per-agent plugin compatibility tables
- Generates `## 🔌 Plugins by Agent` and `## 📊 Plugin Compatibility Matrix` in README

### Step 4: Update README
```bash
cd ~/repository/git/ai-matrix-trends && python3 scripts/update_readme.py
```
- Updates Trend Radar tables with top 5 per category
- Creates atomic notes in `09 - Trend Radar/`
- Updates date

### Step 5: Verify Vault
```bash
cd ~/repository/git/ai-matrix-trends && python3 scripts/verify-vault.py
```
- Verifies all 119+ notes have 0 broken links
- Fails if any orphan found

### Step 6: Commit and Push
```bash
cd ~/repository/git/ai-matrix-trends && git add -A && git commit -m "Daily scan" && git push
```

**Pitfall:** If verify fails, fix and re-run. Do NOT push broken links.
