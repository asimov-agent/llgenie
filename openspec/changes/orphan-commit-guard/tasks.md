# Tasks — orphan-commit-guard

- [x] 1. `scripts/check_orphan_commits.py`: merged-PR map via `scripts/bot_close_reasons.merged_pulls` (the board's single merged-PR read), open-PR map, branch tips via `git ls-remote --heads origin`; orphan rule per spec; report lines name branch/sha/PR; non-zero exit on any orphan; refused gh read fails LOUDLY (never a silent pass)
- [x] 2. `mk/gates.mk`: `check-orphan-commits` target (host-runnable `python3 scripts/check_orphan_commits.py`, `##` docstring)
- [x] 3. `.github/workflows/ci.yml` guard job: `make check-orphan-commits` step (runs on PR lanes and push-to-main)
- [x] 4. `scripts/package-layers.json`: group membership for the new script + the cross-group edge to `bot_close_reasons`
- [x] 5. `tests/test_orphan_commits.py`: real local git repo fixture (bare origin + clone, merged-PR shape, post-merge commit) + fake-gh stub; pins the spec scenarios + loud gh refusal + the squash-landed `git cherry` exclusion
- [x] 6. Targeted pytest green (`tests/test_orphan_commits.py`, 8 passed rc=0) and live proof: `make check-orphan-commits` against the real board named exactly 4 stale engine-bump residues (recorded on issue #442; cleanup consent-gated)
- [x] 7. `make openspec-validate NAME=orphan-commit-guard` exits 0
- [x] 8. Commit text mirrors the issue AC block (seven ticked mirror lines); `make lint`/`check-wiring`/`check-docs`/`changes-index` green at this head
- [x] 9. Baseline tolerance (measured wiring defect: the guard was folded into `ci.yml` while its 4 live residues were consent-gated, which would redden every CI lane): `data/orphan-baseline.json` records the filed residues as (branch, merged PR) pairs, `--baseline` flag; baseline residues named-yet-tolerated, new orphans still fail; new fixture tests green; live `make check-orphan-commits` at this head exits 0 naming the 4 as tolerated; spec + proposal + issue body updated in the same commit
