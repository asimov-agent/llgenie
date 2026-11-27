# Tasks — head-stable acceptance provenance (#3108)

- [x] Add an ancestor-aware head resolution helper to `scripts/check_pr_acceptance.py` (exact match or `git merge-base --is-ancestor`; unresolvable/non-commit stays stale).
- [x] Apply the helper to both stale-head paths (run-cited green-head path and command+rc+sha path) without weakening run-conclusion checks.
- [x] Add regression tests: ancestor proof clean; unrelated sibling red; unresolved/non-commit red; ancestor with red run still red.
- [x] Add `agent-wiki/<stem>.md` + one-row `docs/changes.d/<stem>.md` + regenerated `CHANGES.md` row (#1123), using `$HOME` not a literal home path (#2145).
- [x] `make openspec-validate NAME=acceptance-provenance-ancestor-3108`, `make -s check-docs` and the focused unit tests exit 0 at the pushed head with AGENTS/BASE stamps and allowlisted author.
