# Agent image source stamp: dispatch, verify, then close (#2935)

Implements **#2935** (infrastructure unblock). No code or gate was changed; this note records the measured
remedy so the next stale-image red has a repeatable procedure.

## Problem

`make agent-image-source-check` (`mk/gates.mk:320`) reddened every in-repo issue-bot implement run
(e.g. run `46014554464`, job `140558268362`, head `4995322756`) with:

```
source-check agent: STALE — image labels source fef0147326e3, this checkout hashes to a57d3e2e4a66
... Remedy: dispatch publish-agent-image.yml on main (issue #2935)
```

The image had not been republished since run `45134224656` (2026-11-23). Scanning and gating were
correct; the publisher simply had not run.

## How it was unblocked

1. `git fetch origin main`, then compute the expected source hash in a **clean detached worktree at that
   sha**: `python3 scripts/ci_images.py tag agent` → `a57d3e2e4a66`. The long-lived main checkout was
   still on an older commit and printed `a120c2aacc79`; a stale checkout is not a valid verifier.
2. Dispatch on `main`, not on a branch: `gh api -X POST
   repos/asimov-agent/llgenie/actions/workflows/publish-agent-image.yml/dispatches --input <file>` with
   `{"ref":"main","inputs":{"force":"false"}}`. `gh api -f inputs='{"force":"false"}'` sends the object
   as a string and earns HTTP 422. Result: **run `46015597657`**, conclusion `success` (guard + publish).
3. Read the publish job's own log: all 13 manifest lanes provisioned and resolved, `hermes-smoke` OK via
   the `llgenie-status-keeper` profile, `ci-image-refs` printed.
4. Verify the artifact, not the run's colour: `docker inspect ghcr.io/asimov-agent/llgenie/agent:latest`
   → `llgenie.agent.source = a57d3e2e4a66`; `docker buildx imagetools inspect` gives `:latest` and
   `:a57d3e2e4a66` the same digest `sha256:8ecad0a395923bc8d1aaacc1117c39f79d485de7b6b434d03b62ff753007a3b5`.
5. Refresh the local alias with `make agent-image-pull` (rc=0) **before** running
   `python3 scripts/ci_images.py source-check agent` (rc=0: `OK — carries this tree's source hash
   a57d3e2e4a66`). `docker pull ghcr.io/.../agent:latest` alone leaves `llgenie/agent:latest` on the old
   label and makes a correctly published image look stale.

## What was deliberately not done

No gate was weakened or bypassed, no `force` publish, no merge, no branch push to `main`. The issue's
acceptance boxes stayed `- [ ]`: only a reviewer verdict writes them back (#1644/#745). Issue #2935 was
closed as COMPLETED with the run id and verified label in its body and comments.

Verification worktree left in place, not pruned: `/home/asimov/repository/git/llgenie-wt/2935-verify`.
