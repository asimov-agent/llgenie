# CI Pipeline Scripts Reference

## scripts/ci/ci-pipeline.py

Main orchestrator. Runs all 9 stages sequentially and exits with code 1 if any fail.

```bash
python3 scripts/ci/ci-pipeline.py
```

## scripts/ci/validate-links.py

Validates ALL link formats — body `[[wikilinks]]`, frontmatter `links:`, and body markdown links `[text](path)`.

**Markdown links resolve file-relative (GitHub semantics):** `os.path.normpath(os.path.join(os.path.dirname(filepath), unquote(link)))`. Never resolve against the vault root — that mirrors the writer's bug and stays green while GitHub shows red.

**Pitfalls:**
- Strip code fences (`re.sub(r'```.*?```', '', content, flags=re.DOTALL)`) before scanning — fenced links are examples, not links.
- Use `removesuffix('.md')` when building the file map, never `replace('.md', '')` — `replace` eats every `.md` in a filename (e.g. a note titled `CLAUDE.md as Runtime Config...`).
- The file map must include folder aliases for index files, otherwise links to `[[03 - Agents/]]` fail.

## scripts/ci/validate-frontmatter.py

Validates frontmatter structure (id, created, tags fields) and detects duplicate links within a single file.

## scripts/ci/validate-duplicates.py

Detects duplicate files with the same title in the same folder. Case-insensitive comparison.

## scripts/ci/validate-tags.py

Validates tags against an allowed vocabulary. Tags that are wikilinks (`[[...]]`) or MOC references are skipped.

**Pitfall:** The tag parser must use line-by-line parsing, not greedy regex. Greedy regex consumes the `links:` section into the tags list.

## scripts/ci/validate-index-completeness.py

Validates that every non-index note in each folder appears in that folder's MOC.

## scripts/ci/validate-orphans.py

**CRITICAL:** This script FAILS the pipeline (exit 1) when orphan notes are detected. It does not just warn.

An orphan is a note that is not:
1. Linked from any other note's body as a wikilink
2. Linked from any other note's frontmatter links
3. Indexed in a MOC

**Skip patterns:** `00 -` (indexes), `MOC-` (MOCs), `AGENTS.md`, `README.md`, `LICENSE`, scripts, templates.

## scripts/ci/validate-templates.py

Validates that template files (`.obsidian/templates/*.md`) have required sections like `## Overview` and `## Sources`.

## scripts/ci/validate-formatting.py

Validates:
- No trailing whitespace on lines
- No multiple consecutive blank lines
- Proper heading hierarchy (no jumps from `#` to `###`)

Skips template files (they contain placeholder syntax).

## scripts/ci/fix-pipeline-issues.py

Auto-fixes common issues:
- Deduplicates frontmatter links
- Deduplicates MOC entries
- Deduplicates table rows in index files

**Limitation:** Cannot fix orphans or broken wikilinks automatically — these require human judgment.

## scripts/ci/validate-link-quality.py

Stage 9. Fails when any `[[wikilink]]` remains (frontmatter `links:` must be markdown `[title](path)`) or any markdown link resolves to a missing file (file-relative, GitHub semantics). Also strips code fences before scanning.

## scripts/ci/fix-links-relative.py

Rewrites legacy vault-root-relative markdown links to correct file-relative paths: keeps links that already resolve from the containing file's directory, rewrites ones that only resolve from the vault root (to `../dir/file.md`, `%20`-encoded), leaves truly missing targets for the validators to report. Idempotent; skips code fences and AGENTS.md example links.

**Usage after changing generator scripts:** delete the generated artifacts (Master Indexes, MOCs), regenerate them, then run this — 0 rewrites proves the generators emit correct paths natively.
