# Name the agent's GitHub identity and its required access — and gate both

## Why

Agent lanes stall on admin-scope steps whose tooling is already merged (issue #2923). Measured on
`main` `c564764c5645` (2026-11-19): `make registry-cache-orphans` (shipped by #2914's PR) lists the
8 superseded fixed `:buildcache` tags, but the worker identity that implemented #2914 cannot delete
them — its repo permissions are `admin:false` (pull/push/triage) and its token lacks
`delete:packages`. #2837 (publish the agent image) and #2254/#880 (ruleset decisions) wait on the
same decision: WHICH identity an agent lane acts as, and which token scopes that identity must
carry. Today that lives only in session memory — not grep-able, not reviewable, not enforced — so
finished acceptance items wait for human round-trips and a future run can act under the wrong
identity or paste a credential into an issue/log while debugging auth.

## What changes

- **AGENTS.md** gains a durable section `## The agent's GitHub identity and required access
  (mandatory, durable)`: the acting identity is the repo-owner bot account `asimov-agent` (it holds
  `admin` on `asimov-agent/llgenie`), with a scope roster where each scope names the exact step it
  unblocks (`repo, workflow, read:org, gist, write:packages, delete:packages`).
- **A new host-agent skill** `agents/llgenie-issse-implementer/skills/agent-github-access/SKILL.md`
  (the host agents' behaviour tree, synced to the profile by `make sync-agent-profile`) carries the
  scope→operation map, the audit rule (an elevated/destructive step runs only when an open issue
  already requests it, and every such run is stamped on that issue), and the identity check
  (`gh auth status`, masked tokens only).
- **A new gate** `scripts/check_agent_access.py` wired as `make check-agent-access`
  (+ `make agent-access-report`) into `mk/gates.mk` and the unit battery (`scripts/ci_unit.py`,
  next to `make check-issue-bodies`): it reddens when the AGENTS.md section or the skill is removed
  or loses a required element, and reddens on any token-shaped string (`gh[pousr]_…`,
  `github_pat_…`) inside the policy section or the skill — the artifacts themselves cannot carry a
  credential. Hermetic fixtures in `tests/test_check_agent_access.py` prove each red.
- `agent-wiki/` note + `docs/changes.d/` index row record the change (issues #2923, #2914).

Out of scope (each stays its own issue): executing the GHCR orphan sweep (#2914), the agent-image
dispatch (#2837), the ruleset decisions (#2254, #880).
