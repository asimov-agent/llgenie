---
title: Docs-maintainer change-note audit: fold the locate-by-issue-number lesson live→tree (own-domain-audit)
date: 2026-11-05
issue: 1794
---

# Fold the change-note audit "locate by issue number, never by guessed stem" lesson (own-domain-audit.md)

The documentation-maintainer lane's `references/own-domain-audit.md` (§Check 3 — change-note coverage)
gained a live-only correction to its audit procedure: when verifying a merged change's
note/fragment/index trio, **enumerate the real fragment names — do not guess the slug from the PR
title.** Fragment filenames are `<date>-<their-slug>-<issue>.md` and the slug is authored, not derived
from the title, so `grep '<title-derived-stem>'` returns nothing for a fragment that exists and reads
a false `MISSING`.

The fix: match on the **trailing issue number** (`git ls-tree ... docs/changes.d/ | grep -- '-<issue>\.md$'`,
`agent-wiki/ | grep -- '-<issue>\b'`, `CHANGES.md | grep -- '-<issue>'`), which is stable across slug
renames. The gate is the source of truth — run `python3 scripts/check_docs.py check` at the tip and
expect rc=0 with a `fragments == notes` count. If a per-merge grep says `MISSING` but the gate is
green, the grep was wrong (a guessed slug), not a real gap; never file a change-note finding off an
invented stem, because a genuine gap makes the gate itself red.

This fold brings the tree copy of `own-domain-audit.md` byte-identically up to the live file
(4304 b, blob `72bfcd19`) — the tree was the truncated copy (3574 b), and per #791/#1060 the fix is
live→tree, never a tree→live write-mode sync (which would shrink the live file).
