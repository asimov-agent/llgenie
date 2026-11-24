# 2026-11-24 — issue pointers: `## Not covered` names its issue as a full URL (issue #3055)

## What was verified against the issue

- The hold was measured on a landed lane, not inferred: #3053's PR body carried its deferral as
  `"Not covered" … (#3050)` and `make check-pr-acceptance` answered `scope: fail` with the rollout-lane
  finding — `#3050` was OPEN and cited #3053 back, so the umbrella's own `closes #3050` was held by its
  own out-of-scope list. `scripts/check_pr_acceptance.py::rollout_lane_findings` reads a bare `#<n>` in
  the umbrella body as a lane candidate; a full issue URL is not one.
- The producers that spell pointers bare were enumerated before fixing them: `make check-issue-bodies`
  reports `scripts/registry_change_issue.py:243` `(#669)` and `:321` `(#3013)` inside `not_covered=[`,
  and `scripts/architecture_bot.py:556` documents `(#NNNN)` as the form to use.
- `scripts/issue_body.py` now spells the tracker once (`ISSUE_URL_BASE`, `issue_url(n)`) and
  `link_issue_cites(text)` rewrites a bare `#<n>` to `<base>/issues/<n>` **only in prose**: fenced blocks,
  inline `code`, `file.py#L105`-style anchors, and numbers the text already names as an issue URL are left
  exactly as written. `render` routes its `not_covered` bullets through it (`_link_bullets`), so every
  producer that defers behaviour gets the URL form for free; the other five sections keep their cites as
  prose, because a cite in `## Problem` names a fact, not a lane.
- `pointer_findings(text)` reports a `## Not covered` bullet that still carries a bare cite, which is what
  lets a body be checked without a hand-built regex at each call site; `missing()` now includes it, so a
  body that bypasses the renderer is a shape finding on its own.
- Gate side (`scripts/check_issue_body.py`): each producer's `not_covered=` region is scanned at source
  level (the spelling the producer writes, not just its output) and the renderer is self-probed —
  `_pointer_probe_body()` must come out with the URL form and `pointer_findings` empty, and a probe whose
  deferral stays bare must be reported. Today every producer is GREEN because the renderer links; the
  bypass (`_link_bullets` replaced by verbatim bullets) reddens with BOTH the renderer file and the
  producer that spelled the pointer named.

## Decisions

- The pointer rule is section-scoped. Linkifying every cite in every section would rewrite quoted gate
  wording (`Not covered: bare cites hold the close (#1234)`) and measured evidence, which is exactly what
  AGENTS.md's "an issue's numbers name the commit they were measured on" asks bodies to keep verbatim.
- An already-linked pointer is not rewritten again: `… /issues/3056 (issue #3056)` stays readable instead
  of nesting a link inside a link (found while writing the tests, measured against the pre-fix renderer).
- The gate reads producer SOURCE, not only rendered output: a producer that composes its own bullets and
  splices them into a rendered body would otherwise pass an output-only check.
- `tests/test_registry_change_issue.py` was UPDATED, not duplicated: it now asserts the URL form for its
  `(#669)` deferral and that `pointer_findings` is clean on the rendered report.

## Current status

OpenSpec change `umbrella-cite-renderer` validated (`make openspec-validate` rc=0); `make
check-issue-bodies` rc=0 and `make check-pr-hygiene` rc=0 at the lane head; 285 tests green across
`tests/test_issue_url_rendering.py` (new), `test_issue_body.py`, `test_check_issue_body.py`,
`test_check_pr_acceptance.py`, `test_registry_change_issue.py` and the adjacent issue/PR-gate suites,
inside the full `make test-unit` battery. Branch `feat/umbrella-cite-renderer`, PR #<PR> closes #3055.
No workflow file changed; no pipeline was started, rerun, or cancelled by this change.
