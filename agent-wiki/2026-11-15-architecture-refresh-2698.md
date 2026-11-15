# 2026-11-15 — architecture refresh of `docs/ARCHITECTURE.md` (issue #2698)

- Problem: `docs/ARCHITECTURE.md` lagged the tree — 0 commit(s) and 0 changed path(s) since the doc's last commit (`d43b1df8b496`).
- Fix: the brief+doc legs rebuilt the doc from the real tree (the model leg still writes only the doc); this note and its `docs/changes.d/` row pay the pair `make check-docs` owes a branch that changes the doc (rule: issue #1123; owning the pair is issue #2598).
