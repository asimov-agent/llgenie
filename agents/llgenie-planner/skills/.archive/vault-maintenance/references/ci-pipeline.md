# CI Pipeline for Obsidian Vaults

## Overview

A comprehensive CI pipeline validates all markdown files in the vault and **fails** (not warns) when issues are detected. This ensures the pipeline goes red when there's work to do, rather than silently accumulating warnings.

## Pipeline Stages (9 Total)

| # | Stage | Script | Exit on Issue |
|---|-------|--------|---------------|
| 1 | Link Validation | `validate-links.py` | Yes - broken `[[wikilinks]]` |
| 2 | Frontmatter Validation | `validate-frontmatter.py` | Yes - duplicate links |
| 3 | Duplicate Detection | `validate-duplicates.py` | Yes - same-title files in folder |
| 4 | Tag Validation | `validate-tags.py` | Yes - invalid vocabulary |
| 5 | Index Completeness | `validate-index-completeness.py` | Yes - notes missing from MOCs |
| 6 | Orphan Detection | `validate-orphans.py` | **Yes** - notes not linked from anywhere |
| 7 | Template Consistency | `validate-templates.py` | Yes - missing sections |
| 8 | Markdown Formatting | `validate-formatting.py` | Yes - trailing whitespace, heading jumps |
| 9 | Link Quality | `validate-link-quality.py` | Yes - wikilinks that should be markdown links; markdown links that resolve to missing files |

## Key Design Decisions

### 1. Pipeline Must FAIL, Not Warn

Orphan detection and other checks exit with code 1 on failure. This makes the GitHub Actions workflow go red, signaling that work needs attention. A green pipeline means the vault is clean.

### 2. Relative Paths Only

All scripts compute `VAULT_DIR` from `os.path.dirname(__file__)` — never hardcoded paths. This ensures the pipeline works in any environment (local, CI, different usernames).

```python
# Correct - works anywhere
SCRIPT_PATH = os.path.abspath(__file__)
SCRIPT_DIR = os.path.dirname(SCRIPT_PATH)
CI_DIR = os.path.dirname(SCRIPT_DIR)
VAULT_DIR = os.path.dirname(CI_DIR)

# Wrong - breaks in CI
VAULT_DIR = os.path.expanduser("~/repository/git/vault")
```

### 3. Case-Insensitive Link Matching

Wikilink targets and filenames are compared case-insensitively (`fname.lower()`). The vault uses sentence-case titles in filenames (`202609202000 - Claude Code.md`) but wikilinks may use any case.

### 4. Folder Aliases for Index Files

The link validator includes explicit folder aliases so links like `[[03 - Agents/]]` resolve to the Master Index:

```python
file_map['03 - agents/'] = '03 - Agents/00 - Agent Master Index'
file_map['04 - plugins/'] = '04 - Plugins/00 - Plugin Master Index'
```

### 5. Skip Patterns for Non-Content Files

Validators skip index files (`00 -`), MOCs, templates, and scripts directories. These have different frontmatter structure and link patterns.

```python
skip_patterns = ['00 -', 'MOC-', 'AGENTS.md', 'README.md', 'LICENSE',
                 'daily-scan-prompt.md', 'scripts/ci/', '.obsidian/templates/']
```

### 6. File-Relative Link Resolution (GitHub Semantics)

Markdown links are resolved relative to the **containing file's directory**, exactly like GitHub:

```python
from urllib.parse import unquote
from_dir = os.path.dirname(filepath)
target = os.path.normpath(os.path.join(from_dir, unquote(link.split('#')[0])))
if not (os.path.isfile(target) or os.path.isdir(target)):
    errors.append(f"  Markdown link: {link} -> NOT FOUND (resolves to: {os.path.relpath(target, VAULT_DIR)})")
```

Generators compute paths with `os.path.relpath(target_abs, os.path.dirname(output_file))` and encode spaces as `%20`. Never resolve links against the vault root — that mirrors the writer's own bug and stays green while GitHub shows red. `fix-links-relative.py` rewrites legacy vault-root-relative links to file-relative form (idempotent, skips code fences).

## GitHub Actions Integration

```yaml
name: AI Matrix Trends CI
on:
  push:
    branches: [master, main]
  pull_request:
    branches: [master, main]

jobs:
  validate-vault:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      - name: Run CI Pipeline
        run: python3 scripts/ci/ci-pipeline.py
```

## When the Pipeline is Red

1. Run locally: `python3 scripts/ci/ci-pipeline.py`
2. Identify which stage failed
3. Run auto-fix: `python3 scripts/ci/fix-pipeline-issues.py`
4. Manually fix any remaining issues
5. Re-run CI pipeline locally to verify green
6. Commit and push

## Common Pipeline Failures

| Failure | Cause | Fix |
|---------|-------|-----|
| Orphan notes | New note not linked from any other note or MOC | Add to relevant MOC or link from related note |
| Broken wikilink | Target file was renamed or deleted | Update link to correct filename, or create target |
| Broken markdown link (green locally, red on GitHub) | Link path written vault-root-relative; GitHub resolves relative to the containing file | Run `fix-links-relative.py`, then fix the generator that emitted the wrong path |
| Missing from MOC | Note exists but not in its folder's MOC | Run `update-mocs.py` or manually add |
| Duplicate links | Same link appears twice in frontmatter | Run `fix-master-index.py` |
| Invalid tag | Tag not in allowed vocabulary | Replace with valid tag or add to vocabulary |
| Trailing whitespace | Line ends with spaces/tabs | Run `sed -i 's/[[:space:]]*$//' file.md` |
