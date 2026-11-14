# 2026-11-14 — architecture refresh of `docs/ARCHITECTURE.md` (issue #2681)

- Problem: `docs/ARCHITECTURE.md` lagged the tree — 2 commit(s) and 23 changed path(s) since the doc's last commit (`e7af36f7e8df`).
- Fix: the brief+doc legs rebuilt the doc from the real tree (the model leg still writes only the doc); this note and its `docs/changes.d/` row pay the pair `make check-docs` owes a branch that changes the doc (rule: issue #1123; owning the pair is issue #2598).
