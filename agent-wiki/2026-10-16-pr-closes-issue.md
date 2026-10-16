# A PR closes the issue it implements — the closing rule loses its loophole (#324)

Implemented by PR [#328](https://github.com/asimov-agent/llgenie/pull/328) (issue #324).

## Why

`AGENTS.md` stated the closing requirement with an escape hatch — "If the PR does not close an issue,
still end with the issue reference so the PR ↔ issue link is never ambiguous" — which reads as
permission to ship a PR that implements an issue without closing it. Measured on `main` (`4d999e3`),
**13 of the last 38 merged PRs carried no closing reference at all**
(`gh pr view <n> --json closingIssuesReferences` → empty): `#258`, `#290`, `#266`, `#274`, `#268`,
`#284`, `#283`, `#282`, `#280`, `#278`, `#267`, `#259`, `#255`.

Two of those are the sharp cases:

- **#290** implemented the fix-bot half of issue **#279** and closed nothing — #279 is still `OPEN`,
  its remaining half described only in prose inside the PR body.
- **#321** was **closed by hand** at `2026-10-16T02:47:40Z` with **no implementing PR** — and the
  defect it names still reproduces on the current tip: run `38841759439` on `4d999e33`, `failure`,
  **0 jobs**. An issue closed with no PR reads as "done" while the defect it names is still live.

That is exactly what this repo's issue → branch → OpenSpec → PR pipeline exists to prevent: the issue
is the root, and an issue's state must stay evidence about the code.

## What landed

- **`AGENTS.md`** — the closing rule loses the loophole and states its three cases: a PR that
  implements an issue MUST close it (`closes #<n>`); a PR that implements only PART of an issue MUST
  NOT close it and MUST name what remains as its own linked work item; a PR that implements no issue
  says so. The "still end with the issue reference" sentence — the loophole — is gone. A second
  sentence forbids closing an issue by hand while a PR implements it.
- **`scripts/check_pr_hygiene.py`** — the mandate is split into two named required texts:
  `AGENTS_MANDATE` (the message heading) and `AGENTS_CLOSING_RULE` (the closing rule). `check_agents_mandate`
  now asserts each on its own and reports each as its own finding key, so a deleted closing rule is
  `agents-closing-rule/agents-md` — a red `ci-unit` with its own message, not a silent edit.
- **`tests/test_pr_hygiene.py`** — three new cases: a fixture `AGENTS.md` with the mandate but not the
  closing rule fails with `agents-closing-rule` and NOT `agents-mandate`; the baseline (both present)
  reports neither; and this repo's `AGENTS.md` carries the closing rule verbatim. **16 passed** (was 13).

## Verification

- `python3 scripts/check_pr_hygiene.py check` on this tree: **0 violations**. Against the PRE-FIX
  `AGENTS.md` (`git show origin/main:AGENTS.md`): **exactly one** finding —
  `agents-closing-rule/agents-md` — so the guard fires on the real regression it exists to catch.
- `tests/test_pr_hygiene.py`: **16 passed** in `llgenie/test:latest`
  (`docker run --rm -v "$PWD":/repo:ro … -m pytest tests/test_pr_hygiene.py --noconftest`).
- `make lint`, `make check-pr-hygiene`, `make check-docs`, `make check-wiring`,
  `make check-secret-output`, `make openspec-validate NAME=pr-closes-issue`.

## Note

The guard reads the repo's own files, so it catches a *missing rule* — it cannot see whether a merged
PR *did* close its issue, which is only visible through the API. That is a separate work item,
**#325**, named in the PR's `Not covered` rather than described in prose here.
