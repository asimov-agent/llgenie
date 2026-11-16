# tasks — filer-marker-search-window

- [x] 1. Read the existing `open_issue` mock seam in `tests/test_registry_change_issue.py` and
      extend it with the window-overflow case: >100 open issues, marker-bearing issue ranked past
      position 100 — the filer must report `updated #<n>` and create nothing (test red until the
      lookup changes).
- [x] 2. Replace the bounded `gh issue list --state open --limit 100` scan in
      `scripts/registry_change_issue.py::open_issue` with a body search for the exact marker
      (`gh api search/issues -f q='repo:<repo> "<marker>" in:body state:open'`), failing loudly
      when the search call itself fails (no fall-through to the create path).
- [x] 3. Keep the hit semantics byte-identical in behaviour: REST body update (`_edit_body`,
      #2673), label re-queue when `agent:implement` is missing (#724); keep the create path
      (create once, REST label, no `--label` flag) for the search-miss case.
- [x] 4. Update the existing tests that pinned the old listing call so they pin the search call
      (update tests, not just add new ones); all filer tests pass in the container.
- [x] 5. `make openspec-validate NAME=filer-marker-search-window` exits 0.
- [x] 6. `make test-unit` green at this head.
- [x] 7. agent-wiki entry + `docs/changes.d/` fragment naming #2848, #2847, #2659; `make check-docs` green.
- [x] 8. `make lane-preflight` prints `preflight: OK`.
- [x] 9. Commit (mirrored ticked boxes, `closes #2848` trailer), push, open the PR with the
      mirrored acceptance body; verify live: PR checks and the issue/PR/commit mirrors agree.
