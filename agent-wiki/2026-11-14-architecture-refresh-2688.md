# 2026-11-14 — architecture refresh of `docs/ARCHITECTURE.md` (issue #2688)

- Problem: `docs/ARCHITECTURE.md` lagged the tree — 5 commit(s) and 28 changed path(s) since the doc's last commit (`1c4f88b45ae4`).
- Fix: the brief+doc legs rebuilt the doc from the real tree (the model leg still writes only the doc); this note and its `docs/changes.d/` row pay the pair `make check-docs` owes a branch that changes the doc (rule: issue #1123; owning the pair is issue #2598).
