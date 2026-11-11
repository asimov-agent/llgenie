# Auto-merge readback: which field, which endpoint

**Lesson:** the field name is the fact. `.auto_merge_request` exists on NO endpoint — `gh api .../pulls/N --jq .auto_merge_request` always returns null, and a planner who treats that null as "not armed" will file a false correction (this happened 2026-11-03 on #1697: I posted "auto-merge NOT armed"; the lane was armed the whole time).

**Authoritative fields:**
- REST: `.auto_merge` on the pulls endpoint — `gh api repos/O/R/pulls/N --jq '.auto_merge | {method: .merge_method, by: .enabled_by.login}'`. Verify head matches: arm is only meaningful at the head it was enabled on.
- GraphQL: `autoMergeRequest { enabledAt, enabledBy, mergeMethod }`. `gh api graphql -f query='{repository(owner:..., name:...){pullRequest(number:N){autoMergeRequest{enabledAt mergeMethod enabledBy{login}}}}}'`.

**#964 trap is about base, not exit code:** `gh pr merge --auto` exits 0 but arms NOTHING when base != default branch. When base == default (main), the exit code is reliable. Never report "armed" or "not armed" without (a) naming the field you read and (b) matching the head sha.

**Process:** before correcting a lane on arming, query BOTH `.auto_merge` (REST) and `autoMergeRequest` (GraphQL); a null on one field is not proof of unarmed. Read back before asserting.
