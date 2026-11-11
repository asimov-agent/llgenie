---
name: vault-maintenance
description: Obsidian vault maintenance via staged Python pipelines.
version: 1.0.0
author: andyholst
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [Obsidian, Notes, Markdown, Vault, Automation, Python, Cron]
    related_skills: [obsidian]
---

# Vault Maintenance — Automated Pipeline

Automated maintenance of structured Obsidian knowledge vaults using staged Python scripts.

## Vault Structure

```
vault/
├── 00 - Inbox/          # Raw observations
├── 03 - Agents/         # Entity profiles
│   └── 00 - Agent Master Index.md  # Auto-generated
├── 04 - Plugins/        # Plugin/extension docs
│   └── 00 - Plugin Master Index.md # Auto-generated
├── 05 - Architecture/   # Pattern notes
├── 06 - Use Cases/      # Real-world workflows
├── 07 - Structure/      # MOCs
├── 08 - Projects/       # Time-bound work + data files (trend-data.json)
├── 09 - Trend Radar/    # Trend analysis (Heating Up/Stable/Emerging)
├── scripts/             # Maintenance scripts (.py)
│   ├── stage-1-research.py
│   ├── stage-2-links.py
│   ├── stage-3-scoring.py
│   ├── stage-4-indexes.py
│   └── ci/              # CI validation scripts
│       ├── ci-pipeline.py
│       ├── validate-links.py
│       ├── validate-frontmatter.py
│       ├── validate-duplicates.py
│       ├── validate-tags.py
│       ├── validate-index-completeness.py
│       ├── validate-orphans.py
│       ├── validate-templates.py
│       ├── validate-formatting.py
│       ├── validate-link-quality.py
│       ├── fix-pipeline-issues.py
│       └── fix-links-relative.py
└── .github/workflows/ci.yml  # GitHub Actions CI
```

## Staged Pipeline Architecture

### Daily Scan (4 Staggered Cron Jobs)

The daily scan runs as **4 separate cron jobs at staggered times**, never as one monolithic script. Each stage waits for the previous to complete.

| Stage | Time | Script | What it does |
|-------|------|--------|--------------|
| 1 | 20:00 | `stage-1-research.py` | Creates new notes directly (no delegate_task). Checks ALL vault folders before creating to prevent duplicates. |
| 2 | 20:30 | `stage-2-links.py` | Resolves wikilinks, fixes broken links, verifies vault integrity. |
| 3 | 20:45 | `stage-3-scoring.py` | Aggregates trend scores, collects per-agent plugin compatibility. |
| 4 | 21:00 | `stage-4-indexes.py` | Updates MOCs, Master Indexes, README, commits and pushes. |

### CI Pipeline (9 Validation Stages)

The CI pipeline validates vault integrity on every push/PR and **fails** (not warns) when issues are detected. See [references/ci-pipeline.md](references/ci-pipeline.md) for full documentation.

```bash
# Run full CI pipeline locally
python3 scripts/ci/ci-pipeline.py

# Run individual stage
python3 scripts/ci/validate-orphans.py

# Auto-fix common issues
python3 scripts/ci/fix-pipeline-issues.py
```

**Critical design choice:** The pipeline MUST go red when there's work to do. Orphan detection, broken links, and other checks exit with code 1 — not just warnings. This ensures nothing is silently missed.

See [references/ci-scripts.md](references/ci-scripts.md) for per-script documentation.

## Deduplication Rules

1. **Title uniqueness across ALL folders** — A note title must be unique across the entire vault, not just its target folder. `stage-1-research.py` uses `get_all_existing_titles()` which walks every folder.

2. **Score-based deduplication in indexes** — `scan_all_agents()` and `scan_all_plugins()` use `plugins_by_title` / `agents_by_title` dicts keyed by lowercased title. When duplicates exist, keep the highest-scored version (or longest description on tie).

3. **Frontmatter links via set operations** — `fix-master-index-links.py` computes `missing_links = needed_links - existing_links` and only adds what's truly missing. Running it multiple times produces the same result (idempotent).

4. **Wikilink exact matching only** — `resolve_wikilinks.py` uses exact title matches, never fuzzy/partial. Links with timestamps (already resolved) are skipped.

## Critical Pitfall: YAML Tag Parsing

**The regex `r'^tags:\n((?:\s*-\s*.+\n?)+)'` FAILS on indented YAML lists.** Obsidian frontmatter uses `  - tag` (indented with spaces). The regex must be `r'^tags:\n((?:[-\s]+.+\n?)+)'` to match both the dash and leading whitespace, AND filter empty lines with `if t.strip()`.

When tags aren't parsed, every plugin falls into the "Other" category, creating massive duplicate rows in the Master Index. If you see "Other" growing abnormally, check tag parsing first.

## Critical Pitfall: Link Resolution Semantics (GitHub vs Vault Root)

**GitHub and Obsidian resolve markdown links `[text](path)` relative to the containing file's directory — not the vault root.** A link `./03 - Agents/X.md` inside `04 - Plugins/Y.md` resolves to `04 - Plugins/03 - Agents/X.md` → broken on GitHub, while a validator resolving against the vault root calls it valid. This mismatch can hide thousands of silently-broken links behind a green pipeline.

1. **Generators emit file-relative paths**: `os.path.relpath(target_abs, os.path.dirname(output_file))`, spaces URL-encoded (`%20`). Same folder: `Name.md`; sibling folder: `../03%20-%20Agents/Name.md`.
2. **Validators resolve like the consumer, never like the writer**: `os.path.normpath(os.path.join(os.path.dirname(filepath), unquote(link.split('#')[0])))` then `os.path.isfile/isdir`. A validator that shares the writer's resolution bug passes forever.
3. **Validate every link format present** — body wikilinks, frontmatter `links:`, body markdown links, directory links. A validator that skips a format is green on exactly the links the user will find broken. When the user reports a specific broken file, resolve that file's links by hand per GitHub semantics first — do not re-run the same green validator.
4. **Strip code fences before scanning**: `re.sub(r'```.*?```', '', content, flags=re.DOTALL)` — links inside fenced blocks are examples, not links.
5. **Use `removesuffix('.md')`, never `replace('.md', '')`** — `replace` eats every `.md` in a filename (e.g. a note titled `CLAUDE.md as Runtime Config...`) and silently breaks all matching.
6. **Frontmatter `links:` holds markdown links** `[title](path)` (file-relative), never `[[wikilinks]]`; MOC references belong in the body `## Related` section.

**Verify generators, not just current files:** delete the generated artifacts (Master Indexes, MOCs), regenerate from scratch, re-run the pipeline. If `fix-links-relative.py` then reports 0 rewrites, the generators emit correct paths natively — a green pipeline that depends on the fixer pass is masking a generator bug.

## Critical Pitfall: Plugin Agent Assignment

**Compatibility comes ONLY from the frontmatter `agents:` field, never from body text mentions.** A script that matches agent names in `## Compatibility` or body text will assign every plugin to every agent that mentions it (e.g., any plugin mentioning "Claude Code" gets assigned to Claude Code). This makes all agent-specific plugin tables identical.

**MCP plugins** (tagged `mcp`) should support all MCP-compatible agents. **Agent-specific plugins** (e.g., "Cursor Tab", "OpenCodeRAG") support 1-2 agents only. The categorization:

- `specific`: ≤2 agents — e.g., "Cursor Tab" (cursor only), "OpenCodeRAG" (opencode only)
- `common`: ≥5 agents — universal MCP servers like Sentry MCP, GitHub MCP
- `niche`: 3-4 agents — some integrations like OpenCode Supermemory

**Verification:** After running `collect_agent_plugins.py`, grep each agent's table in the README for its specific plugins. If Cursor's table shows Sentry MCP as #1 and no Cursor-specific plugins, the assignment/scoring is wrong.

## Critical Pitfall: Plugin Scoring and Categorization

**Agent-specific plugins need a massive scoring bonus (100+ pts) to appear first in their agent's table.** Universal MCP plugins score high from `mentions * 5 + mcp * 15` and will crowd out agent-specific plugins (which have few mentions and no MCP tag). Without the bonus, every agent's table shows the same 5 universal MCP plugins.

**Scoring tiers:**
- Agent-specific (≤2 agents): `100 + stars//1000 + mentions*5 + mcp*15` — ensures they always rank first
- Universal MCP (≥10 agents): `stars//1000 + mentions*5 + mcp*15` — no bonus, just quality
- Mid-range (3-9 agents): `50 + stars//1000 + mentions*5 + mcp*15` — small bonus

**Per-agent table sort:** `(category_order, -score, -stars)` where `specific=0, niche=1, common=2`. This places agent-specific plugins first, then fills with top universal MCP plugins.

**README "Top Plugins & Extensions" section** should show agent-specific plugins prioritized over universal ones. Sort: agent-specific first (by score), then universal MCP (by score). A universal MCP plugin with 858 stars should NOT outrank a dedicated "Cursor Tab" plugin.

## Critical Pitfall: Pipeline Scripts Reintroducing Fixed Bugs

Fixing vault files is incomplete until every pipeline script that WRITES those files is audited for the old format — the nightly cron regenerates the bug class on its next run and silently undoes the fix. After changing any link/format rule, grep the scripts tree for old-format emission (`grep -n '\[\[' scripts/*.py`, plus every f-string that builds a link path) and rewrite the emitters to produce the new format natively.

- Check idempotency by running each fixer twice — the second run must report no changes (empty `git diff --stat`).
- Exercise the real cron sequence end-to-end (stage-2 → stage-4, skipping only the git push step) before declaring the fix done; validators alone never touch the writer scripts.

## Alignment Rule: Governing Docs Change With the Pipeline

When any pipeline script, link rule, or stage order changes, the same commit must update the vault's `AGENTS.md` (behavior rules), `scripts/setup-cron.sh` (cron installer + profile script sync), `scripts/daily-scan-prompt.md` (execution order), and the stage scripts themselves — then re-sync all scripts to `~/.hermes/profiles/<profile>/scripts/`. Out-of-sync docs are an incomplete change, not a follow-up task.

## Critical Pitfall: Documentation Drift (Docs vs Actual Script Behavior)

**Pipeline documentation often describes aspirational behavior that the actual scripts don't implement.** When you find that AGENTS.md or daily-scan-prompt.md describes behavior the scripts don't perform (e.g., "launches 4 parallel research sub-agents via delegate_task" when the script uses hardcoded lists, or "single cron job" when there are 4 separate jobs), the docs MUST be updated to match reality — not the other way around.

**Why:** Aspirational docs create confusion about what the pipeline actually does. Future sessions read the docs, expect behavior that doesn't exist, and waste time debugging "broken" scripts that are working as designed.

**How to audit:**
1. Read the actual script code, not just the docs
2. Compare each documented behavior claim against the implementation
3. When they diverge, update the doc to describe what the script ACTUALLY does
4. If the aspirational behavior is desired, implement it in the script first, then update the doc

**Common drift patterns:**
- Docs describe parallel/sub-agent execution; script is sequential with hardcoded data
- Docs describe web search/API calls; script reads from local files only
- Docs describe "single cron job"; setup-cron.sh creates multiple jobs
- Docs describe file extensions (.sh) that don't exist (.py)

## Workflow Rule: Implement → Test → Align Docs

When the user asks for a pipeline change or new feature, the complete delivery is:

1. **Implement** the change in the actual script(s)
2. **Test** by running the pipeline stages end-to-end (at minimum: stage-3 → stage-4)
3. **Align docs** — update AGENTS.md, daily-scan-prompt.md, setup-cron.sh, and any other doc that describes the old behavior

**Why:** A pipeline change that isn't tested and documented is an incomplete change. The user explicitly wants all documents aligned — out-of-sync docs are a follow-up task that never gets done.

**How to verify alignment:**
- `grep -n "delegate_task\|parallel\|sub-agent" scripts/*.py` — does the code match the docs?
- `grep -n "single cron job\|4 separate" AGENTS.md scripts/setup-cron.sh` — do the docs agree?
- `grep -n "stage-1-research" AGENTS.md scripts/daily-scan-prompt.md` — do filenames match?
- Run the pipeline and check that the output matches what the docs describe

## Pattern: Auto-Generated README Sections from JSON Data

When a vault has a central data file (e.g., `08 - Projects/trend-data.json`), the README can be auto-generated from it rather than hand-maintained. The pattern:

1. **Data file** stores structured items with scores, stars, tags, file paths
2. **update_readme.py** loads the JSON, sorts by score, generates markdown tables
3. **Stage 4** runs update_readme.py after scoring updates the data file
4. **Idempotent** — running update_readme.py multiple times produces the same output (cleans duplicates first)

**Benefit:** README always reflects current vault state without manual editing. New agents/plugins appear in the ranked tables automatically after the next pipeline run.

**Implementation notes:**
- Use `re.sub()` with `flags=re.DOTALL` to replace existing sections
- Clean duplicate sections before writing (idempotency)
- Generate status from score thresholds (Heating Up >= 50, Stable >= 20, Emerging < 20)
- URL-encode spaces as `%20` in links

## Verification Commands

```bash
# Check for duplicate files (same title, same folder)
find . -name "*.md" -not -path "*/.git/*" -not -name "00 -*" | while read f; do
  title=$(basename "$f" .md | sed 's/^[0-9]* - //')
  folder=$(dirname "$f")
  echo "$folder|$title"
done | sort | uniq -d

# Check frontmatter link uniqueness
python3 -c "
import re
from collections import Counter
for fp in ['03 - Agents/00 - Agent Master Index.md', '04 - Plugins/00 - Plugin Master Index.md']:
    c = open(fp).read()
    fm = re.search(r'^---\n(.*?)\n---', c, re.S).group(1)
    links = re.findall(r'\'\[\[(.*?)\]\]\'', fm)
    print(f'{fp}: {len(set(links))} unique')
"

# Check table row duplicates
python3 -c "
import re
from collections import Counter
for fp in ['03 - Agents/00 - Agent Master Index.md', '04 - Plugins/00 - Plugin Master Index.md']:
    content = open(fp).read()
    sections = re.split(r'^### .+$', content, flags=re.MULTILINE)
    for section in sections[1:]:
        rows = [l for l in section.split('\n') if l.startswith('|') and not l.startswith('| #') and not l.startswith('|---')]
        links = [re.search(r'\[([^\]]+)\]\(', row).group(1) for row in rows if re.search(r'\[([^\]]+)\]\(', row)]
        dupes = sum(c - 1 for c in Counter(links).values() if c > 1)
        if dupes: print(f'{fp}: {dupes} dupes')
"
```

## Where the LLM lives (the scripts do NOT call one)

The stage scripts are pure deterministic Python — file manipulation, link fixing, scoring, and `git` calls. They contain NO LLM/API calls (no `localhost`, `ollama`, `vllm`, `api_key`, `requests`). The only thing that uses an LLM is the Hermes *agent* that runs the pipeline, and that is configured in the profile config, not in the scripts.

To check which LLM the pipeline uses, read the profile config's `model` block:

```bash
cat ~/.hermes/profiles/ai-matrix-trends/config.yaml   # model.base_url / provider / default
hermes config get model --profile ai-matrix-trends
```

A local server shows `base_url: http://localhost:<port>/v1` (Ollama 11434, vLLM/llama.cpp). The default points at the Nous cloud API (`https://inference-api.nousresearch.com/v1`). To switch to a local server, change `model.base_url` + `provider` in the profile config — the scripts need no changes, they are LLM-agnostic.

**Pitfall:** The profile's script copies (`~/hermes/profiles/<profile>/scripts/`) are SYMLINKS to the repo originals, not copies. Verify they're in sync with `diff -q <repo>/scripts/<f> <profile>/scripts/<f>` — a symlink resolving to the same file reports identical. Edit the repo original, never the profile copy.

## Cron Job Setup

Scripts must be placed in `~/.hermes/profiles/<profile>/scripts/` and referenced by filename only (relative path). Use `--no-agent` for scripts that don't need LLM processing.

```bash
# Stage 1: Research (agent-based)
hermes cron create '0 20 * * *' --profile ai-matrix-trends --name 'Trends Stage 1' \
  --prompt '...' --deliver origin

# Stages 2-4: Script-based
hermes cron create '30 20 * * *' --profile ai-matrix-trends --name 'Trends Stage 2' \
  --script 'stage-2-links.py' --no-agent --deliver origin
```
