# Version the docs-maintainer docs-freshness ownership + sync live→tree skill drift (#1239)

## What shipped

Versioned the documentation-maintainer lane's new owner remit and its behavior, and fixed the lane's
own live→tree skill drift, into the tree:

- **New reference** `agents/llgenie-documentation-maintainer/skills/llgenie-docs-maintainer/references/docs-freshness.md`
  — the lane owns README.md + `docs/` + every user-facing doc/manpage target against the tree
  (`make check-docs`, Makefile:987); a 30-min change monitor that reads `main` and answers "does any
  user-facing doc/README need an update?" before other work, with a per-merge checklist; and the
  never-private-edit rule (refinements versioned under `agents/llgenie-documentation-maintainer/` via
  issue + PR, #791 pattern).
- **SKILL.md linked to it** and live→tree byte-identical sync of the lane's own skill drift:
  SKILL.md 54,513 → 60,769 b (folds the `autoMergeRequest`-has-no-`enabled`-boolean and other
  live-only lessons); refs/script already identical (live authoritative per #791).

## Evidence (measured at PR head)

```
git diff origin/main:agents/llgenie-documentation-maintainer/skills/llgenie-docs-maintainer/SKILL.md
     ~/.hermes/profiles/llgenie-documentation-maintainer/skills/llgenie-docs-maintainer/SKILL.md = EMPTY
make check-docs (change-note gate #1123)  = exit 0
```

Direction live→tree for the drift copy (live authoritative, #791); the new freshness reference is
tree-authored and mirrored tree→live so `make sync-agent-profile CHECK=1` stays green.

## Acceptance

- [ ] Live→tree skill drift byte-identical at head (SKILL.md 60,769 b; refs/script identical).
- [ ] New `references/docs-freshness.md` present + SKILL.md links it (versioned #1239).
- [ ] Tree→live mirror done; note + fragment pass `make check-docs` change-note gate.
- [ ] One PR; never merged by the implementing lane.
