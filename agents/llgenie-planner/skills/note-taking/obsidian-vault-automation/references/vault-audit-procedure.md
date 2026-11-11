---
name: vault-audit-procedure
description: "How to audit the AI Matrix Trends vault for completeness and fill gaps."
---

# Vault Audit Procedure

**Use when:** You need to verify the AI Matrix Trends vault has complete coverage of agents, plugins, architecture patterns, and use cases. Also use after adding notes manually to verify consistency.

## The Problem

`stage-1-research.py` has HARDCODED lists of agents/plugins to create. It only adds notes that DON'T exist. It does NOT:
- Update stale notes
- Discover new agents/plugins on its own
- Fix gaps in coverage

This means the vault perpetually reflects whoever set up the initial list, not the actual landscape.

## When to Audit

Run a full audit:
- After each manual extension (to ensure consistency)
- Monthly (the AI landscape shifts weekly)
- When the user requests a completeness review

## Audit Steps

### 1. Inventory the Vault
```bash
find /path/to/agents -name "*.md" ! -name "00*" | wc -l
find /path/to/plugins -name "*.md" ! -name "00*" | wc -l
find /path/to/architecture -name "*.md" ! -name "00*" | wc -l
```

### 2. Compare to External Sources

Cross-reference vault contents against:
- AGENTS.md "Key Agent Profiles" list
- GitHub MCP server registry (glama.ai, modelcontextprotocol.io servers)
- Recent AI coding agent launches (Factory Code, OpenHands, Sweep AI, etc.)
- MCP plugin directories for each agent (Claude Code, Cursor, Codex, OpenCode, Windsurf)
- Architecture patterns from agent research (ReAct, Reflexion, Tree of Thought, etc.)

### 3. Run the Vault Pipeline

After identifying gaps, run the 4-stage pipeline to verify everything still works:
```bash
cd /path/to/vault/scripts
python3 stage-1-research.py
python3 stage-2-links.py
python3 stage-3-scoring.py
python3 stage-4-indexes.py
```

Stage 1 will skip existing notes (good), stages 2-4 will validate and regenerate indexes.

## Creating Missing Notes

### Template (Python)

```python
import os
from datetime import datetime

VAULT_DIR = os.path.expanduser("~/repository/git/ai-matrix-trends")
AGENTS_DIR = os.path.join(VAULT_DIR, "03 - Agents")

def get_all_existing_titles():
    titles = set()
    for root, dirs, files in os.walk(VAULT_DIR):
        if '/.git' in root:
            continue
        for f in files:
            if f.endswith('.md') and ' - ' in f and not f.startswith('00 -'):
                title = f.split(' - ', 1)[1].replace('.md', '').lower()
                titles.add(title)
    return titles

def get_next_timestamp(folder):
    max_ts = 0
    for f in os.listdir(folder):
        if f.endswith('.md') and ' - ' in f:
            try:
                ts = int(f.split(' - ')[0])
                if ts > max_ts:
                    max_ts = ts
            except ValueError:
                pass
    return max_ts + 10

def create_note(folder, title, tags, links, overview, agents=None):
    existing = get_all_existing_titles()
    if title.lower() in existing:
        return False
    
    ts = get_next_timestamp(folder)
    filename = f"{ts} - {title}.md"
    filepath = os.path.join(folder, filename)
    date_str = datetime.now().strftime('%Y-%m-%dT%H:%M:%S+02:00')
    
    frontmatter = f"""---
id: {ts}
created: {date_str}
tags:
"""
    for tag in tags:
        frontmatter += f"  - {tag}\n"
    
    if agents:
        frontmatter += "agents:\n"
        for agent in agents:
            frontmatter += f"  - {agent}\n"
    
    frontmatter += "links:\n"
    for link in links:
        frontmatter += f'  - "[[{link}]]'\'\n'\''\n'
    frontmatter += "---\n\n"
    
    body = f"# {title}\n\n"
    body += f"## Overview\n{overview}\n\n"
    
    if agents:
        body += "## Compatibility\n"
        body += "**Agent:** " + ", ".join([f"[[{a}]]" for a in agents[:5]])
        if len(agents) > 5:
            body += f" +{len(agents)-5} more"
        body += "\n\n"
    
    body += "## Related\n"
    for link in links:
        body += f"- [[{link}]]\n"
    body += "\n## Sources\n- \n"
    
    with open(filepath, 'w') as f:
        f.write(frontmatter + body)
    return True
```

### After Creating Notes

1. Remove any leftover placeholder files from Inbox/01/02/99 folders
2. Delete `__pycache__/` folders and add `.gitignore` if missing
3. Run `python3 stage-3-scoring.py` (re-aggregates scores)
4. Run `python3 stage-4-indexes.py` (updates MOCs, indexes, README, commits)

### Pitfall: README Count Mismatch

The README has manual count strings ("All 41 tracked...") that must be updated to match actual vault contents. The `update_readme.py` script handles the scored tables but NOT these manual header strings. Update them with `patch()` after running stage 4.

## What the Pipeline Does NOT Fix

- **Stale content**: Existing notes are NOT updated with new information
- **Classification errors**: Trend Radar status is score-based; manual review needed for semantic correctness
- **Orphaned notes**: Notes created outside the pipeline may not link to MOCs
- **Master index drift**: If notes are added manually and stages 3-4 not re-run, indexes lag behind

## Periodic Tasks

- Run `find . -name "*placeholder*"` monthly to catch auto-created folder placeholders
- Run `find . -name "__pycache__" -type d` and add to `.gitignore` if needed
- Check that all `00 - * Index.md` files have `links:` fields matching their note counts
- Verify README count strings match actual `find ... | wc -l` output
