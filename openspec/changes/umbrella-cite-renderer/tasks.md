# Tasks: umbrella-cite-renderer

- [x] 1. `scripts/issue_body.py`: `ISSUE_URL_BASE`, `issue_url(n)`, `link_issue_cites(text)` (skip fenced code, inline code, line anchors, existing URLs) and route `not_covered` bullets through it via `_link_bullets`; `pointer_findings(text)` + `missing()` report a bare pointer in a body that bypassed the renderer.
      (proven: `pytest tests/test_issue_url_rendering.py` rc=0)
- [x] 2. `scripts/check_issue_body.py`: producer `not_covered`-region probe at source level + renderer self-probe assertion; a surviving bare `#<n>` is a finding naming the producer file.
      (proven: `make check-issue-bodies` rc=0 on the tree the PR carries; `pytest tests/test_check_issue_body.py` rc=0)
- [x] 3. `scripts/check_pr_acceptance.py`: `rollout-lane-open` evidence names the bare-`#<n>` pointer form and the full-issue-URL remedy.
      (proven: `pytest tests/test_check_pr_acceptance.py` rc=0)
- [x] 4. Tests: `tests/test_issue_url_rendering.py` (bare cite → URL, cites outside `## Not covered` untouched, already-linked pointer unchanged, code/fence cites bare, `pointer_findings` scope, quoted gate wording safe), `tests/test_issue_body.py` (marker first, every `Not covered` bullet linked), `tests/test_check_issue_body.py` (registry producer probe GREEN today; a normalizer bypass REDs with the producer AND the renderer named), `tests/test_check_pr_acceptance.py` (a URL pointer does not hold the close; the finding carries the remedy), `tests/test_registry_change_issue.py` updated to the URL shape — targeted pytest rc=0.
      (proven: `pytest` on those files rc=0, 285 passed)
- [x] 5. `make check-issue-bodies`, `make check-pr-hygiene` and `make openspec-validate NAME=umbrella-cite-renderer` exit 0 on the tree the PR carries.
      (proven: each rc=0 on the committed tree, recorded in `make lane-preflight` → `preflight: OK`)
- [x] 6. Docs trio (agent-wiki entry + `docs/changes.d` fragment) with `make changes-index` and `make check-docs` rc=0 on that same tree.
      (proven: `make changes-index` rc=0 (963 fragments), `make check-docs` rc=0)
