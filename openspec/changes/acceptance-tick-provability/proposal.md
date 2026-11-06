# Name a run or a reproducible command, or hold the tick

## Why

A merged PR can tick an acceptance criterion with proof that is not a GitHub workflow run — a
hash/cmp or a sync-check — and `check-pr-acceptance` (#745) has no lever on it because the tick
carries `proven: … cmp live==tree` / `agent_profile_sync --check OK 13/13` instead of `run=<id>`.
Measured in the #1857 own-domain audit: the last ~10 merged PRs carry **3 criteria ticked without a
named run id** — all on #1784 (closed by #1819), the security idle-audit LIVE→TREE fold. The proof is
byte-for-byte real, but no named run id records WHICH evidence a re-measurer should repeat, so the
tick is not reproducible from the issue thread alone.

## What changes

`check-pr-acceptance` grows a third finding class, `tick-unprovable`: a TICKED criterion whose
`(proven: …)` evidence names NEITHER a CI run id (`run=<id>`) NOR a reproducible command + its exit
code + the tree sha (`proven: <command> rc=<n> <sha>`) is red at merge time, exactly like an unticked
criterion. The accepted reproducible form IS the drift lamp: it records the tree sha and the rc so
re-running `agent_profile_sync --check` is one command, not a whole byte-compare. A `- [x]` with no
`(proven: …)` line at all stays unprovable (the #745 self-tick class). No `acceptance_writeback`
semantics change (#1644): the gate reads, it never writes.
