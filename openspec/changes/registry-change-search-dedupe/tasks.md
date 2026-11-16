# Tasks — registry-change-search-dedupe

- [x] 1. `scripts/registry_change_issue.py::open_issue` resolves the marker through GitHub issue
      search (`gh api search/issues -f q='repo:"<slug>" "registry-sync-changes: <utc>" in:body
      state:open'`) instead of the truncated `issue list --state open --limit 100` listing; the
      hit still body-updates over REST PATCH (#2673) and re-labels via REST (#724); only a search
      miss creates (#704). The create path scopes `--repo <slug>` explicitly.
- [x] 2. `tests/test_registry_change_issue.py`: the `_Gh` fake answers the `search/issues`
      endpoint (whole-board match, decoupled from any window); a new test proves a marker-bearing
      issue ranked past the 100-issue open window is UPDATED, not duplicated; the two dry-run tests
      allow only the read-only marker search (no PATCH/POST/create/edit).
- [x] 3. Docs in the same commit as the change: `agent-wiki/2026-11-16-registry-change-search-dedupe-2847.md`
      (names the issue and PR, references #2659/#2847/#2849/#2673/#724/#704) and
      `docs/changes.d/2026-11-16-registry-change-search-dedupe-2847.md`; `make changes-index`
      re-renders CHANGES.md.
- [x] 4. Verification (tick only with rc=0 evidence): `python3 -m pytest tests/test_registry_change_issue.py -q`
      (11/11 rc=0), `make test-unit` rc=0, `make check-wiring` rc=0, `make check-docs` rc=0, and
      `make lane-preflight` prints `preflight: OK` at this head (result recorded in the PR body).
      The openspec change could not be `make openspec-validate`d here because the agent container
      has no Docker daemon and no node install; it mirrors the repo's reference OpenSpec change
      structure and is validated by the `ci-openspec` job in the real pipeline.
