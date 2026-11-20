# 2026-11-20 — Orphan-commit guard names commits stranded on merged PR branches (issue #442)

## What was verified against the spec

- New gate `make check-orphan-commits` (`scripts/check_orphan_commits.py`), wired into the CI guard job in `ci.yml` after `make check-pr-closing`; `package-layers.json` carries the membership + the `check_orphan_commits -> bot_close_reasons` edge (the guard reads merged PRs through `merged_pulls`, so guard and closure report share one merged-PR read).
- Orphan rule proven on a real fixture board (bare origin + clone, PATH-stubbed fake `gh`): post-merge push on the merged PR's branch is named with branch, short sha, subject, PR number and merge time; clean state (tip == merged head), open-PR-covered branch, and ancestor tip all stay silent; a refused `gh` merged-PR read exits non-zero loudly (the #312 loudness rule).
- Squash semantics baked in: commit enumeration excludes patch-landed commits via `git cherry` patch-id equivalence — measured on a cherry-pick stand-in repo (`git patch-id` pair identical, `git cherry` prints `-` once the landing is on origin/main). A `git cherry -x` flag does not exist in git 2.56; the plain verb is the patch-id judgement.
- Live sweep on the real board fired exactly 4 findings (stale `chore/engine-bump-{llama.cpp,ollama,strata,tensorfold}` lane branches, each superseded; the strata patch superseded by PR #2874) — logged in issue #442 with the findings table.
- `tests/test_orphan_commits.py`: green.
- Baseline tolerance (measured wiring defect found pre-push: the gate folded into the `ci.yml` guard job while its 4 live residues were consent-gated — it would have reddened every CI lane, including this PR's own): `data/orphan-baseline.json` records the 4 filed residues as `(branch, merged PR)` pairs; the guard names them `tolerated baseline residue` and exits 0, while any orphan outside the baseline still fails (fixture tests pin tolerated-named, no-shelter-for-a-reused-branch-keyed-to-a-different-PR, and a loud malformed-baseline exit). Branch deletion remains the real cleanup on issue #442.

## Key decisions

- Guard reads branch tips via `git ls-remote` + per-branch `git fetch refs/heads/<b>:refs/remotes/origin/<b>` (the CI guard job already checks out with `fetch-depth: 0`, so `origin/main` is fully reachable).
- `git log --no-merges --format=%H\t%h %s origin/<b> ^<mergedHead> ^origin/main` minus the `git cherry` landed set = the orphan commits.
- Git 2.56 prints "Not a valid commit name" for unfetched shas in `merge-base --is-ancestor`; the ancestor probe treats any failure as not-an-ancestor.
- Branch cleanup (deleting the 4 stale lane branches to give the gate a green baseline) is consent-gated: the consent request timed out 2026-11-20 and issue #442 is labeled `blocked` — the PR lands after owner confirm.

## Current status

Implementation complete on branch `feat/orphan-commit-guard-442` (`9ab23095d`); 8/8 tests green; live sweep green-instrumentation (4 named findings). Blocked on the branch-cleanup consent before push.
