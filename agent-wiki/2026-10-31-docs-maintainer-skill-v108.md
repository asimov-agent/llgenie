# Docs-maintainer lane: version post-#1083 live lessons back into the tree

Versions live→tree drift for the `llgenie-documentation-maintainer` lane that appeared **after** #1083
merged (issue #1165; does **not** close #961 / #1060 — those are closed for this lane and not reopened).

`#1083` (merge `a653cdc`, 09:26Z) shipped the lane's `SOUL.md` + `skills/llgenie-docs-maintainer/`
(v1.0.7) and cleared its drift rows. The live profile then grew again at 11:29:3xZ with lessons learned
from the post-merge runner-congestion episode: `SKILL.md` advanced to **v1.0.8** (+254 b, one lesson:
two identical `Timeout (0:05:00)!` cancellations in `make ci-unit` with sibling jobs green mean a starved
runner, not the diff) and `references/ci-triage-for-docs-prs.md` gained the full
"`~1h ci-unit` cancellation fingerprint" section (+1,985 b). Measured at `origin/main` `c3a0860d`:
tree 44,587 b vs live 44,841 b and 3,795 b vs 5,780 b. Because `make sync-agent-profile` is one-way
(tree→live), the live write can never return to the tree on its own, so `check_agent_profiles.py`
re-reports both files `live-longer` until this PR lands.

Verified live is a clean superset of main for these two files (no tree line is dropped — this is a pure
union). Gating checks at head `483870ce`: `CHECK=1` byte-for-byte, `test_rename_llgenie_serve` +
`test_agent_skills` = 42 passed, `check_docs` 0, module-name guard 0 (the new lesson text never spells
the retired module token).

The recurrence (a live skill that keeps absorbing lessons between clearing PRs) is tracked as #1156 for
the sibling lane; should the docs-maintainer lane ever get a dirty-watch cron that writes the live skill
directly instead of via PR, apply the same fix there.
