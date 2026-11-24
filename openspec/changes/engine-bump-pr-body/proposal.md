# ci: the engine-bump lane renders its PR body through one seam that the PR gates accept

Issue: [#3050](https://github.com/asimov-agent/llgenie/issues/3050)

## Why

The 2026-11-23 engine-bump wave opened 7 PRs and all 7 are structurally red: `guard` fails at
`make check-pr-openspec-change` (mk/gates.mk:139) and `scope` fails at `make check-pr-acceptance-form`
(mk/gates.mk:142), so all 7 sit at `mergeStateStatus=BLOCKED` and `ci-verdict` reddens 7/7.

The root cause is one line of inline bash in `.github/workflows/engine-bump.yml`:

```bash
body="$(printf '%b' "${body}" '\n')$(cat params-review-section.md)"
```

Command substitution strips TRAILING newlines. Measured on the live body of PR #3030 (head `20b3f030`):

```
OPENSPEC: publish-changed-pin-images## Documentation review
```

`OPENSPEC_REF` in `scripts/check_pr_hygiene.py` is `^OPENSPEC:\s+([A-Za-z0-9_-]+)\s*$`. A change name with
a heading glued after it matches nothing, so the gate reported "names no existing change" although
`openspec/changes/publish-changed-pin-images/` is ACTIVE on `main` — the triage read it as a missing change
(see the corrected `Acceptance criteria` in #3050). The same bodies carried no `## Acceptance criteria` at
all, so `scope` redded on the same 7/7, and their commit messages carried no ticked mirror for
`make check-pr-commit-checkboxes` (mk/gates.mk:135, issue #2519).

## What Changes

- **New composer seam:** `scripts/engine_bump_pr_body.py` + `make engine-bump-pr-body` become the ONE
  composer of the engine-bump PR body and of its commit-text acceptance mirror. Sections are joined by
  blank lines through a list; no section is ever concatenated to another one's trailing whitespace, and the
  `OPENSPEC:` line is emitted last with nothing after the change name.
- **The workflow composes nothing:** the bump lane's "Open / update the bump PR" step calls the make target
  (`ENGINE/REF/OLD/NEW/RUN/AUTHOR/REPO_SLUG/REVIEW_FILE/HARD_FAIL/DEPS/OUT/COMMIT_OUT`) and feeds
  `/tmp/pr-body.md` to `make bot-stamp-body` / `make bot-body-write` / `gh pr create --body-file` as before.
  The inline `printf`/`$(cat …)` composition is gone and a test forbids it from coming back.
- **The body carries `## Acceptance criteria`** with one `- [x]` per provable outcome, each clause in a
  form `scripts/check_pr_acceptance.py::_is_provable_tick` accepts (the lane's own `gh run` id plus the
  make commands it ran), so `check-pr-acceptance-form` is green and the self-tick audit (#745) stays green.
- **The commit message mirrors the ticks:** the same block is written under `## Acceptance:` and passed as
  a third `-m` paragraph to `git commit`, so the squash text that lands on `main` mirrors the body
  (`check-pr-commit-checkboxes`, issue #2519).
- **The gate names the shape it saw:** `check-pr-openspec-change` now distinguishes an `OPENSPEC:` line that
  does not parse, a line naming a change that is not ACTIVE, and no line at all — the generic hint sent the
  producer down the wrong path when the line was already there.

## Impact

- `scripts/engine_bump_pr_body.py` (new), `mk/engines.mk` (`engine-bump-pr-body` target),
  `.github/workflows/engine-bump.yml` (bump job's PR step), `scripts/check_pr_hygiene.py`
  (`openspec_change_findings` detail), `tests/test_engine_bump_pr_body.py` (rewritten to the new seam),
  `tests/test_pr_hygiene.py` (the three gate-detail shapes).
- No schedule, no new dispatch trigger, no gate added: this is the producer side of gates that already run.
- Not covered (filed as its own issue): the live read that the NEXT engine-bump wave's PRs show `guard` and
  `scope` green at their heads — it can only be measured after this lands on `main` and the weekly lane runs.
