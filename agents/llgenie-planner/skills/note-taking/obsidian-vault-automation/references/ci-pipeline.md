# CI Pipeline Reference

## Pipeline Stages

### Stage 1: Link Validation (`validate-links.py`)
- Validates all `[[wikilinks]]` point to existing files
- Skips: AGENTS.md, `.obsidian/templates/`, `00 - Master Index.md` files
- Builds a file map from actual vault contents
- Checks both frontmatter `links:` and body `## Related` sections

### Stage 2: Frontmatter Validation (`validate-frontmatter.py`)
- Validates frontmatter structure (id, created, tags fields)
- Checks for duplicate links in frontmatter
- Skips template files

### Stage 3: Duplicate Detection (`validate-duplicates.py`)
- Checks for duplicate files with same title in same folder
- Uses title extraction: filename.split(' - ', 1)[1]
- Reports all duplicates with their full paths

### Stage 4: Tag Validation (`validate-tags.py`)
- Validates tags against a whitelist (`VALID_TAGS` set)
- Skips template files and index files
- Uses line-by-line parsing to avoid regex pitfalls

## Auto-Fix Script (`fix-pipeline-issues.py`)

Fixes common issues:
1. Template placeholders in AGENTS.md
2. Malformed wikilinks (wrong timestamps)
3. Missing frontmatter fields (id, created)
4. Invalid tags (normalization)
5. Folder links (e.g., `[[03 - Agents/]]` → `[[03 - Agents/00 - Agent Master Index]]`)
6. Duplicate MOC entries
7. Duplicate table rows in indexes

## GitHub Actions Workflow (`.github/workflows/ci.yml`)

```yaml
name: AI Matrix Trends CI
on:
  push:
    branches: [ master, main ]
  pull_request:
    branches: [ master, main ]
jobs:
  validate-vault:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
    - name: Run CI Pipeline
      run: python3 scripts/ci/ci-pipeline.py
```

## Tag Regex Pitfall

**WRONG:** `r'^tags:\n((?:\s*-\s*.+\n?)+)'`
- This pattern requires whitespace BEFORE the dash, which fails on standard YAML frontmatter where tags are indented with 2 spaces.

**RIGHT:** `r'^tags:\n((?:[-\s]+.+\n?)+)'`
- This pattern matches both `- tag` and `  - tag` formats.
- Also add `if t.strip()` filter to skip empty lines.

## Deduplication Patterns

### MOC Deduplication
```python
def deduplicate_moc_content(content):
    lines = content.split('\n')
    seen = set()
    new_lines = []
    for line in lines:
        match = re.match(r'^(\s*-\s*)\[\[([^\]|]+)(?:\|[^\]]+)?\]\](\s*.*)$', line)
        if match:
            link = match.group(2).strip().lower()
            if link in seen:
                continue
            seen.add(link)
        new_lines.append(line)
    return '\n'.join(new_lines)
```

### Index Deduplication
```python

# Deduplicate by title, keep highest scored version
by_title = {}
for item in items:
    title_key = item['title'].lower()
    if title_key in by_title:
        if item['score'] > by_title[title_key]['score']:
            by_title[title_key] = item
    else:
        by_title[title_key] = item
```

## Setup Commands

```bash

# Install cron jobs
bash scripts/setup-cron.sh

# Verify cron jobs
hermes cron list --profile ai-matrix-trends

# Run full scan
python3 scripts/stage-1-research.py
python3 scripts/stage-2-links.py
python3 scripts/stage-3-scoring.py
python3 scripts/stage-4-indexes.py

# Run CI pipeline
python3 scripts/ci/ci-pipeline.py

# Auto-fix issues
python3 scripts/ci/fix-pipeline-issues.py
```
