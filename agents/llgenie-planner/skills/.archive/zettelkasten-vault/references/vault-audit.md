# Vault Audit and Orphan Detection

## Purpose
Validate vault integrity after automated scans. Detect and fix broken markdown links, missing frontmatter, and duplicate entries.

## Cron Delivery Pitfall

`deliver=all` fails when no delivery gateway is explicitly configured for that job. Fix: re-create with `--deliver origin` or edit with `hermes cron edit <id> --deliver origin`.

## Audit Procedure

Run via `execute_code` after every scan:

```python
import re, os

vault_path = os.path.expanduser('~/repository/git/ai-matrix-trends')
os.chdir(vault_path)

# Build file map — use removesuffix, NOT replace
file_map = {}
for root, dirs, files in os.walk('.'):
    if '/.git' in root: continue
    for f in files:
        if f.endswith('.md'):
            fname = f.removesuffix('.md')
            file_map[fname.lower()] = os.path.join(root, f)

orphans = []
few_links = []
no_links_field = []

for folder in ['03 - Agents', '04 - Plugins', '05 - Architecture', '06 - Use Cases']:
    for f in os.listdir(folder):
        if not f.endswith('.md'): continue
        path = os.path.join(folder, f)
        with open(path) as fh:
            content = fh.read()
        
        fm_match = re.search(r'^---\n(.*?)\n---', content, re.DOTALL)
        if fm_match:
            fm = fm_match.group(1)
            links_match = re.search(r'^links:\n((?:\s*-\s*".*?"\n?)*)', fm, re.MULTILINE)
            if links_match:
                links = re.findall(r'"\[\[([^\]]+)\]\]"', links_match.group(1))
                if len(links) < 2:
                    few_links.append((path, len(links)))
            else:
                no_links_field.append(path)
        
        body = re.sub(r'^---\n.*?\n---\n', '', content, flags=re.DOTALL)
        for link in re.findall(r'\]\(([^)]+)\)', body):
            if link.startswith('http'): continue
            clean = link.replace('%20', ' ').split('#')[0]
            if not clean: continue
            from_dir = os.path.dirname(path)
            target = os.path.normpath(os.path.join(from_dir, clean))
            if os.path.isfile(target) or os.path.isdir(target): continue
            orphans.append((path, link))

print(f'Audit: {len(few_links)} few links, {len(no_links_field)} no links, {len(orphans)} orphans')
```

## Fixing Orphans

Body wikilinks should be converted to markdown links:
```
patch(path="<file>",
      old_string="[[<orphan_link>]]",
      new_string="[<display>](./<relative_path>.md)")
```

## CI Pipeline Failures

When the CI pipeline is red, run `python3 scripts/ci/ci-pipeline.py` locally:

- **Stage 4 (Tags)**: Invalid tag. Add new domain tags to `VALID_TAGS` in `validate-tags.py`.
- **Stage 8 (Formatting)**: Trailing whitespace. `create_note()` must use `## Sources\n-` not `## Sources\n- \n`.
- **Stage 9 (Link Quality)**: Body wikilinks. Convert to markdown links `[text](./path)`.
- **Stage 10 (README)**: New agent/plugin not in README tables.
