## Fold report — round-12 (SKILL + versioning)

`make tester-fold-live PROFILE=llgenie-tester COPY=1` → rc 0.

### Fold table

| file | before (main) | after (live→tree) | delta |
|------|--------------|-------------------|-------|
| skills/llgenie-pr-testing/SKILL.md | `2177a2b5` (98,431 B) | `8bce37e2` (100,211 B) | +1,780 B |
| skills/llgenie-pr-testing/references/agent-profile-versioning.md | `d939d6f1` (25,603 B) | `34560cfd` (26,493 B) | +890 B |

### #1273 byte-identical

- SKILL.md: tree `8bce37e2` == live `8bce37e2` (same, 100,211 B)
- agent-profile-versioning.md: tree `34560cfd` == live `34560cfd` (same, 26,493 B)

### Gate evidence (head)

check-wiring 0 · changes-index 0 · check-docs 0 · census 0 · lint_linefeeds 0 ·
agent_profile_sync --check 0 · report-hygiene 0.

Closes **#1332** (literal `Closes #N` keyword in the PR body).
