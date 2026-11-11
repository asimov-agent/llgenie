# Deduplication Patterns for Vault Scripts

## Purpose
Reusable Python patterns developed to prevent duplicate files, table rows, and links across vault indexes. These patterns emerged from fixing duplicate-creation bugs in `update-agent-master-index.py`, `update-plugin-master-index.py`, `update-mocs.py`, and `fix-master-index.py`.

## Pattern 1: Cross-Folder Title Deduplication

Use before creating ANY note to prevent duplicate files across different folders (e.g., `03 - Agents/202609202000 - Claude Code.md` AND `03 - Agents/202609202500 - Claude Code.md`).

```python
def get_all_existing_titles(vault_dir):
    """Get ALL note titles across ALL vault folders (prevents cross-folder duplicates)"""
    titles = set()
    for root, dirs, files in os.walk(vault_dir):
        if '/.git' in root:
            continue
        for f in files:
            if f.endswith('.md') and ' - ' in f and not f.startswith('00 -'):
                title = f.split(' - ', 1)[1].replace('.md', '').lower()
                titles.add(title)
    return titles

# Usage in note creation:
existing = get_all_existing_titles(VAULT_DIR)
if title.lower() in existing:
    return  # Skip - already exists somewhere
```

## Pattern 2: Title-Keyed Dict for Index Deduplication

Use in index scripts to ensure each agent/plugin appears ONCE per table section, not once per section it qualifies for.

```python
def scan_all_items(folder):
    """Scan items, deduplicating by title (keep highest scored version)"""
    items_by_title = {}
    
    for f in sorted(os.listdir(folder)):
        if not f.endswith('.md') or f.startswith('00 -'):
            continue
        
        # ... extract data ...
        
        title_key = title.lower()
        item_data = {
            'title': title,
            'file': f,
            'rel_path': f"./{f.replace(' ', '%20')}",
            'score': score,
            # ... other fields ...
        }
        
        if title_key in items_by_title:
            existing = items_by_title[title_key]
            # Keep the one with higher score, or longer description if tied
            if score > existing['score'] or \
               (score == existing['score'] and len(description) > len(existing['description'])):
                items_by_title[title_key] = item_data
        else:
            items_by_title[title_key] = item_data
    
    return list(items_by_title.values())
```

## Pattern 3: MOC Entry Extraction and Deduplication

Use to prevent duplicate entries when updating Maps of Content.

```python
def extract_existing_entries(content):
    """Extract all link entries from MOC content (wikilinks + markdown links)"""
    entries = set()
    # Wikilinks
    links = re.findall(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]', content)
    for link in links:
        entries.add(link.strip().lower())
    # Markdown links
    md_links = re.findall(r'\]\(([^)]+)\)', content)
    for link in md_links:
        if not link.startswith('http'):
            clean = link.replace('%20', ' ').lower()
            entries.add(clean)
            # Also add just the filename (basename without .md)
            fname = os.path.basename(clean)
            if fname.endswith('.md'):
                fname = fname.removesuffix('.md')
            entries.add(fname)
    return entries

def deduplicate_moc_content(content):
    """Remove duplicate links from MOC (both wikilinks and markdown links)"""
    lines = content.split('\n')
    seen = set()
    new_lines = []
    
    for line in lines:
        # Check for wikilinks
        match = re.match(r'^(\s*-\s*)\[\[([^\]|]+)(?:\|[^\]]+)?\]\](\s*.*)$', line)
        if match:
            link = match.group(2).strip().lower()
            if link in seen:
                continue
            seen.add(link)
            new_lines.append(line)
            continue
        
        # Check for markdown links
        match = re.match(r'^(\s*-\s*)\[([^\]]+)\]\(([^)]+)\)(\s*.*)$', line)
        if match:
            link = match.group(3).strip().replace('%20', ' ').lower()
            if link in seen:
                continue
            seen.add(link)
            new_lines.append(line)
            continue
        
        new_lines.append(line)
    
    return '\n'.join(new_lines)
```

**CRITICAL**: Always use `f.removesuffix('.md')` NOT `f.replace('.md', '')` to strip extensions. `replace()` removes ALL `.md` occurrences in the string, corrupting filenames like `CLAUDE.md as Runtime Configuration` → `CLAUDE as Runtime Configuration`.

## Pattern 4: Set-Based Frontmatter Link Deduplication

Use in `fix-master-index-links.py` to ensure idempotency.

```python
def fix_frontmatter_links(filepath, folder_filter):
    with open(filepath) as f:
        content = f.read()
    
    fm_match = re.search(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not fm_match:
        return
    
    fm = fm_match.group(1)
    
    # Extract existing links
    links_match = re.search(r'^links:\n((?:\s*-\s*"\[\[.*?\]\]"\n?)+)', fm, re.MULTILINE)
    existing_links = set()
    if links_match:
        existing_links = set(re.findall(r'"\[\[(.*?)\]\]"', links_match.group(1)))
    
    # Get all files in target folder (these are the links we need)
    folder_path = os.path.join(VAULT_DIR, folder_filter)
    needed_links = set()
    for f in os.listdir(folder_path):
        if f.endswith('.md') and not f.startswith('00 -'):
            needed_links.add(f.replace('.md', ''))
    
    # Find missing links
    missing_links = needed_links - existing_links
    
    if not missing_links:
        return  # Already complete - idempotent
    
    # Build new links section with ALL links (existing + new), sorted
    all_links = sorted(existing_links | missing_links)
    links_lines = '\n'.join([f'  - "[[{l}]]]"' for l in all_links])
    new_links_section = f'links:\n{links_lines}'
    
    # Replace in frontmatter
    if links_match:
        new_fm = fm.replace(links_match.group(0), new_links_section)
    else:
        new_fm = fm + '\nlinks:\n' + links_lines
    
    new_content = content.replace(fm, new_fm)
    
    with open(filepath, 'w') as f:
        f.write(new_content)
```

## Pattern 5: YAML Tag Parsing (Fixed Regex)

The broken pattern `\s*-\s*` doesn't match YAML frontmatter format `  - tag`.

```python
# BROKEN:
tags_match = re.search(r'^tags:\n((?:\s*-\s*.+\n?)+)', content, re.MULTILINE)

# FIXED:
tags_match = re.search(r'^tags:\n((?:[-\s]+.+\n?)+)', content, re.MULTILINE)
tags = []
if tags_match:
    tags = [t.strip().strip('-').strip() for t in tags_match.group(1).strip().split('\n') if t.strip()]
```

## Pattern 6: resolve_wikilinks.py Exact Matching

Prevent re-resolution of already-fixed links and false positives from partial matching.

```python
def resolve_link(link, by_title):
    """Resolve a wikilink to actual filename using exact matching only"""
    link_lower = link.lower().strip()
    
    # Direct lookup
    if link_lower in by_title:
        return by_title[link_lower]
    
    # Try with hyphens instead of spaces
    link_hyphenated = link_lower.replace(' ', '-')
    if link_hyphenated in by_title:
        return by_title[link_hyphenated]
    
    # If it already has a timestamp prefix, keep it
    if ' - ' in link:
        title_part = link.split(' - ', 1)[1].lower()
        if title_part in by_title:
            return by_title[title_part]
    
    return None

def fix_file(filepath, by_title):
    # ... 
    for link in links:
        # Skip MOCs
        if 'moc' in link.lower():
            continue
        
        # Skip links that already have timestamps (already resolved)
        if re.match(r'\d{12,14} - ', link):
            continue
        
        actual = resolve_link(link, by_title)
        # ...
```

## Key Insight: Why Duplicates Persisted

The root cause was that each script operated in isolation:
- `stage-1-research.py` created notes without checking other folders
- `update-agent-master-index.py` included ALL files matching a pattern, not deduplicating by title
- `update-mocs.py` appended without checking existing entries
- `fix-master-index-links.py` added links without checking for existing ones

The fix requires each script to be **idempotent**: running it N times produces the same result as running it once. This is achieved by:
1. Checking existing state before adding
2. Using set operations for deduplication
3. Using dict keyed by unique identifier (title) for index entries
