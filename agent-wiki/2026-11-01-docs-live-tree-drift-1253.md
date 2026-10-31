# Version the docs-maintainer live->tree drift (#1253)

**Issue:** #1253 · **PR:** this PR (docs/1253-live-tree-drift) · **base** main `1db367a`

## Why

Fleet-wide SOUL/skill reload directive (owner) surfaced a host-vs-repo gap on the
`llgenie-documentation-maintainer` lane, measured at `main` `1db367a`: the **live** profile was
richer and cleaner than the tree copy on three files, and the **tree** `SOUL.md` Mission line was a
garbled downgrade:

| file | tree | live | judge |
|---|---|---|---|
| `SOUL.md` | 15,200 b | 15,254 b | live better — tree Mission line garbled (`"…even implement it it told to do it"`) vs live's crisp docs-only scope |
| `SKILL.md` | 61,064 b | 63,197 b | live superset (+19 lines): `Role artifact (2026-11-01)` + refined #964 `autoMergeRequest` null-read-back = already-completed lesson |
| `references/docs-freshness.md` | 2,023 b | 4,026 b | live superset (+25 lines): `RED gate on main` census-blocker classification (#1246 class) |

The other four member files (`agents-soul-tree.md`, `ci-triage-for-docs-prs.md`, `live-vs-tree-drift.md`,
`docs_audit.py`) were already byte-identical.

Per **#791** and `#919` ("the sync cannot shrink one"), a write-mode tree→live copy would have
truncated the live lessons and enshrined the garbled Mission — prohibited. The compliant route is to
**version live→tree** (the `#1239`/`#1234` pattern), which this PR does.

## Change

- `agents/llgenie-documentation-maintainer/SOUL.md` — adopt the live Mission (fixes the tree garble).
- `agents/llgenie-documentation-maintainer/skills/llgenie-docs-maintainer/SKILL.md` — gain the
  `Role artifact (2026-11-01)` section + refined #964 lesson.
- `.../references/docs-freshness.md` — gain the RED-gate-on-main census lesson.
- All three byte-identical live→tree (`cmp` verified); `docs/changes.d` fragment + `agent-wiki/` note incl.

## Acceptance (from #1253)

- [ ] the three files are byte-identical to live (`cmp`).
- [ ] no live content was truncated during reconciliation (this lane makes no private edit; the PR is the change).
- [ ] `make check-docs` exit 0 on this head and on a merge-tree onto `1db367a`; census referent unchanged.
- [ ] after merge, `make sync-agent-profile PROFILE=llgenie-documentation-maintainer CHECK=1` is green.
