# CI Pipeline Fix Workflow

When the AI Matrix Trends CI pipeline is red, follow this systematic process to diagnose and fix issues.

## Diagnosis Steps

1. **Run locally**: `python3 scripts/ci/ci-pipeline.py 2>&1 | tail -50`
2. **Identify failing stage**: Look for `✗ Stage N: ... FAILED`
3. **Read the stage's script**: `cat scripts/ci/validate-<stage>.py`
4. **Run stage individually**: `python3 scripts/ci/validate-<stage>.py`

## Stage-Specific Fixes

### Stage 1: Link Validation (validate-links.py)
- **Symptom**: `Wikilink (body): [[title]] -> NOT FOUND` or `Markdown link: path -> NOT FOUND`
- **Fix**: Check frontmatter uses `[title](./path.md)` format. Check body uses markdown links, not `[[wikilinks]]`.
- **Common cause**: New notes created by `create_note()` with short-name wikilinks or broken markdown links.

### Stage 4: Tag Validation (validate-tags.py)
- **Symptom**: `Invalid tag: <tag>`
- **Fix**: Add the tag to `VALID_TAGS` in `validate-tags.py`. The parser already skips markdown links (`[text](path)`) and quoted wikilinks.
- **Common cause**: New plugins use domain-specific tags (e.g., `vector-database`, `project-management`) not in the controlled vocabulary.

### Stage 8: Markdown Formatting (validate-formatting.py)
- **Symptom**: `Trailing whitespace on line N`
- **Fix**: Strip trailing whitespace. Check `create_note()` doesn't add ` ` after `-` in Sources section.
- **Rule**: End files with `## Sources\n-` (no trailing space, no extra newline).

### Stage 9: Link Quality (validate-link-quality.py)
- **Symptom**: `Wikilink: [[title]] (should be markdown: [title](./path.md))`
- **Fix**: Body sections (`## Related`, `## Compatibility`) must use markdown links. Frontmatter `links:` with `[[wikilinks]]` is OK — validator strips frontmatter.
- **Common cause**: `create_note()` body uses `[[wikilinks]]` instead of `[text](./path)`.

### Stage 10: README Completeness (validate-readme-completeness.py)
- **Symptom**: `Broken: ./202609202065 - Factory Code.md` or missing from tables
- **Fix**: New agents must be added to `update_readme.py`'s `extended_agents` list with full file paths.
- **Rule**: README Agent Tools table must list ALL agents with correct `./03%20-%20Agents/` prefix.

## Prevention Rules

When creating new notes via `create_note()` in `stage-1-research.py`:
- Tags must be from `VALID_TAGS` (expand if needed)
- Body links must be markdown: `[text](./path.md)`
- No trailing whitespace on any line
- Frontmatter `links:` uses Obsidian `[[wikilinks]]` (safe — validator skips frontmatter)

## Full Fix Cycle

```bash

# 1. Run CI
python3 scripts/ci/ci-pipeline.py

# 2. Fix issues (examples)

# Tags: edit scripts/ci/validate-tags.py -> VALID_TAGS

# Body links: edit stage-1-research.py -> create_note() uses markdown

# Formatting: edit stage-1-research.py -> remove trailing space after '-'

# README: edit scripts/update_readme.py -> extended_agents list

# 3. Re-run stages 3-4 to regenerate indexes
cd scripts && python3 stage-3-scoring.py && python3 stage-4-indexes.py

# 4. Verify CI green
python3 scripts/ci/ci-pipeline.py

# 5. Commit and push
git add -A && git commit -m 'Fix CI: ...' && git push
```
