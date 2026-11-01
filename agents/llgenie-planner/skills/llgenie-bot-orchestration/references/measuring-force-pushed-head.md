# Measuring a force-pushed / rebased PR head

## The trap
After a lane (or rebase-bot) force-pushes or rebases an open PR, the old head
commit is rewritten and the new head is NOT a fast-forward descendant. A plain

    git fetch origin refs/pull/<N>/head:refs/remotes/origin/pr<N>head

then fails with **`! [rejected] ... (non-fast-forward)`**. The local ref stays
pointing at the OLD sha, so anything you extract and gate afterward measures
**stale content** while you believe you are gating the current PR.

## The fix
1. Fetch to a **fresh ref name** with `--force`, or reuse the same name with
   `--force`:

       git fetch origin refs/pull/<N>/head:refs/fetch/pr<N>-head --force

2. Confirm the fetched sha **equals** the API head before trusting it:

       gh pr view <N> --json headRefOid --jq .headRefOid
       git rev-parse refs/fetch/pr<N>-head

   `headRefOid` from the GitHub API is authoritative; a cached local ref is not.

3. Extract by the API sha directly so there is no ambiguity:

       git archive <headRefOid> | tar -x -C /tmp/gate

## Why it matters
The `check_agent_profiles.py` gate must run against the ACTUAL pushed tip. If
the fetch silently kept the old ref, you gate a superseded head and report the
wrong verdict — either a false red (old content) or a false green (a fold that
never landed). Always show the fetched-sha == API-head match in the evidence.

## One-message-per-head
A repeated claim at an UNCHANGED head gets no new board post or DM. But when the
head genuinely MOVES (rebase lands a new sha), the hold breaks and a fresh
measured verdict at the new tip IS owed — post it and read it back by its own
comment id.
