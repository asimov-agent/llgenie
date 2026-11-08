# docs/ARCHITECTURE.md refresh for the tree at 20261107T2222 (PR #2053)

## What was verified

- `docs/ARCHITECTURE.md` was re-derived from real `git` state at `cb6c56a9` (main tip that this
  branch bases from) by the architecture bot (`make architecture-bot-brief` -> `make
  architecture-bot-doc` -> `make architecture-bot-publish`).
- The document lagged the tree — last updated at `171b4fe76676`, with 1 commit and 8 changed path(s)
  since — so it did not describe the code a reviewer was reading. Only `docs/ARCHITECTURE.md` is
  committed here; the drift record lives in the PR body.
- A live refresh makes the next 6-hour architecture run quiet until the tree moves again: a stale doc
  is re-derived, not hand-patched, so the census numbers in `check-architecture-census` keep agreeing
  with the tree (`git ls-tree -r --name-only <sha>` counts the commit the document names).

## What is at stake

A stale architecture document is a false referent: a reviewer reads a map that does not match the
code. Keeping the document's census in lockstep with the tree is what `make check-architecture-census`
(enforced in `check-docs`, issues #896, #1053) is for.

## Index

- Issue: #2052 (the refresh this PR implements)
- PR: #2053
