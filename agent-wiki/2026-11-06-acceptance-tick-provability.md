# Acceptance ticks must name replayable evidence (issue #1858)

The fleet's acceptance-criteria honesty contract (#745, #791) says a tick is only as honest as the
run behind it. The #1857 own-domain audit measured the last ~10 merged PRs and found **3 criteria
ticked with no named run id** — all on #1784 (closed by #1819), the security idle-audit LIVE→TREE
fold. Their proof was byte-for-byte real, but the tick carried `proven: … cmp live==tree` /
`agent_profile_sync --check OK 13/13` — a hash/compare and a sync-check — with no `run=<id>` and no
re-runnable `command rc=<n> <sha>`. A re-measurer could not repeat WHICH evidence was measured from
the issue thread alone.

`check-pr-acceptance.py` (#745) grows a third finding class, `tick-unprovable`: a TICKED criterion
whose `(proven: …)` evidence names neither a CI run id nor a reproducible command + its exit code +
the tree sha is red at merge time, exactly like an unticked criterion. Accepted forms:

- `run=<id>` — a named, live GitHub workflow run;
- `proven: <command> rc=<n> <sha>` — the drift-lamp form: re-running that one command at that sha
  reproduces the proof (e.g. `agent_profile_sync --check PROFILE=<x> rc=0 <sha>`).

A bare `- [x]` with no `(proven: …)` line stays unprovable (the #745 self-tick class). The gate
reads; it never writes — `acceptance_writeback` semantics are unchanged (#1644).

**Resolved:** the #1784/#1819 class — a folded reference ticked without a run id or reproducible
evidence line — is now a merge-time red. The fix is verified by unit tests
(`tests/test_check_pr_acceptance.py`): the fold-tick form reds, a sha-without-rc reds, a named
`run=` greens, a reproducible `command rc=<n> <sha>` greens, and a bare tick with no evidence reds.
