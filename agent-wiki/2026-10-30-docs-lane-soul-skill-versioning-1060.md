# 2026-10-30 — issue #1060: version the documentation lane's SOUL and llgenie-docs-maintainer skill

## What

The documentation-maintainer lane's behaviour lived only on the host: `agents/llgenie-documentation-maintainer/`
on `main` was a `SOUL.md` that was 12,416 b against a live 14,665 b, and the `llgenie-docs-maintainer`
skill existed nowhere in the repo. Behaviour that lives only on the host is unreviewable — there is no
diff to read when it misbehaves.

## The change

- `agents/llgenie-documentation-maintainer/SOUL.md` → the live copy (adds the `#1010` Fleet-orchestration
  contract block — the single insertion hunk; live is newer, zero deletions).
- `agents/llgenie-documentation-maintainer/skills/llgenie-docs-maintainer/` → the lane skill, now versioned
  (SKILL.md + `references/agents-soul-tree.md` + `references/ci-triage-for-docs-prs.md` +
  `scripts/docs_audit.py`).

Direction judged on content, not copied blindly: the repo→live diff was one insertion after line 103,
zero deletions, and nothing the repo held was absent from live — so live is the source for that hunk.

## The record

`make check-agent-profiles` reduces findings 18 → 17: this clears `live-longer
llgenie-documentation-maintainer/SOUL.md` (tree 12,416 vs live 14,665). The remaining `UNPROTECTED`
finding is deliberate and pre-exists: the manifest declares `rules: []` for this lane because it holds
the docs-merge grant and does not declare `never-merge`.

Issue: #1060

## Verification (recorded at the PR head)

```
make sync-agent-profile PROFILE=llgenie-documentation-maintainer CHECK=1
[agent-profile] OK: 5 file(s) of agents/llgenie-documentation-maintainer match … byte for byte   → exit 0
make lint / check-docs / check-wiring                                             → exit 0
python -m pytest tests/test_agent_profiles.py                                     → 104 passed
```
