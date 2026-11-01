## agents(llgenie-tester): round-10 live fold — #1327

**AGENTS:** branched fresh from `origin/main` @ `c3ead71d` (fetched to confirm, then re-checked the tip
moved — this PR's base is the fetched fresh main).

### Fold content (live→tree, planner-dispatched round-10)

Measured at branch time off fresh `origin/main`, copied via the wired `make tester-fold-live
PROFILE=llgenie-tester COPY=1` (rc 0, `5 same / 2 drifted / 0 mid-write`):

| file | live sha | vs main | note |
|------|----------|---------|------|
| SKILL.md | `770d355` | +1,901 B | two in-review lesson-blocks folded live this session |
| references/agent-profile-versioning.md | `d939d6f1` | +723 B | the `tester-fold-live` `COPY=1` forwarding / exit-code-signal block |

The fold tool itself is `== main` (`scripts/fold-live-profile.py` `05f829`), so no tool change.

### #1273 byte-identical proof (after copy, tree vs live)

- SKILL.md: tree `770d3555605b` == live `770d3555605b` (same, 97,752 B)
- agent-profile-versioning.md: tree `d939d6f1d6dd` == live `d939d6f1d6dd` (same, 25,603 B)

### Gates green at head `a6b62c3`

`check_wiring` 0 · `changes_index` 0 · `check_docs` 0 · `check_architecture_census` 0 (referent `bb11bb1f`
ancestor of HEAD) · `lint_linefeeds` 0 · `agent_profile_sync --check` 0 (byte-for-byte) ·
`check_report_hygiene` 0 · `make check-docs` 0.

Addresses and closes **#1327**. Never merged, never armed.

